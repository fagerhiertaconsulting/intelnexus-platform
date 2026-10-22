from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.core.finops.cost_estimator import DryRunEstimate, cost_estimator
from app.db.database import db
from app.plugins.base import EntityInput
from app.transforms.registry import registry
from app.transforms.base import TransformResult

router = APIRouter(prefix="/transforms", tags=["Transforms Engine"])


class DryRunRequest(BaseModel):
    plugin_slug: str
    targets: List[EntityInput]
    force_refresh: bool = False


class ExecuteTransformRequest(BaseModel):
    transform_name: str
    entity_id: str
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ExecuteBatchTransformsRequest(BaseModel):
    transform_names: List[str]
    entity_id: str
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


@router.post("/dry-run", response_model=DryRunEstimate)
def dry_run_cost_estimation(req: DryRunRequest):
    """
    Beräknar förhandsgranskning (Dry-Run) för API-kvoter och kostnader
    före körning av transformeringar mot externa API:er.
    """
    try:
        return cost_estimator.estimate(
            plugin_slug=req.plugin_slug,
            targets=req.targets,
            force_refresh=req.force_refresh,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("")
def list_available_transforms():
    """Listar alla registrerade transforms och vilka entitetstyper de stödjer."""
    return registry.list_transforms()


@router.get("/for-entity/{entity_id}")
def get_transforms_for_entity(entity_id: str):
    """Hämtar de transforms som kan köras mot en given nod."""
    entity = db.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entitet hittades inte")
    return {
        "entity_id": entity.id,
        "name": entity.name,
        "type": entity.type.value if hasattr(entity.type, "value") else str(entity.type),
        "available_transforms": registry.get_supported_transforms_for_entity(entity),
    }


@router.post("/execute", response_model=TransformResult)
async def execute_transform(req: ExecuteTransformRequest):
    """Kör en specificerad transform asynkront mot en entitet."""
    entity = db.get_entity(req.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entitet hittades inte")

    result = await registry.execute_transform(req.transform_name, entity, req.options)
    return result


@router.post("/execute-batch", response_model=List[TransformResult])
async def execute_batch_transforms(req: ExecuteBatchTransformsRequest):
    """Kör flera transforms parallellt mot samma entitet."""
    entity = db.get_entity(req.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entitet hittades inte")

    results = []
    for t_name in req.transform_names:
        res = await registry.execute_transform(t_name, entity, req.options)
        results.append(res)
    return results


class FetchUrlRequest(BaseModel):
    url: str


@router.post("/fetch-url")
def fetch_target_url(req: FetchUrlRequest):
    """Validerar måladress mot SSRF-blocklistan och avvisar interna/molnmetadata-destinationer."""
    from app.core.ssrf_protector import validate_target_url

    safe_url = validate_target_url(req.url)
    return {"status": "ALLOWED", "url": safe_url}
