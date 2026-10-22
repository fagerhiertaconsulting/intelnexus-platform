from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request

from app.db.database import db
from app.models.two_factor import (
    BackupCodeVerifyRequest,
    SecurityKeyInfo,
    StepUpVerifyRequest,
    ToggleStepUpRequest,
    TOTPEnableRequest,
    TOTPGenerateResponse,
    User2FASettingsResponse,
    WebAuthnAuthVerifyRequest,
    WebAuthnRegisterVerifyRequest,
)
from app.services.two_factor import BackupCodeService, TOTPService, WebAuthnService

router = APIRouter(prefix="/auth/2fa", tags=["Two-Factor Authentication (2FA)"])


def check_is_elevated(elevated_until_str: Optional[str]) -> bool:
    """Kontrollerar om användarens elevation fortfarande är aktiv."""
    if not elevated_until_str:
        return False
    try:
        elevated_until = datetime.fromisoformat(elevated_until_str)
        now = datetime.now(timezone.utc)
        if elevated_until.tzinfo is None:
            elevated_until = elevated_until.replace(tzinfo=timezone.utc)
        return now < elevated_until
    except Exception:
        return False


def require_elevated_session(user_id: str = "default_user"):
    """
    FastAPI dependency som validerar Step-Up elevation.
    Om 2FA är inaktivt släpps anropet igenom direkt (strikt frivilligt).
    Om 2FA och Step-Up är aktivt men ej verifierat/utgånget returneras HTTP 403 med X-Require-Step-Up header.
    """
    settings = db.get_2fa_settings(user_id)
    if not settings.get("is_2fa_enabled"):
        return True

    if not settings.get("step_up_vault_required"):
        return True

    if not check_is_elevated(settings.get("elevated_until")):
        raise HTTPException(
            status_code=403,
            detail="Åtkomst nekad: Tvåfaktorsautentisering krävs för att låsa upp valvet.",
            headers={"X-Require-Step-Up": "true"},
        )
    return True


@router.get("/status", response_model=User2FASettingsResponse)
def get_2fa_status(user_id: str = "default_user"):
    """Returnerar aktuell 2FA-konfiguration, registrerade nycklar och elevationsstatus."""
    settings = db.get_2fa_settings(user_id)
    keys = db.list_security_keys(user_id)
    unused_backup = db.list_unused_backup_codes(user_id)
    is_elevated = check_is_elevated(settings.get("elevated_until"))

    return User2FASettingsResponse(
        user_id=user_id,
        is_2fa_enabled=settings.get("is_2fa_enabled", False),
        totp_verified=settings.get("totp_verified", False),
        step_up_vault_required=settings.get("step_up_vault_required", False),
        elevated_until=settings.get("elevated_until"),
        is_elevated=is_elevated,
        has_security_keys=len(keys) > 0,
        security_keys_count=len(keys),
        unused_backup_codes_count=len(unused_backup),
    )


@router.get("/keys", response_model=List[SecurityKeyInfo])
def list_security_keys(user_id: str = "default_user"):
    """Listar alla registrerade FIDO2/WebAuthn-hårdvarunycklar för användaren."""
    rows = db.list_security_keys(user_id)
    return [
        SecurityKeyInfo(
            id=r["id"],
            user_id=r["user_id"],
            key_name=r["key_name"],
            credential_id=r["credential_id"],
            sign_count=r["sign_count"],
            transports=r.get("transports", []),
            aaguid=r.get("aaguid"),
            created_at=r["created_at"],
            last_used_at=r.get("last_used_at"),
        )
        for r in rows
    ]


@router.delete("/keys/{key_id}")
def delete_security_key(key_id: str, user_id: str = "default_user"):
    """Tar bort en registrerad säkerhetsnyckel."""
    deleted = db.delete_security_key(key_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Säkerhetsnyckeln hittades inte.")

    # Uppdatera 2FA status om inga nycklar och ingen TOTP finns kvar
    remaining_keys = db.list_security_keys(user_id)
    settings = db.get_2fa_settings(user_id)
    if not remaining_keys and not settings.get("totp_verified"):
        db.update_2fa_settings(user_id=user_id, is_2fa_enabled=False)

    return {"status": "success", "message": "Säkerhetsnyckeln har raderats."}


# --- WEBAUTHN ENDPOINTS ---


@router.post("/webauthn/register-options")
def webauthn_register_options(request: Request, user_id: str = "default_user"):
    """Genererar PublicKeyCredentialCreationOptions för WebAuthn-registrering."""
    host = request.headers.get("host", "localhost").split(":")[0]
    rp_id = host if host in ("localhost", "127.0.0.1") else "localhost"
    return WebAuthnService.get_registration_options(user_id=user_id, rp_id=rp_id)


@router.post("/webauthn/register-verify")
def webauthn_register_verify(payload: WebAuthnRegisterVerifyRequest, request: Request, user_id: str = "default_user"):
    """Verifierar WebAuthn-registrering och sparar hårdvarunyckeln."""
    client_origin = request.headers.get("origin")
    host = request.headers.get("host", "localhost").split(":")[0]
    rp_id = host if host in ("localhost", "127.0.0.1") else "localhost"

    success, err_msg, backup_codes = WebAuthnService.verify_registration(
        user_id=user_id,
        credential_data=payload.credential,
        key_name=payload.key_name,
        client_origin=client_origin,
        rp_id=rp_id,
    )

    if not success:
        raise HTTPException(status_code=400, detail=err_msg or "WebAuthn-registrering misslyckades.")

    return {
        "status": "success",
        "message": f"Säkerhetsnyckeln '{payload.key_name}' har registrerats.",
        "backup_codes": backup_codes,
    }


@router.post("/webauthn/auth-options")
def webauthn_auth_options(request: Request, user_id: str = "default_user"):
    """Genererar PublicKeyCredentialRequestOptions för WebAuthn-verifiering."""
    host = request.headers.get("host", "localhost").split(":")[0]
    rp_id = host if host in ("localhost", "127.0.0.1") else "localhost"
    return WebAuthnService.get_authentication_options(user_id=user_id, rp_id=rp_id)


@router.post("/webauthn/auth-verify")
def webauthn_auth_verify(payload: WebAuthnAuthVerifyRequest, request: Request, user_id: str = "default_user"):
    """Verifierar WebAuthn-touch och upphöjer sessionen (step-up) i 15 minuter."""
    client_origin = request.headers.get("origin")
    host = request.headers.get("host", "localhost").split(":")[0]
    rp_id = host if host in ("localhost", "127.0.0.1") else "localhost"

    success, err_msg = WebAuthnService.verify_authentication(
        user_id=user_id,
        credential_data=payload.credential,
        client_origin=client_origin,
        rp_id=rp_id,
    )

    if not success:
        raise HTTPException(status_code=400, detail=err_msg or "WebAuthn-verifiering misslyckades.")

    # 15 minuters elevation
    elevated_until = (datetime.now(timezone.utc) + timedelta(seconds=900)).isoformat()
    db.update_2fa_settings(user_id=user_id, elevated_until=elevated_until)

    return {
        "status": "success",
        "message": "Hårdvarunyckel verifierad. Valvet är upplåst i 15 minuter.",
        "is_elevated": True,
        "elevated_until": elevated_until,
    }


# --- TOTP ENDPOINTS ---


@router.post("/totp/generate", response_model=TOTPGenerateResponse)
def totp_generate(user_id: str = "default_user"):
    """Genererar en ny preliminär TOTP-hemlighet, otpauth-URI och SVG-QR-kod."""
    res = TOTPService.generate_secret(user_id=user_id)
    return TOTPGenerateResponse(
        secret=res["secret"],
        otpauth_uri=res["otpauth_uri"],
        qr_code_svg=res["qr_code_svg"],
    )


@router.post("/totp/enable")
def totp_enable(payload: TOTPEnableRequest, user_id: str = "default_user"):
    """Verifierar den preliminära koden och aktiverar TOTP permanent."""
    success, err_msg, backup_codes = TOTPService.enable_totp(user_id=user_id, code=payload.code)
    if not success:
        raise HTTPException(status_code=400, detail=err_msg or "Ogiltig TOTP-kod.")

    return {
        "status": "success",
        "message": "Autentiseringsapp har aktiverats för 2FA.",
        "backup_codes": backup_codes,
    }


@router.post("/totp/disable")
def totp_disable(user_id: str = "default_user"):
    """Avaktiverar TOTP."""
    TOTPService.disable_totp(user_id=user_id)
    return {"status": "success", "message": "Autentiseringsapp har avaktiverats."}


# --- BACKUP CODES ENDPOINTS ---


@router.post("/backup-codes/verify")
def verify_backup_code(payload: BackupCodeVerifyRequest, user_id: str = "default_user"):
    """Verifierar och förbrukar en engångsnödkod (single-use) samt upphöjer sessionen."""
    ok = BackupCodeService.verify_and_redeem_code(user_id=user_id, code=payload.code)
    if not ok:
        raise HTTPException(status_code=400, detail="Ogiltig eller redan förbrukad nödkod.")

    elevated_until = (datetime.now(timezone.utc) + timedelta(seconds=900)).isoformat()
    db.update_2fa_settings(user_id=user_id, elevated_until=elevated_until)

    remaining = len(db.list_unused_backup_codes(user_id))
    return {
        "status": "success",
        "message": f"Nödkod godkänd och förbrukad. {remaining} koder återstår. Valvet är upplåst i 15 minuter.",
        "is_elevated": True,
        "elevated_until": elevated_until,
        "remaining_backup_codes": remaining,
    }


@router.post("/backup-codes/regenerate")
def regenerate_backup_codes(user_id: str = "default_user"):
    """Genererar 8 nya nödkoder och ersätter eventuella gamla oanvända koder."""
    settings = db.get_2fa_settings(user_id)
    if not settings.get("is_2fa_enabled"):
        raise HTTPException(status_code=400, detail="2FA måste vara aktiverat för att generera nödkoder.")

    # Ta bort gamla oanvända koder och generera nya
    codes = BackupCodeService.generate_and_save_backup_codes(user_id=user_id, count=8)
    return {
        "status": "success",
        "message": "8 nya nödkoder har genererats. Spara dem på en säker plats.",
        "backup_codes": codes,
    }


# --- STEP-UP ELEVATION & GENERAL 2FA ---


@router.post("/step-up/verify")
def step_up_verify(payload: StepUpVerifyRequest, request: Request, user_id: str = "default_user"):
    """
    Universell Step-Up-verifiering: tar emot antingen TOTP-kod, WebAuthn-assertion eller nödkod.
    Vid godkännande låses det känsliga läget upp i 15 minuter.
    """
    settings = db.get_2fa_settings(user_id)
    if not settings.get("is_2fa_enabled"):
        return {"status": "success", "message": "2FA är inte aktivt. Ingen elevation krävs.", "is_elevated": True}

    method = payload.method.lower().strip()
    elevated = False

    if method == "totp":
        if not payload.code:
            raise HTTPException(status_code=400, detail="Saknar TOTP-kod.")
        elevated = TOTPService.verify_user_totp(user_id=user_id, code=payload.code)
        if not elevated:
            raise HTTPException(status_code=400, detail="Felaktig eller utgången TOTP-kod.")

    elif method == "webauthn":
        if not payload.credential:
            raise HTTPException(status_code=400, detail="Saknar WebAuthn-autentiseringsdata.")
        client_origin = request.headers.get("origin")
        host = request.headers.get("host", "localhost").split(":")[0]
        rp_id = host if host in ("localhost", "127.0.0.1") else "localhost"
        success, err = WebAuthnService.verify_authentication(
            user_id=user_id,
            credential_data=payload.credential,
            client_origin=client_origin,
            rp_id=rp_id,
        )
        if not success:
            raise HTTPException(status_code=400, detail=err or "WebAuthn-verifiering misslyckades.")
        elevated = True

    elif method == "backup_code":
        if not payload.code:
            raise HTTPException(status_code=400, detail="Saknar nödkod.")
        elevated = BackupCodeService.verify_and_redeem_code(user_id=user_id, code=payload.code)
        if not elevated:
            raise HTTPException(status_code=400, detail="Ogiltig eller redan förbrukad nödkod.")

    else:
        raise HTTPException(status_code=400, detail=f"Okänd metod: {method}. Stöds: 'totp', 'webauthn', 'backup_code'.")

    elevated_until = (datetime.now(timezone.utc) + timedelta(seconds=900)).isoformat()
    db.update_2fa_settings(user_id=user_id, elevated_until=elevated_until)

    return {
        "status": "success",
        "message": "Identitet bekräftad. Valvet är upplåst i 15 minuter.",
        "is_elevated": True,
        "elevated_until": elevated_until,
    }


@router.post("/step-up/toggle-vault")
def toggle_step_up_vault(payload: ToggleStepUpRequest, user_id: str = "default_user"):
    """Slår på eller av krav på 2FA-verifiering (Step-Up) vid åtkomst till API-valvet."""
    updated = db.update_2fa_settings(user_id=user_id, step_up_vault_required=payload.step_up_vault_required)
    msg = (
        "2FA-skydd vid valvåtkomst har aktiverats."
        if payload.step_up_vault_required
        else "2FA-skydd vid valvåtkomst har avaktiverats."
    )
    return {
        "status": "success",
        "message": msg,
        "step_up_vault_required": updated["step_up_vault_required"],
    }


@router.post("/disable")
def disable_all_2fa(user_id: str = "default_user"):
    """
    Stänger av 2FA fullständigt och raderar alla registrerade nycklar och koder.
    Återställer systemet till frivilligt 1-faktorsläge.
    """
    db.reset_2fa(user_id=user_id)
    return {
        "status": "success",
        "message": "Tvåfaktorsautentisering har stängts av helt.",
        "is_2fa_enabled": False,
    }
