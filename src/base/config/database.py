import logging
import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


def _get_database_url() -> str:
    """Resolve database URL from environment, defaulting to local SQLite."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    return "sqlite+aiosqlite:///./local.db"


async def init_db() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Initialize the database engine and session factory.

    Returns:
        Tuple of (engine, session_factory).
    """
    url = _get_database_url()

    # Log connection target without credentials
    safe_url = url.split("@")[-1] if "@" in url else url
    logger.info("Connecting to database: %s", safe_url)

    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_async_engine(url, connect_args=connect_args)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Schema management is handled by Alembic migrations.
    # Run `uv run alembic upgrade head` to apply pending migrations.

    return engine, session_factory


async def close_db(engine: AsyncEngine) -> None:
    """Dispose the database engine and release connections."""
    if engine:
        await engine.dispose()
        logger.info("Database connection closed.")
        logger.info("Database connection closed.")
