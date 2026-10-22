import base64
import os
import time
from typing import Dict, Optional, Tuple
import pyotp
import segno
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.vault import credential_vault
from app.db.database import db


# In-memory lagring av preliminära TOTP-hemligheter under konfiguration (TTL 300 sekunder)
_pending_totp_secrets: Dict[str, Tuple[str, float]] = {}


def _clean_expired_pending():
    now = time.time()
    expired = [uid for uid, (_, exp) in _pending_totp_secrets.items() if now > exp]
    for uid in expired:
        _pending_totp_secrets.pop(uid, None)


def encrypt_totp_secret(secret: str) -> str:
    """Krypterar TOTP-hemligheten med AES-256-GCM via valvets härledda master-nyckel."""
    aes_key = credential_vault._derive_aes_key()
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, secret.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_totp_secret(encrypted_b64: str) -> Optional[str]:
    """Dekrypterar TOTP-hemligheten."""
    try:
        raw = base64.b64decode(encrypted_b64)
        if len(raw) < 13:
            return None
        nonce = raw[:12]
        ciphertext = raw[12:]
        aes_key = credential_vault._derive_aes_key()
        aesgcm = AESGCM(aes_key)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception:
        return None


class TOTPService:
    @staticmethod
    def generate_secret(user_id: str = "default_user", email: str = "analyst@openintel.local") -> Dict[str, str]:
        """
        Genererar en slumpmässig Base32-hemlighet, otpauth-URI och SVG Data URI för QR-kod.
        Sparar hemligheten temporärt i minnet tills verifiering sker.
        """
        _clean_expired_pending()
        secret = pyotp.random_base32()
        _pending_totp_secrets[user_id] = (secret, time.time() + 300.0)

        totp = pyotp.TOTP(secret)
        otpauth_uri = totp.provisioning_uri(name=email, issuer_name="OpenIntel OSINT")

        qr = segno.make(otpauth_uri)
        qr_svg_uri = qr.svg_data_uri(scale=5)

        return {
            "secret": secret,
            "otpauth_uri": otpauth_uri,
            "qr_code_svg": qr_svg_uri,
        }

    @staticmethod
    def verify_code(secret: str, code: str) -> bool:
        """
        Verifierar en 6-siffrig kod med RFC 6238.
        Tillåter tidsdrift på +-30 sekunder (valid_window=1).
        """
        if not secret or not code:
            return False
        cleaned_code = code.strip().replace(" ", "").replace("-", "")
        if len(cleaned_code) != 6 or not cleaned_code.isdigit():
            return False
        totp = pyotp.TOTP(secret)
        return bool(totp.verify(cleaned_code, valid_window=1))

    @staticmethod
    def enable_totp(user_id: str = "default_user", code: str = "") -> Tuple[bool, Optional[str], Optional[list]]:
        """
        Bekräftar den preliminära TOTP-koden, krypterar hemligheten i databasen och aktiverar 2FA.
        Returnerar (lyckades, felmeddelande, nya_backup_koder_om_första_gången).
        """
        _clean_expired_pending()
        pending = _pending_totp_secrets.get(user_id)
        if not pending:
            return False, "Ingen aktiv TOTP-konfiguration hittades. Generera en ny QR-kod.", None

        secret, exp = pending
        if time.time() > exp:
            _pending_totp_secrets.pop(user_id, None)
            return False, "TOTP-konfigurationen har gått ut. Försök igen.", None

        if not TOTPService.verify_code(secret, code):
            return False, "Felaktig 6-siffrig kod från din autentiseringsapp.", None

        # Spara krypterat i DB
        encrypted_secret = encrypt_totp_secret(secret)
        _pending_totp_secrets.pop(user_id, None)

        from app.services.two_factor.backup_code_service import BackupCodeService

        # Kontrollera om användaren redan har backupkoder
        existing_codes = db.list_unused_backup_codes(user_id)
        new_backup_codes = None
        if not existing_codes:
            new_backup_codes = BackupCodeService.generate_and_save_backup_codes(user_id)

        db.update_2fa_settings(
            user_id=user_id,
            is_2fa_enabled=True,
            totp_secret_encrypted=encrypted_secret,
            totp_verified=True,
        )

        return True, None, new_backup_codes

    @staticmethod
    def verify_user_totp(user_id: str = "default_user", code: str = "") -> bool:
        """Verifierar en kod mot användarens sparade TOTP-hemlighet."""
        settings = db.get_2fa_settings(user_id)
        if not settings.get("totp_verified") or not settings.get("totp_secret_encrypted"):
            return False

        secret = decrypt_totp_secret(settings["totp_secret_encrypted"])
        if not secret:
            return False

        return TOTPService.verify_code(secret, code)

    @staticmethod
    def disable_totp(user_id: str = "default_user"):
        """Avaktiverar TOTP för användaren."""
        keys = db.list_security_keys(user_id)
        has_keys = len(keys) > 0
        db.update_2fa_settings(
            user_id=user_id,
            is_2fa_enabled=has_keys,  # Fortsätt vara 2FA om säkerhetsnycklar finns
            totp_secret_encrypted=None,
            totp_verified=False,
        )
