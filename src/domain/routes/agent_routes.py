import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.base.core.dependencies import (
    get_agent_service,
    get_current_user,
    get_db_session,
    get_permission_service,
)
from src.base.models.user import User
from src.domain.auth.authorization import require_group_admin
from src.domain.models.agent_schemas import (
    AgentListResponse,
    AgentResponse,
    AssignAgentToGroupRequest,
    RegisterAgentRequest,
)
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group_membership import GroupMembership
from src.domain.models.group_schemas import GroupListResponse, GroupResponse
from src.domain.services.agent_service import AgentService
from src.domain.services.permission_service import PermissionService

router = APIRouter(tags=["Agent Management"])
logger = logging.getLogger(__name__)

ERROR_MAP = {
    "group_not_found": (status.HTTP_404_NOT_FOUND, "Group not found"),
    "agent_not_found": (status.HTTP_404_NOT_FOUND, "Agent not found"),
    "assignment_not_found": (
        status.HTTP_404_NOT_FOUND,
        "Agent is not assigned to this group",
    ),
    "duplicate_agent": (
        status.HTTP_409_CONFLICT,
        "An agent with this external ID already exists",
    ),
    "duplicate_assignment": (
        status.HTTP_409_CONFLICT,
        "Agent is already assigned to this group",
    ),
}


def _handle_service_error(e: ValueError) -> None:
    """Map service ValueError codes to HTTP exceptions."""
    code = str(e)
    if code in ERROR_MAP:
        status_code, detail = ERROR_MAP[code]
        raise HTTPException(status_code=status_code, detail=detail)
    raise


@router.post(
    "/agents", status_code=status.HTTP_201_CREATED, response_model=AgentResponse
)
async def register_agent(
    body: RegisterAgentRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    service: AgentService = Depends(get_agent_service),
):
    """Register a new agent and assign it to a group.

    The caller must be an admin of the target group or a superadmin.
    """
    # Authorize: user must be admin of the target group (or superadmin)
    if not user.is_superadmin:
        result = await session.execute(
            select(GroupMembership).where(
                GroupMembership.entra_object_id == user.id,
                GroupMembership.group_id == body.group_id,
                GroupMembership.role == GroupRole.ADMIN,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Group admin access required",
            )

    try:
        agent = await service.register_agent(
            session,
            agent_external_id=body.agent_external_id,
            name=body.name,
            group_id=body.group_id,
            created_by=user.id,
        )
    except ValueError as e:
        _handle_service_error(e)

    return AgentResponse.model_validate(agent)


@router.post(
    "/groups/{group_id}/agents",
    status_code=status.HTTP_201_CREATED,
    response_model=AgentResponse,
)
async def assign_agent_to_group(
    group_id: int,
    body: AssignAgentToGroupRequest,
    user: User = Depends(require_group_admin()),
    session: AsyncSession = Depends(get_db_session),
    service: AgentService = Depends(get_agent_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Assign an existing agent to an additional group (group admin or superadmin)."""
    try:
        await service.assign_agent_to_group(
            session,
            group_id=group_id,
            agent_id=body.agent_id,
            added_by=user.id,
        )
    except ValueError as e:
        _handle_service_error(e)

    await permission_service.invalidate_agent_permissions(body.agent_id)

    # Return the agent details
    agents = await service.list_agents_in_group(session, group_id)
    for a in agents:
        if a.id == body.agent_id:
            return AgentResponse.model_validate(a)


@router.delete(
    "/groups/{group_id}/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_agent_from_group(
    group_id: int,
    agent_id: int,
    user: User = Depends(require_group_admin()),
    session: AsyncSession = Depends(get_db_session),
    service: AgentService = Depends(get_agent_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Remove an agent from a group (group admin or superadmin)."""
    try:
        await service.remove_agent_from_group(
            session, group_id=group_id, agent_id=agent_id
        )
    except ValueError as e:
        _handle_service_error(e)

    await permission_service.invalidate_agent_permissions(agent_id)


@router.get("/groups/{group_id}/agents", response_model=AgentListResponse)
async def list_agents_in_group(
    group_id: int,
    user: User = Depends(require_group_admin()),
    session: AsyncSession = Depends(get_db_session),
    service: AgentService = Depends(get_agent_service),
):
    """List agents assigned to a group (group admin or superadmin)."""
    try:
        agents = await service.list_agents_in_group(session, group_id)
    except ValueError as e:
        _handle_service_error(e)

    return AgentListResponse(agents=[AgentResponse.model_validate(a) for a in agents])


@router.get("/users/{entra_object_id}/admin-groups", response_model=GroupListResponse)
async def get_admin_groups(
    entra_object_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    service: AgentService = Depends(get_agent_service),
):
    """Return groups where the specified user is admin.

    Used by the core platform to populate the group selector on agent creation.
    Users can query their own admin groups; superadmins can query any user's.
    """
    if not user.is_superadmin and user.id != entra_object_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view another user's admin groups",
        )

    groups = await service.get_admin_groups(session, entra_object_id)
    return GroupListResponse(groups=[GroupResponse.model_validate(g) for g in groups])
