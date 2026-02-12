# Domain-level authorization dependencies: enforce business rules like
# "user must be a superadmin" or "user must be an admin of this group".
# Unlike base/auth/ (which only reads JWT claims), these guards may
# query the database (e.g. group_memberships) to make access decisions.
#
# Token-level checks (Entra ID roles/scopes) live in
# src/base/auth/rbac.py.

import logging

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.base.core.dependencies import get_db_session
from src.base.models.user import User
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group_membership import GroupMembership

logger = logging.getLogger(__name__)


async def require_superadmin(request: Request) -> User:
    """Dependency that enforces superadmin access. Returns the user or raises."""
    user: User | None = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    if not user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required",
        )
    return user


def require_group_admin(group_id_param: str = "group_id"):
    """Factory that returns a dependency enforcing group-admin (or superadmin) access.

    Args:
        group_id_param: Name of the path parameter that contains the group ID.
    """

    async def dependency(
        request: Request,
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        user: User | None = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        if user.is_superadmin:
            return user

        group_id = request.path_params.get(group_id_param)
        if group_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing path parameter: {group_id_param}",
            )

        result = await session.execute(
            select(GroupMembership).where(
                GroupMembership.entra_object_id == user.id,
                GroupMembership.group_id == int(group_id),
                GroupMembership.role == GroupRole.ADMIN,
            )
        )
        membership = result.scalar_one_or_none()

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Group admin access required",
            )

        return user

    return dependency
