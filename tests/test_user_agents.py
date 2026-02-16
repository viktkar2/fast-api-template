import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.base.config.redis_cache import RedisCache
from src.base.models.user import User
from src.domain.models.entities.agent import AgentDocument
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import GroupDocument
from src.domain.models.entities.group_agent import GroupAgentDocument
from src.domain.models.entities.group_membership import GroupMembershipDocument
from src.domain.models.entities.user import UserDocument
from src.domain.routes.agent_routes import router
from src.domain.services.agent_service import AgentService
from src.domain.services.permission_service import PermissionService
from src.domain.services.user_service import UserService
from tests.conftest import FakeAuthMiddleware


def _user_header(user: User) -> dict[str, str]:
    return {"X-Test-User": json.dumps(user.model_dump())}


SUPERADMIN = User(
    id="sa-001", email="admin@test.com", name="Super Admin", is_superadmin=True
)
REGULAR_USER = User(
    id="user-001", email="user@test.com", name="Regular User", is_superadmin=False
)
OTHER_USER = User(
    id="user-002", email="other@test.com", name="Other User", is_superadmin=False
)


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.state.agent_service = AgentService()
    test_app.state.permission_service = PermissionService(cache=RedisCache())
    test_app.state.user_service = UserService()
    test_app.add_middleware(FakeAuthMiddleware)
    test_app.include_router(router, prefix="/api")
    return test_app


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _seed_data():
    """Create users, groups, agents, memberships, and group-agent assignments.

    Layout:
    - Group A: user-001 (user), agent-1, agent-2
    - Group B: user-001 (admin), agent-2, agent-3
    - Group C: user-002 (user), agent-4

    So user-001 sees agents 1, 2, 3 (agent-2 via both groups).
    user-002 sees agent-4 only.
    Superadmin sees all agents (1, 2, 3, 4).
    """
    # Users
    await UserDocument(
        entra_object_id="user-001", display_name="Regular User", email="user@test.com"
    ).insert()
    await UserDocument(
        entra_object_id="user-002", display_name="Other User", email="other@test.com"
    ).insert()
    await UserDocument(
        entra_object_id="sa-001", display_name="Super Admin", email="admin@test.com"
    ).insert()

    # Groups
    group_a = GroupDocument(name="Group A", description="First group")
    group_b = GroupDocument(name="Group B", description="Second group")
    group_c = GroupDocument(name="Group C", description="Third group")
    await group_a.insert()
    await group_b.insert()
    await group_c.insert()

    # Memberships
    await GroupMembershipDocument(
        entra_object_id="user-001", group_id=group_a.id, role=GroupRole.USER
    ).insert()
    await GroupMembershipDocument(
        entra_object_id="user-001", group_id=group_b.id, role=GroupRole.ADMIN
    ).insert()
    await GroupMembershipDocument(
        entra_object_id="user-002", group_id=group_c.id, role=GroupRole.USER
    ).insert()

    # Agents
    agent1 = AgentDocument(agent_external_id="ext-1", name="Agent 1", created_by="user-001")
    agent2 = AgentDocument(agent_external_id="ext-2", name="Agent 2", created_by="user-001")
    agent3 = AgentDocument(agent_external_id="ext-3", name="Agent 3", created_by="user-001")
    agent4 = AgentDocument(agent_external_id="ext-4", name="Agent 4", created_by="user-002")
    await agent1.insert()
    await agent2.insert()
    await agent3.insert()
    await agent4.insert()

    # Group-agent assignments
    await GroupAgentDocument(group_id=group_a.id, agent_id=agent1.id, added_by="user-001").insert()
    await GroupAgentDocument(group_id=group_a.id, agent_id=agent2.id, added_by="user-001").insert()
    await GroupAgentDocument(group_id=group_b.id, agent_id=agent2.id, added_by="user-001").insert()
    await GroupAgentDocument(group_id=group_b.id, agent_id=agent3.id, added_by="user-001").insert()
    await GroupAgentDocument(group_id=group_c.id, agent_id=agent4.id, added_by="user-002").insert()

    return {
        "group_a": group_a,
        "group_b": group_b,
        "group_c": group_c,
        "agent1": agent1,
        "agent2": agent2,
        "agent3": agent3,
        "agent4": agent4,
    }


class TestGetUserAgents:
    async def test_regular_user_sees_own_agents(self, client):
        data = await _seed_data()

        resp = await client.get(
            "/api/users/user-001/agents", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 200

        body = resp.json()
        agents = body["agents"]
        agent_ids = {a["id"] for a in agents}

        # user-001 should see agents 1, 2, 3 (deduplicated)
        assert agent_ids == {
            str(data["agent1"].id),
            str(data["agent2"].id),
            str(data["agent3"].id),
        }

    async def test_agent_includes_group_info(self, client):
        data = await _seed_data()

        resp = await client.get(
            "/api/users/user-001/agents", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 200

        agents = resp.json()["agents"]
        # Find agent-2 which is in both Group A and Group B
        agent2 = next(a for a in agents if a["id"] == str(data["agent2"].id))
        group_ids = {g["group_id"] for g in agent2["groups"]}
        assert group_ids == {str(data["group_a"].id), str(data["group_b"].id)}

    async def test_superadmin_sees_all_agents(self, client):
        data = await _seed_data()

        resp = await client.get(
            "/api/users/sa-001/agents", headers=_user_header(SUPERADMIN)
        )
        assert resp.status_code == 200

        agents = resp.json()["agents"]
        agent_ids = {a["id"] for a in agents}

        # Superadmin should see all 4 agents
        assert agent_ids == {
            str(data["agent1"].id),
            str(data["agent2"].id),
            str(data["agent3"].id),
            str(data["agent4"].id),
        }

    async def test_superadmin_can_view_other_users_agents(self, client):
        data = await _seed_data()

        resp = await client.get(
            "/api/users/user-002/agents", headers=_user_header(SUPERADMIN)
        )
        assert resp.status_code == 200

        agents = resp.json()["agents"]
        agent_ids = {a["id"] for a in agents}
        # When superadmin queries another user, they see that user's agents
        assert agent_ids == {str(data["agent4"].id)}

    async def test_cannot_view_other_users_agents(self, client):
        await _seed_data()

        resp = await client.get(
            "/api/users/user-002/agents", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 403

    async def test_user_with_no_groups_returns_empty(self, client):
        # Create user with no memberships
        await UserDocument(
            entra_object_id="user-lonely",
            display_name="Lonely User",
            email="lonely@test.com",
        ).insert()

        lonely_user = User(
            id="user-lonely",
            email="lonely@test.com",
            name="Lonely User",
            is_superadmin=False,
        )
        resp = await client.get(
            "/api/users/user-lonely/agents", headers=_user_header(lonely_user)
        )
        assert resp.status_code == 200
        assert resp.json()["agents"] == []

    async def test_user_not_found_returns_404(self, client):
        # Create user entity for the requester so upsert works
        await UserDocument(
            entra_object_id="nonexistent",
            display_name="Ghost",
            email="ghost@test.com",
        ).insert()

        ghost = User(
            id="nonexistent",
            email="ghost@test.com",
            name="Ghost",
            is_superadmin=False,
        )

        # This user exists (so the auth upsert works) but has no memberships
        # - should return empty, not 404
        resp = await client.get(
            "/api/users/nonexistent/agents", headers=_user_header(ghost)
        )
        assert resp.status_code == 200
        assert resp.json()["agents"] == []

    async def test_deduplication_of_shared_agent(self, client):
        """An agent in multiple groups the user belongs to appears only once."""
        data = await _seed_data()

        resp = await client.get(
            "/api/users/user-001/agents", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 200

        agents = resp.json()["agents"]
        agent_ids = [a["id"] for a in agents]
        # No duplicates
        assert len(agent_ids) == len(set(agent_ids))
        # Agent 2 appears once, with two groups
        agent2 = next(a for a in agents if a["id"] == str(data["agent2"].id))
        assert len(agent2["groups"]) == 2
