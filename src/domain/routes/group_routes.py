import logging

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from src.base.core.dependencies import (
    get_current_user,
    get_group_service,
)
from src.base.models.user import User
from src.domain.auth.authorization import require_group_admin, require_superadmin
from src.domain.models.entities.group_membership import GroupMembershipDocument
from src.domain.models.group_schemas import (
    GroupCreate,
    GroupListResponse,
    GroupResponse,
    GroupUpdate,
)
from src.domain.services.group_service import GroupService

router = APIRouter(prefix="/groups", tags=["Groups"])
logger = logging.getLogger(__name__)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=GroupResponse)
async def create_group(
    body: GroupCreate,
    user: User = Depends(require_superadmin),
    service: GroupService = Depends(get_group_service),
):
    """Create a new group (superadmin only)."""
    group = await service.create_group(name=body.name, description=body.description)
    return GroupResponse.model_validate(group, from_attributes=True)


@router.get("", response_model=GroupListResponse)
async def list_groups(
    user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    """List groups visible to the current user."""
    groups = await service.list_groups_for_user(
        entra_object_id=user.id,
        is_superadmin=user.is_superadmin,
    )
    return GroupListResponse(
        groups=[GroupResponse.model_validate(g, from_attributes=True) for g in groups]
    )


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: str,
    user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    """Get group details. Accessible by group members and superadmins."""
    group_oid = PydanticObjectId(group_id)
    group = await service.get_group(group_oid)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    if not user.is_superadmin:
        membership = await GroupMembershipDocument.find_one(
            GroupMembershipDocument.entra_object_id == user.id,
            GroupMembershipDocument.group_id == group_oid,
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this group",
            )

    return GroupResponse.model_validate(group, from_attributes=True)


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: str,
    body: GroupUpdate,
    user: User = Depends(require_group_admin()),
    service: GroupService = Depends(get_group_service),
):
    """Update a group (group admin or superadmin)."""
    group_oid = PydanticObjectId(group_id)
    group = await service.update_group(
        group_oid, name=body.name, description=body.description
    )
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    return GroupResponse.model_validate(group, from_attributes=True)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    user: User = Depends(require_superadmin),
    service: GroupService = Depends(get_group_service),
):
    """Delete a group (superadmin only)."""
    group_oid = PydanticObjectId(group_id)
    deleted = await service.delete_group(group_oid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
