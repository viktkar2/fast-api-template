import logging
from contextlib import asynccontextmanager

from src.base.config.logging_config import LoggingConfig
from src.domain.services.example_service import ExampleService
from fastapi import FastAPI


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Centralized initialization and teardown for app services."""
    logger.info("Starting application lifespan...")

    # Start Splunk handler async worker (if configured)
    if LoggingConfig.splunk_handler:
        await LoggingConfig.splunk_handler.start()
        logger.info("Splunk HEC handler started.")

    # Initialize registries/services
    logger.info("Initializing services...")
    app.state.example_service = ExampleService()

    logger.info("Services initialized.")
    yield  # --- Application runs here ---

    # Gracefully stop Splunk handler (flush remaining logs)
    if LoggingConfig.splunk_handler:
        logger.info("Stopping Splunk HEC handler...")
        await LoggingConfig.splunk_handler.stop()
