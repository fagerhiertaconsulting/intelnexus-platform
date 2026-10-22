import pytest
from app.core.finops.cache import ResponseCache
from app.core.finops.cost_estimator import CostEstimator
from app.core.finops.rate_limiter import TokenBucketRateLimiter
from app.core.net.client import AsyncEgressClient, EgressPolicy, get_egress_client
from app.core.reporting.sanitizer import PIISanitizer
from app.core.roles import WORKSPACE_ROLES
from app.db.database import db
from app.models.case import CaseCreateRequest
from app.models.entity import Entity, InfoCredibility, SourceReliability
from app.models.evidence import EvidenceItem
from app.models.relationship import Relationship
from app.plugins.base import EntityInput, TransformResult
from app.plugins.registry import PluginManager
from app.plugins.shodan_plugin import ShodanHostIntelPlugin
from app.plugins.virustotal_plugin import VirusTotalThreatIntelPlugin
from app.plugins.whois_plugin import WhoisLookupPlugin
from app.resolution.entity_resolver import EntityResolver


# --- 1. PLUGIN SDK & SAMPLES ---


@pytest.mark.asyncio
async def test_plugin_contracts_and_execution():
    shodan = ShodanHostIntelPlugin()
    assert shodan.slug == "shodan_host_intel"
    assert shodan.is_commercial is True
    assert shodan.cost_per_query_estimate == 1.0
    assert any(i.lower() in ("ip", "ipaddress") for i in shodan.supported_inputs)

    res = await shodan.execute(EntityInput(entity_type="IPAddress", value="8.8.8.8"))
    assert isinstance(res, TransformResult)
    assert len(res.entities) >= 1
    assert any(e.entity_type.lower() == "domain" for e in res.entities)
    assert len(res.relationships) >= 1

    whois = WhoisLookupPlugin()
    assert whois.is_commercial is False
    assert whois.cost_per_query_estimate == 0.0
    whois_res = await whois.execute(EntityInput(entity_type="Domain", value="example.com"))
    assert isinstance(whois_res, TransformResult)
    assert any(e.entity_type.lower() == "organization" for e in whois_res.entities)

    vt = VirusTotalThreatIntelPlugin()
    assert vt.slug == "virustotal_threat_intel"
    vt_res = await vt.execute(EntityInput(entity_type="Domain", value="malware-target.org"))
    assert isinstance(vt_res, TransformResult)
    assert any(e.entity_type == "incident" for e in vt_res.entities)


def test_plugin_manager_discovery_and_filtering():
    mgr = PluginManager()
    plugins = mgr.list_plugins()
    assert len(plugins) >= 3

    slugs = [p["slug"] for p in plugins]
    assert "shodan_host_intel" in slugs
    assert "whois_lookup" in slugs
    assert "virustotal_threat_intel" in slugs

    ip_plugins = mgr.get_plugins_for_type("IPAddress")
    assert any(p.slug == "shodan_host_intel" for p in ip_plugins)

    domain_plugins = mgr.get_plugins_for_type("Domain")
    assert any(p.slug == "whois_lookup" for p in domain_plugins)
    assert any(p.slug == "virustotal_threat_intel" for p in domain_plugins)


@pytest.mark.asyncio
async def test_plugin_manager_execution():
    mgr = PluginManager()
    res = await mgr.execute_plugin("whois_lookup", EntityInput(entity_type="Domain", value="testdomain.se"))
    assert isinstance(res, TransformResult)
    assert len(res.entities) > 0


# --- 2. FINOPS: RATE LIMITER, CACHE, DRY-RUN ---


def test_token_bucket_rate_limiter_in_memory():
    limiter = TokenBucketRateLimiter(redis_url=None)
    key = "test_plugin_bucket"

    # Konsumera tillgängliga tokens
    assert limiter.acquire(key, max_tokens=3, refill_rate_per_sec=1.0) is True
    assert limiter.acquire(key, max_tokens=3, refill_rate_per_sec=1.0) is True
    assert limiter.acquire(key, max_tokens=3, refill_rate_per_sec=1.0) is True

    # Fjärde anropet ska nekas eftersom kapaciteten (3) är nådd
    assert limiter.acquire(key, max_tokens=3, refill_rate_per_sec=1.0) is False

    # Reset
    limiter.reset(key)
    assert limiter.acquire(key, max_tokens=3, refill_rate_per_sec=1.0) is True


def test_response_cache_deterministic_hashing():
    cache = ResponseCache(redis_url=None)
    k1 = cache.compute_key("shodan_host_intel", "IPAddress", "1.1.1.1")
    k2 = cache.compute_key("shodan_host_intel", "IPAddress", "1.1.1.1")
    k3 = cache.compute_key("shodan_host_intel", "IPAddress", "8.8.8.8")

    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64  # SHA-256 hexdigest

    payload = {"status": "ok", "open_ports": [80, 443]}
    cache.set("shodan_host_intel", "IPAddress", "1.1.1.1", payload)

    cached = cache.get("shodan_host_intel", "IPAddress", "1.1.1.1")
    assert cached == payload

    # TTL beräkning: nätverksdata får 2h (7200s), statisk får 24h (86400s)
    assert cache.get_ttl_for_target("IPAddress") == 7200
    assert cache.get_ttl_for_target("Domain") == 7200
    assert cache.get_ttl_for_target("Company") == 86400


def test_finops_cost_estimator_dry_run():
    from app.core.finops.cache import response_cache

    # Rensa eller simulera specifik träff i den aktiva cachen
    response_cache.set("shodan_host_intel", "IPAddress", "192.168.1.1", {"cached": True})

    targets = [
        EntityInput(entity_type="IPAddress", value="192.168.1.1"),
        EntityInput(entity_type="IPAddress", value="10.0.0.1"),
        EntityInput(entity_type="IPAddress", value="10.0.0.2"),
    ]

    # Kör kostnadsestimering
    estimate = CostEstimator.estimate("shodan_host_intel", targets, force_refresh=False)
    assert estimate.planned_calls == 3
    # En var cachad
    assert estimate.cache_hits == 1
    assert estimate.net_calls == 2
    assert estimate.cost_per_query == 1.0
    assert estimate.estimated_total_cost == 2.0
    assert "192.168.1.1" in estimate.cached_targets

    # Med force_refresh=True ska cache ignoreras
    estimate_forced = CostEstimator.estimate("shodan_host_intel", targets, force_refresh=True)
    assert estimate_forced.cache_hits == 0
    assert estimate_forced.net_calls == 3
    assert estimate_forced.estimated_total_cost == 3.0


# --- 3. NATO ADMIRALTY SYSTEM (A1-F6) ---


def test_nato_admiralty_system_models_and_properties():
    ent = Entity(
        name="Officiellt Bolagsregister",
        type="Company",
        source_reliability=SourceReliability.A,
        info_credibility=InfoCredibility.ONE,
    )
    assert ent.admiralty_code == "A1"

    ent_default = Entity(
        name="Ospecifierad källa",
        type="Person",
    )
    assert ent_default.source_reliability == SourceReliability.B
    assert ent_default.info_credibility == InfoCredibility.TWO
    assert ent_default.admiralty_code == "B2"

    evidence = EvidenceItem(
        case_id="case--test",
        title="Domstolsprotokoll",
        file_path="/data/evidence/test.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        source_reliability=SourceReliability.A,
        info_credibility=InfoCredibility.ONE,
    )
    assert evidence.admiralty_code == "A1"


def test_nato_admiralty_persistence():
    case = db.create_case(CaseCreateRequest(title="NATO Admiralty Test Case"))

    ent = Entity(
        case_id=case.id,
        name="Signalspaning Nod",
        type="NetworkEntity",
        source_reliability=SourceReliability.B,
        info_credibility=InfoCredibility.TWO,
    )
    db.save_entity(ent)

    loaded = db.get_entity(ent.id)
    assert loaded is not None
    assert loaded.source_reliability == SourceReliability.B
    assert loaded.info_credibility == InfoCredibility.TWO
    assert loaded.admiralty_code == "B2"


# --- 4. NEW WORKSPACE ROLES ---


def test_new_workspace_roles():
    assert "cyber_threat_intelligence" in WORKSPACE_ROLES
    cti = WORKSPACE_ROLES["cyber_threat_intelligence"]
    assert "Cyber Threat Intelligence" in cti.display_name
    assert "mitre_attack_navigator" in cti.active_widgets
    assert "ioc_correlation_engine" in cti.active_widgets
    assert "stix_taxii_export" in cti.active_widgets

    assert "fact_checking_human_rights" in WORKSPACE_ROLES
    fact = WORKSPACE_ROLES["fact_checking_human_rights"]
    assert "Faktagranskning" in fact.display_name or "Human Rights" in fact.display_name
    assert "chrono_suncalc_tool" in fact.active_widgets
    assert "reverse_video_fragment_matcher" in fact.active_widgets
    assert "environmental_anomaly_firms" in fact.active_widgets


# --- 5. OPSEC & EGRESS MANAGER ---


def test_opsec_egress_policies_and_routing():
    direct_client = AsyncEgressClient(policy=EgressPolicy.DIRECT)
    assert direct_client.policy == EgressPolicy.DIRECT
    assert direct_client.effective_proxy_url is None
    assert direct_client.is_dns_leak_protected() is False

    tor_client = AsyncEgressClient(policy=EgressPolicy.TOR_STRICT)
    assert tor_client.policy == EgressPolicy.TOR_STRICT
    assert tor_client.effective_proxy_url.startswith("socks5://")
    assert tor_client.is_dns_leak_protected() is True

    routing = tor_client.get_routing_info()
    assert routing["policy"] == "TOR_STRICT"
    assert routing["dns_leak_protected"] is True

    proxy_client = AsyncEgressClient(policy=EgressPolicy.PROXY_RESIDENTIAL)
    assert proxy_client.is_dns_leak_protected() is True


def test_case_egress_policy_persistence():
    case = db.create_case(
        CaseCreateRequest(
            title="Tor Confidential Case",
            egress_policy=EgressPolicy.TOR_STRICT,
        )
    )
    assert case.egress_policy == EgressPolicy.TOR_STRICT

    loaded = db.get_case(case.id)
    assert loaded is not None
    assert loaded.egress_policy == EgressPolicy.TOR_STRICT

    client = get_egress_client(case_id=case.id)
    assert client.policy == EgressPolicy.TOR_STRICT
    assert client.is_dns_leak_protected() is True


# --- 6. ENTITY RESOLUTION & CANONICAL KEYS ---


def test_entity_resolver_canonical_keys_and_deduplication():
    resolver = EntityResolver()
    case = db.create_case(CaseCreateRequest(title="Resolution Test Case"))

    # Person med personnummer
    p1 = Entity(
        case_id=case.id,
        name="Anna Andersson",
        type="Person",
        attributes={"national_id": "19850612-1234"},
    )
    k1 = resolver.compute_canonical_key(p1)
    assert k1 == "person:nid:19850612-1234"

    # Företag med org-nummer
    c1 = Entity(
        case_id=case.id,
        name="Nordic Tech AB",
        type="Company",
        attributes={"jurisdiction_code": "SE", "org_number": "556123-4567"},
    )
    k_org = resolver.compute_canonical_key(c1)
    assert k_org == "org:SE:556123-4567"

    # Nätverksenhet
    net1 = Entity(
        case_id=case.id,
        name="192.168.1.1",
        type="IPAddress",
        attributes={"ip": "192.168.1.1"},
    )
    assert resolver.compute_canonical_key(net1) == "net:192.168.1.1"

    # Spara p1 via resolve_or_merge
    saved_p1, was_created = resolver.resolve_or_merge(case.id, p1)
    assert was_created is True

    # Försök spara samma person igen från en annan källa (t.ex. Folkbokföring)
    p2 = Entity(
        case_id=case.id,
        name="Anna K. Andersson",
        type="Person",
        attributes={"national_id": "19850612-1234", "city": "Stockholm"},
    )
    merged_p, was_created2 = resolver.resolve_or_merge(case.id, p2)
    assert was_created2 is False
    assert merged_p.id == saved_p1.id
    assert merged_p.attributes.get("city") == "Stockholm"
    assert "Anna K. Andersson" in merged_p.aliases

    # Verifiera att databasen endast innehåller en entitet för detta ärende
    entities = db.list_entities(case_id=case.id)
    assert len(entities) == 1


# --- 7. PII SANITIZER & GDPR EXPORT ---


def test_pii_sanitizer_masking():
    sanitizer = PIISanitizer()

    # Maskering av 12- och 10-siffriga personnummer
    text = "Målet är 19850612-1234 och medmisstänkt 900101-5678 på Storgatan 1."
    masked = sanitizer.mask_text(text)
    assert "19850612-****" in masked
    assert "900101-****" in masked
    assert "1234" not in masked
    assert "5678" not in masked

    # Maskering av entitetsattribut
    attrs = {
        "full_name": "Test Testsson",
        "national_id": "19920315-9999",
        "street_address": "Hemliga Gatan 5",
        "postal_address": "11122 Stockholm",
    }
    sanitized_attrs = sanitizer.sanitize_attributes(attrs, is_third_party=True)
    assert sanitized_attrs["national_id"] == "19920315-****"
    assert sanitized_attrs["street_address"] == "[MASKERAD ADRESS / GDPR]"
    assert sanitized_attrs["postal_address"] == "[MASKERAD ADRESS / GDPR]"


def test_pii_sanitizer_dossier_filtering():
    sanitizer = PIISanitizer()
    case_id = "case--gdpr-test"

    suspect = Entity(
        id="ent-1",
        case_id=case_id,
        name="Huvudmisstänkt 19800101-1111",
        type="Person",
        confidence_score=0.95,
        attributes={"suspect": True},
    )
    innocent = Entity(
        id="ent-2",
        case_id=case_id,
        name="Oskyldig Granne",
        type="Person",
        confidence_score=0.40,
        attributes={"is_third_party": True},
    )
    rel = Relationship(
        id="rel-1",
        case_id=case_id,
        source_id="ent-1",
        target_id="ent-2",
        relation_type="ASSOCIATED_WITH",
    )

    retained_ents, retained_rels = sanitizer.sanitize_dossier(
        entities=[suspect, innocent],
        relationships=[rel],
        min_confidence_threshold=0.6,
        remove_innocent_contacts=True,
    )

    # innocent ska ha tagits bort på grund av konfidens < 0.6 och is_third_party
    assert len(retained_ents) == 1
    assert "ent-1" in retained_ents[0].id
    assert "19800101-****" in retained_ents[0].name

    # Relationen till den borttagna grannen ska raderas för att förhindra trasiga kanter
    assert len(retained_rels) == 0


# --- 8. REST API ENDPOINTS ---


def test_rest_api_plugins_and_transforms_dry_run():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. GET /api/v1/plugins and /api/plugins
    resp_v1 = client.get("/api/v1/plugins")
    assert resp_v1.status_code == 200
    plugins_v1 = resp_v1.json()
    assert len(plugins_v1) >= 3
    slugs = [p["slug"] for p in plugins_v1]
    assert "shodan_host_intel" in slugs
    assert "whois_lookup" in slugs

    resp = client.get("/api/plugins")
    assert resp.status_code == 200

    # 2. GET /api/v1/plugins/for-type/IPAddress
    resp_type = client.get("/api/v1/plugins/for-type/IPAddress")
    assert resp_type.status_code == 200
    assert any(p["slug"] == "shodan_host_intel" for p in resp_type.json())

    # 3. POST /api/v1/plugins/execute
    exec_resp = client.post(
        "/api/v1/plugins/execute",
        json={"plugin_slug": "whois_lookup", "target": {"entity_type": "Domain", "value": "testapi.org"}},
    )
    assert exec_resp.status_code == 200
    assert "entities" in exec_resp.json()
    assert len(exec_resp.json()["entities"]) > 0

    # 4. POST /api/v1/transforms/dry-run & /api/transforms/dry-run
    dry_req = {
        "plugin_slug": "shodan_host_intel",
        "targets": [
            {"entity_type": "IPAddress", "value": "1.2.3.4"},
            {"entity_type": "IPAddress", "value": "5.6.7.8"},
        ],
        "force_refresh": True,
    }
    dry_resp = client.post("/api/v1/transforms/dry-run", json=dry_req)
    assert dry_resp.status_code == 200
    dry_data = dry_resp.json()
    assert dry_data["planned_calls"] == 2
    assert dry_data["net_calls"] == 2
    assert dry_data["estimated_total_cost"] == 2.0
    assert dry_data["currency_or_unit"] == "credits"

    dry_resp2 = client.post("/api/transforms/dry-run", json=dry_req)
    assert dry_resp2.status_code == 200

    # 5. NATO Admiralty in POST /api/entities
    case = db.create_case(CaseCreateRequest(title="API Admiralty Case"))
    ent_req = {
        "case_id": case.id,
        "name": "Interpol Red Notice Dossier",
        "type": "Incident",
        "source_reliability": "A",
        "info_credibility": 1,
    }
    ent_resp = client.post("/api/entities", json=ent_req)
    assert ent_resp.status_code == 200
    ent_data = ent_resp.json()
    assert ent_data["source_reliability"] == "A"
    assert ent_data["info_credibility"] == 1
    assert ent_data["admiralty_code"] == "A1"

    # 6. Sanitized Report Export
    # Lägg till en person med personnummer
    client.post(
        "/api/entities",
        json={
            "case_id": case.id,
            "name": "19750101-1234",
            "type": "Person",
            "attributes": {"national_id": "19750101-1234", "address": "Storgatan 10"},
        },
    )
    md_resp = client.get(f"/api/analysis/report/{case.id}/markdown?mode=sanitized")
    assert md_resp.status_code == 200
    md_text = md_resp.text
    assert "SANITISERAD EXPORT" in md_text
    assert "19750101-****" in md_text
    assert "19750101-1234" not in md_text

    html_resp = client.get(f"/api/analysis/report/{case.id}/html?mode=sanitized")
    assert html_resp.status_code == 200
    assert "19750101-****" in html_resp.text

    # Report Generator i18n locales (en, uk)
    en_resp = client.get(f"/api/analysis/report/{case.id}/markdown?locale=en")
    assert en_resp.status_code == 200
    assert "Investigation Report" in en_resp.text
    assert "Case ID:" in en_resp.text

    uk_resp = client.get(f"/api/analysis/report/{case.id}/markdown?locale=uk")
    assert uk_resp.status_code == 200
    assert "Звіт про розслідування" in uk_resp.text
    assert "ID справи:" in uk_resp.text

    # Fallback to English on unknown locale
    fallback_resp = client.get(f"/api/analysis/report/{case.id}/markdown?locale=unknown_loc")
    assert fallback_resp.status_code == 200
    assert "Investigation Report" in fallback_resp.text

    html_uk_resp = client.get(f"/api/analysis/report/{case.id}/html?locale=uk")
    assert html_uk_resp.status_code == 200
    assert 'lang="uk"' in html_uk_resp.text

    # 7. Error handling in plugin execution
    err_resp = client.post(
        "/api/v1/plugins/execute",
        json={"plugin_slug": "non_existent_slug", "target": {"entity_type": "Domain", "value": "test.com"}},
    )
    assert err_resp.status_code == 404

    # Commercial plugin without required vault key
    from app.core.vault import credential_vault

    had_key = credential_vault.get_key("SHODAN_API_KEY")
    try:
        credential_vault.delete_key("SHODAN_API_KEY")
        vault_err_resp = client.post(
            "/api/v1/plugins/execute",
            json={"plugin_slug": "shodan_host_intel", "target": {"entity_type": "IPAddress", "value": "1.1.1.1"}},
        )
        assert vault_err_resp.status_code == 400
    finally:
        if had_key:
            credential_vault.set_key("SHODAN_API_KEY", had_key)


# --- 9. FINOPS & RESOLVER COVERAGE EXTENSIONS ---


def test_rate_limiter_get_status_and_redis_mock():
    from unittest.mock import MagicMock

    limiter = TokenBucketRateLimiter(redis_url=None)
    status_empty = limiter.get_status("unknown_bucket")
    assert status_empty["current_tokens"] == limiter.default_capacity

    limiter.acquire("my_bucket", cost=5, capacity=20, refill_rate=2.0)
    status_active = limiter.get_status("my_bucket")
    assert status_active["current_tokens"] < 20
    assert status_active["capacity"] == 20

    # Simulera Redis-klient
    mock_redis = MagicMock()
    mock_redis.eval.return_value = 1
    mock_redis.hmget.return_value = ["15.0", "123456789.0"]

    limiter.redis_client = mock_redis
    assert limiter.acquire("redis_bucket", cost=1, capacity=30, refill_rate=1.0) is True
    redis_status = limiter.get_status("redis_bucket")
    assert redis_status["backend"] == "redis"

    limiter.reset("redis_bucket")
    mock_redis.delete.assert_called_with("finops:ratelimit:redis_bucket")


def test_response_cache_invalidation_and_redis_mock():
    import json
    from unittest.mock import MagicMock

    cache = ResponseCache(redis_url=None)
    cache.set("plugin_a", "Domain", "target.org", {"ok": True})
    assert cache.get("plugin_a", "Domain", "target.org") == {"ok": True}

    cache.invalidate("plugin_a", "Domain", "target.org")
    assert cache.get("plugin_a", "Domain", "target.org") is None

    cache.set("plugin_b", "Domain", "b.org", {"ok": True})
    cache.clear()
    assert cache.get("plugin_b", "Domain", "b.org") is None

    # Mockad Redis-cache
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps({"redis_cached": True})
    cache.redis_client = mock_redis

    val = cache.get("shodan", "IPAddress", "1.1.1.1")
    assert val == {"redis_cached": True}

    cache.set("shodan", "IPAddress", "1.1.1.1", {"redis_cached": True})
    mock_redis.setex.assert_called()

    cache.invalidate("shodan", "IPAddress", "1.1.1.1")
    mock_redis.delete.assert_called()


@pytest.mark.asyncio
async def test_async_egress_client_lifecycle():
    client = AsyncEgressClient(policy=EgressPolicy.DIRECT)
    async with client as c:
        assert c._client is not None
        assert not c._client.is_closed
    # Kontrollera att den stängdes efter context exit
    assert client._client is None


def test_entity_resolver_digital_identity_and_jw():
    from app.resolution.entity_resolver import jaro_winkler_distance

    resolver = EntityResolver()

    # Jaro-Winkler kantfall
    assert jaro_winkler_distance("", "") == 1.0
    assert jaro_winkler_distance("abc", "") == 0.0
    assert jaro_winkler_distance("test", "test") == 1.0
    assert jaro_winkler_distance("abcdef", "xyz123") == 0.0

    # DigitalIdentity kanonisk nyckel
    d1 = Entity(
        name="johndoe",
        type="username",
        attributes={"platform": "twitter", "username": "johndoe"},
    )
    k = resolver.compute_canonical_key(d1)
    assert k == "identity:twitter:johndoe"

    case = db.create_case(CaseCreateRequest(title="Digital Identity Case"))
    d1.case_id = case.id
    saved, created = resolver.resolve_or_merge(case.id, d1)
    assert created is True

    # Ny entitet med samma identitet
    d2 = Entity(
        case_id=case.id,
        name="John Doe Official",
        type="username",
        attributes={"platform": "twitter", "username": "johndoe", "followers": 5000},
    )
    merged, created2 = resolver.resolve_or_merge(case.id, d2)
    assert created2 is False
    assert merged.id == saved.id
    assert merged.attributes.get("followers") == 5000
    assert "John Doe Official" in merged.aliases


def test_pii_sanitizer_nested_structures():
    sanitizer = PIISanitizer()
    nested = {
        "person": {
            "pnr": "19901231-1234",
            "phones": ["070-1234567", "19901231-1234"],
            "address": "Hemliga Vägen 4",
        },
        "innocent_list": [
            {"national_id": "19800101-5678"},
            "Kontakt: 19820202-9999",
        ],
    }

    sanitized = sanitizer.sanitize_attributes(nested, is_third_party=True)
    assert sanitized["person"]["pnr"] == "19901231-****"
    assert sanitized["person"]["address"] == "[MASKERAD ADRESS / GDPR]"
    assert sanitized["person"]["phones"][1] == "19901231-****"
    assert sanitized["innocent_list"][0]["national_id"] == "19800101-****"
    assert "19820202-****" in sanitized["innocent_list"][1]
