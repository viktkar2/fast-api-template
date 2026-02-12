import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import Group
from src.domain.models.entities.group_membership import GroupMembership
from src.domain.models.entities.user import User
from src.domain.services.membership_service import MembershipService


async def _seed(session: AsyncSession):
    """Create two users and one group."""
    u1 = User(entra_object_id="user-001", display_name="Alice", email="alice@test.com")
    u2 = User(entra_object_id="user-002", display_name="Bob", email="bob@test.com")
    session.add_all([u1, u2])
    await session.flush()

    group = Group(name="Team A", description="Test group")
    session.add(group)
    await session.flush()
    await session.commit()
    return {"group": group, "u1": u1, "u2": u2}


@pytest.fixture
def service():
    return MembershipService()


class TestAddMember:
    async def test_add_member_success(self, db_session, service):
        data = await _seed(db_session)
        membership = await service.add_member(
            db_session, data["group"].id, "user-001", GroupRole.ADMIN
        )
        assert membership.entra_object_id == "user-001"
        assert membership.group_id == data["group"].id
        assert membership.role == GroupRole.ADMIN

    async def test_add_member_group_not_found(self, db_session, service):
        await _seed(db_session)
        with pytest.raises(ValueError, match="group_not_found"):
            await service.add_member(db_session, 9999, "user-001", GroupRole.USER)

    async def test_add_member_user_not_found(self, db_session, service):
        data = await _seed(db_session)
        with pytest.raises(ValueError, match="user_not_found"):
            await service.add_member(
                db_session, data["group"].id, "nonexistent", GroupRole.USER
            )

    async def test_add_member_duplicate(self, db_session, service):
        data = await _seed(db_session)
        await service.add_member(
            db_session, data["group"].id, "user-001", GroupRole.USER
        )
        with pytest.raises(ValueError, match="duplicate_membership"):
            await service.add_member(
                db_session, data["group"].id, "user-001", GroupRole.ADMIN
            )


class TestRemoveMember:
    async def test_remove_member_success(self, db_session, service):
        data = await _seed(db_session)
        # Add two admins so we can safely remove one
        await service.add_member(
            db_session, data["group"].id, "user-001", GroupRole.ADMIN
        )
        await service.add_member(
            db_session, data["group"].id, "user-002", GroupRole.ADMIN
        )
        result = await service.remove_member(db_session, data["group"].id, "user-001")
        assert result is True

    async def test_remove_member_not_found(self, db_session, service):
        data = await _seed(db_session)
        with pytest.raises(ValueError, match="membership_not_found"):
            await service.remove_member(db_session, data["group"].id, "user-001")

    async def test_remove_last_admin_blocked(self, db_session, service):
        data = await _seed(db_session)
        await service.add_member(
            db_session, data["group"].id, "user-001", GroupRole.ADMIN
        )
        with pytest.raises(ValueError, match="last_admin"):
            await service.remove_member(db_session, data["group"].id, "user-001")

    async def test_remove_regular_user_when_only_one_admin(self, db_session, service):
        """Removing a regular user should succeed even if there's only one admin."""
        data = await _seed(db_session)
        await service.add_member(
            db_session, data["group"].id, "user-001", GroupRole.ADMIN
        )
        await service.add_member(
            db_session, data["group"].id, "user-002", GroupRole.USER
        )
        result = await service.remove_member(db_session, data["group"].id, "user-002")
        assert result is True


class TestUpdateMemberRole:
    async def test_promote_user_to_admin(self, db_session, service):
        data = await _seed(db_session)
        await service.add_member(
            db_session, data["group"].id, "user-001", GroupRole.USER
        )
        membership = await service.update_member_role(
            db_session, data["group"].id, "user-001", GroupRole.ADMIN
        )
        assert membership.role == GroupRole.ADMIN

    async def test_demote_admin_to_user(self, db_session, service):
        data = await _seed(db_session)
        # Two admins so demotion is allowed
        await service.add_member(
            db_session, data["group"].id, "user-001", GroupRole.ADMIN
        )
        await service.add_member(
            db_session, data["group"].id, "user-002", GroupRole.ADMIN
        )
        membership = await service.update_member_role(
            db_session, data["group"].id, "user-001", GroupRole.USER
        )
        assert membership.role == GroupRole.USER

    async def test_demote_last_admin_blocked(self, db_session, service):
        data = await _seed(db_session)
        await service.add_member(
            db_session, data["group"].id, "user-001", GroupRole.ADMIN
        )
        with pytest.raises(ValueError, match="last_admin"):
            await service.update_member_role(
                db_session, data["group"].id, "user-001", GroupRole.USER
            )

    async def test_update_role_membership_not_found(self, db_session, service):
        data = await _seed(db_session)
        with pytest.raises(ValueError, match="membership_not_found"):
            await service.update_member_role(
                db_session, data["group"].id, "user-001", GroupRole.ADMIN
            )


class TestListMembers:
    async def test_list_members_with_details(self, db_session, service):
        data = await _seed(db_session)
        await service.add_member(
            db_session, data["group"].id, "user-001", GroupRole.ADMIN
        )
        await service.add_member(
            db_session, data["group"].id, "user-002", GroupRole.USER
        )
        members = await service.list_members(db_session, data["group"].id)
        assert len(members) == 2
        ids = {m.entra_object_id for m in members}
        assert ids == {"user-001", "user-002"}

    async def test_list_members_empty_group(self, db_session, service):
        data = await _seed(db_session)
        members = await service.list_members(db_session, data["group"].id)
        assert members == []

    async def test_list_members_group_not_found(self, db_session, service):
        with pytest.raises(ValueError, match="group_not_found"):
            await service.list_members(db_session, 9999)
