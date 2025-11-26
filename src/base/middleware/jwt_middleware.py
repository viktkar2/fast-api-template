import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import ExpiredSignatureError, JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from src.base.auth.auth_core import validate_jwt_token

logger = logging.getLogger(__name__)

# Paths that don’t require auth
WHITELIST = [
    "/api/test/public",
    "/docs",
    "/openapi.json",
    "/api/ws/public",
    "/favicon.ico",
    "/docs/oauth2-redirect",
]


class JWTMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JWT on every HTTP request.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        if path in WHITELIST:
            logger.debug(f"Skipping auth for whitelisted path: {method} {path}")
            return await call_next(request)

        logger.info(f"Authenticating request: {method} {path}")

        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(
                f"Missing or invalid Authorization header for: {method} {path}"
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header"},
            )

        token = auth_header[len("Bearer ") :]
        logger.debug("JWT token extracted from Authorization header")

        try:
            claims = validate_jwt_token(token)
            request.state.claims = claims
            logger.info("Authentication successful for user")

        except ExpiredSignatureError:
            logger.warning(f"JWT token expired for: {method} {path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Token has expired"},
            )
        except JWTError as e:
            logger.error(f"JWT validation failed for {method} {path}: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": f"Invalid token: {e}"},
            )

        return await call_next(request)
