import logging

from dotenv import load_dotenv
from fastapi import FastAPI

from src.base.config.logging_config import LoggingConfig
from src.base.config.openapi_config import setup_openapi
from src.base.core.lifespan import lifespan
from src.base.middleware.correlation_middleware import CorrelationMiddleware
from src.base.middleware.global_exception_handler_middleware import (
    GlobalExceptionHandlerMiddleware,
)
from src.base.middleware.jwt_middleware import JWTMiddleware
from src.base.routes.health import router as health_router
from src.domain.routes.group_routes import router as group_router
from src.domain.routes.rest_routes_example import router as rest_router

# Load environment variables
load_dotenv()

# --- Logging configuration ---
LoggingConfig.setup_logging()
logger = logging.getLogger(__name__)

logger.info("Starting FastAPI application")

# --- FastAPI app ---
app = FastAPI(title="FastAPI OpenAPI Playground", version="1.0.0", lifespan=lifespan)

# Setup OpenAPI configuration
setup_openapi(app)

# --- Middleware ---
app.add_middleware(JWTMiddleware)
app.add_middleware(CorrelationMiddleware)
app.add_middleware(GlobalExceptionHandlerMiddleware)

# --- Routes ---
app.include_router(health_router, prefix="/api")
app.include_router(group_router, prefix="/api")
app.include_router(rest_router, prefix="/api")
