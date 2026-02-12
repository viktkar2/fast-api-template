import json
import logging

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.entities.enums import GroupRole
from src.domain.models.entities.group_agent import GroupAgent
from src.domain.models.entities.group_membership import GroupMembership
from src.domain.models.permission_schemas import PermissionAction

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60


class PermissionService:
    def __init__(self, redis_client: Redis | None = None):
        self._redis = redis_client

    def _cache_key(self, user_id: str, agent_id: int, action: str) -> str:
        return f"perm:{user_id}:{agent_id}:{action}"

    async def _get_cached(self, key: str) -> tuple[bool, str | None] | None:
        if not self._redis:
            return None
        try:
            value = await self._redis.get(key)
            if value is not None:
                data = json.loads(value)
                return data["allowed"], data.get("role")
        except Exception:
            logger.warning("Redis cache read failed", exc_info=True)
        return None

    async def _set_cached(self, key: str, allowed: bool, role: str | None) -> None:
        if not self._redis:
            return
        try:
            value = json.dumps({"allowed": allowed, "role": role})
            await self._redis.set(key, value, ex=CACHE_TTL_SECONDS)
        except Exception:
            logger.warning("Redis cache write failed", exc_info=True)

    async def check_permission(
        self,
        session: AsyncSession,
        user_id: str,
        agent_id: int,
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
        cached = await self._get_cached(key)
        if cached is not None:
            return cached

        # Query DB: join group_memberships with group_agents on group_id
        stmt = (
            select(GroupMembership.role)
            .join(GroupAgent, GroupMembership.group_id == GroupAgent.group_id)
            .where(
                GroupMembership.entra_object_id == user_id,
                GroupAgent.agent_id == agent_id,
            )
        )

        if action == PermissionAction.CREATE:
            stmt = stmt.where(GroupMembership.role == GroupRole.ADMIN)

        result = await session.execute(stmt)
        roles = [row[0] for row in result.all()]

        if not roles:
            await self._set_cached(key, False, None)
            return False, None

        # Determine highest role: admin > user
        if GroupRole.ADMIN in roles:
            highest = "admin"
        else:
            highest = "user"

        await self._set_cached(key, True, highest)
        return True, highest

    async def invalidate_user_permissions(self, user_id: str) -> None:
        """Delete all cached permissions for a user."""
        if not self._redis:
            return
        try:
            pattern = f"perm:{user_id}:*"
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            logger.warning(
                "Redis invalidation failed for user %s", user_id, exc_info=True
            )

    async def invalidate_agent_permissions(self, agent_id: int) -> None:
        """Delete all cached permissions for an agent."""
        if not self._redis:
            return
        try:
            pattern = f"perm:*:{agent_id}:*"
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            logger.warning(
                "Redis invalidation failed for agent %s", agent_id, exc_info=True
            )
