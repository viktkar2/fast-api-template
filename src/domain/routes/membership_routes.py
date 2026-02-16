import logging

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from src.base.core.dependencies import (
    get_membership_service,
    get_permission_service,
)
from src.base.models.user import User
from src.domain.auth.authorization import require_group_admin
from src.domain.models.membership_schemas import (
    AddMemberRequest,
    MemberListResponse,
    MemberResponse,
    UpdateMemberRoleRequest,
)
from src.domain.services.membership_service import MembershipService
from src.domain.services.permission_service import PermissionService

router = APIRouter(prefix="/groups", tags=["Group Membership"])
logger = logging.getLogger(__name__)

ERROR_MAP = {
    "group_not_found": (status.HTTP_404_NOT_FOUND, "Group not found"),
    "user_not_found": (status.HTTP_404_NOT_FOUND, "User not found"),
    "membership_not_found": (status.HTTP_404_NOT_FOUND, "Membership not found"),
    "duplicate_membership": (
        status.HTTP_409_CONFLICT,
        "User is already a member of this group",
    ),
    "last_admin": (
        status.HTTP_400_BAD_REQUEST,
        "Cannot remove or demote the last admin of a group",
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
    "/{group_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=MemberResponse,
)
async def add_member(
    group_id: str,
    body: AddMemberRequest,
    user: User = Depends(require_group_admin()),
    service: MembershipService = Depends(get_membership_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Add a member to a group (group admin or superadmin)."""
    group_oid = PydanticObjectId(group_id)
    try:
        membership = await service.add_member(
            group_id=group_oid,
            entra_object_id=body.entra_object_id,
            role=body.role,
        )
    except ValueError as e:
        _handle_service_error(e)

    await permission_service.invalidate_user_permissions(body.entra_object_id)

    # Re-query to get user details for response
    members = await service.list_members(group_oid)
    for m in members:
        if m["entra_object_id"] == body.entra_object_id:
            return MemberResponse.model_validate(m)

    return MemberResponse.model_validate(membership, from_attributes=True)


@router.get("/{group_id}/members", response_model=MemberListResponse)
async def list_members(
    group_id: str,
    user: User = Depends(require_group_admin()),
    service: MembershipService = Depends(get_membership_service),
):
    """List members of a group (group admin or superadmin)."""
    group_oid = PydanticObjectId(group_id)
    try:
        members = await service.list_members(group_oid)
    except ValueError as e:
        _handle_service_error(e)

    return MemberListResponse(
        members=[MemberResponse.model_validate(m) for m in members]
    )


@router.put("/{group_id}/members/{entra_object_id}", response_model=MemberResponse)
async def update_member_role(
    group_id: str,
    entra_object_id: str,
    body: UpdateMemberRoleRequest,
    user: User = Depends(require_group_admin()),
    service: MembershipService = Depends(get_membership_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Update a member's role (group admin or superadmin)."""
    group_oid = PydanticObjectId(group_id)
    try:
        await service.update_member_role(
            group_id=group_oid,
            entra_object_id=entra_object_id,
            new_role=body.role,
        )
    except ValueError as e:
        _handle_service_error(e)

    await permission_service.invalidate_user_permissions(entra_object_id)

    # Re-query to get user details for response
    members = await service.list_members(group_oid)
    for m in members:
        if m["entra_object_id"] == entra_object_id:
            return MemberResponse.model_validate(m)


@router.delete(
    "/{group_id}/members/{entra_object_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    group_id: str,
    entra_object_id: str,
    user: User = Depends(require_group_admin()),
    service: MembershipService = Depends(get_membership_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Remove a member from a group (group admin or superadmin)."""
    group_oid = PydanticObjectId(group_id)
    try:
        await service.remove_member(group_id=group_oid, entra_object_id=entra_object_id)
    except ValueError as e:
        _handle_service_error(e)

    await permission_service.invalidate_user_permissions(entra_object_id)
