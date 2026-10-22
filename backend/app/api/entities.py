from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.db.database import db
from app.db.graph_store import graph_store
from app.models.entity import Entity, EntityCreateRequest, ProvenanceRecord
from app.models.relationship import Relationship, RelationshipCreateRequest
from app.resolution.entity_resolver import entity_resolver, MatchCandidate

router = APIRouter(prefix="/entities", tags=["Entities & Relationships"])


@router.post("", response_model=Entity)
def create_entity(req: EntityCreateRequest):
    provenance = []
    if req.provenance_source:
        provenance.append(
            ProvenanceRecord(
                source_url=req.provenance_source,
                sha256="manual_seed",
                collector_plugin=req.provenance_plugin or "analyst_manual_entry",
                note="Manuellt inmatad seed-nod av utredare",
            )
        )

    extra_kwargs: Dict[str, Any] = {}
    if req.source_reliability is not None:
        extra_kwargs["source_reliability"] = req.source_reliability
    if req.info_credibility is not None:
        extra_kwargs["info_credibility"] = req.info_credibility

    entity = Entity(
        type=req.type,
        name=req.name.strip(),
        aliases=req.aliases,
        attributes=req.attributes,
        provenance=provenance,
        confidence_score=req.confidence_score,
        case_id=req.case_id,
        **extra_kwargs,
    )
    saved = db.save_entity(entity)
    if req.case_id:
        graph_store.add_entity_to_graph(req.case_id, saved)
    return saved


@router.get("", response_model=List[Entity])
def list_entities(case_id: Optional[str] = None, entity_type: Optional[str] = None):
    return db.list_entities(case_id=case_id, entity_type=entity_type)


# --- RELATIONSHIPS ---


@router.post("/relationships", response_model=Relationship)
def create_relationship(req: RelationshipCreateRequest):
    source = db.get_entity(req.source_id)
    target = db.get_entity(req.target_id)
    if not source or not target:
        raise HTTPException(status_code=400, detail="Både käll- och målentitet måste existera.")

    case_id = req.case_id or source.case_id or target.case_id
    provenance = []
    if req.provenance_source:
        provenance.append(
            ProvenanceRecord(
                source_url=req.provenance_source,
                sha256="manual_link",
                collector_plugin=req.provenance_plugin or "analyst_manual_link",
                note="Manuell relation kopplad av utredare",
            )
        )

    rel = Relationship(
        source_id=req.source_id,
        target_id=req.target_id,
        relation_type=req.relation_type,
        attributes=req.attributes,
        provenance=provenance,
        confidence_score=req.confidence_score,
        case_id=case_id,
    )
    saved = db.save_relationship(rel)
    if case_id:
        graph_store.add_relationship_to_graph(case_id, saved)
    return saved


@router.get("/relationships", response_model=List[Relationship])
def list_relationships(case_id: Optional[str] = None):
    return db.list_relationships(case_id=case_id)


@router.delete("/relationships/{rel_id}")
def delete_relationship(rel_id: str):
    rel = db.get_relationship(rel_id)
    if not rel:
        raise HTTPException(status_code=404, detail="Relation hittades inte")
    db.delete_relationship(rel_id)
    if rel.case_id:
        graph_store.reload_case_graph(rel.case_id)
    return {"message": f"Relation {rel_id} raderad."}


# --- ENTITY RESOLUTION ---


class MergeRequest(BaseModel):
    primary_id: str
    secondary_id: str
    case_id: str


@router.get("/resolution/matches/{case_id}", response_model=List[MatchCandidate])
def find_resolution_matches(case_id: str, threshold: float = Query(0.85, ge=0.5, le=1.0)):
    return entity_resolver.find_matches(case_id=case_id, probabilistic_threshold=threshold)


@router.post("/resolution/merge", response_model=Entity)
def merge_entities_endpoint(req: MergeRequest):
    try:
        return entity_resolver.merge_entities(
            primary_id=req.primary_id, secondary_id=req.secondary_id, case_id=req.case_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- SPECIFIC ENTITY BY ID ---


@router.get("/{entity_id}", response_model=Entity)
def get_entity(entity_id: str):
    entity = db.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entitet hittades inte")
    return entity


@router.delete("/{entity_id}")
def delete_entity(entity_id: str):
    entity = db.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entitet hittades inte")
    db.delete_entity(entity_id)
    if entity.case_id:
        graph_store.reload_case_graph(entity.case_id)
    return {"message": f"Entitet {entity_id} raderad."}
