# WebSocket authentication helpers: token validation and token-level
# role/scope enforcement for WebSocket connections.  Like the rest of
# base/auth/, this layer only reads JWT claims — no database access.

import logging

from fastapi import WebSocket, WebSocketException, status
from jose import ExpiredSignatureError, JWTError

from src.base.auth.auth_core import check_roles_and_scopes, validate_jwt_token
from src.base.models.role import Role
from src.base.models.user import User

logger = logging.getLogger(__name__)


def authenticate_websocket(websocket: WebSocket, token: str = None):
    """
    Authenticate WebSocket connection and return claims.
    """
    token = token or websocket.query_params.get("token")

    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing token"
        )

    try:
        claims = validate_jwt_token(token)
        return claims
    except ExpiredSignatureError as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Token has expired"
        ) from e
    except JWTError as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason=f"Invalid token: {e}"
        ) from e


def check_websocket_permissions(
    user: User,
    required_roles: list[list[Role]] = None,
    required_scopes: list[list[str]] = None,
):
    """
    Enforce RBAC for WebSocket connections.
    """
    if not check_roles_and_scopes(
        user.roles, user.scopes, required_roles, required_scopes
    ):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Insufficient roles or scopes"
        )
    return True
