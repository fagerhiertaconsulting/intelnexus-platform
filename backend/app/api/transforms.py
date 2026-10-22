from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.db.database import db
from app.transforms.registry import registry
from app.transforms.base import TransformResult

router = APIRouter(prefix="/transforms", tags=["Transforms Engine"])


class ExecuteTransformRequest(BaseModel):
    transform_name: str
    entity_id: str
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ExecuteBatchTransformsRequest(BaseModel):
    transform_names: List[str]
    entity_id: str
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


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

    results = await registry.execute_parallel(req.transform_names, entity, req.options)
    return results
