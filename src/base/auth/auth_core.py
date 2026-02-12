# Authentication infrastructure: JWT validation, JWKS fetching, and
# token-level role/scope checks.  Everything here reads from the token
# only — no database access.  Domain-level authorization (group
# membership checks, etc.) lives in src/domain/auth/.

import logging
import os
from functools import lru_cache
from typing import Any

import requests
from dotenv import load_dotenv
from jose import JWTError, jwt

from src.base.models.role import Role

# --- Env setup ---
load_dotenv()
TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")

if not TENANT_ID or not CLIENT_ID:
    raise RuntimeError("AZURE_TENANT_ID and AZURE_CLIENT_ID must be set")

ISSUER = f"https://sts.windows.net/{TENANT_ID}/"
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_jwks() -> dict[str, Any]:
    return requests.get(JWKS_URL).json()


def validate_jwt_token(token: str) -> dict[str, Any]:
    """
    Validates a JWT and returns claims (raises JWTError/ExpiredSignatureError if invalid).
    """
    logger.debug("Starting JWT token validation")

    try:
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)

        kid = unverified_header.get("kid")
        logger.debug(f"Token key ID: {kid}")

        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if not key:
            logger.error(f"No matching signing key found for kid: {kid}")
            raise JWTError("Invalid signing key")

        payload = jwt.decode(
            token, key, algorithms=["RS256"], audience=CLIENT_ID, issuer=ISSUER
        )

        logger.info("JWT validated successfully")

        return payload

    except JWTError as e:
        logger.error(f"JWT validation failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}")
        raise JWTError(f"Token validation error: {e}") from e


def check_roles_and_scopes(
    user_roles: list[str],
    user_scopes: list[str],
    required_roles: list[list[Role]] = None,
    required_scopes: list[list[str]] = None,
) -> bool:
    """
    Check if claims contain at least one valid combination of roles and scopes.
    """
    required_roles = required_roles or []
    required_scopes = required_scopes or []

    # Convert Role enums to string values for comparison with user_roles
    roles_ok = not required_roles or any(
        all(r.value in user_roles for r in group) for group in required_roles
    )
    scopes_ok = not required_scopes or any(
        all(s in user_scopes for s in group) for group in required_scopes
    )

    result = roles_ok and scopes_ok

    if result:
        logger.info("Authorization successful")
    else:
        logger.warning("Authorization failed for user")

    return result
