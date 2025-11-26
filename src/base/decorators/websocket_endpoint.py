import functools
import logging
from fastapi import WebSocket, WebSocketDisconnect, status
from src.base.auth.websocket_auth import (
    authenticate_websocket,
    check_websocket_permissions,
)

logger = logging.getLogger()


def websocket_endpoint(required_roles=None, required_scopes=None, public=False):
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
                    if required_roles or required_scopes:
                        check_websocket_permissions(
                            claims,
                            required_roles=required_roles,
                            required_scopes=required_scopes,
                        )
                websocket.state.claims = claims

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
