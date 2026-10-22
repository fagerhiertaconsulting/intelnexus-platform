import logging
import io
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from app.main import app
from app.core.vault import credential_vault
from app.core.ssrf_protector import validate_target_url, SSRFProtectionError

client = TestClient(app)


def test_ssrf_cloud_metadata_blocked():
    """DAST SSRF-1: Anrop mot AWS/GCP/Azure molnmetadata ska avvisas med HTTP 400 BLOCKED_DESTINATION."""
    url = "http://169.254.169.254/latest/meta-data/"
    with pytest.raises(SSRFProtectionError) as exc_info:
        validate_target_url(url)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "BLOCKED_DESTINATION"

    # Verifiera även via API endpointen
    res = client.post("/api/transforms/fetch-url", json={"url": url})
    assert res.status_code == 400
    assert res.json()["detail"] == "BLOCKED_DESTINATION"


def test_ssrf_private_and_loopback_networks_blocked():
    """DAST SSRF-2: Anrop mot loopback och RFC 1918 privata nätverk ska blockeras."""
    forbidden_targets = [
        "http://127.0.0.1:8000/internal",
        "http://localhost:8080/admin",
        "http://10.0.0.1/secret",
        "http://172.16.0.10/database",
        "http://192.168.1.1/router",
        "http://[::1]/debug",
    ]

    for target in forbidden_targets:
        res = client.post("/api/transforms/fetch-url", json={"url": target})
        assert res.status_code == 400, f"URL {target} blockerades inte korrekt!"
        assert res.json()["detail"] == "BLOCKED_DESTINATION"


def test_idor_data_isolation_between_users():
    """
    DAST IDOR: User A skapar ett ärende.
    User B skickar förfrågningar för att läsa, modifiera eller radera ärendet.
    Samtliga anrop ska returnera HTTP 404 (Not Found).
    """
    # User A skapar ett ärende
    create_res = client.post(
        "/api/cases",
        headers={"X-User-Id": "User_A"},
        json={
            "title": "Hemlig Utredning User A",
            "description": "Känsliga underrättelser",
            "priority": "high",
            "investigator": "User_A",
        },
    )
    assert create_res.status_code == 200
    case_id = create_res.json()["id"]

    # 1. User B försöker läsa ärendet -> ska returnera 404
    read_res = client.get(f"/api/cases/{case_id}", headers={"X-User-Id": "User_B"})
    assert read_res.status_code == 404
    assert read_res.json()["detail"] == "Ärende hittades inte"

    # 2. User B försöker ändra ärendet -> ska returnera 404
    update_res = client.patch(
        f"/api/cases/{case_id}",
        headers={"X-User-Id": "User_B"},
        json={"title": "Manipulerad titel"},
    )
    assert update_res.status_code == 404
    assert update_res.json()["detail"] == "Ärende hittades inte"

    # 3. User B försöker radera ärendet -> ska returnera 404
    delete_res = client.delete(f"/api/cases/{case_id}", headers={"X-User-Id": "User_B"})
    assert delete_res.status_code == 404
    assert delete_res.json()["detail"] == "Ärende hittades inte"

    # Verifiera att User A fortfarande äger och kan läsa sitt ärende intakt
    user_a_res = client.get(f"/api/cases/{case_id}", headers={"X-User-Id": "User_A"})
    assert user_a_res.status_code == 200
    assert user_a_res.json()["title"] == "Hemlig Utredning User A"


def test_log_secrecy_api_vault():
    """
    DAST Log Secrecy: Injicera en testnyckel TEST_SECRET_DO_NOT_LEAK_99 i valvet.
    Generera felanrop och verifiera att hemligheten aldrig läcker till loggarna.
    """
    secret = "TEST_SECRET_DO_NOT_LEAK_99"
    key_name = "SHODAN_API_KEY"

    # Spara nyckeln krypterad
    credential_vault.set_key(key_name, secret)

    # Fånga loggutskrifter
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger()
    logger.addHandler(handler)

    try:
        # Gör ett testanrop mot valvet
        test_res = client.post(f"/api/vault/test/{key_name}")
        assert test_res.status_code == 200

        # Testa även ett felaktigt anrop
        bad_res = client.post("/api/vault/test/NON_EXISTENT_KEY_XYZ")
        assert bad_res.status_code == 404

        # Kontrollera loggar
        log_contents = log_stream.getvalue()
        assert secret not in log_contents, "SÄKERHETSBROTT: API-nyckeln i klartext hittades i loggarna!"
    finally:
        logger.removeHandler(handler)


def test_aes_gcm_tampering_resistance():
    """
    Verifiera kryptografisk integritet i AES-256-GCM.
    Manipulering av 1 bit i ciphertext eller nonce ska orsaka avvisning (InvalidTag).
    """
    aes_key = credential_vault._derive_aes_key()
    aesgcm = AESGCM(aes_key)
    nonce = b"123456789012"  # 12 bytes
    plaintext = b"top_secret_intel_data_payload"

    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Korrekt dekryptering fungerar
    assert aesgcm.decrypt(nonce, ciphertext, None) == plaintext

    # Manipulera en bit i ciphertext
    tampered_ciphertext = bytearray(ciphertext)
    tampered_ciphertext[0] ^= 0x01

    with pytest.raises(InvalidTag):
        aesgcm.decrypt(nonce, bytes(tampered_ciphertext), None)

    # Manipulera en bit i nonce
    tampered_nonce = bytearray(nonce)
    tampered_nonce[0] ^= 0x01

    with pytest.raises(InvalidTag):
        aesgcm.decrypt(bytes(tampered_nonce), ciphertext, None)


def test_phone_and_domain_normalization():
    """FAS 2: Verifiera normalisering av telefonnummer och domäner."""
    from app.transforms.phone_breach_transform import PhoneBreachCheckTransform
    from app.transforms.dns_transform import DnsWhoisTransform

    # Svenska mobilnummer ska normaliseras till E.164
    assert PhoneBreachCheckTransform.normalize_phone("070-123 45 67") == "+46701234567"
    assert PhoneBreachCheckTransform.normalize_phone("+46 70 123 45 67") == "+46701234567"
    assert PhoneBreachCheckTransform.normalize_phone("0701234567") == "+46701234567"

    # Domäner ska normaliseras till ren FQDN i gemener
    assert DnsWhoisTransform.normalize_domain("HTTPS://WWW.EXAMPLE.COM./") == "www.example.com"
    assert DnsWhoisTransform.normalize_domain("  SVT.SE   ") == "svt.se"
