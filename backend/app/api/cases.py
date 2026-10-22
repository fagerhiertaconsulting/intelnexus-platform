from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from app.db.database import db
from app.db.graph_store import graph_store
from app.models.case import Case, CaseCreateRequest, CaseUpdateRequest

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=Case)
def create_case(req: CaseCreateRequest):
    return db.create_case(req)


@router.get("", response_model=List[Case])
def list_cases():
    return db.list_cases()


@router.get("/{case_id}", response_model=Case)
def get_case(case_id: str):
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Ärende hittades inte")
    return case


@router.patch("/{case_id}", response_model=Case)
def update_case(case_id: str, req: CaseUpdateRequest):
    updated = db.update_case(case_id, req)
    if not updated:
        raise HTTPException(status_code=404, detail="Ärende hittades inte")
    return updated


@router.delete("/{case_id}")
def delete_case(case_id: str):
    deleted = db.delete_case(case_id)
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
