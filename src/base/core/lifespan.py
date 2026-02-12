import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import src.domain.models.entities  # noqa: F401 — register ORM models with Base.metadata
from src.base.config.database import close_db, init_db
from src.base.config.logging_config import LoggingConfig
from src.domain.services.example_service import ExampleService
from src.domain.services.group_service import GroupService
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

    # Initialize registries/services
    logger.info("Initializing services...")
    app.state.example_service = ExampleService()
    app.state.group_service = GroupService()
    app.state.user_service = UserService()

    logger.info("Services initialized.")
    yield  # --- Application runs here ---

    # Shutdown: close database connections
    await close_db(app.state.db_engine)

    # Gracefully stop Splunk handler (flush remaining logs)
    if LoggingConfig.splunk_handler:
        logger.info("Stopping Splunk HEC handler...")
        await LoggingConfig.splunk_handler.stop()
