import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient

from src.base.utils.env_utils import is_local_development

logger = logging.getLogger(__name__)


def _get_mongo_uri() -> str:
    """Resolve MongoDB URI from environment, defaulting to local mongod."""
    uri = os.getenv("MONGODB_URI")
    if not uri:
        uri = "mongodb://localhost:27017"
    return uri


def _get_database_name() -> str:
    """Resolve MongoDB database name from environment."""
    return os.getenv("MONGODB_DATABASE", "sidekick")


async def init_db() -> AsyncIOMotorClient:
    """Create and return a Motor client.

    In local development, falls back to an in-memory mock database
    when no real MongoDB instance is reachable.
    """
    uri = _get_mongo_uri()
    safe_uri = uri.split("@")[-1] if "@" in uri else uri
    logger.info("Connecting to MongoDB: %s", safe_uri)
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)

    # Motor is lazy — force a connection check so we fail fast
    try:
        await client.admin.command("ping")
        logger.info("MongoDB connection established.")
    except Exception:
        client.close()

        if not is_local_development():
            raise

        logger.warning(
            "MongoDB not reachable at %s — falling back to in-memory mock database. "
            "Data will not persist across restarts.",
            safe_uri,
        )
        from mongomock_motor import AsyncMongoMockClient

        client = AsyncMongoMockClient()

    return client


async def close_db(client: AsyncIOMotorClient) -> None:
    """Close the Motor client."""
    if client:
        client.close()
        logger.info("MongoDB connection closed.")
