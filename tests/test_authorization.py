import json

from src.base.models.user import User
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import Group
from src.domain.models.entities.group_membership import GroupMembership
from src.domain.models.entities.user import User as UserEntity


def _user_header(user: User) -> dict[str, str]:
    return {"X-Test-User": json.dumps(user.model_dump())}


SUPERADMIN = User(id="sa-001", email="admin@test.com", name="Super Admin", is_superadmin=True)
REGULAR_USER = User(id="user-001", email="user@test.com", name="Regular User", is_superadmin=False)
OTHER_USER = User(id="user-002", email="other@test.com", name="Other User", is_superadmin=False)


# ── require_superadmin ──────────────────────────────────────────────


class TestRequireSuperadmin:
    async def test_superadmin_allowed(self, client):
        resp = await client.get("/superadmin-only", headers=_user_header(SUPERADMIN))
        assert resp.status_code == 200
        assert resp.json()["user_id"] == SUPERADMIN.id

    async def test_non_superadmin_forbidden(self, client):
        resp = await client.get("/superadmin-only", headers=_user_header(REGULAR_USER))
        assert resp.status_code == 403

    async def test_unauthenticated_unauthorized(self, client):
        resp = await client.get("/superadmin-only")
        assert resp.status_code == 401


# ── require_group_admin ─────────────────────────────────────────────


async def _seed_group_and_membership(db_session, entra_object_id: str, role: GroupRole):
    """Insert a user entity, a group, and a membership, then return the group ID."""
    user_entity = UserEntity(
        entra_object_id=entra_object_id,
        display_name="Test",
        email="test@test.com",
    )
    group = Group(name="Test Group", description="desc")
    db_session.add_all([user_entity, group])
    await db_session.flush()

    membership = GroupMembership(
        entra_object_id=entra_object_id,
        group_id=group.id,
        role=role,
    )
    db_session.add(membership)
    await db_session.commit()
    return group.id


class TestRequireGroupAdmin:
    async def test_superadmin_bypasses_group_check(self, client):
        resp = await client.get("/groups/999/admin-only", headers=_user_header(SUPERADMIN))
        assert resp.status_code == 200
        assert resp.json()["user_id"] == SUPERADMIN.id

    async def test_group_admin_allowed(self, client, db_session):
        group_id = await _seed_group_and_membership(db_session, REGULAR_USER.id, GroupRole.ADMIN)
        resp = await client.get(
            f"/groups/{group_id}/admin-only", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 200
        assert resp.json()["user_id"] == REGULAR_USER.id

    async def test_group_user_forbidden(self, client, db_session):
        group_id = await _seed_group_and_membership(db_session, REGULAR_USER.id, GroupRole.USER)
        resp = await client.get(
            f"/groups/{group_id}/admin-only", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 403

    async def test_no_membership_forbidden(self, client, db_session):
        group_id = await _seed_group_and_membership(db_session, OTHER_USER.id, GroupRole.ADMIN)
        resp = await client.get(
            f"/groups/{group_id}/admin-only", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_unauthorized(self, client):
        resp = await client.get("/groups/1/admin-only")
        assert resp.status_code == 401
