import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient

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
    """Create and return a Motor client."""
    uri = _get_mongo_uri()
    safe_uri = uri.split("@")[-1] if "@" in uri else uri
    logger.info("Connecting to MongoDB: %s", safe_uri)
    client = AsyncIOMotorClient(uri)
    return client


async def close_db(client: AsyncIOMotorClient) -> None:
    """Close the Motor client."""
    if client:
        client.close()
        logger.info("MongoDB connection closed.")
