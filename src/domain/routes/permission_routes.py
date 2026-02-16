import logging

from fastapi import APIRouter, Depends, Query

from src.base.core.dependencies import (
    get_current_user,
    get_permission_service,
)
from src.base.models.user import User
from src.domain.models.permission_schemas import (
    PermissionAction,
    PermissionCheckResponse,
)
from src.domain.services.permission_service import PermissionService

router = APIRouter(prefix="/permissions", tags=["Permissions"])
logger = logging.getLogger(__name__)


@router.get("/check", response_model=PermissionCheckResponse)
async def check_permission(
    user_id: str = Query(..., description="Entra object ID of the user"),
    agent_id: str = Query(..., description="Agent ID"),
    action: PermissionAction = Query(..., description="Action to check"),
    user: User = Depends(get_current_user),
    service: PermissionService = Depends(get_permission_service),
):
    """Check whether a user can perform an action on an agent.

    Used by the core platform before every agent interaction.
    """
    allowed, role = await service.check_permission(
        user_id=user_id,
        agent_id=agent_id,
        action=action,
        is_superadmin=user.is_superadmin,
    )
    return PermissionCheckResponse(allowed=allowed, role=role)
