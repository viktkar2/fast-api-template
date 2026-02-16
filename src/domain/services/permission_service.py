import json
import logging

from beanie import PydanticObjectId

from src.base.infra.redis_cache import RedisCache
from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group_agent import GroupAgentDocument
from src.domain.models.entities.group_membership import GroupMembershipDocument
from src.domain.models.permission_schemas import PermissionAction

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60


class PermissionService:
    def __init__(self, cache: RedisCache):
        self._cache = cache

    def _cache_key(self, user_id: str, agent_id: str, action: str) -> str:
        return f"perm:{user_id}:{agent_id}:{action}"

    def _user_agents_key(self, user_id: str) -> str:
        return f"user_agents:{user_id}"

    async def check_permission(
        self,
        user_id: str,
        agent_id: str,
        action: PermissionAction,
        *,
        is_superadmin: bool = False,
    ) -> tuple[bool, str | None]:
        """Check whether a user can perform an action on an agent.

        Returns (allowed, role) where role is the user's highest relevant role.
        """
        if is_superadmin:
            return True, "superadmin"

        key = self._cache_key(user_id, agent_id, action.value)
        cached = await self._cache.get(key)
        if cached is not None:
            data = json.loads(cached)
            return data["allowed"], data.get("role")

        # Find groups this agent belongs to
        agent_oid = PydanticObjectId(agent_id)
        gas = await GroupAgentDocument.find(
            GroupAgentDocument.agent_id == agent_oid
        ).to_list()
        group_ids = [ga.group_id for ga in gas]

        if not group_ids:
            value = json.dumps({"allowed": False, "role": None})
            await self._cache.set(key, value, CACHE_TTL_SECONDS)
            return False, None

        # Find user's memberships in those groups
        query_filter = {
            "group_id": {"$in": group_ids},
            "entra_object_id": user_id,
        }
        if action == PermissionAction.CREATE:
            query_filter["role"] = GroupRole.ADMIN.value

        memberships = await GroupMembershipDocument.find(query_filter).to_list()
        roles = [m.role for m in memberships]

        if not roles:
            value = json.dumps({"allowed": False, "role": None})
            await self._cache.set(key, value, CACHE_TTL_SECONDS)
            return False, None

        # Determine highest role: admin > user
        highest = "admin" if GroupRole.ADMIN in roles else "user"

        value = json.dumps({"allowed": True, "role": highest})
        await self._cache.set(key, value, CACHE_TTL_SECONDS)
        return True, highest

    async def get_cached_user_agents(self, user_id: str) -> list[dict] | None:
        """Return cached user agents list, or None if not cached."""
        value = await self._cache.get(self._user_agents_key(user_id))
        if value is not None:
            return json.loads(value)
        return None

    async def set_cached_user_agents(self, user_id: str, agents: list[dict]) -> None:
        """Cache the user agents list."""
        value = json.dumps(agents, default=str)
        await self._cache.set(self._user_agents_key(user_id), value, CACHE_TTL_SECONDS)

    async def invalidate_user_permissions(self, user_id: str) -> None:
        """Delete all cached permissions and user agents list for a user."""
        await self._cache.delete_pattern(f"perm:{user_id}:*")
        await self._cache.delete(self._user_agents_key(user_id))
        logger.info("Invalidated permission cache for user_id=%s", user_id)

    async def invalidate_agent_permissions(self, agent_id: str) -> None:
        """Delete all cached permissions for an agent and affected user agent lists."""
        await self._cache.delete_pattern(f"perm:*:{agent_id}:*")
        await self._cache.delete_pattern("user_agents:*")
        logger.info("Invalidated permission cache for agent_id=%s", agent_id)
