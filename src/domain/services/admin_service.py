import logging

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.entities.agent import Agent
from src.domain.models.entities.group import Group
from src.domain.models.entities.group_agent import GroupAgent
from src.domain.models.entities.group_membership import GroupMembership

logger = logging.getLogger(__name__)


class AdminService:
    async def list_all_agents(self, session: AsyncSession) -> list[dict]:
        """Return all agents with their group assignments."""
        result = await session.execute(
            select(Agent, Group.id, Group.name)
            .join(GroupAgent, GroupAgent.agent_id == Agent.id)
            .join(Group, Group.id == GroupAgent.group_id)
            .order_by(Agent.id, Group.id)
        )
        rows = result.all()

        agents_map: dict[int, dict] = {}
        for agent, group_id, group_name in rows:
            if agent.id not in agents_map:
                agents_map[agent.id] = {
                    "id": agent.id,
                    "agent_external_id": agent.agent_external_id,
                    "name": agent.name,
                    "created_by": agent.created_by,
                    "created_at": agent.created_at,
                    "groups": [],
                }
            group_entry = {"group_id": group_id, "group_name": group_name}
            if group_entry not in agents_map[agent.id]["groups"]:
                agents_map[agent.id]["groups"].append(group_entry)

        return list(agents_map.values())

    async def list_all_groups_with_counts(self, session: AsyncSession) -> list[dict]:
        """Return all groups with their member counts."""
        result = await session.execute(
            select(
                Group,
                func.count(GroupMembership.id).label("member_count"),
            )
            .outerjoin(GroupMembership, GroupMembership.group_id == Group.id)
            .group_by(Group.id)
            .order_by(Group.id)
        )
        rows = result.all()

        return [
            {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "created_at": group.created_at,
                "updated_at": group.updated_at,
                "member_count": member_count,
            }
            for group, member_count in rows
        ]

    async def bulk_update_agent_groups(
        self,
        session: AsyncSession,
        agent_id: int,
        group_ids: list[int],
        updated_by: str,
    ) -> dict:
        """Replace an agent's group assignments atomically.

        Raises ValueError("agent_not_found") if agent doesn't exist.
        Raises ValueError("group_not_found") if any group_id doesn't exist.
        """
        # Verify agent exists
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError("agent_not_found")

        # Verify all groups exist
        result = await session.execute(select(Group.id).where(Group.id.in_(group_ids)))
        found_ids = {row[0] for row in result.all()}
        missing = set(group_ids) - found_ids
        if missing:
            raise ValueError("group_not_found")

        # Delete old assignments
        await session.execute(delete(GroupAgent).where(GroupAgent.agent_id == agent_id))

        # Insert new assignments
        for gid in group_ids:
            session.add(
                GroupAgent(group_id=gid, agent_id=agent_id, added_by=updated_by)
            )

        await session.commit()

        # Build response with new group info
        result = await session.execute(
            select(Group.id, Group.name)
            .join(GroupAgent, GroupAgent.group_id == Group.id)
            .where(GroupAgent.agent_id == agent_id)
            .order_by(Group.id)
        )
        groups = [{"group_id": row[0], "group_name": row[1]} for row in result.all()]

        await session.refresh(agent)

        return {
            "id": agent.id,
            "agent_external_id": agent.agent_external_id,
            "name": agent.name,
            "created_by": agent.created_by,
            "created_at": agent.created_at,
            "groups": groups,
        }
