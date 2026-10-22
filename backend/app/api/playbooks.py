from typing import Any, Dict, Optional
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from app.core.playbooks import playbook_orchestrator
from app.core.metadata_stripper import metadata_stripper
from app.db.object_store import object_store
from app.models.evidence import EvidenceItem
from app.db.database import db

router = APIRouter(prefix="/playbooks", tags=["Playbooks & Orchestration"])


class DatingVerificationRequest(BaseModel):
    case_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    image_url: Optional[str] = None
    story: Optional[str] = None


@router.post("/dating-verification")
async def run_dating_verification_playbook(req: DatingVerificationRequest):
    """
    Kör komplett automatiserad säkerhetskoll för en privatperson (dejt/kontakt):
    Omvänd bildsökning, VoIP/burner-detektering, dataläckor och sol-och-vår-varningslistor.
    """
    try:
        result = await playbook_orchestrator.run_dating_verification(
            case_id=req.case_id,
            name=req.name,
            phone=req.phone,
            email=req.email,
            image_url=req.image_url,
            story=req.story,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kunde inte köra verifieringsguiden: {str(e)}")


@router.post("/whistleblower-sanitize")
async def sanitize_whistleblower_media(
    case_id: str,
    file: UploadFile = File(...),
):
    """
    Källskyddsflöde: Tar emot en bild eller dokument, raderar all EXIF-, GPS- och enhetsmetadata
    samt sparar både original och sanerad kopia i bevisarkivet med SHA-256.
    """
    try:
        content = await file.read()
        clean_bytes, hashes = metadata_stripper.strip_image_metadata(content)

        clean_filename = f"sanitized_{file.filename}"
        rel_path, clean_sha, size = object_store.store_bytes(
            case_id=case_id,
            filename=clean_filename,
            data=clean_bytes,
            subfolder="sanitized_vault",
        )

        evidence = EvidenceItem(
            case_id=case_id,
            title=f"Sanitized Whistleblower Document: {file.filename}",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type=file.content_type or "image/jpeg",
            sha256=clean_sha,
            source_url="whistleblower://sanitizer",
            collector_plugin="metadata_stripper",
            metadata=hashes,
        )
        db.save_evidence(evidence)

        return {
            "status": "success",
            "original_filename": file.filename,
            "sanitized_filename": clean_filename,
            "original_sha256": hashes["original_sha256"],
            "sanitized_sha256": clean_sha,
            "evidence_id": evidence.id,
            "message": "All EXIF-, GPS- och enhetsmetadata har raderats permanent.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid metadatarensning: {str(e)}")
