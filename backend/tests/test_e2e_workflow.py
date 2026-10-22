import hashlib
from fastapi.testclient import TestClient
import pyotp

from app.main import app
from app.db.database import db
from app.core.roles import role_manager
from app.services.two_factor import TOTPService

client = TestClient(app)


def test_complete_end_to_end_investigative_workflow():
    """
    FAS 4 E2E:
    1. Skapa ärende
    2. Välj roll och verifiera rollanpassning
    3. Valfritt aktivera 2FA
    4. Valvåtkomst med Step-Up elevation
    5. Insamling av entiteter och bevis
    6. Exportera graf och rapport samt validera SHA-256 integritet
    """
    db.reset_2fa("Lead_Investigator")

    # 1. Skapa ett nytt utredningsärende
    case_res = client.post(
        "/api/cases",
        json={
            "title": "Operation Baltic Shadow",
            "description": "Undersökning av misstänkta skalföretag och sanktionsöverträdelser",
            "priority": "critical",
            "tags": ["baltic", "sanctions", "ubo"],
            "investigator": "Lead_Investigator",
        },
    )
    assert case_res.status_code == 200
    case_id = case_res.json()["id"]

    # 2. Välj roll (finance_aml) och verifiera persona-egenskaper
    role = role_manager.get_role("finance_aml")
    assert role is not None
    assert "Finans" in role.display_name
    assert "OPENSANCTIONS_API_KEY" in [
        k.get("key_name") if isinstance(k, dict) else k.key_name for k in role.suggested_api_keys
    ]

    # 3. Valfritt aktivera 2FA för utredaren
    totp_data = TOTPService.generate_secret(user_id="Lead_Investigator")
    totp_code = pyotp.TOTP(totp_data["secret"]).now()
    ok, err, backup_codes = TOTPService.enable_totp("Lead_Investigator", totp_code)
    assert ok is True
    assert len(backup_codes) == 8

    # 4. Slå på Step-Up för API-valvet och lås upp det med 2FA-koden
    toggle_res = client.post(
        "/api/auth/2fa/step-up/toggle-vault?user_id=Lead_Investigator",
        json={"step_up_vault_required": True},
    )
    assert toggle_res.status_code == 200

    # Valvet kräver nu step-up
    step_code = pyotp.TOTP(totp_data["secret"]).now()
    unlock_res = client.post(
        "/api/auth/2fa/step-up/verify?user_id=Lead_Investigator",
        json={"method": "totp", "code": step_code},
    )
    assert unlock_res.status_code == 200
    assert unlock_res.json()["is_elevated"] is True

    # Spara en API-nyckel i valvet
    vault_save_res = client.post(
        "/api/vault",
        json={
            "key_name": "OPENSANCTIONS_API_KEY",
            "api_key": "sec_sanctions_test_token_8899",
            "label": "OpenSanctions Commercial",
        },
    )
    assert vault_save_res.status_code == 200

    # 5. Lägg till entiteter (bolag och person) och relationer i ärendet
    comp_res = client.post(
        "/api/entities",
        json={
            "case_id": case_id,
            "type": "organization",
            "name": "Baltic Trade Logistics OU",
            "attributes": {"jurisdiction": "EE", "sanctioned": True},
        },
    )
    assert comp_res.status_code == 200
    comp_id = comp_res.json()["id"]

    person_res = client.post(
        "/api/entities",
        json={
            "case_id": case_id,
            "type": "person",
            "name": "Viktor Petrov",
            "attributes": {"role": "Director"},
        },
    )
    assert person_res.status_code == 200
    person_id = person_res.json()["id"]

    rel_res = client.post(
        "/api/entities/relationships",
        json={
            "case_id": case_id,
            "source_id": person_id,
            "target_id": comp_id,
            "relation_type": "DIRECTOR_OF",
            "confidence_score": 0.95,
        },
    )
    assert rel_res.status_code == 200

    # 6. Exportera graf i GEXF-format och verifiera SHA-256 hash
    export_res = client.get(f"/api/graph/{case_id}/export/gexf")
    assert export_res.status_code == 200
    gexf_content = export_res.content
    assert len(gexf_content) > 100
    assert b"Baltic Trade Logistics OU" in gexf_content

    # Beräkna och validera SHA-256
    sha256_hash = hashlib.sha256(gexf_content).hexdigest()
    assert len(sha256_hash) == 64

    # Generera rapport och verifiera Chain of Custody
    report_res = client.get(f"/api/analysis/report/{case_id}/markdown")
    assert report_res.status_code == 200
    assert "Operation Baltic Shadow" in report_res.text
    assert "Baltic Trade Logistics OU" in report_res.text
