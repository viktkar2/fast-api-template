import logging

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from src.base.core.dependencies import (
    get_agent_service,
    get_current_user,
    get_permission_service,
)
from src.base.models.user import User
from src.domain.auth.authorization import require_group_admin
from src.domain.models.agent_schemas import (
    AgentListResponse,
    AgentResponse,
    AssignAgentToGroupRequest,
    RegisterAgentRequest,
    UserAgentListResponse,
    UserAgentResponse,
)
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group_membership import GroupMembershipDocument
from src.domain.models.group_schemas import GroupListResponse, GroupResponse
from src.domain.services.agent_service import AgentService
from src.domain.services.permission_service import PermissionService

router = APIRouter(tags=["Agent Management"])
logger = logging.getLogger(__name__)

ERROR_MAP = {
    "group_not_found": (status.HTTP_404_NOT_FOUND, "Group not found"),
    "agent_not_found": (status.HTTP_404_NOT_FOUND, "Agent not found"),
    "user_not_found": (status.HTTP_404_NOT_FOUND, "User not found"),
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
    service: AgentService = Depends(get_agent_service),
):
    """Register a new agent and assign it to a group.

    The caller must be an admin of the target group or a superadmin.
    """
    group_oid = PydanticObjectId(body.group_id)

    # Authorize: user must be admin of the target group (or superadmin)
    if not user.is_superadmin:
        membership = await GroupMembershipDocument.find_one(
            GroupMembershipDocument.entra_object_id == user.id,
            GroupMembershipDocument.group_id == group_oid,
            GroupMembershipDocument.role == GroupRole.ADMIN,
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Group admin access required",
            )

    try:
        agent = await service.register_agent(
            agent_external_id=body.agent_external_id,
            name=body.name,
            group_id=group_oid,
            created_by=user.id,
        )
    except ValueError as e:
        _handle_service_error(e)

    return AgentResponse.model_validate(agent, from_attributes=True)


@router.post(
    "/groups/{group_id}/agents",
    status_code=status.HTTP_201_CREATED,
    response_model=AgentResponse,
)
async def assign_agent_to_group(
    group_id: str,
    body: AssignAgentToGroupRequest,
    user: User = Depends(require_group_admin()),
    service: AgentService = Depends(get_agent_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Assign an existing agent to an additional group (group admin or superadmin)."""
    group_oid = PydanticObjectId(group_id)
    agent_oid = PydanticObjectId(body.agent_id)
    try:
        await service.assign_agent_to_group(
            group_id=group_oid,
            agent_id=agent_oid,
            added_by=user.id,
        )
    except ValueError as e:
        _handle_service_error(e)

    await permission_service.invalidate_agent_permissions(body.agent_id)

    # Return the agent details
    agents = await service.list_agents_in_group(group_oid)
    for a in agents:
        if a.id == agent_oid:
            return AgentResponse.model_validate(a, from_attributes=True)


@router.delete(
    "/groups/{group_id}/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_agent_from_group(
    group_id: str,
    agent_id: str,
    user: User = Depends(require_group_admin()),
    service: AgentService = Depends(get_agent_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Remove an agent from a group (group admin or superadmin)."""
    group_oid = PydanticObjectId(group_id)
    agent_oid = PydanticObjectId(agent_id)
    try:
        await service.remove_agent_from_group(group_id=group_oid, agent_id=agent_oid)
    except ValueError as e:
        _handle_service_error(e)

    await permission_service.invalidate_agent_permissions(agent_id)


@router.get("/groups/{group_id}/agents", response_model=AgentListResponse)
async def list_agents_in_group(
    group_id: str,
    user: User = Depends(require_group_admin()),
    service: AgentService = Depends(get_agent_service),
):
    """List agents assigned to a group (group admin or superadmin)."""
    group_oid = PydanticObjectId(group_id)
    try:
        agents = await service.list_agents_in_group(group_oid)
    except ValueError as e:
        _handle_service_error(e)

    return AgentListResponse(
        agents=[AgentResponse.model_validate(a, from_attributes=True) for a in agents]
    )


@router.get("/users/{entra_object_id}/admin-groups", response_model=GroupListResponse)
async def get_admin_groups(
    entra_object_id: str,
    user: User = Depends(get_current_user),
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

    groups = await service.get_admin_groups(entra_object_id)
    return GroupListResponse(
        groups=[GroupResponse.model_validate(g, from_attributes=True) for g in groups]
    )


@router.get("/users/{entra_object_id}/agents", response_model=UserAgentListResponse)
async def get_user_agents(
    entra_object_id: str,
    user: User = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Return all agents accessible to a user across their group memberships.

    Used by the core platform to populate the agent selector.
    Users can query their own agents; superadmins can query any user's.
    """
    if not user.is_superadmin and user.id != entra_object_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view another user's agents",
        )

    # Check cache first
    cached = await permission_service.get_cached_user_agents(entra_object_id)
    if cached is not None:
        return UserAgentListResponse(agents=[UserAgentResponse(**a) for a in cached])

    # Only treat as superadmin when querying own agents
    querying_self = user.id == entra_object_id
    try:
        agents = await service.get_user_agents(
            entra_object_id,
            is_superadmin=user.is_superadmin and querying_self,
        )
    except ValueError as e:
        _handle_service_error(e)

    # Cache the result
    await permission_service.set_cached_user_agents(entra_object_id, agents)

    return UserAgentListResponse(agents=[UserAgentResponse(**a) for a in agents])
