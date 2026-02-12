import logging
import os

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def _create_entra_client(host: str, port: int) -> Redis:
    """Create a Redis client authenticated via Entra ID."""
    from redis_entraid.cred_provider import create_from_default_azure_credential

    cred_provider = create_from_default_azure_credential(
        scopes=("https://redis.azure.com/.default",),
    )
    return Redis(
        host=host,
        port=port,
        ssl=True,
        credential_provider=cred_provider,
        decode_responses=True,
    )


async def init_redis() -> Redis | None:
    """Initialize Redis client.

    Connection strategy (first match wins):
    1. REDIS_URL set       → connect via URL (local dev / Docker)
    2. REDIS_HOST set      → connect via Entra ID auth (Azure production)
    3. Neither set         → run without cache, return None
    """
    url = os.getenv("REDIS_URL")
    host = os.getenv("REDIS_HOST")

    if url:
        logger.info("Connecting to Redis via URL...")
        client = Redis.from_url(url, decode_responses=True)
    elif host:
        port = int(os.getenv("REDIS_PORT", "6380"))
        logger.info("Connecting to Redis at %s:%d via Entra ID...", host, port)
        client = _create_entra_client(host, port)
    else:
        logger.info("REDIS_URL/REDIS_HOST not set — running without Redis cache.")
        return None

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
