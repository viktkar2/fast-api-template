import logging

from beanie import PydanticObjectId

from src.domain.models.entities.agent import AgentDocument
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group import GroupDocument
from src.domain.models.entities.group_agent import GroupAgentDocument
from src.domain.models.entities.group_membership import GroupMembershipDocument
from src.domain.models.entities.user import UserDocument

logger = logging.getLogger(__name__)


class AgentService:
    async def register_agent(
        self,
        agent_external_id: str,
        name: str,
        group_id: PydanticObjectId,
        created_by: str,
    ) -> AgentDocument:
        """Register a new agent and assign it to the specified group."""
        if not await GroupDocument.get(group_id):
            raise ValueError("group_not_found")

        if await AgentDocument.find_one(
            AgentDocument.agent_external_id == agent_external_id
        ):
            raise ValueError("duplicate_agent")

        agent = AgentDocument(
            agent_external_id=agent_external_id,
            name=name,
            created_by=created_by,
        )
        await agent.insert()

        # Compensating delete if GroupAgent insert fails (no transactions)
        try:
            group_agent = GroupAgentDocument(
                group_id=group_id,
                agent_id=agent.id,
                added_by=created_by,
            )
            await group_agent.insert()
        except Exception:
            await agent.delete()
            raise

        logger.info(
            "Registered agent id=%s external_id=%s in group_id=%s",
            agent.id,
            agent_external_id,
            group_id,
        )
        return agent

    async def assign_agent_to_group(
        self,
        group_id: PydanticObjectId,
        agent_id: PydanticObjectId,
        added_by: str,
    ) -> GroupAgentDocument:
        """Assign an existing agent to an additional group."""
        if not await GroupDocument.get(group_id):
            raise ValueError("group_not_found")

        if not await AgentDocument.get(agent_id):
            raise ValueError("agent_not_found")

        existing = await GroupAgentDocument.find_one(
            GroupAgentDocument.group_id == group_id,
            GroupAgentDocument.agent_id == agent_id,
        )
        if existing:
            raise ValueError("duplicate_assignment")

        group_agent = GroupAgentDocument(
            group_id=group_id,
            agent_id=agent_id,
            added_by=added_by,
        )
        await group_agent.insert()
        logger.info(
            "Assigned agent_id=%s to group_id=%s",
            agent_id,
            group_id,
        )
        return group_agent

    async def remove_agent_from_group(
        self,
        group_id: PydanticObjectId,
        agent_id: PydanticObjectId,
    ) -> bool:
        """Remove an agent from a group."""
        group_agent = await GroupAgentDocument.find_one(
            GroupAgentDocument.group_id == group_id,
            GroupAgentDocument.agent_id == agent_id,
        )
        if group_agent is None:
            raise ValueError("assignment_not_found")

        await group_agent.delete()
        logger.info("Removed agent_id=%s from group_id=%s", agent_id, group_id)
        return True

    async def list_agents_in_group(
        self,
        group_id: PydanticObjectId,
    ) -> list[AgentDocument]:
        """List all agents assigned to a group."""
        if not await GroupDocument.get(group_id):
            raise ValueError("group_not_found")

        gas = await GroupAgentDocument.find(
            GroupAgentDocument.group_id == group_id
        ).to_list()
        agent_ids = [ga.agent_id for ga in gas]
        if not agent_ids:
            return []
        return await AgentDocument.find({"_id": {"$in": agent_ids}}).to_list()

    async def get_admin_groups(
        self,
        entra_object_id: str,
    ) -> list[GroupDocument]:
        """Return groups where the user has admin role."""
        memberships = await GroupMembershipDocument.find(
            GroupMembershipDocument.entra_object_id == entra_object_id,
            GroupMembershipDocument.role == GroupRole.ADMIN,
        ).to_list()
        group_ids = [m.group_id for m in memberships]
        if not group_ids:
            return []
        return await GroupDocument.find({"_id": {"$in": group_ids}}).to_list()

    async def get_user_agents(
        self,
        entra_object_id: str,
        *,
        is_superadmin: bool = False,
    ) -> list[dict]:
        """Return all agents accessible to a user with their group info.

        For superadmins, returns all agents with all their group assignments.
        For regular users, returns agents from groups they belong to.

        Returns a list of dicts with agent fields plus a 'groups' list.
        """
        if is_superadmin:
            gas = await GroupAgentDocument.find_all().to_list()
        else:
            if not await UserDocument.find_one(
                UserDocument.entra_object_id == entra_object_id
            ):
                raise ValueError("user_not_found")

            memberships = await GroupMembershipDocument.find(
                GroupMembershipDocument.entra_object_id == entra_object_id
            ).to_list()
            user_group_ids = [m.group_id for m in memberships]
            if not user_group_ids:
                return []

            gas = await GroupAgentDocument.find(
                {"group_id": {"$in": user_group_ids}}
            ).to_list()

        if not gas:
            return []

        # Fetch all relevant agents and groups
        agent_ids = list({ga.agent_id for ga in gas})
        group_ids = list({ga.group_id for ga in gas})

        agents = await AgentDocument.find({"_id": {"$in": agent_ids}}).to_list()
        groups = await GroupDocument.find({"_id": {"$in": group_ids}}).to_list()

        agent_map = {a.id: a for a in agents}
        group_map = {g.id: g for g in groups}

        # Assemble agent -> groups mapping
        agents_out: dict = {}
        for ga in gas:
            a = agent_map.get(ga.agent_id)
            g = group_map.get(ga.group_id)
            if a is None or g is None:
                continue
            aid = str(a.id)
            if aid not in agents_out:
                agents_out[aid] = {
                    "id": str(a.id),
                    "agent_external_id": a.agent_external_id,
                    "name": a.name,
                    "created_by": a.created_by,
                    "created_at": a.created_at,
                    "groups": [],
                }
            group_entry = {"group_id": str(g.id), "group_name": g.name}
            if group_entry not in agents_out[aid]["groups"]:
                agents_out[aid]["groups"].append(group_entry)

        return list(agents_out.values())
