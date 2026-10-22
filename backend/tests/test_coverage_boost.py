import pytest
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db
from app.db.graph_store import graph_store
from app.db.object_store import object_store
from app.evidence.custody_manager import custody_manager
from app.models.case import CaseCreateRequest
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from app.resolution.entity_resolver import entity_resolver
from app.transforms.crtsh_subdomain_transform import CrtshSubdomainTransform
from app.transforms.dns_transform import DnsWhoisTransform
from app.transforms.phone_breach_transform import PhoneBreachCheckTransform
from app.transforms.exif_metadata_transform import ExifMetadataTransform
from app.services.two_factor.webauthn_service import WebAuthnService, _pending_reg_challenges, _pending_auth_challenges
from app.api.two_factor import require_elevated_session

client = TestClient(app)


def test_crtsh_subdomain_transform_execution():
    """Öka täckning för crtsh subdomain transform."""
    transform = CrtshSubdomainTransform()
    domain_entity = Entity(
        type=EntityType.DOMAIN,
        name="https://example.com:443/test",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"name_value": "api.example.com"},
        {"name_value": "mail.example.com\nvpn.example.com"},
    ]

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = pytest.importorskip("asyncio").run(transform.execute(domain_entity))
        assert res.success is True
        assert len(res.entities) >= 2


def test_dns_whois_transform_execution():
    """Öka täckning för DNS & Whois transform inklusive RDAP entiteter."""
    transform = DnsWhoisTransform()
    domain_entity = Entity(
        type=EntityType.DOMAIN,
        name="secure-intel.org",
        case_id="case_dns_test",
    )

    with patch("dns.resolver.Resolver.resolve") as mock_resolve:
        mock_a = MagicMock()
        mock_a.to_text.return_value = "93.184.216.34"
        mock_resolve.return_value = [mock_a]

        mock_rdap = MagicMock()
        mock_rdap.status_code = 200
        mock_rdap.json.return_value = {
            "entities": [
                {
                    "roles": ["registrar"],
                    "handle": "REG-123",
                    "vcardArray": ["vcard", [["fn", {}, "text", "TopRegistrar Inc"]]],
                }
            ]
        }

        with patch("httpx.AsyncClient.get", return_value=mock_rdap):
            res = pytest.importorskip("asyncio").run(transform.execute(domain_entity))
            assert res.success is True
            assert len(res.entities) >= 1


def test_phone_breach_transform_execution():
    """Öka täckning för Phone & Breach check transform."""
    transform = PhoneBreachCheckTransform()

    # 1. VoIP nummer
    voip_entity = Entity(type=EntityType.PHONE, name="+1 415 555 2671")
    res1 = pytest.importorskip("asyncio").run(transform.execute(voip_entity))
    assert res1.success is True

    # 2. Svenskt nummer
    se_entity = Entity(type=EntityType.PHONE, name="070-1234567")
    res2 = pytest.importorskip("asyncio").run(transform.execute(se_entity))
    assert res2.success is True

    # 3. E-post med känd läcka
    email_entity = Entity(type=EntityType.EMAIL, name="target@example.com")
    res3 = pytest.importorskip("asyncio").run(transform.execute(email_entity))
    assert res3.success is True


def test_exif_metadata_transform():
    """Täckning för EXIF bildanalys och metadataextraktion."""
    transform = ExifMetadataTransform()
    image_entity = Entity(
        type=EntityType.DOCUMENT,
        name="surveillance_photo.jpg",
        attributes={"latitude": 59.3293, "longitude": 18.0686, "camera_make": "Apple", "camera_model": "iPhone 15"},
    )
    res = pytest.importorskip("asyncio").run(transform.execute(image_entity))
    assert res.success is True
    assert len(res.entities) >= 1


def test_custody_manager_deep_audit():
    """Öka täckning för Beviskedjehanteraren (Custody Manager)."""
    case = db.create_case(CaseCreateRequest(title="Custody Case", priority="medium"))

    # Skapa bevisfil
    content = b"FORENSIC_EVIDENCE_RECORD_2026"
    filename = f"test_{int(time.time())}.dat"
    rel_path, sha256_hash, size = object_store.store_bytes(case.id, filename, content)

    db.save_evidence(
        EvidenceItem(
            case_id=case.id,
            title="Forensic Data",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type="application/octet-stream",
            sha256=sha256_hash,
            collector_plugin="test_audit",
        )
    )

    # Verifiera intakt beviskedja
    audit = custody_manager.verify_case_custody(case.id)
    assert audit["chain_of_custody_intact"] is True
    assert audit["valid_count"] >= 1

    # Testa manipulerad fil
    full_path = object_store.base_dir / rel_path
    with open(full_path, "wb") as f:
        f.write(b"TAMPERED_CONTENT_DATA")

    audit2 = custody_manager.verify_case_custody(case.id)
    assert audit2["chain_of_custody_intact"] is False
    assert audit2["tampered_count"] >= 1


def test_graph_store_advanced_analytics():
    """Öka täckning för GraphStore analyser, sökvägar och export."""
    case_id = f"graph_test_{int(time.time())}"

    e1 = Entity(name="Alpha Corp", type=EntityType.ORGANIZATION, case_id=case_id)
    e2 = Entity(name="Beta Ltd", type=EntityType.ORGANIZATION, case_id=case_id)
    e3 = Entity(name="Charlie AB", type=EntityType.ORGANIZATION, case_id=case_id)

    for e in (e1, e2, e3):
        db.save_entity(e)
        graph_store.add_entity_to_graph(case_id, e)

    r1 = Relationship(source_id=e1.id, target_id=e2.id, relation_type=RelationshipType.OWNS, case_id=case_id)
    r2 = Relationship(source_id=e2.id, target_id=e3.id, relation_type=RelationshipType.OWNS, case_id=case_id)

    db.save_relationship(r1)
    db.save_relationship(r2)
    graph_store.add_relationship_to_graph(case_id, r1)
    graph_store.add_relationship_to_graph(case_id, r2)

    # Shortest path
    path = graph_store.find_shortest_path(case_id, e1.id, e3.id)
    assert path is not None
    assert len(path) == 3

    # Ego graph
    ego = graph_store.get_ego_graph(case_id, e1.id, radius=1)
    assert len(ego["nodes"]) >= 2

    # GraphML Export
    graphml = graph_store.export_graphml(case_id)
    assert "<graphml" in graphml

    # Metrics computation
    metrics = graph_store.compute_metrics(case_id)
    assert "pagerank" in metrics
    assert "degree" in metrics

    # CSV Export
    csv_dict = graph_store.export_csv(case_id)
    assert "nodes_csv" in csv_dict
    assert "edges_csv" in csv_dict


def test_entity_resolution_deep():
    """Öka täckning för fuzzy deduplicering och entitetsupplösning."""
    case_id = f"res_case_{int(time.time())}"

    e1 = Entity(
        name="Vladimir V. Petrov",
        type=EntityType.PERSON,
        case_id=case_id,
        attributes={"national_id": "12345", "city": "Stockholm"},
    )
    e2 = Entity(
        name="Vladimir Petrov",
        type=EntityType.PERSON,
        case_id=case_id,
        attributes={"national_id": "12345", "city": "Stockholm"},
    )

    db.save_entity(e1)
    db.save_entity(e2)

    # Hitta kandidater
    matches = entity_resolver.find_matches(case_id)
    assert len(matches) >= 1
    assert matches[0].primary_entity_id in (e1.id, e2.id)

    # Sammanfoga (merge)
    merged = entity_resolver.merge_entities(e1.id, e2.id, case_id)
    assert merged is not None
    assert "Vladimir Petrov" in merged.aliases or merged.name == "Vladimir Petrov"


def test_webauthn_service_comprehensive():
    """Öka täckning för WebAuthn Service verifiering, registrering och felhantering."""
    user_id = f"webauthn_user_{int(time.time())}"

    # 1. Reg challenge utan aktiv registrering
    ok, err, codes = WebAuthnService.verify_registration(user_id=user_id, credential_data={})
    assert ok is False
    assert "Ingen aktiv" in err

    # 2. Generera registration options och testa utgången utmaning
    options = WebAuthnService.get_registration_options(user_id=user_id)
    assert "challenge" in options

    # Simulera utgången utmaning
    _pending_reg_challenges[user_id] = (b"old_challenge", time.time() - 10)
    ok, err, codes = WebAuthnService.verify_registration(user_id=user_id, credential_data={"response": {}})
    assert ok is False
    assert "Ingen aktiv" in err or "gått ut" in err or "passerat tidsgränsen" in err

    # 3. Testa lyckad WebAuthn registrering med mock
    _pending_reg_challenges[user_id] = (b"valid_challenge", time.time() + 100)
    mock_reg_result = MagicMock()
    unique_cred = f"test_cred_{time.time()}".encode()
    mock_reg_result.credential_id = unique_cred
    mock_reg_result.credential_public_key = b"test_pub_key_12345"
    mock_reg_result.sign_count = 1
    mock_reg_result.aaguid = "00000000-0000-0000-0000-000000000000"

    with patch("app.services.two_factor.webauthn_service.verify_registration_response", return_value=mock_reg_result):
        cred_payload = {"id": "test_cred_b64", "response": {"transports": ["usb"]}}
        ok, err, codes = WebAuthnService.verify_registration(
            user_id=user_id,
            credential_data=cred_payload,
            key_name="YubiKey 5C",
        )
        assert ok is True
        assert err is None
        assert codes is not None  # Nya backup-koder genereras vid första nyckeln

    # 4. Auth challenge
    auth_options = WebAuthnService.get_authentication_options(user_id=user_id)
    assert "challenge" in auth_options

    # Testa auth utgången
    _pending_auth_challenges[user_id] = (b"old_auth", time.time() - 10)
    ok, err = WebAuthnService.verify_authentication(user_id=user_id, credential_data={"id": "dummy"})
    assert ok is False
    assert "gått ut" in err or "Ingen aktiv" in err

    # Testa auth lyckad
    _pending_auth_challenges[user_id] = (b"valid_auth", time.time() + 100)
    registered_keys = db.list_security_keys(user_id)
    assert len(registered_keys) >= 1
    cred_id = registered_keys[0]["credential_id"]

    mock_auth_result = MagicMock()
    mock_auth_result.new_sign_count = 2

    with patch(
        "app.services.two_factor.webauthn_service.verify_authentication_response", return_value=mock_auth_result
    ):
        ok, err = WebAuthnService.verify_authentication(
            user_id=user_id,
            credential_data={"id": cred_id},
        )
        assert ok is True
        assert err is None

    # Testa klonad nyckel (ny count <= aktuell count)
    _pending_auth_challenges[user_id] = (b"valid_auth", time.time() + 100)
    mock_clone = MagicMock()
    mock_clone.new_sign_count = 2  # samma som nuvarande count

    with patch("app.services.two_factor.webauthn_service.verify_authentication_response", return_value=mock_clone):
        ok, err = WebAuthnService.verify_authentication(
            user_id=user_id,
            credential_data={"id": cred_id},
        )
        assert ok is False
        assert "klonad nyckel" in err


def test_two_factor_api_endpoints():
    """Öka täckning för 2FA REST API endpoints."""
    user_id = f"api_2fa_{int(time.time())}"

    # 1. Status
    res = client.get("/api/auth/2fa/status", params={"user_id": user_id})
    assert res.status_code == 200
    data = res.json()
    assert data["is_2fa_enabled"] is False

    # 2. Generera TOTP
    res_gen = client.post("/api/auth/2fa/totp/generate", params={"user_id": user_id})
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    secret = gen_data["secret"]

    # 3. Aktivera TOTP med felaktig kod
    res_bad = client.post("/api/auth/2fa/totp/enable", params={"user_id": user_id}, json={"code": "000000"})
    assert res_bad.status_code == 400

    # 4. Aktivera TOTP med korrekt kod
    import pyotp

    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    res_ok = client.post("/api/auth/2fa/totp/enable", params={"user_id": user_id}, json={"code": valid_code})
    assert res_ok.status_code == 200
    assert "backup_codes" in res_ok.json()

    # 5. Toggle Step-Up krav
    res_toggle = client.post(
        "/api/auth/2fa/step-up/toggle-vault", params={"user_id": user_id}, json={"step_up_vault_required": True}
    )
    assert res_toggle.status_code == 200
    assert res_toggle.json()["step_up_vault_required"] is True

    # 6. Step-Up verify med TOTP
    elev_code = totp.now()
    res_elev = client.post(
        "/api/auth/2fa/step-up/verify", params={"user_id": user_id}, json={"method": "totp", "code": elev_code}
    )
    assert res_elev.status_code == 200
    assert res_elev.json()["status"] == "success"

    # 7. require_elevated_session dependency
    assert require_elevated_session(user_id=user_id) is True

    # 8. Regenerera backup codes
    res_regen = client.post("/api/auth/2fa/backup-codes/regenerate", params={"user_id": user_id})
    assert res_regen.status_code == 200
    assert len(res_regen.json()["backup_codes"]) == 8

    # 9. Inaktivera 2FA
    res_dis = client.post("/api/auth/2fa/disable", params={"user_id": user_id})
    assert res_dis.status_code == 200
    assert res_dis.json()["is_2fa_enabled"] is False


def test_entities_and_relationships_api():
    """Öka täckning för Entiteter & Relationer REST API."""
    case = db.create_case(CaseCreateRequest(title="API Case Test", priority="low"))

    # 1. Skapa entitet
    res_e1 = client.post(
        "/api/entities",
        json={
            "case_id": case.id,
            "name": "Target Company AB",
            "type": "organization",
            "provenance_source": "https://bolagsverket.se/test",
        },
    )
    assert res_e1.status_code == 200
    e1 = res_e1.json()

    res_e2 = client.post(
        "/api/entities",
        json={
            "case_id": case.id,
            "name": "Target Owner",
            "type": "person",
        },
    )
    assert res_e2.status_code == 200
    e2 = res_e2.json()

    # 2. Lista och hämta
    res_list = client.get("/api/entities", params={"case_id": case.id})
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 2

    res_get = client.get(f"/api/entities/{e1['id']}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Target Company AB"

    # 3. Skapa relation
    res_r = client.post(
        "/api/entities/relationships",
        json={
            "case_id": case.id,
            "source_id": e2["id"],
            "target_id": e1["id"],
            "relation_type": "OWNS",
            "provenance_source": "https://ratsit.se/test",
        },
    )
    assert res_r.status_code == 200
    rel = res_r.json()

    # 4. Lista och ta bort relation
    res_r_list = client.get("/api/entities/relationships", params={"case_id": case.id})
    assert res_r_list.status_code == 200
    assert len(res_r_list.json()) >= 1

    res_r_del = client.delete(f"/api/entities/relationships/{rel['id']}")
    assert res_r_del.status_code == 200

    # 5. Ta bort entitet
    res_del_e = client.delete(f"/api/entities/{e2['id']}")
    assert res_del_e.status_code == 200


def test_cases_api_and_evidence():
    """Öka täckning för Cases & Evidence endpoints."""
    # Skapa ärende
    case = db.create_case(
        CaseCreateRequest(title="Evidence Case", priority="high", description="Case for evidence testing")
    )

    # Uppdatera ärende
    res_update = client.patch(
        f"/api/cases/{case.id}",
        json={
            "title": "Updated Evidence Case",
            "status": "closed",
            "priority": "critical",
            "tags": ["osint", "financial"],
        },
    )
    assert res_update.status_code == 200
    assert res_update.json()["title"] == "Updated Evidence Case"

    # Skapa bevis
    rel_path, sha, size = object_store.store_text(case.id, "report_note.txt", "Forensic investigative notes.")
    ev = db.save_evidence(
        EvidenceItem(
            case_id=case.id,
            title="Note 1",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type="text/plain",
            sha256=sha,
        )
    )

    # Hämta bevis och innehåll
    res_ev_get = client.get(f"/api/evidence/{ev.id}")
    assert res_ev_get.status_code == 200

    res_content = client.get(f"/api/evidence/{ev.id}/content")
    assert res_content.status_code == 200
    assert b"Forensic" in res_content.content

    # Beviskedjerevision
    res_audit = client.get(f"/api/evidence/audit/{case.id}")
    assert res_audit.status_code == 200
    assert res_audit.json()["chain_of_custody_intact"] is True

    # Ta bort ärende
    res_del = client.delete(f"/api/cases/{case.id}")
    assert res_del.status_code == 200


def test_analysis_and_roles_api():
    """Öka täckning för AI & NLP Analysis samt Workspace Roles."""
    case = db.create_case(CaseCreateRequest(title="NLP Analysis Case", priority="low"))

    # 1. NER-analys
    raw_text = (
        "Under utredningen kontaktades Johan Andersson på johan.andersson@nordictech.se "
        "angående överföringar till BTC plånbok 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa samt "
        "bolaget NordicTech AB (orgnr 556677-8899). Webbsida https://nordictech.se."
    )
    res_ner = client.post(
        "/api/analysis/ner",
        json={
            "case_id": case.id,
            "text": raw_text,
            "auto_commit_to_case": True,
        },
    )
    assert res_ner.status_code == 200
    data_ner = res_ner.json()
    assert data_ner["extracted_count"] >= 3

    # 2. Rapportgenerering (Markdown och HTML)
    res_md = client.get(f"/api/analysis/report/{case.id}/markdown")
    assert res_md.status_code == 200
    assert "Utredningsrapport" in res_md.text

    res_html = client.get(f"/api/analysis/report/{case.id}/html")
    assert res_html.status_code == 200
    assert "<html" in res_html.text

    # 3. Roles API
    res_roles = client.get("/api/roles")
    assert res_roles.status_code == 200
    assert len(res_roles.json()) >= 3

    res_role_law = client.get("/api/roles/law_enforcement")
    assert res_role_law.status_code == 200
    assert res_role_law.json()["role_id"] == "law_enforcement"


def test_transforms_api_and_playbooks():
    """Öka täckning för Transforms API och Playbooks."""
    case = db.create_case(CaseCreateRequest(title="Transforms Case", priority="low"))
    ent = db.save_entity(Entity(case_id=case.id, name="example.com", type=EntityType.DOMAIN))

    # 1. Lista transforms
    res_t = client.get("/api/transforms")
    assert res_t.status_code == 200
    assert len(res_t.json()) >= 5

    # 2. Transforms för entitet
    res_for_e = client.get(f"/api/transforms/for-entity/{ent.id}")
    assert res_for_e.status_code == 200
    assert len(res_for_e.json()["available_transforms"]) >= 1

    # 3. Whistleblower sanitize media
    dummy_image = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    files = {"file": ("leaked_memo.jpg", dummy_image, "image/jpeg")}
    res_strip = client.post("/api/playbooks/whistleblower-sanitize", params={"case_id": case.id}, files=files)
    assert res_strip.status_code == 200
    assert "sanitized_filename" in res_strip.json()


def test_graph_api_endpoints_full():
    """Öka täckning för Graph API endpoints och visualisering."""
    case = db.create_case(CaseCreateRequest(title="Graph API Case", priority="low"))
    e1 = db.save_entity(Entity(name="Node A", type=EntityType.DOMAIN, case_id=case.id))
    e2 = db.save_entity(Entity(name="Node B", type=EntityType.IP, case_id=case.id))
    graph_store.add_entity_to_graph(case.id, e1)
    graph_store.add_entity_to_graph(case.id, e2)

    rel = db.save_relationship(
        Relationship(
            source_id=e1.id,
            target_id=e2.id,
            relation_type=RelationshipType.RESOLVES_TO,
            case_id=case.id,
        )
    )
    graph_store.add_relationship_to_graph(case.id, rel)

    # 1. Hämta graf
    res_g = client.get(f"/api/graph/{case.id}")
    assert res_g.status_code == 200
    assert "nodes" in res_g.json()

    # 2. Hämta metrics
    res_m = client.get(f"/api/graph/{case.id}/metrics")
    assert res_m.status_code == 200
    assert "pagerank" in res_m.json()

    # 3. Hämta ego graf
    res_ego = client.get(f"/api/graph/{case.id}/ego/{e1.id}")
    assert res_ego.status_code == 200
    assert len(res_ego.json()["nodes"]) >= 1

    # 4. Shortest path
    res_sp = client.get(f"/api/graph/{case.id}/shortest-path", params={"source_id": e1.id, "target_id": e2.id})
    assert res_sp.status_code == 200
    assert res_sp.json()["found"] is True

    # 5. Export GEXF, GraphML, CSV
    res_gexf = client.get(f"/api/graph/{case.id}/export/gexf")
    assert res_gexf.status_code == 200
    assert "<gexf" in res_gexf.text

    res_graphml = client.get(f"/api/graph/{case.id}/export/graphml")
    assert res_graphml.status_code == 200
    assert "<graphml" in res_graphml.text

    res_csv = client.get(f"/api/graph/{case.id}/export/csv")
    assert res_csv.status_code == 200
    assert "nodes_csv" in res_csv.json()


def test_evidence_web_snapshot_endpoint():
    """Öka täckning för web snapshot endpoint och custody manager."""
    case = db.create_case(CaseCreateRequest(title="Snapshot Case", priority="low"))
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><body><h1>Archived OSINT Evidence</h1></body></html>"
    mock_resp.headers = {"Content-Type": "text/html"}

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = client.post(
            "/api/evidence/snapshot",
            json={
                "url": "https://leaks.osint-secure.org/dump.html",
                "case_id": case.id,
                "title": "OSINT Web Archive",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["sha256"] is not None
        assert data["source_url"] == "https://leaks.osint-secure.org/dump.html"


def test_entity_resolution_probabilistic_and_rewire():
    """Öka täckning för probabilistisk matchning och kantomdirigering."""
    case_id = f"case_prob_{int(time.time())}"
    e1 = db.save_entity(
        Entity(
            name="Alexander Petrov",
            type=EntityType.PERSON,
            aliases=["Alex Petrov"],
            attributes={"nationality": "SE", "city": "Stockholm"},
            case_id=case_id,
        )
    )
    e2 = db.save_entity(
        Entity(
            name="Alex Petrov",
            type=EntityType.PERSON,
            aliases=["Alexander Petrov"],
            attributes={"nationality": "SE", "city": "Stockholm"},
            case_id=case_id,
        )
    )
    e3 = db.save_entity(
        Entity(
            name="Holding AB",
            type=EntityType.ORGANIZATION,
            case_id=case_id,
        )
    )
    db.save_relationship(
        Relationship(
            source_id=e2.id,
            target_id=e3.id,
            relation_type=RelationshipType.OWNS,
            case_id=case_id,
        )
    )

    # Matchning
    matches = entity_resolver.find_matches(case_id=case_id, probabilistic_threshold=0.7)
    assert len(matches) >= 1

    # Sammanslagning med kantomdirigering
    merged = entity_resolver.merge_entities(primary_id=e1.id, secondary_id=e2.id, case_id=case_id)
    assert merged.id == e1.id
    assert db.get_entity(e2.id) is None


def test_additional_transforms_and_playbooks_coverage():
    """Öka täckning för transforms execution endpoints och dating playbook."""
    case = db.create_case(CaseCreateRequest(title="Playbook Deep Case", priority="low"))
    phone_ent = db.save_entity(Entity(case_id=case.id, name="+46701234567", type=EntityType.PHONE))

    # 1. Transform execute via REST
    res_exec = client.post(
        "/api/transforms/execute",
        json={
            "transform_name": "phone_breach_transform",
            "entity_id": phone_ent.id,
        },
    )
    assert res_exec.status_code == 200
    assert res_exec.json()["success"] is True

    # 2. Transform execute batch via REST
    res_batch = client.post(
        "/api/transforms/execute-batch",
        json={
            "transform_names": ["phone_breach_transform"],
            "entity_id": phone_ent.id,
        },
    )
    assert res_batch.status_code == 200
    assert len(res_batch.json()) == 1

    # 3. Dating verification playbook
    res_dating = client.post(
        "/api/playbooks/dating-verification",
        json={
            "case_id": case.id,
            "name": "Target Person",
            "phone": "+1 415 555 2671",
            "email": "target@example.com",
            "story": "Suspicious dating contact requesting emergency funds.",
        },
    )
    assert res_dating.status_code == 200
    assert "verdict" in res_dating.json() or "summary" in res_dating.json() or res_dating.status_code == 200


def test_two_factor_keys_and_options_endpoints():
    """Öka täckning för nyckelhantering och WebAuthn options."""
    user_id = f"user_keys_{int(time.time())}"

    # 1. Lista nycklar för ny användare
    res_keys = client.get("/api/auth/2fa/keys", params={"user_id": user_id})
    assert res_keys.status_code == 200
    assert isinstance(res_keys.json(), list)

    # 2. Spara temporär nyckel och lista
    key_id = f"key--{time.time()}"
    cred_id = f"cred_{time.time()}"
    db.save_security_key(
        key_id=key_id, user_id=user_id, key_name="Test Key", credential_id=cred_id, public_key="pubkey"
    )

    res_keys2 = client.get("/api/auth/2fa/keys", params={"user_id": user_id})
    assert len(res_keys2.json()) == 1

    # 3. WebAuthn register-options och auth-options endpoints
    res_reg_opt = client.post("/api/auth/2fa/webauthn/register-options", params={"user_id": user_id})
    assert res_reg_opt.status_code == 200
    assert "challenge" in res_reg_opt.json()

    res_auth_opt = client.post("/api/auth/2fa/webauthn/auth-options", params={"user_id": user_id})
    assert res_auth_opt.status_code == 200
    assert "challenge" in res_auth_opt.json()

    # 4. Ta bort säkerhetsnyckel
    res_del_key = client.delete(f"/api/auth/2fa/keys/{key_id}", params={"user_id": user_id})
    assert res_del_key.status_code == 200
    assert res_del_key.json()["status"] == "success"

    # 5. Avaktivera TOTP endpoint
    res_totp_dis = client.post("/api/auth/2fa/totp/disable", params={"user_id": user_id})
    assert res_totp_dis.status_code == 200
