import functools
import logging

from fastapi import WebSocket, WebSocketDisconnect, status

from src.base.auth.websocket_auth import (
    authenticate_websocket,
    check_websocket_permissions,
)
from src.base.models.role import Role
from src.base.models.user import User

logger = logging.getLogger()


def websocket_endpoint(
    required_roles: list[list[Role]] = None,
    required_scopes: list[list[str]] = None,
    public=False,
):
    """
    Decorator for WebSocket endpoints.
    Handles authentication, authorization, error handling.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            websocket: WebSocket = kwargs.get("websocket") or (
                args[0] if args else None
            )
            if websocket is None:
                raise ValueError(
                    "websocket_endpoint decorator requires a WebSocket parameter"
                )

            claims = None
            try:
                # Public WS doesn't require auth
                if not public:
                    claims = authenticate_websocket(websocket)

                    # Create user object consistent with HTTP middleware
                    user = User(
                        id=claims.get("oid"),
                        email=claims.get("email") or claims.get("preferred_username"),
                        name=claims.get("name"),
                        roles=claims.get("roles", []),
                        scopes=claims.get("scp", "").split()
                        if claims.get("scp")
                        else [],
                    )

                    if required_roles or required_scopes:
                        check_websocket_permissions(
                            user,
                            required_roles=required_roles,
                            required_scopes=required_scopes,
                        )

                websocket.state.user = user
                await websocket.accept()

                # Call the actual endpoint handler
                return await func(*args, **kwargs)

            except WebSocketDisconnect:
                logger.info("WebSocket disconnected: %s", func.__name__)
            except Exception as e:
                logger.error(
                    "WebSocket %s failed: %s", func.__name__, str(e), exc_info=True
                )
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Access denied" if not public else "Internal error",
                )

        return wrapper

    return decorator
