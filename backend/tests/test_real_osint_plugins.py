import httpx
import pytest
from app.core.finops.cache import response_cache
from app.core.finops.rate_limiter import rate_limiter
from app.plugins.base import (
    EntityInput,
    PluginCategory,
    PluginResult,
)
from app.plugins.cti.crtsh_subdomains import CrtshSubdomainsPlugin
from app.plugins.cti.doh_dns_probe import DoHDNSProbePlugin
from app.plugins.cti.ripestat_asn_probe import RIPEstatASNProbePlugin
from app.plugins.cti.shodan_cti_plugin import ShodanCTIPlugin
from app.plugins.finmint.bolagsverket_plugin import BolagsverketPlugin
from app.plugins.finmint.crypto_mempool_plugin import CryptoMempoolPlugin
from app.plugins.finmint.opencorporates_plugin import OpenCorporatesPlugin
from app.plugins.finmint.opensanctions_plugin import OpenSanctionsPlugin
from app.plugins.geoint.nasa_firms_plugin import NASAFIRMSPlugin
from app.plugins.geoint.opensky_adsb_plugin import OpenSkyADSBPlugin
from app.plugins.geoint.overpass_infra_plugin import OverpassInfraPlugin
from app.plugins.darkint.hibp_breach_probe import HIBPBreachProbe
from app.plugins.darkint.wayback_archive_plugin import WaybackArchivePlugin
from app.plugins.registry import PluginManager, plugin_manager
from app.plugins.socmint.gravatar_probe import GravatarProbe
from app.plugins.socmint.pgp_keyserver_probe import PGPKeyserverProbe
from app.plugins.socmint.whatsmyname_probe import WhatsMyNameProbe


@pytest.fixture(autouse=True)
def clean_cache_and_limiter():
    response_cache.clear()
    rate_limiter.reset("shodan_query_credit")
    yield
    response_cache.clear()


# --- 1. BASE PLUGIN CONTRACT & CACHING ---


@pytest.mark.asyncio
async def test_base_plugin_caching_and_evidence_hashing():
    plugin = GravatarProbe()
    assert plugin.plugin_id == "socmint_gravatar"
    assert plugin.category == PluginCategory.SOCMINT
    assert plugin.nato_admiralty == "A1"
    assert plugin.requires_api_key is False
    assert plugin.cost_per_query_usd == 0.0

    # 1:a anrop (ej cachat)
    res1 = await plugin.execute("test.user@example.com")
    assert isinstance(res1, PluginResult)
    assert res1.cached is False
    assert len(res1.evidence_hash) == 64
    assert res1.nato_admiralty == "A1"
    assert len(res1.entities) >= 1

    # 2:a anrop (ska svara från cache)
    res2 = await plugin.execute("test.user@example.com")
    assert res2.cached is True
    assert res2.evidence_hash == res1.evidence_hash
    assert len(res2.entities) == len(res1.entities)

    # Anrop med EntityInput
    res3 = await plugin.execute(EntityInput(entity_type="Email", value="test.user@example.com"))
    assert res3.cached is True


# --- 2. PLUGIN REGISTRY DISCOVERY ---


def test_plugin_registry_discovery():
    mgr = PluginManager()
    plugins = mgr.list_plugins()

    slugs_and_ids = {p.get("plugin_id") or p.get("slug") for p in plugins}

    expected_plugins = [
        "shodan_host_intel",
        "virustotal_threat_intel",
        "whois_lookup",
        "socmint_whatsmyname",
        "socmint_gravatar",
        "socmint_pgp_keyserver",
        "finmint_bolagsverket",
        "finmint_opencorporates",
        "finmint_opensanctions",
        "finmint_crypto_mempool",
        "cti_crtsh",
        "cti_doh_dns",
        "cti_ripestat_asn",
        "cti_shodan",
        "geoint_opensky_adsb",
        "geoint_nasa_firms",
        "geoint_overpass_infra",
        "darkint_hibp_breach",
        "darkint_wayback_archive",
    ]

    for ep in expected_plugins:
        assert ep in slugs_and_ids, f"Plugin '{ep}' saknas i PluginRegistry."


def test_plugin_registry_type_filtering():
    email_plugins = plugin_manager.get_plugins_for_input("Email")
    email_ids = [p.plugin_id for p in email_plugins]
    assert "socmint_gravatar" in email_ids
    assert "socmint_pgp_keyserver" in email_ids

    company_plugins = plugin_manager.get_plugins_for_input("Company")
    comp_ids = [p.plugin_id for p in company_plugins]
    assert "finmint_bolagsverket" in comp_ids
    assert "finmint_opencorporates" in comp_ids

    domain_plugins = plugin_manager.get_plugins_for_input("Domain")
    dom_ids = [p.plugin_id for p in domain_plugins]
    assert "cti_crtsh" in dom_ids
    assert "cti_doh_dns" in dom_ids


# --- 3. SOCMINT PLUGINS ---


@pytest.mark.asyncio
async def test_socmint_whatsmyname_probe():
    plugin = WhatsMyNameProbe()
    assert plugin.nato_admiralty == "B2"
    res = await plugin.execute("octocat")

    assert res.nato_admiralty == "B2"
    assert len(res.evidence_hash) == 64
    assert any(e.entity_type == "account" for e in res.entities)
    assert any(r.relation_type == "HAS_ACCOUNT" for r in res.relationships)
    assert res.raw_payload["mock"] is True


@pytest.mark.asyncio
async def test_socmint_gravatar_probe():
    plugin = GravatarProbe()
    assert plugin.nato_admiralty == "A1"
    res = await plugin.execute("investigator@example.com")

    assert res.nato_admiralty == "A1"
    assert any(e.entity_type == "Person" for e in res.entities)
    assert any(e.entity_type == "Avatar" for e in res.entities)
    assert any(r.relation_type == "IDENTIFIED_AS" for r in res.relationships)
    assert any(r.relation_type == "HAS_AVATAR" for r in res.relationships)


@pytest.mark.asyncio
async def test_socmint_pgp_keyserver_probe():
    plugin = PGPKeyserverProbe()
    assert plugin.nato_admiralty == "A1"
    res = await plugin.execute("alice@crypto.org")

    assert res.nato_admiralty == "A1"
    assert any(e.entity_type == "PGPKey" for e in res.entities)
    assert any(r.relation_type == "HAS_PGP_KEY" for r in res.relationships)


# --- 4. FINMINT PLUGINS ---


@pytest.mark.asyncio
async def test_finmint_bolagsverket_plugin():
    plugin = BolagsverketPlugin()
    assert plugin.nato_admiralty == "A1"
    res = await plugin.execute("559400-0000")

    assert res.nato_admiralty == "A1"
    assert any(e.entity_type == "Company" for e in res.entities)
    assert any(e.entity_type == "Location" for e in res.entities)
    assert any(r.relation_type == "RESOLVES_TO_COMPANY" for r in res.relationships)
    assert any(r.relation_type == "LOCATED_IN" for r in res.relationships)


@pytest.mark.asyncio
async def test_finmint_opencorporates_plugin():
    plugin = OpenCorporatesPlugin()
    assert plugin.nato_admiralty == "B2"
    res = await plugin.execute("Acme Global Solutions Ltd")

    assert res.nato_admiralty == "B2"
    assert any(e.entity_type == "Company" for e in res.entities)
    assert any(e.entity_type == "Jurisdiction" for e in res.entities)
    assert any(e.entity_type == "Person" for e in res.entities)
    assert any(r.relation_type == "INCORPORATED_IN" for r in res.relationships)
    assert any(r.relation_type == "OFFICER_OF" for r in res.relationships)


@pytest.mark.asyncio
async def test_finmint_opensanctions_plugin():
    plugin = OpenSanctionsPlugin()
    assert plugin.nato_admiralty == "A1"

    # Test träff vid sanktionerad måltavla
    res_hit = await plugin.execute("Targeted Sanction Person")
    assert res_hit.nato_admiralty == "A1"
    assert any(e.entity_type == "SanctionListing" for e in res_hit.entities)
    assert any(r.relation_type == "LISTED_UNDER_SANCTIONS" for r in res_hit.relationships)

    # Test ren sökning
    res_clean = await plugin.execute("Innocent Civilian")
    assert res_clean.nato_admiralty == "A1"
    assert len(res_clean.entities) == 0


@pytest.mark.asyncio
async def test_finmint_crypto_mempool_plugin():
    plugin = CryptoMempoolPlugin()
    assert plugin.nato_admiralty == "A1"
    res = await plugin.execute("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

    assert res.nato_admiralty == "A1"
    assert any(e.entity_type == "CryptoWallet" for e in res.entities)
    assert any(r.relation_type == "HAS_BALANCE" for r in res.relationships)
    assert res.raw_payload["balance_btc"] == 1.1


# --- 5. CTI / NETMINT PLUGINS ---


@pytest.mark.asyncio
async def test_cti_crtsh_subdomains_plugin():
    plugin = CrtshSubdomainsPlugin()
    assert plugin.nato_admiralty == "A2"
    res = await plugin.execute("target-enterprise.com")

    assert res.nato_admiralty == "A2"
    assert len(res.entities) >= 3
    assert any(e.entity_type == "domain" for e in res.entities)
    assert any(r.relation_type == "HAS_SUBDOMAIN" for r in res.relationships)


@pytest.mark.asyncio
async def test_cti_doh_dns_probe_plugin():
    plugin = DoHDNSProbePlugin()
    assert plugin.nato_admiralty == "A1"
    res = await plugin.execute("target-enterprise.com")

    assert res.nato_admiralty == "A1"
    assert any(e.entity_type == "IPAddress" for e in res.entities)
    assert any(e.entity_type == "MailServer" for e in res.entities)
    assert any(e.entity_type == "DNSRecord" for e in res.entities)
    assert any(r.relation_type == "RESOLVES_TO" for r in res.relationships)
    assert any(r.relation_type == "HAS_MAIL_SERVER" for r in res.relationships)


@pytest.mark.asyncio
async def test_cti_ripestat_asn_probe_plugin():
    plugin = RIPEstatASNProbePlugin()
    assert plugin.nato_admiralty == "A1"
    res = await plugin.execute("1.1.1.1")

    assert res.nato_admiralty == "A1"
    assert any(e.entity_type == "AutonomousSystem" for e in res.entities)
    assert any(e.entity_type == "NetworkPrefix" for e in res.entities)
    assert any(r.relation_type == "ANNOUNCED_BY" for r in res.relationships)


@pytest.mark.asyncio
async def test_cti_shodan_plugin():
    plugin = ShodanCTIPlugin()
    assert plugin.nato_admiralty == "B2"
    assert plugin.cost_per_query_usd == 1.0

    res = await plugin.execute("8.8.8.8")
    assert res.nato_admiralty == "B2"
    assert res.cost_usd == 1.0
    assert any(e.entity_type == "Organization" for e in res.entities)
    assert any(e.entity_type == "Domain" for e in res.entities)
    assert any(e.entity_type == "Vulnerability" for e in res.entities)


# --- 6. GEOINT PLUGINS ---


@pytest.mark.asyncio
async def test_geoint_opensky_adsb_plugin():
    plugin = OpenSkyADSBPlugin()
    assert plugin.nato_admiralty == "A2"
    res = await plugin.execute("4bb0e1")

    assert res.nato_admiralty == "A2"
    assert any(e.entity_type == "Aircraft" for e in res.entities)
    assert any(e.entity_type == "Flight" for e in res.entities)
    assert any(e.entity_type == "Location" for e in res.entities)
    assert any(r.relation_type == "OPERATED_AS" for r in res.relationships)
    assert any(r.relation_type == "CURRENT_POSITION" for r in res.relationships)


@pytest.mark.asyncio
async def test_geoint_nasa_firms_plugin():
    plugin = NASAFIRMSPlugin()
    assert plugin.nato_admiralty == "A2"
    res = await plugin.execute("59.3293, 18.0686")

    assert res.nato_admiralty == "A2"
    assert any(e.entity_type == "ThermalAnomaly" for e in res.entities)
    assert any(e.entity_type == "Location" for e in res.entities)
    assert any(r.relation_type == "DETECTED_AT" for r in res.relationships)


@pytest.mark.asyncio
async def test_geoint_overpass_infra_plugin():
    plugin = OverpassInfraPlugin()
    assert plugin.nato_admiralty == "B2"
    res = await plugin.execute("59.3293, 18.0686")

    assert res.nato_admiralty == "B2"
    assert any(e.entity_type == "Infrastructure" for e in res.entities)
    assert any(r.relation_type == "SPATIAL_INFRASTRUCTURE" for r in res.relationships)


@pytest.mark.asyncio
async def test_darkint_hibp_breach_probe():
    plugin = HIBPBreachProbe()
    assert plugin.nato_admiralty == "A1"

    # E-postkontroll
    res_email = await plugin.execute("victim@example.com")
    assert res_email.nato_admiralty == "A1"
    assert any(e.entity_type == "DataBreach" for e in res_email.entities)
    assert any(r.relation_type == "EXPOSED_IN" for r in res_email.relationships)

    # Lösenords-k-anonymitetskontroll
    res_pwd = await plugin.execute("P@ssw0rd123!")
    assert res_pwd.nato_admiralty == "A1"
    assert any(e.entity_type == "CompromisedCredential" for e in res_pwd.entities)


@pytest.mark.asyncio
async def test_darkint_wayback_archive_plugin():
    plugin = WaybackArchivePlugin()
    assert plugin.nato_admiralty == "A1"
    res = await plugin.execute("https://example.com/target-page")

    assert res.nato_admiralty == "A1"
    assert any(e.entity_type == "ArchiveSnapshot" for e in res.entities)
    assert any(r.relation_type == "HISTORICAL_SNAPSHOT" for r in res.relationships)


# --- 7. LIVE NETWORK BRANCH COVERAGE VIA MOCK HTTP TRANSPORT ---


@pytest.mark.asyncio
async def test_live_network_branches_via_mock_transport(monkeypatch):
    """Säkerställer testtäckning av nätverksgrenarna när mock_osint är inaktiverat."""
    monkeypatch.setenv("MOCK_OSINT", "false")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "gravatar.com" in url_str:
            return httpx.Response(
                200,
                json={
                    "entry": [
                        {
                            "displayName": "Network Analyst",
                            "thumbnailUrl": "https://avatar.url",
                            "currentLocation": "Stockholm",
                            "aboutMe": "Analyst",
                            "accounts": [
                                {"url": "https://github.com/netanalyst", "domain": "github.com", "display": "net"}
                            ],
                        }
                    ]
                },
            )
        elif "keyserver.ubuntu.com" in url_str:
            body = "info:1:2\npub:4A89C19B22F9E83A:1:4096:1618221600::\nuid:Alice <alice@test.com>:\n"
            return httpx.Response(200, text=body)
        elif "bolagsverket.se" in url_str:
            return httpx.Response(
                200,
                json={"foretagsnamn": "Live Test AB", "organisationsnummer": "559400-0000", "organisationsform": "AB"},
            )
        elif "opencorporates.com" in url_str:
            return httpx.Response(
                200,
                json={
                    "results": {
                        "companies": [
                            {"company": {"name": "Live Corp UK", "company_number": "123456", "jurisdiction_code": "gb"}}
                        ]
                    }
                },
            )
        elif "opensanctions.org" in url_str:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"caption": "Live Sanction Entity", "score": 0.98, "datasets": ["eu_fsf"], "properties": {}}
                    ]
                },
            )
        elif "mempool.space" in url_str:
            return httpx.Response(
                200,
                json={"chain_stats": {"funded_txo_sum": 200000000, "spent_txo_sum": 100000000, "tx_count": 5}},
            )
        elif "crt.sh" in url_str:
            return httpx.Response(200, json=[{"name_value": "sub1.example.com\nsub2.example.com"}])
        elif "1.1.1.1/dns-query" in url_str:
            if "type=A" in url_str:
                return httpx.Response(200, json={"Answer": [{"data": "93.184.216.34", "TTL": 300}]})
            elif "type=MX" in url_str:
                return httpx.Response(200, json={"Answer": [{"data": "10 mail.example.com"}]})
            else:
                return httpx.Response(200, json={"Answer": [{"data": "v=spf1 -all"}]})
        elif "stat.ripe.net" in url_str:
            return httpx.Response(
                200,
                json={"data": {"asns": [{"asn": "13335", "holder": "CLOUDFLARENET"}]}},
            )
        elif "shodan.io" in url_str:
            return httpx.Response(
                200,
                json={"org": "Live Net Org", "isp": "Live ISP"},
            )
        elif "opensky-network.org" in url_str:
            return httpx.Response(
                200,
                json={
                    "states": [
                        [
                            "4bb0e1",
                            "SAS142",
                            "Sweden",
                            1774166400,
                            1774166400,
                            18.0,
                            59.0,
                            10000.0,
                            False,
                            250.0,
                            180.0,
                            0.0,
                            None,
                            10000.0,
                            None,
                            False,
                            0,
                        ]
                    ]
                },
            )
        elif "firms.modaps.eosdis.nasa.gov" in url_str:
            csv_content = "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,confidence,version,bright_t31,frp,daynight\n59.32,18.06,330.5,0.4,0.36,2026-10-22,0300,N,nominal,2.0NRT,290.0,15.2,N\n"
            return httpx.Response(200, text=csv_content)
        elif "github.com" in url_str or "reddit.com" in url_str or "gitlab.com" in url_str:
            return httpx.Response(200, text="valid user profile")
        elif "overpass-api.de" in url_str:
            return httpx.Response(
                200,
                json={
                    "elements": [
                        {"type": "node", "id": 1234, "lat": 59.32, "lon": 18.06, "tags": {"name": "Live Tower"}}
                    ]
                },
            )
        elif "api.pwnedpasswords.com" in url_str:
            # 5-char prefix query returnerar suffix:count
            return httpx.Response(200, text="0018A45C4D1def:5\n1234567890ABCDEF:10\n")
        elif "haveibeenpwned.com" in url_str:
            return httpx.Response(
                200,
                json=[
                    {"Name": "LiveBreach", "Title": "Live Breach", "Domain": "breach.com", "BreachDate": "2024-01-01"}
                ],
            )
        elif "web.archive.org/cdx" in url_str:
            return httpx.Response(
                200,
                json=[
                    ["timestamp", "original", "mimetype", "statuscode", "digest"],
                    ["20230101120000", "https://example.com", "text/html", "200", "DIGEST123"],
                ],
            )
        return httpx.Response(404, text="not found")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    # Testa live-grenarna för alla plugins med mock_client
    g_res = await GravatarProbe().execute("alice@example.com", opsec_client=mock_client)
    assert any(e.entity_type == "Person" for e in g_res.entities)

    pgp_res = await PGPKeyserverProbe().execute("alice@test.com", opsec_client=mock_client)
    assert any(e.entity_type == "PGPKey" for e in pgp_res.entities)

    wmn_res = await WhatsMyNameProbe().execute("testuser", opsec_client=mock_client)
    assert isinstance(wmn_res, PluginResult)

    bv_res = await BolagsverketPlugin().execute("559400-0000", opsec_client=mock_client)
    assert any(e.entity_type == "Company" for e in bv_res.entities)

    oc_res = await OpenCorporatesPlugin().execute("Live Corp", opsec_client=mock_client)
    assert any(e.entity_type == "Company" for e in oc_res.entities)

    os_res = await OpenSanctionsPlugin().execute("Sanction Target", opsec_client=mock_client)
    assert any(e.entity_type == "SanctionListing" for e in os_res.entities)

    mp_res = await CryptoMempoolPlugin().execute("1BitcoinAddr", opsec_client=mock_client)
    assert any(e.entity_type == "CryptoWallet" for e in mp_res.entities)

    crt_res = await CrtshSubdomainsPlugin().execute("example.com", opsec_client=mock_client)
    assert any(e.entity_type == "domain" for e in crt_res.entities)

    doh_res = await DoHDNSProbePlugin().execute("example.com", opsec_client=mock_client)
    assert any(e.entity_type == "IPAddress" for e in doh_res.entities)

    ripe_res = await RIPEstatASNProbePlugin().execute("1.1.1.1", opsec_client=mock_client)
    assert any(e.entity_type == "AutonomousSystem" for e in ripe_res.entities)

    sho_res = await ShodanCTIPlugin().execute("1.1.1.1", opsec_client=mock_client, api_key="test_key")
    assert any(e.entity_type == "Organization" for e in sho_res.entities)

    sky_res = await OpenSkyADSBPlugin().execute("4bb0e1", opsec_client=mock_client)
    assert any(e.entity_type == "Aircraft" for e in sky_res.entities)

    firm_res = await NASAFIRMSPlugin().execute("59.32,18.06", opsec_client=mock_client)
    assert any(e.entity_type == "ThermalAnomaly" for e in firm_res.entities)

    over_res = await OverpassInfraPlugin().execute("59.32,18.06", opsec_client=mock_client)
    assert any(e.entity_type == "Infrastructure" for e in over_res.entities)

    hibp_email_res = await HIBPBreachProbe().execute("test@example.com", opsec_client=mock_client, api_key="test_hibp")
    assert any(e.entity_type == "DataBreach" for e in hibp_email_res.entities)

    hibp_pwd_res = await HIBPBreachProbe().execute("Password123", opsec_client=mock_client)
    assert isinstance(hibp_pwd_res, PluginResult)

    wb_res = await WaybackArchivePlugin().execute("https://example.com", opsec_client=mock_client)
    assert any(e.entity_type == "ArchiveSnapshot" for e in wb_res.entities)

    await mock_client.aclose()
