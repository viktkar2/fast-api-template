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
from src.domain.routes.admin_routes import router
from src.domain.services.admin_service import AdminService
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


@pytest.fixture
def app(db_session_factory):
    test_app = FastAPI()
    test_app.state.db_session_factory = db_session_factory
    test_app.state.admin_service = AdminService()
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
    - Group A: user-001 (admin), agent-1, agent-2
    - Group B: user-001 (user), agent-2, agent-3
    - Group C: (no members), agent-4
    """
    u1 = UserEntity(
        entra_object_id="user-001", display_name="Regular User", email="user@test.com"
    )
    u_sa = UserEntity(
        entra_object_id="sa-001", display_name="Super Admin", email="admin@test.com"
    )
    session.add_all([u1, u_sa])
    await session.flush()

    group_a = Group(name="Group A", description="First group")
    group_b = Group(name="Group B", description="Second group")
    group_c = Group(name="Group C", description="Third group")
    session.add_all([group_a, group_b, group_c])
    await session.flush()

    session.add_all(
        [
            GroupMembership(
                entra_object_id="user-001", group_id=group_a.id, role=GroupRole.ADMIN
            ),
            GroupMembership(
                entra_object_id="user-001", group_id=group_b.id, role=GroupRole.USER
            ),
        ]
    )
    await session.flush()

    agent1 = Agent(agent_external_id="ext-1", name="Agent 1", created_by="user-001")
    agent2 = Agent(agent_external_id="ext-2", name="Agent 2", created_by="user-001")
    agent3 = Agent(agent_external_id="ext-3", name="Agent 3", created_by="user-001")
    agent4 = Agent(agent_external_id="ext-4", name="Agent 4", created_by="sa-001")
    session.add_all([agent1, agent2, agent3, agent4])
    await session.flush()

    session.add_all(
        [
            GroupAgent(group_id=group_a.id, agent_id=agent1.id, added_by="user-001"),
            GroupAgent(group_id=group_a.id, agent_id=agent2.id, added_by="user-001"),
            GroupAgent(group_id=group_b.id, agent_id=agent2.id, added_by="user-001"),
            GroupAgent(group_id=group_b.id, agent_id=agent3.id, added_by="user-001"),
            GroupAgent(group_id=group_c.id, agent_id=agent4.id, added_by="sa-001"),
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


class TestListAllAgents:
    async def test_superadmin_lists_all_agents(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.get("/api/admin/agents", headers=_user_header(SUPERADMIN))
        assert resp.status_code == 200

        agents = resp.json()["agents"]
        agent_ids = {a["id"] for a in agents}
        assert agent_ids == {
            data["agent1"].id,
            data["agent2"].id,
            data["agent3"].id,
            data["agent4"].id,
        }

    async def test_agents_include_group_info(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.get("/api/admin/agents", headers=_user_header(SUPERADMIN))
        agents = resp.json()["agents"]
        # Agent 2 is in both Group A and Group B
        agent2 = next(a for a in agents if a["id"] == data["agent2"].id)
        group_ids = {g["group_id"] for g in agent2["groups"]}
        assert group_ids == {data["group_a"].id, data["group_b"].id}

    async def test_non_superadmin_gets_403(self, client, db_session):
        await _seed_data(db_session)

        resp = await client.get("/api/admin/agents", headers=_user_header(REGULAR_USER))
        assert resp.status_code == 403


class TestListAllGroups:
    async def test_superadmin_lists_all_groups_with_counts(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.get("/api/admin/groups", headers=_user_header(SUPERADMIN))
        assert resp.status_code == 200

        groups = resp.json()["groups"]
        groups_by_id = {g["id"]: g for g in groups}

        assert set(groups_by_id.keys()) == {
            data["group_a"].id,
            data["group_b"].id,
            data["group_c"].id,
        }
        # Group A has 1 member (user-001), Group B has 1 member, Group C has 0
        assert groups_by_id[data["group_a"].id]["member_count"] == 1
        assert groups_by_id[data["group_b"].id]["member_count"] == 1
        assert groups_by_id[data["group_c"].id]["member_count"] == 0

    async def test_non_superadmin_gets_403(self, client, db_session):
        await _seed_data(db_session)

        resp = await client.get("/api/admin/groups", headers=_user_header(REGULAR_USER))
        assert resp.status_code == 403


class TestBulkUpdateAgentGroups:
    async def test_superadmin_bulk_updates_groups(self, client, db_session):
        data = await _seed_data(db_session)

        # Move agent1 from Group A only to Group B and Group C
        resp = await client.put(
            f"/api/admin/agents/{data['agent1'].id}/groups",
            json={"group_ids": [data["group_b"].id, data["group_c"].id]},
            headers=_user_header(SUPERADMIN),
        )
        assert resp.status_code == 200

        agent = resp.json()["agent"]
        assert agent["id"] == data["agent1"].id
        group_ids = {g["group_id"] for g in agent["groups"]}
        assert group_ids == {data["group_b"].id, data["group_c"].id}

    async def test_non_superadmin_gets_403(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.put(
            f"/api/admin/agents/{data['agent1'].id}/groups",
            json={"group_ids": [data["group_a"].id]},
            headers=_user_header(REGULAR_USER),
        )
        assert resp.status_code == 403

    async def test_nonexistent_agent_returns_404(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.put(
            "/api/admin/agents/9999/groups",
            json={"group_ids": [data["group_a"].id]},
            headers=_user_header(SUPERADMIN),
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Agent not found"

    async def test_nonexistent_group_returns_404(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.put(
            f"/api/admin/agents/{data['agent1'].id}/groups",
            json={"group_ids": [9999]},
            headers=_user_header(SUPERADMIN),
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "One or more groups not found"

    async def test_empty_group_ids_rejected(self, client, db_session):
        data = await _seed_data(db_session)

        resp = await client.put(
            f"/api/admin/agents/{data['agent1'].id}/groups",
            json={"group_ids": []},
            headers=_user_header(SUPERADMIN),
        )
        assert resp.status_code == 422
