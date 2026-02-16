import logging

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from src.base.core.dependencies import (
    get_admin_service,
    get_permission_service,
)
from src.base.models.user import User
from src.domain.auth.authorization import require_superadmin
from src.domain.models.admin_schemas import (
    AdminAgentListResponse,
    AdminAgentResponse,
    AdminGroupListResponse,
    AdminGroupResponse,
    BulkUpdateAgentGroupsRequest,
    BulkUpdateAgentGroupsResponse,
)
from src.domain.services.admin_service import AdminService
from src.domain.services.permission_service import PermissionService

router = APIRouter(prefix="/admin", tags=["Superadmin"])
logger = logging.getLogger(__name__)


@router.get("/agents", response_model=AdminAgentListResponse)
async def list_all_agents(
    user: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
):
    """List all agents with their group assignments (superadmin only)."""
    agents = await service.list_all_agents()
    return AdminAgentListResponse(agents=[AdminAgentResponse(**a) for a in agents])


@router.get("/groups", response_model=AdminGroupListResponse)
async def list_all_groups(
    user: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
):
    """List all groups with member counts (superadmin only)."""
    groups = await service.list_all_groups_with_counts()
    return AdminGroupListResponse(groups=[AdminGroupResponse(**g) for g in groups])


@router.put(
    "/agents/{agent_id}/groups",
    response_model=BulkUpdateAgentGroupsResponse,
)
async def bulk_update_agent_groups(
    agent_id: str,
    body: BulkUpdateAgentGroupsRequest,
    user: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Bulk update group assignments for an agent (superadmin only)."""
    agent_oid = PydanticObjectId(agent_id)
    group_oids = [PydanticObjectId(gid) for gid in body.group_ids]
    try:
        result = await service.bulk_update_agent_groups(
            agent_id=agent_oid,
            group_ids=group_oids,
            updated_by=user.id,
        )
    except ValueError as e:
        code = str(e)
        if code == "agent_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            ) from None
        if code == "group_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more groups not found",
            ) from None
        raise

    await permission_service.invalidate_agent_permissions(agent_id)

    return BulkUpdateAgentGroupsResponse(agent=AdminAgentResponse(**result))
