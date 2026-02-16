import logging

from beanie import PydanticObjectId

from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import GroupDocument
from src.domain.models.entities.group_membership import GroupMembershipDocument
from src.domain.models.entities.user import UserDocument

logger = logging.getLogger(__name__)


class MembershipService:
    async def add_member(
        self,
        group_id: PydanticObjectId,
        entra_object_id: str,
        role: GroupRole,
    ) -> GroupMembershipDocument:
        """Add a user to a group with the given role."""
        if not await GroupDocument.get(group_id):
            raise ValueError("group_not_found")

        if not await UserDocument.find_one(
            UserDocument.entra_object_id == entra_object_id
        ):
            raise ValueError("user_not_found")

        existing = await GroupMembershipDocument.find_one(
            GroupMembershipDocument.entra_object_id == entra_object_id,
            GroupMembershipDocument.group_id == group_id,
        )
        if existing:
            raise ValueError("duplicate_membership")

        membership = GroupMembershipDocument(
            entra_object_id=entra_object_id,
            group_id=group_id,
            role=role,
        )
        await membership.insert()
        logger.info(
            "Added member entra_object_id=%s to group_id=%s role=%s",
            entra_object_id,
            group_id,
            role.value,
        )
        return membership

    async def remove_member(
        self,
        group_id: PydanticObjectId,
        entra_object_id: str,
    ) -> bool:
        """Remove a user from a group. Returns True on success."""
        membership = await GroupMembershipDocument.find_one(
            GroupMembershipDocument.group_id == group_id,
            GroupMembershipDocument.entra_object_id == entra_object_id,
        )
        if membership is None:
            raise ValueError("membership_not_found")

        # Last-admin protection
        if membership.role == GroupRole.ADMIN:
            admin_count = await self._count_admins(group_id)
            if admin_count <= 1:
                logger.warning(
                    "Blocked removal of last admin entra_object_id=%s from group_id=%s",
                    entra_object_id,
                    group_id,
                )
                raise ValueError("last_admin")

        await membership.delete()
        logger.info(
            "Removed member entra_object_id=%s from group_id=%s",
            entra_object_id,
            group_id,
        )
        return True

    async def update_member_role(
        self,
        group_id: PydanticObjectId,
        entra_object_id: str,
        new_role: GroupRole,
    ) -> GroupMembershipDocument:
        """Update a member's role within a group."""
        membership = await GroupMembershipDocument.find_one(
            GroupMembershipDocument.group_id == group_id,
            GroupMembershipDocument.entra_object_id == entra_object_id,
        )
        if membership is None:
            raise ValueError("membership_not_found")

        # Last-admin protection when demoting admin -> user
        if membership.role == GroupRole.ADMIN and new_role == GroupRole.USER:
            admin_count = await self._count_admins(group_id)
            if admin_count <= 1:
                logger.warning(
                    "Blocked demotion of last admin entra_object_id=%s in group_id=%s",
                    entra_object_id,
                    group_id,
                )
                raise ValueError("last_admin")

        membership.role = new_role
        await membership.save()
        logger.info(
            "Updated member entra_object_id=%s in group_id=%s to role=%s",
            entra_object_id,
            group_id,
            new_role.value,
        )
        return membership

    async def list_members(
        self,
        group_id: PydanticObjectId,
    ) -> list[dict]:
        """List members of a group with user details."""
        if not await GroupDocument.get(group_id):
            raise ValueError("group_not_found")

        memberships = await GroupMembershipDocument.find(
            GroupMembershipDocument.group_id == group_id
        ).to_list()

        entra_ids = [m.entra_object_id for m in memberships]
        users = await UserDocument.find(
            {"entra_object_id": {"$in": entra_ids}}
        ).to_list()
        user_map = {u.entra_object_id: u for u in users}

        result = []
        for m in memberships:
            u = user_map.get(m.entra_object_id)
            result.append({
                "entra_object_id": m.entra_object_id,
                "display_name": u.display_name if u else "",
                "email": u.email if u else "",
                "role": m.role,
                "created_at": m.created_at,
            })
        return result

    async def _count_admins(self, group_id: PydanticObjectId) -> int:
        """Count the number of admins in a group."""
        return await GroupMembershipDocument.find(
            GroupMembershipDocument.group_id == group_id,
            GroupMembershipDocument.role == GroupRole.ADMIN,
        ).count()
