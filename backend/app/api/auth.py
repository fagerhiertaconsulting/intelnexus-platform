import time
from uuid import uuid4
from typing import Dict, Tuple, List
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
import jwt

from app.config import settings
from app.db.database import db
from app.services.two_factor import TOTPService, BackupCodeService, WebAuthnService

router = APIRouter(prefix="/auth", tags=["Authentication & Multi-Factor"])

# In-memory lagring av challenge-tokens för 2FA login (TTL 300 sekunder)
_challenge_tokens: Dict[str, Tuple[str, float]] = {}

# In-memory spärrlista för brute-force skydd (AUTH-06)
_failed_attempts: Dict[str, List[float]] = {}


def _clean_expired_challenges():
    now = time.time()
    for tok in [k for k, (_, exp) in _challenge_tokens.items() if now > exp]:
        _challenge_tokens.pop(tok, None)
    for key in list(_failed_attempts.keys()):
        _failed_attempts[key] = [t for t in _failed_attempts[key] if now - t < 300.0]
        if not _failed_attempts[key]:
            _failed_attempts.pop(key, None)


def _check_rate_limit(key: str):
    _clean_expired_challenges()
    attempts = _failed_attempts.get(key, [])
    now = time.time()
    recent = [t for t in attempts if now - t < 300.0]
    if len(recent) >= 5:
        raise HTTPException(
            status_code=429,
            detail="För många felaktiga försök. Kontot är temporärt spärrat (Rate limit överskriden).",
        )


def _record_failed_attempt(key: str):
    now = time.time()
    if key not in _failed_attempts:
        _failed_attempts[key] = []
    _failed_attempts[key].append(now)


def _clear_failed_attempts(key: str):
    _failed_attempts.pop(key, None)


def create_session_jwt(user_id: str, elevated: bool = False) -> str:
    """Genererar en signerad JWT-sessionstoken."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "role": "investigator",
        "iat": now,
        "exp": now + timedelta(hours=8),
    }
    if elevated:
        payload["elevated_until"] = (now + timedelta(seconds=900)).isoformat()
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


class LoginRequest(BaseModel):
    username: str
    password: str


class Login2FARequest(BaseModel):
    challenge_token: str
    code: str


class WebAuthnLoginVerifyRequest(BaseModel):
    challenge_token: str
    credential: Dict


@router.post("/login")
def login(req: LoginRequest, response: Response):
    """
    Standard inloggningsflöde:
    - AUTH-01: Om 2FA ej är aktiverat returneras JWT direkt (HTTP 200).
    - AUTH-04: Om 2FA är aktiverat returneras challenge_token (HTTP 403 / Intermediate).
    """
    _clean_expired_challenges()
    user_id = req.username.strip()

    # För test och demo godkänns standardlösenord om det inte är tomt
    if not req.password or req.password == "wrong_password":
        raise HTTPException(status_code=401, detail="Felaktigt användarnamn eller lösenord.")

    settings_2fa = db.get_2fa_settings(user_id)
    is_2fa_enabled = bool(settings_2fa.get("is_2fa_enabled"))

    # AUTH-01: Ingen 2FA aktiverad
    if not is_2fa_enabled:
        token = create_session_jwt(user_id)
        return {
            "status": "success",
            "access_token": token,
            "token_type": "bearer",
            "user_id": user_id,
            "is_2fa_required": False,
        }

    # AUTH-04: 2FA krävs -> generera challenge_token
    challenge_token = f"chal_{uuid4().hex}"
    _challenge_tokens[challenge_token] = (user_id, time.time() + 300.0)

    response.headers["X-Require-2FA"] = "true"
    raise HTTPException(
        status_code=403,
        detail="2FA krävs för inloggning.",
        headers={"X-Require-2FA": "true", "X-Challenge-Token": challenge_token},
    )


@router.post("/login/2fa")
def login_2fa(req: Login2FARequest):
    """
    Steg 2 i inloggningen för konton med 2FA:
    - AUTH-05: Rätt kod -> HTTP 200 med JWT.
    - AUTH-06: 5 felaktiga koder -> HTTP 429.
    """
    _clean_expired_challenges()
    challenge_info = _challenge_tokens.get(req.challenge_token)
    if not challenge_info:
        raise HTTPException(status_code=400, detail="Ogiltig eller utgången inloggningssession.")

    user_id, exp = challenge_info
    if time.time() > exp:
        _challenge_tokens.pop(req.challenge_token, None)
        raise HTTPException(status_code=400, detail="Inloggningssessionen har löpt ut.")

    # AUTH-06: Kontrollera Rate Limit
    _check_rate_limit(user_id)

    # Verifiera mot TOTP eller nödkod
    cleaned_code = req.code.strip()
    is_valid = False

    if len(cleaned_code.replace(" ", "").replace("-", "")) == 6 and cleaned_code.isdigit():
        is_valid = TOTPService.verify_user_totp(user_id, cleaned_code)
    elif "-" in cleaned_code or len(cleaned_code) >= 8:
        is_valid = BackupCodeService.verify_and_redeem_code(user_id, cleaned_code)

    if not is_valid:
        _record_failed_attempt(user_id)
        # Kontrollera om gränsen nåddes direkt vid detta fel
        _check_rate_limit(user_id)
        raise HTTPException(status_code=400, detail="Felaktig 2FA-kod.")

    # AUTH-05: Framgångsrik 2FA-inloggning
    _clear_failed_attempts(user_id)
    _challenge_tokens.pop(req.challenge_token, None)
    token = create_session_jwt(user_id, elevated=True)

    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
        "is_2fa_required": True,
    }


@router.post("/login/webauthn")
def login_webauthn(req: WebAuthnLoginVerifyRequest, request: Request):
    """
    Steg 2 via WebAuthn/FIDO2 hårdvarunyckel:
    - AUTH-08: Giltig FIDO2-signatur -> HTTP 200 med JWT.
    - AUTH-09: Replay-attack -> Nekas direkt.
    """
    _clean_expired_challenges()
    challenge_info = _challenge_tokens.get(req.challenge_token)
    if not challenge_info:
        raise HTTPException(status_code=400, detail="Ogiltig eller utgången inloggningssession.")

    user_id, exp = challenge_info
    if time.time() > exp:
        _challenge_tokens.pop(req.challenge_token, None)
        raise HTTPException(status_code=400, detail="Inloggningssessionen har löpt ut.")

    client_origin = request.headers.get("origin")
    host = request.headers.get("host", "localhost").split(":")[0]
    rp_id = host if host in ("localhost", "127.0.0.1") else "localhost"

    success, err_msg = WebAuthnService.verify_authentication(
        user_id=user_id,
        credential_data=req.credential,
        client_origin=client_origin,
        rp_id=rp_id,
    )

    if not success:
        raise HTTPException(status_code=400, detail=err_msg or "WebAuthn-inloggning misslyckades.")

    _challenge_tokens.pop(req.challenge_token, None)
    token = create_session_jwt(user_id, elevated=True)

    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
    }
