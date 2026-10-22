from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
import pyotp

from app.main import app
from app.db.database import db
from app.services.two_factor import TOTPService, BackupCodeService
from app.services.two_factor.totp_service import encrypt_totp_secret, decrypt_totp_secret

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_2fa():
    """Återställ 2FA-inställningar före och efter varje test."""
    db.reset_2fa("test_user")
    db.reset_2fa("default_user")
    yield
    db.reset_2fa("test_user")
    db.reset_2fa("default_user")


def test_voluntary_opt_in_by_default():
    """Verifiera att 2FA är 100% frivilligt och att valvet kan nås utan prompter som standard."""
    status_res = client.get("/api/auth/2fa/status")
    assert status_res.status_code == 200
    data = status_res.json()
    assert data["is_2fa_enabled"] is False
    assert data["totp_verified"] is False
    assert data["step_up_vault_required"] is False
    assert data["is_elevated"] is False

    # Valvet ska gå att lista utan något 403 Step-Up-krav
    vault_res = client.get("/api/vault")
    assert vault_res.status_code == 200
    assert isinstance(vault_res.json(), list)


def test_totp_secret_generation_and_drift_verification():
    """Verifiera TOTP-generering, SVG QR-kod samt verifiering med +-30 sekunder drift."""
    gen = TOTPService.generate_secret(user_id="test_user")
    assert "secret" in gen
    assert "otpauth_uri" in gen
    assert "qr_code_svg" in gen
    assert gen["qr_code_svg"].startswith("data:image/svg+xml")
    assert "OpenIntel" in gen["otpauth_uri"]

    secret = gen["secret"]
    totp = pyotp.TOTP(secret)

    # Nuvarande kod ska vara giltig
    current_code = totp.now()
    assert TOTPService.verify_code(secret, current_code) is True

    # Kod från föregående tidsintervall (-30s) ska accepteras pga valid_window=1
    past_time = datetime.now() - timedelta(seconds=30)
    past_code = totp.at(past_time)
    assert TOTPService.verify_code(secret, past_code) is True

    # Kod från nästa tidsintervall (+30s) ska accepteras pga valid_window=1
    future_time = datetime.now() + timedelta(seconds=30)
    future_code = totp.at(future_time)
    assert TOTPService.verify_code(secret, future_code) is True

    # Ogiltig kod eller fel format ska avvisas
    assert TOTPService.verify_code(secret, "000000") is False
    assert TOTPService.verify_code(secret, "abc") is False


def test_totp_aes_gcm_encryption_in_vault():
    """Verifiera att TOTP-hemligheter krypteras i vila med AES-256-GCM."""
    raw_secret = pyotp.random_base32()
    encrypted = encrypt_totp_secret(raw_secret)
    assert encrypted != raw_secret

    decrypted = decrypt_totp_secret(encrypted)
    assert decrypted == raw_secret


def test_totp_enable_flow_and_backup_codes():
    """Verifiera hela aktiveringsflödet för TOTP via REST API samt engångskoder."""
    gen_res = client.post("/api/auth/2fa/totp/generate")
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    secret = gen_data["secret"]

    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    # Försök aktivera med fel kod
    bad_res = client.post("/api/auth/2fa/totp/enable", json={"code": "999999"})
    assert bad_res.status_code == 400

    # Aktivera med korrekt kod
    ok_res = client.post("/api/auth/2fa/totp/enable", json={"code": valid_code})
    assert ok_res.status_code == 200
    ok_data = ok_res.json()
    assert ok_data["status"] == "success"
    assert "backup_codes" in ok_data
    backup_codes = ok_data["backup_codes"]
    assert len(backup_codes) == 8
    assert all("-" in code for code in backup_codes)

    # Kontrollera status nu
    status_res = client.get("/api/auth/2fa/status")
    status_data = status_res.json()
    assert status_data["is_2fa_enabled"] is True
    assert status_data["totp_verified"] is True
    assert status_data["unused_backup_codes_count"] == 8


def test_backup_code_single_use_redemption():
    """Verifiera att en nödkod kan användas exakt en gång (single-use) och förbrukas."""
    # Generera koder för default_user
    codes = BackupCodeService.generate_and_save_backup_codes("default_user", count=8)
    assert len(codes) == 8
    target_code = codes[0]

    # Lös in koden första gången
    res1 = client.post("/api/auth/2fa/backup-codes/verify", json={"code": target_code})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["is_elevated"] is True
    assert data1["remaining_backup_codes"] == 7

    # Försök lösa in samma kod en andra gång -> ska nekas
    res2 = client.post("/api/auth/2fa/backup-codes/verify", json={"code": target_code})
    assert res2.status_code == 400
    assert "redan förbrukad" in res2.json()["detail"]


def test_step_up_vault_protection():
    """Verifiera att valvet skyddas av Step-Up när 2FA och step_up_vault_required är aktiverat."""
    # Aktivera TOTP
    gen = TOTPService.generate_secret("default_user")
    code = pyotp.TOTP(gen["secret"]).now()
    TOTPService.enable_totp("default_user", code)

    # Slå på step_up_vault_required
    toggle_res = client.post("/api/auth/2fa/step-up/toggle-vault", json={"step_up_vault_required": True})
    assert toggle_res.status_code == 200

    # Nu ska anrop till /api/vault ge 403 Forbidden med X-Require-Step-Up: true
    vault_res = client.get("/api/vault")
    assert vault_res.status_code == 403
    assert vault_res.headers.get("x-require-step-up") == "true"

    # Verifiera Step-Up med korrekt TOTP-kod
    step_code = pyotp.TOTP(gen["secret"]).now()
    step_res = client.post("/api/auth/2fa/step-up/verify", json={"method": "totp", "code": step_code})
    assert step_res.status_code == 200
    assert step_res.json()["is_elevated"] is True

    # Nu ska valvet kunna öppnas framgångsrikt (elevation aktiv i 15 minuter)
    vault_res_after = client.get("/api/vault")
    assert vault_res_after.status_code == 200


def test_webauthn_options_generation():
    """Verifiera att registrerings- och autentiseringsalternativ för FIDO2 genereras korrekt."""
    reg_res = client.post("/api/auth/2fa/webauthn/register-options")
    assert reg_res.status_code == 200
    reg_opts = reg_res.json()
    assert "challenge" in reg_opts
    assert "rp" in reg_opts
    assert reg_opts["rp"]["id"] == "localhost"
    assert "user" in reg_opts

    # Autentiseringsalternativ
    auth_res = client.post("/api/auth/2fa/webauthn/auth-options")
    assert auth_res.status_code == 200
    auth_opts = auth_res.json()
    assert "challenge" in auth_opts
    assert auth_opts["rpId"] == "localhost"


def test_disable_2fa_flow():
    """Verifiera att 2FA kan stängas av fullständigt och återställa systemet."""
    gen = TOTPService.generate_secret("default_user")
    code = pyotp.TOTP(gen["secret"]).now()
    TOTPService.enable_totp("default_user", code)
    client.post("/api/auth/2fa/step-up/toggle-vault", json={"step_up_vault_required": True})

    status_before = client.get("/api/auth/2fa/status").json()
    assert status_before["is_2fa_enabled"] is True

    # Avaktivera
    disable_res = client.post("/api/auth/2fa/disable")
    assert disable_res.status_code == 200
    assert disable_res.json()["is_2fa_enabled"] is False

    # Kontrollera status
    status_after = client.get("/api/auth/2fa/status").json()
    assert status_after["is_2fa_enabled"] is False
    assert status_after["totp_verified"] is False
    assert status_after["step_up_vault_required"] is False

    # Valvet ska återigen vara helt öppet utan 2FA
    assert client.get("/api/vault").status_code == 200
