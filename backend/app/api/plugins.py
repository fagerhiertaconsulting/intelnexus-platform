from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.plugins import plugin_manager, EntityInput, TransformResult
from app.core.vault import credential_vault

router = APIRouter(prefix="/plugins", tags=["Plugin SDK & Transforms"])


class ExecutePluginRequest(BaseModel):
    plugin_slug: str
    target: EntityInput
    proxy_url: Optional[str] = None
    force_refresh: bool = False


@router.get("", response_model=List[Dict[str, Any]])
def list_plugins():
    """Listar samtliga installerade och tillgängliga OSINT-plugins."""
    return plugin_manager.list_plugins()


@router.get("/for-type/{entity_type}", response_model=List[Dict[str, Any]])
def get_plugins_for_entity_type(entity_type: str):
    """Hämtar plugins som kan köras mot en given entitetstyp."""
    plugins = plugin_manager.get_plugins_for_input(entity_type)
    return [
        {
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "is_commercial": p.is_commercial,
            "cost_per_query_estimate": p.cost_per_query_estimate,
            "supported_inputs": p.supported_inputs,
            "output_entities": p.output_entities,
        }
        for p in plugins
    ]


@router.post("/execute", response_model=TransformResult)
async def execute_plugin(req: ExecutePluginRequest):
    """
    Kör ett plugin mot ett mål. Hämtar automatiskt API-nyckel ur valvet
    om pluginet kräver det.
    """
    plugin = plugin_manager.get_plugin(req.plugin_slug)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{req.plugin_slug}' hittades inte.")

    api_key = None
    if plugin.required_vault_key:
        api_key = credential_vault.get_key(plugin.required_vault_key)
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail=f"Kräver API-nyckel '{plugin.required_vault_key}' i det krypterade valvet.",
            )

    try:
        result = await plugin.execute(
            target=req.target,
            api_key=api_key,
            proxy_url=req.proxy_url,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plugin-exekvering misslyckades: {str(e)}")
