from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.vault import credential_vault
from app.api.two_factor import require_elevated_session

router = APIRouter(prefix="/vault", tags=["Credential Vault (BYOAK)"])


class StoreKeyRequest(BaseModel):
    key_name: str
    api_key: str
    label: Optional[str] = None


@router.get("", dependencies=[Depends(require_elevated_session)])
def list_vault_keys():
    """Listar alla kända API-tjänster i valvet och deras krypteringsstatus."""
    return credential_vault.list_configured_keys()


@router.post("", dependencies=[Depends(require_elevated_session)])
def store_vault_key(req: StoreKeyRequest):
    """Sparar och krypterar en användardefinierad API-nyckel med AES-256-GCM."""
    if not req.key_name or not req.api_key.strip():
        raise HTTPException(status_code=400, detail="Ogiltigt nyckelnamn eller tomt API-värde.")

    credential_vault.set_key(
        key_name=req.key_name.strip(),
        secret_value=req.api_key.strip(),
        label=req.label,
    )
    return {
        "status": "success",
        "message": f"API-nyckeln '{req.key_name}' har krypterats och lagrats säkert i det lokala valvet.",
    }


@router.delete("/{key_name}", dependencies=[Depends(require_elevated_session)])
def delete_vault_key(key_name: str):
    """Tar bort en API-nyckel från valvet."""
    deleted = credential_vault.delete_key(key_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Nyckeln fanns inte i valvet.")
    return {"status": "success", "message": f"API-nyckeln '{key_name}' har raderats."}


@router.post("/test/{key_name}", dependencies=[Depends(require_elevated_session)])
def test_vault_key(key_name: str):
    """Verifierar att en API-nyckel kan dekrypteras korrekt och har giltigt format."""
    val = credential_vault.get_key(key_name)
    if not val:
        raise HTTPException(status_code=404, detail="Nyckeln är inte konfigurerad.")
    return {
        "key_name": key_name,
        "valid_format": len(val.strip()) > 3,
        "length": len(val),
        "status": "OPERATIONAL",
    }
