import logging
import os

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


async def init_redis() -> Redis | None:
    """Initialize Redis client from REDIS_URL env var.

    Returns None if REDIS_URL is not configured, allowing the app
    to run without caching (every permission check hits the DB).
    """
    url = os.getenv("REDIS_URL")
    if not url:
        logger.info("REDIS_URL not set — running without Redis cache.")
        return None

    logger.info("Connecting to Redis...")
    client = Redis.from_url(url, decode_responses=True)
    # Verify connectivity
    try:
        await client.ping()
        logger.info("Redis connection established.")
    except Exception:
        logger.warning("Redis ping failed — running without cache.", exc_info=True)
        await client.aclose()
        return None

    return client


async def close_redis(client: Redis | None) -> None:
    """Gracefully close the Redis connection."""
    if client:
        await client.aclose()
        logger.info("Redis connection closed.")
