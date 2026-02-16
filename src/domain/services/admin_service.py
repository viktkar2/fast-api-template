import logging

from beanie import PydanticObjectId

from src.domain.models.entities.agent import AgentDocument
from src.domain.models.entities.group import GroupDocument
from src.domain.models.entities.group_agent import GroupAgentDocument
from src.domain.models.entities.group_membership import GroupMembershipDocument

logger = logging.getLogger(__name__)


class AdminService:
    async def list_all_agents(self) -> list[dict]:
        """Return all agents with their group assignments."""
        gas = await GroupAgentDocument.find_all().to_list()
        if not gas:
            return []

        agent_ids = list({ga.agent_id for ga in gas})
        group_ids = list({ga.group_id for ga in gas})
        agents = await AgentDocument.find({"_id": {"$in": agent_ids}}).to_list()
        groups = await GroupDocument.find({"_id": {"$in": group_ids}}).to_list()
        agent_map = {a.id: a for a in agents}
        group_map = {g.id: g for g in groups}

        agents_out: dict = {}
        for ga in gas:
            a = agent_map.get(ga.agent_id)
            g = group_map.get(ga.group_id)
            if not a or not g:
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

    async def list_all_groups_with_counts(self) -> list[dict]:
        """Return all groups with their member counts."""
        pipeline = [
            {"$group": {"_id": "$group_id", "count": {"$sum": 1}}},
        ]
        raw = await GroupMembershipDocument.aggregate(pipeline).to_list()
        count_map = {doc["_id"]: doc["count"] for doc in raw}

        groups = await GroupDocument.find_all().to_list()
        return [
            {
                "id": str(g.id),
                "name": g.name,
                "description": g.description,
                "created_at": g.created_at,
                "updated_at": g.updated_at,
                "member_count": count_map.get(g.id, 0),
            }
            for g in groups
        ]

    async def bulk_update_agent_groups(
        self,
        agent_id: PydanticObjectId,
        group_ids: list[PydanticObjectId],
        updated_by: str,
    ) -> dict:
        """Replace an agent's group assignments.

        Raises ValueError("agent_not_found") if agent doesn't exist.
        Raises ValueError("group_not_found") if any group_id doesn't exist.
        """
        agent = await AgentDocument.get(agent_id)
        if agent is None:
            raise ValueError("agent_not_found")

        existing_groups = await GroupDocument.find(
            {"_id": {"$in": group_ids}}
        ).to_list()
        if len(existing_groups) != len(group_ids):
            raise ValueError("group_not_found")

        # Delete old assignments
        await GroupAgentDocument.find(GroupAgentDocument.agent_id == agent_id).delete()

        # Insert new assignments
        new_gas = [
            GroupAgentDocument(group_id=gid, agent_id=agent_id, added_by=updated_by)
            for gid in group_ids
        ]
        if new_gas:
            await GroupAgentDocument.insert_many(new_gas)

        # Build response
        group_map = {g.id: g for g in existing_groups}
        groups = [
            {"group_id": str(gid), "group_name": group_map[gid].name}
            for gid in group_ids
        ]

        logger.info(
            "Bulk-updated agent_id=%s group assignments to group_ids=%s by=%s",
            agent_id,
            group_ids,
            updated_by,
        )

        return {
            "id": str(agent.id),
            "agent_external_id": agent.agent_external_id,
            "name": agent.name,
            "created_by": agent.created_by,
            "created_at": agent.created_at,
            "groups": groups,
        }
