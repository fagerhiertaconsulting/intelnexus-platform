from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class User2FASettingsResponse(BaseModel):
    user_id: str = "default_user"
    is_2fa_enabled: bool = False
    totp_verified: bool = False
    step_up_vault_required: bool = False
    elevated_until: Optional[str] = None
    is_elevated: bool = False
    has_security_keys: bool = False
    security_keys_count: int = 0
    unused_backup_codes_count: int = 0


class SecurityKeyInfo(BaseModel):
    id: str
    user_id: str
    key_name: str
    credential_id: str
    sign_count: int
    transports: List[str] = []
    aaguid: Optional[str] = None
    created_at: str
    last_used_at: Optional[str] = None


class TOTPGenerateResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_code_svg: str


class TOTPEnableRequest(BaseModel):
    code: str


class WebAuthnRegisterVerifyRequest(BaseModel):
    key_name: str = "Säkerhetsnyckel"
    credential: Dict[str, Any]


class WebAuthnAuthVerifyRequest(BaseModel):
    credential: Dict[str, Any]


class BackupCodeVerifyRequest(BaseModel):
    code: str


class StepUpVerifyRequest(BaseModel):
    method: str = Field(..., description="totp | webauthn | backup_code")
    code: Optional[str] = None
    credential: Optional[Dict[str, Any]] = None


class ToggleStepUpRequest(BaseModel):
    step_up_vault_required: bool
