import logging
import re

from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import ExpiredSignatureError, JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from src.base.auth.auth_core import validate_jwt_token
from src.base.models.user import User

logger = logging.getLogger(__name__)

# Paths that don’t require auth
WHITELIST = [
    r"^/favicon.ico",
    r"^/docs/oauth2-redirect",
    r"^/docs",
    r"^/redoc",
    r"^/openapi.json",
    r"^/health",
    r"^/robots.*\.txt$",
    r"^/api/$",
    r"^/api/health",
]


class JWTMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JWT on every HTTP request.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        if any(re.match(pattern, path) for pattern in WHITELIST):
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

            # Store user information
            request.state.user = User(
                id=claims.get("oid"),
                email=claims.get("email") or claims.get("preferred_username"),
                name=claims.get("name"),
                roles=claims.get("roles", []),
                scopes=claims.get("scp", "").split() if claims.get("scp") else [],
            )

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
                content={"detail": "Invalid token"},
            )

        return await call_next(request)
