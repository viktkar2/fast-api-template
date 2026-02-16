import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisCache:
    """Thin wrapper around redis.asyncio.Redis providing safe cache operations.

    All methods are no-ops when Redis is None (graceful degradation).
    All methods catch exceptions and log warnings.
    """

    def __init__(self, redis_client: Redis | None = None):
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception:
            logger.warning("Redis cache read failed", exc_info=True)
            return None

    async def set(self, key: str, value: str, ttl: int) -> None:
        if not self._redis:
            return
        try:
            await self._redis.set(key, value, ex=ttl)
        except Exception:
            logger.warning("Redis cache write failed", exc_info=True)

    async def delete(self, *keys: str) -> None:
        if not self._redis or not keys:
            return
        try:
            await self._redis.delete(*keys)
        except Exception:
            logger.warning("Redis cache delete failed", exc_info=True)

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching a glob pattern using SCAN."""
        if not self._redis:
            return
        try:
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
                "Redis cache delete_pattern failed for %s", pattern, exc_info=True
            )
