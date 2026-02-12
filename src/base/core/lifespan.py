import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import src.domain.models.entities  # noqa: F401 — register ORM models with Base.metadata
from src.base.config.database import close_db, init_db
from src.base.config.logging_config import LoggingConfig
from src.base.config.redis import close_redis, init_redis
from src.base.config.redis_cache import RedisCache
from src.domain.services.admin_service import AdminService
from src.domain.services.agent_service import AgentService
from src.domain.services.group_service import GroupService
from src.domain.services.membership_service import MembershipService
from src.domain.services.permission_service import PermissionService
from src.domain.services.user_service import UserService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Centralized initialization and teardown for app services."""
    logger.info("Starting application lifespan...")

    # Start Splunk handler async worker (if configured)
    if LoggingConfig.splunk_handler:
        await LoggingConfig.splunk_handler.start()
        logger.info("Splunk HEC handler started.")

    # Initialize database
    engine, session_factory = await init_db()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # Initialize Redis
    redis_client = await init_redis()
    app.state.redis_client = redis_client

    # Initialize registries/services
    logger.info("Initializing services...")
    cache = RedisCache(redis_client)
    app.state.admin_service = AdminService()
    app.state.agent_service = AgentService()
    app.state.group_service = GroupService()
    app.state.membership_service = MembershipService()
    app.state.permission_service = PermissionService(cache)
    app.state.user_service = UserService()

    logger.info("Services initialized.")
    yield  # --- Application runs here ---

    # Shutdown: close Redis connection
    await close_redis(app.state.redis_client)

    # Shutdown: close database connections
    await close_db(app.state.db_engine)

    # Gracefully stop Splunk handler (flush remaining logs)
    if LoggingConfig.splunk_handler:
        logger.info("Stopping Splunk HEC handler...")
        await LoggingConfig.splunk_handler.stop()
