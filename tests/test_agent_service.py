import pytest
from beanie import PydanticObjectId

from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import GroupDocument
from src.domain.models.entities.group_membership import GroupMembershipDocument
from src.domain.models.entities.user import UserDocument
from src.domain.services.agent_service import AgentService


async def _seed():
    """Create users and groups.

    Layout:
    - Group A: user-001 (admin)
    - Group B: user-001 (user)
    """
    await UserDocument(
        entra_object_id="user-001", display_name="Alice", email="alice@test.com"
    ).insert()
    await UserDocument(
        entra_object_id="user-002", display_name="Bob", email="bob@test.com"
    ).insert()

    ga = GroupDocument(name="Group A")
    gb = GroupDocument(name="Group B")
    await ga.insert()
    await gb.insert()

    await GroupMembershipDocument(
        entra_object_id="user-001", group_id=ga.id, role=GroupRole.ADMIN
    ).insert()
    await GroupMembershipDocument(
        entra_object_id="user-001", group_id=gb.id, role=GroupRole.USER
    ).insert()

    return {"ga": ga, "gb": gb}


@pytest.fixture
def service():
    return AgentService()


class TestRegisterAgent:
    async def test_register_agent_success(self, service):
        data = await _seed()
        agent = await service.register_agent(
            "ext-100", "My Agent", data["ga"].id, "user-001"
        )
        assert agent.agent_external_id == "ext-100"
        assert agent.name == "My Agent"
        assert agent.created_by == "user-001"

    async def test_register_agent_creates_group_assignment(self, service):
        data = await _seed()
        agent = await service.register_agent(
            "ext-100", "My Agent", data["ga"].id, "user-001"
        )
        agents = await service.list_agents_in_group(data["ga"].id)
        assert any(a.id == agent.id for a in agents)

    async def test_register_agent_group_not_found(self, service):
        await _seed()
        with pytest.raises(ValueError, match="group_not_found"):
            await service.register_agent(
                "ext-100", "Agent", PydanticObjectId(), "user-001"
            )

    async def test_register_agent_duplicate_external_id(self, service):
        data = await _seed()
        await service.register_agent(
            "ext-100", "First", data["ga"].id, "user-001"
        )
        with pytest.raises(ValueError, match="duplicate_agent"):
            await service.register_agent(
                "ext-100", "Second", data["ga"].id, "user-001"
            )


class TestAssignAgentToGroup:
    async def test_assign_to_additional_group(self, service):
        data = await _seed()
        agent = await service.register_agent(
            "ext-100", "Agent", data["ga"].id, "user-001"
        )
        ga_entry = await service.assign_agent_to_group(
            data["gb"].id, agent.id, "user-001"
        )
        assert ga_entry.group_id == data["gb"].id
        assert ga_entry.agent_id == agent.id

    async def test_assign_group_not_found(self, service):
        data = await _seed()
        agent = await service.register_agent(
            "ext-100", "Agent", data["ga"].id, "user-001"
        )
        with pytest.raises(ValueError, match="group_not_found"):
            await service.assign_agent_to_group(
                PydanticObjectId(), agent.id, "user-001"
            )

    async def test_assign_agent_not_found(self, service):
        data = await _seed()
        with pytest.raises(ValueError, match="agent_not_found"):
            await service.assign_agent_to_group(
                data["ga"].id, PydanticObjectId(), "user-001"
            )

    async def test_assign_duplicate(self, service):
        data = await _seed()
        agent = await service.register_agent(
            "ext-100", "Agent", data["ga"].id, "user-001"
        )
        with pytest.raises(ValueError, match="duplicate_assignment"):
            await service.assign_agent_to_group(
                data["ga"].id, agent.id, "user-001"
            )


class TestRemoveAgentFromGroup:
    async def test_remove_success(self, service):
        data = await _seed()
        agent = await service.register_agent(
            "ext-100", "Agent", data["ga"].id, "user-001"
        )
        result = await service.remove_agent_from_group(
            data["ga"].id, agent.id
        )
        assert result is True
        agents = await service.list_agents_in_group(data["ga"].id)
        assert len(agents) == 0

    async def test_remove_not_found(self, service):
        data = await _seed()
        with pytest.raises(ValueError, match="assignment_not_found"):
            await service.remove_agent_from_group(
                data["ga"].id, PydanticObjectId()
            )


class TestListAgentsInGroup:
    async def test_list_agents(self, service):
        data = await _seed()
        await service.register_agent(
            "ext-1", "Agent 1", data["ga"].id, "user-001"
        )
        await service.register_agent(
            "ext-2", "Agent 2", data["ga"].id, "user-001"
        )
        agents = await service.list_agents_in_group(data["ga"].id)
        assert len(agents) == 2

    async def test_list_agents_empty_group(self, service):
        data = await _seed()
        agents = await service.list_agents_in_group(data["ga"].id)
        assert agents == []

    async def test_list_agents_group_not_found(self, service):
        with pytest.raises(ValueError, match="group_not_found"):
            await service.list_agents_in_group(PydanticObjectId())


class TestGetAdminGroups:
    async def test_returns_only_admin_groups(self, service):
        data = await _seed()
        groups = await service.get_admin_groups("user-001")
        group_ids = {g.id for g in groups}
        # user-001 is admin of Group A only
        assert group_ids == {data["ga"].id}

    async def test_user_with_no_admin_groups(self, service):
        await _seed()
        groups = await service.get_admin_groups("user-002")
        assert groups == []
