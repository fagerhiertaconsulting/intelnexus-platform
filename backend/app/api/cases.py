from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from app.db.database import db
from app.models.case import Case, CaseCreateRequest, CaseUpdateRequest
from app.api.two_factor import require_elevated_session

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=Case)
def create_case(req: CaseCreateRequest, x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if x_user_id and req.investigator in ("Analyst", "default_user", ""):
        req.investigator = x_user_id
    return db.create_case(req)


@router.get("", response_model=List[Case])
def list_cases(x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    return db.list_cases(investigator=x_user_id)


@router.get("/{case_id}", response_model=Case)
def get_case(case_id: str, x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    case = db.get_case(case_id, investigator=x_user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Ärende hittades inte")
    return case


@router.patch("/{case_id}", response_model=Case)
def update_case(case_id: str, req: CaseUpdateRequest, x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    updated = db.update_case(case_id, req, investigator=x_user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Ärende hittades inte")
    return updated


@router.delete("/{case_id}", dependencies=[Depends(require_elevated_session)])
def delete_case(case_id: str, x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    deleted = db.delete_case(case_id, investigator=x_user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ärende hittades inte")
    return {"message": f"Ärende {case_id} och alla kopplade entiteter har raderats."}


@router.get("/{case_id}/stats")
def get_case_stats(case_id: str) -> Dict[str, Any]:
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Ärende hittades inte")

    entities = db.list_entities(case_id=case_id)
    relationships = db.list_relationships(case_id=case_id)
    evidence = db.list_evidence(case_id=case_id)

    type_counts: Dict[str, int] = {}
    sanctions_hits = 0
    for e in entities:
        t = e.type.value if hasattr(e.type, "value") else str(e.type)
        type_counts[t] = type_counts.get(t, 0) + 1
        if e.attributes.get("sanctioned") is True:
            sanctions_hits += 1

    return {
        "case_id": case_id,
        "title": case.title,
        "entity_count": len(entities),
        "relationship_count": len(relationships),
        "evidence_count": len(evidence),
        "sanctions_hits": sanctions_hits,
        "entity_types": type_counts,
    }
