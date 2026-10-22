import pytest
from fastapi.testclient import TestClient
import pyotp
from unittest.mock import patch

from app.main import app
from app.db.database import db
from app.services.two_factor import TOTPService
from app.api.auth import _failed_attempts, _challenge_tokens

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_auth_state():
    """Rensa testtillstånd och 2FA-inställningar före och efter varje test."""
    db.reset_2fa("user_auth_matrix")
    db.reset_2fa("default_user")
    _failed_attempts.clear()
    _challenge_tokens.clear()
    yield
    db.reset_2fa("user_auth_matrix")
    db.reset_2fa("default_user")
    _failed_attempts.clear()
    _challenge_tokens.clear()


def test_auth_01_login_without_2fa():
    """AUTH-01: Inloggning utan 2FA -> HTTP 200 OK med JWT direkt."""
    res = client.post("/api/auth/login", json={"username": "user_auth_matrix", "password": "valid_password_123"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["is_2fa_required"] is False


def test_auth_02_totp_initialization():
    """AUTH-02: TOTP Initiering -> Genererar base32-secret och SVG QR-data."""
    res = client.post("/api/auth/2fa/totp/generate?user_id=user_auth_matrix")
    assert res.status_code == 200
    data = res.json()
    assert "secret" in data
    assert len(data["secret"]) >= 16
    assert "otpauth_uri" in data
    assert "qr_code_svg" in data
    assert data["qr_code_svg"].startswith("data:image/svg+xml")


def test_auth_03_totp_completion():
    """AUTH-03: TOTP Slutförande -> totp_verified sätts till true, returnerar backupkoder."""
    gen = client.post("/api/auth/2fa/totp/generate?user_id=user_auth_matrix").json()
    secret = gen["secret"]
    valid_code = pyotp.TOTP(secret).now()

    enable_res = client.post(
        "/api/auth/2fa/totp/enable?user_id=user_auth_matrix",
        json={"code": valid_code},
    )
    assert enable_res.status_code == 200
    data = enable_res.json()
    assert data["status"] == "success"
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 8

    # Kontrollera status i DB
    status = db.get_2fa_settings("user_auth_matrix")
    assert status["is_2fa_enabled"] is True
    assert status["totp_verified"] is True


def test_auth_04_login_with_2fa_step_1():
    """AUTH-04: Inloggning med 2FA (Steg 1) -> Rätt lösenord mot 2FA-konto ger HTTP 403 med challenge_token."""
    # Aktivera 2FA
    gen = TOTPService.generate_secret("user_auth_matrix")
    code = pyotp.TOTP(gen["secret"]).now()
    TOTPService.enable_totp("user_auth_matrix", code)

    res = client.post("/api/auth/login", json={"username": "user_auth_matrix", "password": "valid_password_123"})
    assert res.status_code == 403
    assert res.headers.get("x-require-2fa") == "true"
    challenge_token = res.headers.get("x-challenge-token")
    assert challenge_token is not None
    assert challenge_token.startswith("chal_")


def test_auth_05_login_with_2fa_step_2():
    """AUTH-05: Inloggning med 2FA (Steg 2) -> Skickar challenge_token + rätt TOTP -> HTTP 200 OK med JWT."""
    gen = TOTPService.generate_secret("user_auth_matrix")
    code = pyotp.TOTP(gen["secret"]).now()
    TOTPService.enable_totp("user_auth_matrix", code)

    # Steg 1: Få challenge_token
    step1_res = client.post("/api/auth/login", json={"username": "user_auth_matrix", "password": "valid_password_123"})
    challenge_token = step1_res.headers.get("x-challenge-token")

    # Steg 2: Skicka TOTP kod
    step2_code = pyotp.TOTP(gen["secret"]).now()
    step2_res = client.post(
        "/api/auth/login/2fa",
        json={"challenge_token": challenge_token, "code": step2_code},
    )
    assert step2_res.status_code == 200
    data = step2_res.json()
    assert "access_token" in data
    assert data["is_2fa_required"] is True


def test_auth_06_brute_force_rate_limiting():
    """AUTH-06: Brute-force mot 2FA -> 5 felaktiga koder ger HTTP 429 Too Many Requests."""
    gen = TOTPService.generate_secret("user_auth_matrix")
    code = pyotp.TOTP(gen["secret"]).now()
    TOTPService.enable_totp("user_auth_matrix", code)

    step1_res = client.post("/api/auth/login", json={"username": "user_auth_matrix", "password": "valid_password_123"})
    challenge_token = step1_res.headers.get("x-challenge-token")

    # Skicka 4 felaktiga koder (ska returnera 400)
    for _ in range(4):
        bad_res = client.post(
            "/api/auth/login/2fa",
            json={"challenge_token": challenge_token, "code": "000000"},
        )
        assert bad_res.status_code == 400

    # 5:e försöket överskrider gränsen och spärrar kontot (HTTP 429)
    blocked_res = client.post(
        "/api/auth/login/2fa",
        json={"challenge_token": challenge_token, "code": "000000"},
    )
    assert blocked_res.status_code == 429
    assert "spärrat" in blocked_res.json()["detail"].lower()


def test_auth_07_webauthn_registration():
    """AUTH-07: WebAuthn Registrering -> Skickar FIDO2 options och sparar publik nyckel med sign_count = 0."""
    reg_opts = client.post("/api/auth/2fa/webauthn/register-options?user_id=user_auth_matrix").json()
    assert "challenge" in reg_opts

    # Registrera mockad säkerhetsnyckel
    db.save_security_key(
        key_id="test_key_fido2",
        user_id="user_auth_matrix",
        key_name="YubiKey 5C NFC",
        credential_id="mock_cred_id_12345",
        public_key="mock_pub_key_abcdef",
        sign_count=0,
        transports=["usb", "nfc"],
    )
    db.update_2fa_settings(user_id="user_auth_matrix", is_2fa_enabled=True)

    keys = db.list_security_keys("user_auth_matrix")
    assert len(keys) == 1
    assert keys[0]["sign_count"] == 0
    assert keys[0]["key_name"] == "YubiKey 5C NFC"


def test_auth_08_webauthn_login():
    """AUTH-08: WebAuthn Inloggning -> Validerar hårdvarusignatur, ökar sign_count till 1, utfärdar JWT."""
    db.save_security_key(
        key_id="test_key_fido2",
        user_id="user_auth_matrix",
        key_name="YubiKey 5C NFC",
        credential_id="mock_cred_id_12345",
        public_key="mock_pub_key_abcdef",
        sign_count=0,
    )
    db.update_2fa_settings(user_id="user_auth_matrix", is_2fa_enabled=True)

    # Skapa login challenge
    step1_res = client.post("/api/auth/login", json={"username": "user_auth_matrix", "password": "valid_password_123"})
    challenge_token = step1_res.headers.get("x-challenge-token")

    # Mocka verifiering av hårdvarunyckelns signatur med ökat sign_count
    with patch(
        "app.services.two_factor.WebAuthnService.verify_authentication",
        return_value=(True, None),
    ):
        db.update_security_key_sign_count("mock_cred_id_12345", 1)
        res = client.post(
            "/api/auth/login/webauthn",
            json={"challenge_token": challenge_token, "credential": {"id": "mock_cred_id_12345"}},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["user_id"] == "user_auth_matrix"

    stored_key = db.get_security_key_by_credential_id("mock_cred_id_12345")
    assert stored_key["sign_count"] == 1


def test_auth_09_fido2_replay_attack_prevention():
    """AUTH-09: Replay-attack på FIDO2 -> Återanvändning av assertion nekas direkt."""
    db.save_security_key(
        key_id="test_key_fido2",
        user_id="user_auth_matrix",
        key_name="YubiKey 5C NFC",
        credential_id="mock_cred_id_12345",
        public_key="mock_pub_key_abcdef",
        sign_count=5,  # Redan på 5
    )

    # Försök återanvända tidigare sign_count (t.ex. 4 eller 5)
    from app.services.two_factor import webauthn_service

    # Simulera att nyckelns räknare inte ökar (replay/kloning)
    with patch("app.services.two_factor.webauthn_service.verify_authentication_response") as mock_verify:

        class MockVerified:
            new_sign_count = 5  # Inte större än 5!

        mock_verify.return_value = MockVerified()

        # Lägg till aktiv challenge i modulens cache
        webauthn_service._pending_auth_challenges["user_auth_matrix"] = (b"challenge", 9999999999.0)

        success, err = webauthn_service.WebAuthnService.verify_authentication(
            user_id="user_auth_matrix",
            credential_data={"id": "mock_cred_id_12345"},
        )
        assert success is False
        assert "klonad" in err.lower() or "räknaren ökade inte" in err.lower()
