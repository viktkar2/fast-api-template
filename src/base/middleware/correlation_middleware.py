import logging
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.base.middleware.request_context import (
    reset_request_context,
    set_request_context,
)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to each request for better log tracing."""

    async def dispatch(self, request: Request, call_next):
        # Reset context for this request
        reset_request_context()

        # Get correlation ID from header or generate new one
        correlation_id_value = request.headers.get(
            "x-correlation-id", str(uuid.uuid4())
        )

        set_request_context("correlation_id", correlation_id_value)

        logger = logging.getLogger(__name__)
        logger.info("Assigned correlation ID to request")

        # Process request
        response: Response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["x-correlation-id"] = correlation_id_value

        return response
