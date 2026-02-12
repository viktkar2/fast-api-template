import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class GlobalExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware that globally handles exceptions and formats responses in ProblemDetails style.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except Exception as ex:
            return await self._handle_exception(request, ex)

    # ------------------------
    # Internal helpers
    # ------------------------
    async def _handle_exception(self, request: Request, ex: Exception):
        """
        Convert unhandled exceptions to ProblemDetails format.
        """
        logger.error(
            "Unhandled exception occurred",
            exc_info=ex,
            extra={"path": str(request.url)},
        )

        tb = traceback.format_exc()
        content = {
            "type": "about:blank",
            "title": ex.__class__.__name__,
            "status": 500,
            "detail": str(ex),
            "instance": str(request.url),
            "trace": tb,
        }

        return JSONResponse(content=content, status_code=500)
