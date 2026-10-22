import json
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import webauthn
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.bytes_to_base64url import bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)
from app.db.database import db

# RP Konfiguration
RP_ID = "localhost"
RP_NAME = "OpenIntel OSINT Platform"
DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Minneslagring av challenges med TTL (120 sekunder)
_pending_reg_challenges: Dict[str, Tuple[bytes, float]] = {}
_pending_auth_challenges: Dict[str, Tuple[bytes, float]] = {}


def _clean_expired_challenges():
    now = time.time()
    for uid in [k for k, (_, exp) in _pending_reg_challenges.items() if now > exp]:
        _pending_reg_challenges.pop(uid, None)
    for uid in [k for k, (_, exp) in _pending_auth_challenges.items() if now > exp]:
        _pending_auth_challenges.pop(uid, None)


class WebAuthnService:
    @staticmethod
    def get_registration_options(
        user_id: str = "default_user", user_email: str = "analyst@openintel.local", rp_id: str = RP_ID
    ) -> Dict[str, Any]:
        """Genererar WebAuthn-registreringsalternativ och sparar utmaningen med TTL 120s."""
        _clean_expired_challenges()

        # Befintliga nycklar ska exkluderas så att samma nyckel inte registreras två gånger
        existing_keys = db.list_security_keys(user_id)
        exclude_credentials = []
        for k in existing_keys:
            try:
                exclude_credentials.append(PublicKeyCredentialDescriptor(id=base64url_to_bytes(k["credential_id"])))
            except Exception:
                pass

        options = generate_registration_options(
            rp_id=rp_id,
            rp_name=RP_NAME,
            user_id=user_id.encode("utf-8"),
            user_name=user_email,
            user_display_name="OpenIntel Utredare",
            attestation=webauthn.helpers.structs.AttestationConveyancePreference.NONE,
            authenticator_selection=AuthenticatorSelectionCriteria(
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
            exclude_credentials=exclude_credentials if exclude_credentials else None,
            timeout=60000,
        )

        _pending_reg_challenges[user_id] = (options.challenge, time.time() + 120.0)
        return json.loads(options_to_json(options))

    @staticmethod
    def verify_registration(
        user_id: str = "default_user",
        credential_data: Optional[Dict[str, Any]] = None,
        key_name: str = "Säkerhetsnyckel",
        client_origin: Optional[str] = None,
        rp_id: str = RP_ID,
    ) -> Tuple[bool, Optional[str], Optional[List[str]]]:
        """
        Verifierar WebAuthn-registreringen och sparar nyckeln i databasen.
        Returnerar (lyckades, felmeddelande, nya_backup_koder_om_första_gången).
        """
        _clean_expired_challenges()
        pending = _pending_reg_challenges.get(user_id)
        if not pending:
            return False, "Ingen aktiv registreringsutmaning hittades eller så har den gått ut.", None

        challenge_bytes, exp = pending
        if time.time() > exp:
            _pending_reg_challenges.pop(user_id, None)
            return False, "Registreringsutmaningen har passerat tidsgränsen (120s).", None

        if not credential_data:
            return False, "Saknar credential-data från webbläsaren.", None

        origins = list(DEFAULT_ORIGINS)
        if client_origin and client_origin not in origins:
            origins.append(client_origin)

        try:
            verified = verify_registration_response(
                credential=credential_data,
                expected_challenge=challenge_bytes,
                expected_rp_id=rp_id,
                expected_origin=origins,
                require_user_verification=False,
            )
        except Exception as e:
            return False, f"WebAuthn-registrering misslyckades: {str(e)}", None
        finally:
            _pending_reg_challenges.pop(user_id, None)

        credential_id_b64 = bytes_to_base64url(verified.credential_id)
        public_key_b64 = bytes_to_base64url(verified.credential_public_key)
        aaguid_str = str(verified.aaguid) if verified.aaguid else None

        # Hämta eventuella transports från klientresponsen
        raw_transports = credential_data.get("response", {}).get("transports", [])

        # Spara nyckeln
        key_id = f"key--{uuid4()}"
        db.save_security_key(
            key_id=key_id,
            user_id=user_id,
            key_name=key_name.strip() or "Hårdvarunyckel",
            credential_id=credential_id_b64,
            public_key=public_key_b64,
            sign_count=verified.sign_count,
            transports=raw_transports,
            aaguid=aaguid_str,
        )

        from app.services.two_factor.backup_code_service import BackupCodeService

        # Generera nödkoder om användaren inte redan har några
        existing_codes = db.list_unused_backup_codes(user_id)
        new_backup_codes = None
        if not existing_codes:
            new_backup_codes = BackupCodeService.generate_and_save_backup_codes(user_id)

        # Aktivera 2FA för användaren
        db.update_2fa_settings(user_id=user_id, is_2fa_enabled=True)

        return True, None, new_backup_codes

    @staticmethod
    def get_authentication_options(user_id: str = "default_user", rp_id: str = RP_ID) -> Dict[str, Any]:
        """Genererar WebAuthn-autentiseringsalternativ för användarens registrerade nycklar."""
        _clean_expired_challenges()

        keys = db.list_security_keys(user_id)
        allow_credentials = []
        for k in keys:
            try:
                allow_credentials.append(PublicKeyCredentialDescriptor(id=base64url_to_bytes(k["credential_id"])))
            except Exception:
                pass

        options = generate_authentication_options(
            rp_id=rp_id,
            allow_credentials=allow_credentials if allow_credentials else None,
            user_verification=UserVerificationRequirement.PREFERRED,
            timeout=60000,
        )

        _pending_auth_challenges[user_id] = (options.challenge, time.time() + 120.0)
        return json.loads(options_to_json(options))

    @staticmethod
    def verify_authentication(
        user_id: str = "default_user",
        credential_data: Optional[Dict[str, Any]] = None,
        client_origin: Optional[str] = None,
        rp_id: str = RP_ID,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifierar WebAuthn-autentisering.
        Kontrollerar att sign_count ökar strikt för att skydda mot klonade/duplicerade enheter.
        """
        _clean_expired_challenges()
        pending = _pending_auth_challenges.get(user_id)
        if not pending:
            return False, "Ingen aktiv autentiseringsutmaning hittades."

        challenge_bytes, exp = pending
        if time.time() > exp:
            _pending_auth_challenges.pop(user_id, None)
            return False, "Autentiseringsutmaningen har gått ut."

        if not credential_data:
            return False, "Saknar credential-data från webbläsaren."

        raw_id = credential_data.get("id")
        if not raw_id:
            return False, "Saknar credential ID i svaret."

        stored_key = db.get_security_key_by_credential_id(raw_id)
        if not stored_key or stored_key["user_id"] != user_id:
            return False, "Okänd eller obehörig säkerhetsnyckel."

        origins = list(DEFAULT_ORIGINS)
        if client_origin and client_origin not in origins:
            origins.append(client_origin)

        try:
            verified = verify_authentication_response(
                credential=credential_data,
                expected_challenge=challenge_bytes,
                expected_rp_id=rp_id,
                expected_origin=origins,
                credential_public_key=base64url_to_bytes(stored_key["public_key"]),
                credential_current_sign_count=stored_key["sign_count"],
                require_user_verification=False,
            )
        except Exception as e:
            return False, f"WebAuthn-verifiering misslyckades: {str(e)}"
        finally:
            _pending_auth_challenges.pop(user_id, None)

        current_count = stored_key["sign_count"]
        new_count = verified.new_sign_count

        # Kontrollera sign_count mot replay / klonade nycklar (om nyckeln stödjer räknare)
        if current_count > 0 and new_count <= current_count:
            return False, "Varning för potentiellt klonad nyckel: Signaturräknaren ökade inte."

        db.update_security_key_sign_count(raw_id, new_count)
        return True, None
