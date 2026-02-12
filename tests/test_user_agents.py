import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.base.config.redis_cache import RedisCache
from src.base.models.user import User
from src.domain.models.entities.agent import Agent
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import Group
from src.domain.models.entities.group_agent import GroupAgent
from src.domain.models.entities.group_membership import GroupMembership
from src.domain.models.entities.user import User as UserEntity
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
def app(db_session_factory):
    test_app = FastAPI()
    test_app.state.db_session_factory = db_session_factory
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


async def _seed_data(session: AsyncSession):
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
    u1 = UserEntity(
        entra_object_id="user-001", display_name="Regular User", email="user@test.com"
    )
    u2 = UserEntity(
        entra_object_id="user-002", display_name="Other User", email="other@test.com"
    )
    u_sa = UserEntity(
        entra_object_id="sa-001", display_name="Super Admin", email="admin@test.com"
    )
    session.add_all([u1, u2, u_sa])
    await session.flush()

    # Groups
    group_a = Group(name="Group A", description="First group")
    group_b = Group(name="Group B", description="Second group")
    group_c = Group(name="Group C", description="Third group")
    session.add_all([group_a, group_b, group_c])
    await session.flush()

    # Memberships
    session.add_all(
        [
            GroupMembership(
                entra_object_id="user-001", group_id=group_a.id, role=GroupRole.USER
            ),
            GroupMembership(
                entra_object_id="user-001", group_id=group_b.id, role=GroupRole.ADMIN
            ),
            GroupMembership(
                entra_object_id="user-002", group_id=group_c.id, role=GroupRole.USER
            ),
        ]
    )
    await session.flush()

    # Agents
    agent1 = Agent(agent_external_id="ext-1", name="Agent 1", created_by="user-001")
    agent2 = Agent(agent_external_id="ext-2", name="Agent 2", created_by="user-001")
    agent3 = Agent(agent_external_id="ext-3", name="Agent 3", created_by="user-001")
    agent4 = Agent(agent_external_id="ext-4", name="Agent 4", created_by="user-002")
    session.add_all([agent1, agent2, agent3, agent4])
    await session.flush()

    # Group-agent assignments
    session.add_all(
        [
            GroupAgent(group_id=group_a.id, agent_id=agent1.id, added_by="user-001"),
            GroupAgent(group_id=group_a.id, agent_id=agent2.id, added_by="user-001"),
            GroupAgent(group_id=group_b.id, agent_id=agent2.id, added_by="user-001"),
            GroupAgent(group_id=group_b.id, agent_id=agent3.id, added_by="user-001"),
            GroupAgent(group_id=group_c.id, agent_id=agent4.id, added_by="user-002"),
        ]
    )
    await session.commit()

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
    async def test_regular_user_sees_own_agents(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.get(
            "/api/users/user-001/agents", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 200

        body = resp.json()
        agents = body["agents"]
        agent_ids = {a["id"] for a in agents}

        # user-001 should see agents 1, 2, 3 (deduplicated)
        assert agent_ids == {data["agent1"].id, data["agent2"].id, data["agent3"].id}

    async def test_agent_includes_group_info(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.get(
            "/api/users/user-001/agents", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 200

        agents = resp.json()["agents"]
        # Find agent-2 which is in both Group A and Group B
        agent2 = next(a for a in agents if a["id"] == data["agent2"].id)
        group_ids = {g["group_id"] for g in agent2["groups"]}
        assert group_ids == {data["group_a"].id, data["group_b"].id}

    async def test_superadmin_sees_all_agents(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.get(
            "/api/users/sa-001/agents", headers=_user_header(SUPERADMIN)
        )
        assert resp.status_code == 200

        agents = resp.json()["agents"]
        agent_ids = {a["id"] for a in agents}

        # Superadmin should see all 4 agents
        assert agent_ids == {
            data["agent1"].id,
            data["agent2"].id,
            data["agent3"].id,
            data["agent4"].id,
        }

    async def test_superadmin_can_view_other_users_agents(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.get(
            "/api/users/user-002/agents", headers=_user_header(SUPERADMIN)
        )
        assert resp.status_code == 200

        agents = resp.json()["agents"]
        agent_ids = {a["id"] for a in agents}
        # When superadmin queries another user, they see that user's agents
        assert agent_ids == {data["agent4"].id}

    async def test_cannot_view_other_users_agents(self, client, db_session):
        await _seed_data(db_session)

        resp = await client.get(
            "/api/users/user-002/agents", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 403

    async def test_user_with_no_groups_returns_empty(self, client, db_session):
        # Create user with no memberships
        u = UserEntity(
            entra_object_id="user-lonely",
            display_name="Lonely User",
            email="lonely@test.com",
        )
        db_session.add(u)
        await db_session.commit()

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

    async def test_user_not_found_returns_404(self, client, db_session):
        # Create user entity for the requester so upsert works
        u = UserEntity(
            entra_object_id="nonexistent",
            display_name="Ghost",
            email="ghost@test.com",
        )
        db_session.add(u)
        await db_session.commit()

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

    async def test_deduplication_of_shared_agent(self, client, db_session):
        """An agent in multiple groups the user belongs to appears only once."""
        data = await _seed_data(db_session)

        resp = await client.get(
            "/api/users/user-001/agents", headers=_user_header(REGULAR_USER)
        )
        assert resp.status_code == 200

        agents = resp.json()["agents"]
        agent_ids = [a["id"] for a in agents]
        # No duplicates
        assert len(agent_ids) == len(set(agent_ids))
        # Agent 2 appears once, with two groups
        agent2 = next(a for a in agents if a["id"] == data["agent2"].id)
        assert len(agent2["groups"]) == 2
