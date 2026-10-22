from typing import List
from fastapi import APIRouter, HTTPException
from app.core.roles import role_manager, WorkspaceRoleConfig

router = APIRouter(prefix="/roles", tags=["Workspace Profiles"])


@router.get("", response_model=List[WorkspaceRoleConfig])
def list_workspace_roles():
    """Listar alla tillgängliga utredningsroller och deras konfigurerade widgets och playbooks."""
    return role_manager.list_roles()


@router.get("/{role_id}", response_model=WorkspaceRoleConfig)
def get_workspace_role(role_id: str):
    """Hämtar layout- och widgetkonfiguration för en specifik roll."""
    role = role_manager.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rollen hittades inte")
    return role
