import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.entities.group import Group
from src.domain.models.entities.group_membership import GroupMembership

logger = logging.getLogger(__name__)


class GroupService:
    async def create_group(
        self,
        session: AsyncSession,
        name: str,
        description: str | None = None,
    ) -> Group:
        """Create a new group."""
        group = Group(name=name, description=description)
        session.add(group)
        await session.commit()
        await session.refresh(group)
        logger.info("Created group id=%s name=%s", group.id, group.name)
        return group

    async def get_group(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> Group | None:
        """Return a single group by ID, or None if not found."""
        result = await session.execute(select(Group).where(Group.id == group_id))
        return result.scalar_one_or_none()

    async def list_groups_for_user(
        self,
        session: AsyncSession,
        entra_object_id: str,
        is_superadmin: bool,
    ) -> list[Group]:
        """Return groups visible to the user.

        Superadmins see all groups; others see only groups they belong to.
        """
        if is_superadmin:
            result = await session.execute(select(Group))
        else:
            result = await session.execute(
                select(Group)
                .join(GroupMembership, GroupMembership.group_id == Group.id)
                .where(GroupMembership.entra_object_id == entra_object_id)
            )
        return list(result.scalars().all())

    async def update_group(
        self,
        session: AsyncSession,
        group_id: int,
        name: str | None = None,
        description: str | None = None,
    ) -> Group | None:
        """Update a group's name and/or description. Returns None if not found."""
        group = await self.get_group(session, group_id)
        if group is None:
            return None

        if name is not None:
            group.name = name
        if description is not None:
            group.description = description

        await session.commit()
        await session.refresh(group)
        logger.info("Updated group id=%s", group.id)
        return group

    async def delete_group(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> bool:
        """Delete a group by ID. Returns False if not found."""
        group = await self.get_group(session, group_id)
        if group is None:
            return False

        await session.delete(group)
        await session.commit()
        logger.info("Deleted group id=%s", group_id)
        return True
