import logging

from fastapi import WebSocket, WebSocketException, status
from jose import ExpiredSignatureError, JWTError

from src.base.auth.auth_core import check_roles_and_scopes, validate_jwt_token

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
    except ExpiredSignatureError:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Token has expired"
        )
    except JWTError as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason=f"Invalid token: {e}"
        )


def check_websocket_permissions(
    claims: dict, required_roles: list = None, required_scopes: list = None
):
    """
    Enforce RBAC for WebSocket connections.
    """
    if not check_roles_and_scopes(claims, required_roles, required_scopes):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Insufficient roles or scopes"
        )
    return True
