import json
from unittest.mock import AsyncMock

import pytest

from src.base.config.redis_cache import RedisCache
from src.domain.models.entities.agent import AgentDocument
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import GroupDocument
from src.domain.models.entities.group_agent import GroupAgentDocument
from src.domain.models.entities.group_membership import GroupMembershipDocument
from src.domain.models.entities.user import UserDocument
from src.domain.models.permission_schemas import PermissionAction
from src.domain.services.permission_service import PermissionService


async def _seed():
    """Create users, groups, agents, and assignments.

    Layout:
    - Group A: user-001 (admin), agent-1
    - Group B: user-001 (user), agent-2
    - Group C: user-002 (admin), agent-3
    """
    await UserDocument(
        entra_object_id="user-001", display_name="Alice", email="alice@test.com"
    ).insert()
    await UserDocument(
        entra_object_id="user-002", display_name="Bob", email="bob@test.com"
    ).insert()

    ga = GroupDocument(name="Group A")
    gb = GroupDocument(name="Group B")
    gc = GroupDocument(name="Group C")
    await ga.insert()
    await gb.insert()
    await gc.insert()

    await GroupMembershipDocument(
        entra_object_id="user-001", group_id=ga.id, role=GroupRole.ADMIN
    ).insert()
    await GroupMembershipDocument(
        entra_object_id="user-001", group_id=gb.id, role=GroupRole.USER
    ).insert()
    await GroupMembershipDocument(
        entra_object_id="user-002", group_id=gc.id, role=GroupRole.ADMIN
    ).insert()

    a1 = AgentDocument(agent_external_id="ext-1", name="Agent 1", created_by="user-001")
    a2 = AgentDocument(agent_external_id="ext-2", name="Agent 2", created_by="user-001")
    a3 = AgentDocument(agent_external_id="ext-3", name="Agent 3", created_by="user-002")
    await a1.insert()
    await a2.insert()
    await a3.insert()

    await GroupAgentDocument(group_id=ga.id, agent_id=a1.id, added_by="user-001").insert()
    await GroupAgentDocument(group_id=gb.id, agent_id=a2.id, added_by="user-001").insert()
    await GroupAgentDocument(group_id=gc.id, agent_id=a3.id, added_by="user-002").insert()

    return {"ga": ga, "gb": gb, "gc": gc, "a1": a1, "a2": a2, "a3": a3}


@pytest.fixture
def service():
    """PermissionService with no Redis (cache disabled)."""
    return PermissionService(cache=RedisCache())


class TestCheckPermissionAccess:
    async def test_user_can_access_agent_in_their_group(self, service):
        data = await _seed()
        allowed, role = await service.check_permission(
            "user-001", str(data["a1"].id), PermissionAction.ACCESS
        )
        assert allowed is True
        assert role == "admin"

    async def test_user_can_access_agent_as_regular_member(self, service):
        data = await _seed()
        allowed, role = await service.check_permission(
            "user-001", str(data["a2"].id), PermissionAction.ACCESS
        )
        assert allowed is True
        assert role == "user"

    async def test_user_cannot_access_agent_outside_their_groups(self, service):
        data = await _seed()
        allowed, role = await service.check_permission(
            "user-001", str(data["a3"].id), PermissionAction.ACCESS
        )
        assert allowed is False
        assert role is None

    async def test_nonexistent_agent_denied(self, service):
        await _seed()
        allowed, role = await service.check_permission(
            "user-001", "000000000000000000009999", PermissionAction.ACCESS
        )
        assert allowed is False
        assert role is None


class TestCheckPermissionCreate:
    async def test_admin_can_create_in_their_admin_group(self, service):
        data = await _seed()
        allowed, role = await service.check_permission(
            "user-001", str(data["a1"].id), PermissionAction.CREATE
        )
        assert allowed is True
        assert role == "admin"

    async def test_regular_user_cannot_create(self, service):
        """User with USER role in group should not have CREATE permission."""
        data = await _seed()
        allowed, role = await service.check_permission(
            "user-001", str(data["a2"].id), PermissionAction.CREATE
        )
        assert allowed is False
        assert role is None


class TestSuperadminBypass:
    async def test_superadmin_always_allowed(self, service):
        data = await _seed()
        allowed, role = await service.check_permission(
            "anyone", str(data["a3"].id), PermissionAction.ACCESS, is_superadmin=True
        )
        assert allowed is True
        assert role == "superadmin"

    async def test_superadmin_create_allowed(self, service):
        data = await _seed()
        allowed, role = await service.check_permission(
            "anyone", str(data["a1"].id), PermissionAction.CREATE, is_superadmin=True
        )
        assert allowed is True
        assert role == "superadmin"


class TestPermissionCaching:
    async def test_cache_hit_returns_cached_result(self):
        """When cache has a value, the DB should not be queried."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=json.dumps({"allowed": True, "role": "admin"})
        )
        cache = RedisCache(redis_client=mock_redis)
        svc = PermissionService(cache=cache)

        data = await _seed()
        allowed, role = await svc.check_permission(
            "user-001", str(data["a1"].id), PermissionAction.ACCESS
        )
        assert allowed is True
        assert role == "admin"
        mock_redis.get.assert_called_once()
        # set should NOT be called when cache hit
        mock_redis.set.assert_not_called()

    async def test_cache_miss_queries_db_and_caches(self):
        """When cache misses, the result should be fetched from DB and cached."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache = RedisCache(redis_client=mock_redis)
        svc = PermissionService(cache=cache)

        data = await _seed()
        allowed, role = await svc.check_permission(
            "user-001", str(data["a1"].id), PermissionAction.ACCESS
        )
        assert allowed is True
        mock_redis.set.assert_called_once()
        cached_value = json.loads(mock_redis.set.call_args[0][1])
        assert cached_value["allowed"] is True
        assert cached_value["role"] == "admin"
