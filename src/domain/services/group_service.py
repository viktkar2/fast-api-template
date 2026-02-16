import datetime
import logging

from beanie import PydanticObjectId

from src.domain.models.entities.group import GroupDocument
from src.domain.models.entities.group_membership import GroupMembershipDocument

logger = logging.getLogger(__name__)


class GroupService:
    async def create_group(
        self,
        name: str,
        description: str | None = None,
    ) -> GroupDocument:
        """Create a new group."""
        group = GroupDocument(name=name, description=description)
        await group.insert()
        logger.info("Created group id=%s name=%s", group.id, group.name)
        return group

    async def get_group(
        self,
        group_id: PydanticObjectId,
    ) -> GroupDocument | None:
        """Return a single group by ID, or None if not found."""
        return await GroupDocument.get(group_id)

    async def list_groups_for_user(
        self,
        entra_object_id: str,
        is_superadmin: bool,
    ) -> list[GroupDocument]:
        """Return groups visible to the user.

        Superadmins see all groups; others see only groups they belong to.
        """
        if is_superadmin:
            return await GroupDocument.find_all().to_list()

        memberships = await GroupMembershipDocument.find(
            GroupMembershipDocument.entra_object_id == entra_object_id
        ).to_list()
        group_ids = [m.group_id for m in memberships]
        if not group_ids:
            return []
        return await GroupDocument.find({"_id": {"$in": group_ids}}).to_list()

    async def update_group(
        self,
        group_id: PydanticObjectId,
        name: str | None = None,
        description: str | None = None,
    ) -> GroupDocument | None:
        """Update a group's name and/or description. Returns None if not found."""
        group = await GroupDocument.get(group_id)
        if group is None:
            return None

        if name is not None:
            group.name = name
        if description is not None:
            group.description = description
        group.updated_at = datetime.datetime.now(datetime.UTC)
        await group.save()
        logger.info("Updated group id=%s", group.id)
        return group

    async def delete_group(
        self,
        group_id: PydanticObjectId,
    ) -> bool:
        """Delete a group by ID. Returns False if not found."""
        group = await GroupDocument.get(group_id)
        if group is None:
            return False

        await group.delete()
        logger.info("Deleted group id=%s", group_id)
        return True
