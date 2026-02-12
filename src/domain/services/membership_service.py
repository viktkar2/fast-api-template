import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import Group
from src.domain.models.entities.group_membership import GroupMembership
from src.domain.models.entities.user import User

logger = logging.getLogger(__name__)


class MembershipService:
    async def add_member(
        self,
        session: AsyncSession,
        group_id: int,
        entra_object_id: str,
        role: GroupRole,
    ) -> GroupMembership:
        """Add a user to a group with the given role."""
        # Verify group exists
        result = await session.execute(select(Group).where(Group.id == group_id))
        if result.scalar_one_or_none() is None:
            raise ValueError("group_not_found")

        # Verify user exists in local users table
        result = await session.execute(
            select(User).where(User.entra_object_id == entra_object_id)
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("user_not_found")

        membership = GroupMembership(
            entra_object_id=entra_object_id,
            group_id=group_id,
            role=role,
        )
        session.add(membership)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise ValueError("duplicate_membership") from None

        await session.refresh(membership)
        logger.info(
            "Added member entra_object_id=%s to group_id=%s role=%s",
            entra_object_id,
            group_id,
            role.value,
        )
        return membership

    async def remove_member(
        self,
        session: AsyncSession,
        group_id: int,
        entra_object_id: str,
    ) -> bool:
        """Remove a user from a group. Returns True on success."""
        result = await session.execute(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.entra_object_id == entra_object_id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise ValueError("membership_not_found")

        # Last-admin protection
        if membership.role == GroupRole.ADMIN:
            admin_count = await self._count_admins(session, group_id)
            if admin_count <= 1:
                logger.warning(
                    "Blocked removal of last admin entra_object_id=%s from group_id=%s",
                    entra_object_id,
                    group_id,
                )
                raise ValueError("last_admin")

        await session.delete(membership)
        await session.commit()
        logger.info(
            "Removed member entra_object_id=%s from group_id=%s",
            entra_object_id,
            group_id,
        )
        return True

    async def update_member_role(
        self,
        session: AsyncSession,
        group_id: int,
        entra_object_id: str,
        new_role: GroupRole,
    ) -> GroupMembership:
        """Update a member's role within a group."""
        result = await session.execute(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.entra_object_id == entra_object_id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise ValueError("membership_not_found")

        # Last-admin protection when demoting admin -> user
        if membership.role == GroupRole.ADMIN and new_role == GroupRole.USER:
            admin_count = await self._count_admins(session, group_id)
            if admin_count <= 1:
                logger.warning(
                    "Blocked demotion of last admin entra_object_id=%s in group_id=%s",
                    entra_object_id,
                    group_id,
                )
                raise ValueError("last_admin")

        membership.role = new_role
        await session.commit()
        await session.refresh(membership)
        logger.info(
            "Updated member entra_object_id=%s in group_id=%s to role=%s",
            entra_object_id,
            group_id,
            new_role.value,
        )
        return membership

    async def list_members(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> list:
        """List members of a group with user details."""
        # Verify group exists
        result = await session.execute(select(Group).where(Group.id == group_id))
        if result.scalar_one_or_none() is None:
            raise ValueError("group_not_found")

        result = await session.execute(
            select(
                GroupMembership.entra_object_id,
                User.display_name,
                User.email,
                GroupMembership.role,
                GroupMembership.created_at,
            )
            .join(User, User.entra_object_id == GroupMembership.entra_object_id)
            .where(GroupMembership.group_id == group_id)
        )
        return list(result.all())

    async def _count_admins(self, session: AsyncSession, group_id: int) -> int:
        """Count the number of admins in a group."""
        result = await session.execute(
            select(func.count()).where(
                GroupMembership.group_id == group_id,
                GroupMembership.role == GroupRole.ADMIN,
            )
        )
        return result.scalar_one()
