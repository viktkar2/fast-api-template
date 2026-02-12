import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.base.core.dependencies import (
    get_current_user,
    get_db_session,
    get_group_service,
)
from src.base.models.user import User
from src.domain.auth.authorization import require_group_admin, require_superadmin
from src.domain.models.entities.group_membership import GroupMembership
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
    session: AsyncSession = Depends(get_db_session),
    service: GroupService = Depends(get_group_service),
):
    """Create a new group (superadmin only)."""
    group = await service.create_group(
        session, name=body.name, description=body.description
    )
    return GroupResponse.model_validate(group)


@router.get("", response_model=GroupListResponse)
async def list_groups(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    service: GroupService = Depends(get_group_service),
):
    """List groups visible to the current user."""
    groups = await service.list_groups_for_user(
        session,
        entra_object_id=user.id,
        is_superadmin=user.is_superadmin,
    )
    return GroupListResponse(groups=[GroupResponse.model_validate(g) for g in groups])


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    service: GroupService = Depends(get_group_service),
):
    """Get group details. Accessible by group members and superadmins."""
    group = await service.get_group(session, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    if not user.is_superadmin:
        result = await session.execute(
            select(GroupMembership).where(
                GroupMembership.entra_object_id == user.id,
                GroupMembership.group_id == group_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this group",
            )

    return GroupResponse.model_validate(group)


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    body: GroupUpdate,
    user: User = Depends(require_group_admin()),
    session: AsyncSession = Depends(get_db_session),
    service: GroupService = Depends(get_group_service),
):
    """Update a group (group admin or superadmin)."""
    group = await service.update_group(
        session, group_id, name=body.name, description=body.description
    )
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    return GroupResponse.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
    service: GroupService = Depends(get_group_service),
):
    """Delete a group (superadmin only)."""
    deleted = await service.delete_group(session, group_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
