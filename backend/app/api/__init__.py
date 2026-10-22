from fastapi import APIRouter
from .cases import router as cases_router
from .entities import router as entities_router
from .transforms import router as transforms_router
from .graph import router as graph_router
from .evidence import router as evidence_router
from .analysis import router as analysis_router
from .vault import router as vault_router
from .roles import router as roles_router
from .playbooks import router as playbooks_router

api_router = APIRouter(prefix="/api")
api_router.include_router(cases_router)
api_router.include_router(entities_router)
api_router.include_router(transforms_router)
api_router.include_router(graph_router)
api_router.include_router(evidence_router)
api_router.include_router(analysis_router)
api_router.include_router(vault_router)
api_router.include_router(roles_router)
api_router.include_router(playbooks_router)

__all__ = ["api_router"]
