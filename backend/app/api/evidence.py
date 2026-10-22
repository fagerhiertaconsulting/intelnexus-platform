from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from app.db.database import db
from app.db.object_store import object_store
from app.evidence.custody_manager import custody_manager
from app.models.evidence import EvidenceItem

router = APIRouter(prefix="/evidence", tags=["Evidence & Chain of Custody"])


class WebSnapshotRequest(BaseModel):
    url: str
    case_id: str
    title: Optional[str] = None


@router.get("", response_model=List[EvidenceItem])
def list_evidence(case_id: Optional[str] = None):
    return db.list_evidence(case_id=case_id)


@router.get("/{evidence_id}", response_model=EvidenceItem)
def get_evidence(evidence_id: str):
    ev = db.get_evidence(evidence_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Bevispost hittades inte")
    return ev


@router.get("/{evidence_id}/content")
def get_evidence_content(evidence_id: str):
    """Hämtar råinnehållet i en bevisfil och verifierar dess SHA-256 kontrollsumma."""
    ev = db.get_evidence(evidence_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Bevispost hittades inte")
    try:
        raw_bytes = object_store.read_bytes(ev.file_path)
        return Response(content=raw_bytes, media_type=ev.mime_type)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Bevisfilen saknas på lagringsmediet")


@router.post("/snapshot", response_model=EvidenceItem)
async def create_web_snapshot(req: WebSnapshotRequest):
    """Arkiverar en webbsida med tidsstämpel, HTTP-metadata och SHA-256 hashning."""
    try:
        evidence = await custody_manager.capture_web_snapshot(
            url=req.url,
            case_id=req.case_id,
            title=req.title,
        )
        return evidence
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kunde inte arkivera webbsidan: {str(e)}")


@router.get("/audit/{case_id}")
def audit_chain_of_custody(case_id: str):
    """
    Kör fullständig integritetsrevision av beviskedjan för ett ärende.
    Verifierar att alla filer på disk exakt matchar sina registrerade SHA-256 kontrollsummor.
    """
    return custody_manager.verify_case_custody(case_id)
