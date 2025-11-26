import uuid
import logging
from contextvars import ContextVar
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to store correlation ID
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to each request for better log tracing."""

    async def dispatch(self, request: Request, call_next):
        # Get correlation ID from header or generate new one
        correlation_id_value = request.headers.get(
            "x-correlation-id", str(uuid.uuid4())
        )

        # Set correlation ID in context
        correlation_id.set(correlation_id_value)

        logger = logging.getLogger(__name__)
        logger.info("Assigned correlation ID to request")

        # Process request
        response: Response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["x-correlation-id"] = correlation_id_value

        return response


class CorrelationFilter(logging.Filter):
    """Logging filter to add correlation ID to log records."""

    def filter(self, record):
        record.correlation_id = correlation_id.get("")
        return True
