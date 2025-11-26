import logging
from contextlib import asynccontextmanager

from src.domain.services.example_service import ExampleService
from fastapi import FastAPI


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Centralized initialization and teardown for app services."""
    logger.info("Starting application lifespan...")

    # Initialize registries/services
    logger.info("Initializing services...")
    app.state.example_service = ExampleService()

    logger.info("Services initialized.")
    yield  # --- Application runs here ---
