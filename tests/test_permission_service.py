import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.base.config.redis_cache import RedisCache
from src.domain.models.entities.agent import Agent
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import Group
from src.domain.models.entities.group_agent import GroupAgent
from src.domain.models.entities.group_membership import GroupMembership
from src.domain.models.entities.user import User
from src.domain.models.permission_schemas import PermissionAction
from src.domain.services.permission_service import PermissionService


async def _seed(session: AsyncSession):
    """Create users, groups, agents, and assignments.

    Layout:
    - Group A: user-001 (admin), agent-1
    - Group B: user-001 (user), agent-2
    - Group C: user-002 (admin), agent-3
    """
    u1 = User(entra_object_id="user-001", display_name="Alice", email="alice@test.com")
    u2 = User(entra_object_id="user-002", display_name="Bob", email="bob@test.com")
    session.add_all([u1, u2])
    await session.flush()

    ga = Group(name="Group A")
    gb = Group(name="Group B")
    gc = Group(name="Group C")
    session.add_all([ga, gb, gc])
    await session.flush()

    session.add_all(
        [
            GroupMembership(entra_object_id="user-001", group_id=ga.id, role=GroupRole.ADMIN),
            GroupMembership(entra_object_id="user-001", group_id=gb.id, role=GroupRole.USER),
            GroupMembership(entra_object_id="user-002", group_id=gc.id, role=GroupRole.ADMIN),
        ]
    )
    await session.flush()

    a1 = Agent(agent_external_id="ext-1", name="Agent 1", created_by="user-001")
    a2 = Agent(agent_external_id="ext-2", name="Agent 2", created_by="user-001")
    a3 = Agent(agent_external_id="ext-3", name="Agent 3", created_by="user-002")
    session.add_all([a1, a2, a3])
    await session.flush()

    session.add_all(
        [
            GroupAgent(group_id=ga.id, agent_id=a1.id, added_by="user-001"),
            GroupAgent(group_id=gb.id, agent_id=a2.id, added_by="user-001"),
            GroupAgent(group_id=gc.id, agent_id=a3.id, added_by="user-002"),
        ]
    )
    await session.commit()
    return {"ga": ga, "gb": gb, "gc": gc, "a1": a1, "a2": a2, "a3": a3}


@pytest.fixture
def service():
    """PermissionService with no Redis (cache disabled)."""
    return PermissionService(cache=RedisCache())


class TestCheckPermissionAccess:
    async def test_user_can_access_agent_in_their_group(self, db_session, service):
        data = await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "user-001", data["a1"].id, PermissionAction.ACCESS
        )
        assert allowed is True
        assert role == "admin"

    async def test_user_can_access_agent_as_regular_member(self, db_session, service):
        data = await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "user-001", data["a2"].id, PermissionAction.ACCESS
        )
        assert allowed is True
        assert role == "user"

    async def test_user_cannot_access_agent_outside_their_groups(self, db_session, service):
        data = await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "user-001", data["a3"].id, PermissionAction.ACCESS
        )
        assert allowed is False
        assert role is None

    async def test_nonexistent_agent_denied(self, db_session, service):
        await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "user-001", 9999, PermissionAction.ACCESS
        )
        assert allowed is False
        assert role is None


class TestCheckPermissionCreate:
    async def test_admin_can_create_in_their_admin_group(self, db_session, service):
        data = await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "user-001", data["a1"].id, PermissionAction.CREATE
        )
        assert allowed is True
        assert role == "admin"

    async def test_regular_user_cannot_create(self, db_session, service):
        """User with USER role in group should not have CREATE permission."""
        data = await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "user-001", data["a2"].id, PermissionAction.CREATE
        )
        assert allowed is False
        assert role is None


class TestSuperadminBypass:
    async def test_superadmin_always_allowed(self, db_session, service):
        data = await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "anyone", data["a3"].id, PermissionAction.ACCESS, is_superadmin=True
        )
        assert allowed is True
        assert role == "superadmin"

    async def test_superadmin_create_allowed(self, db_session, service):
        data = await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "anyone", data["a1"].id, PermissionAction.CREATE, is_superadmin=True
        )
        assert allowed is True
        assert role == "superadmin"


class TestPermissionCaching:
    async def test_cache_hit_returns_cached_result(self, db_session):
        """When cache has a value, the DB should not be queried."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=json.dumps({"allowed": True, "role": "admin"})
        )
        cache = RedisCache(redis_client=mock_redis)
        service = PermissionService(cache=cache)

        data = await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "user-001", data["a1"].id, PermissionAction.ACCESS
        )
        assert allowed is True
        assert role == "admin"
        mock_redis.get.assert_called_once()
        # set should NOT be called when cache hit
        mock_redis.set.assert_not_called()

    async def test_cache_miss_queries_db_and_caches(self, db_session):
        """When cache misses, the result should be fetched from DB and cached."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache = RedisCache(redis_client=mock_redis)
        service = PermissionService(cache=cache)

        data = await _seed(db_session)
        allowed, role = await service.check_permission(
            db_session, "user-001", data["a1"].id, PermissionAction.ACCESS
        )
        assert allowed is True
        mock_redis.set.assert_called_once()
        cached_value = json.loads(mock_redis.set.call_args[0][1])
        assert cached_value["allowed"] is True
        assert cached_value["role"] == "admin"
