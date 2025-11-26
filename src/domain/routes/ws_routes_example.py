from fastapi import APIRouter, WebSocket
import logging
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from src.base.decorators.websocket_endpoint import websocket_endpoint


class WebSocketMessage(BaseModel):
    """Standard WebSocket message structure."""

    message: str = Field(..., description="The message content")
    user: Optional[str] = Field(None, description="User who sent the message")
    claims: Optional[Dict[str, Any]] = Field(
        None, description="User claims if authenticated"
    )
    echo: Optional[str] = Field(None, description="Echoed message content")
    admin_message: Optional[str] = Field(None, description="Admin-specific message")
    scope_message: Optional[str] = Field(None, description="Scope-specific message")
    timestamp: Optional[str] = Field(None, description="Message timestamp")


class WebSocketResponse(BaseModel):
    """WebSocket response wrapper."""

    type: str = Field(..., description="Message type")
    data: WebSocketMessage = Field(..., description="Message data")

    def to_json(self) -> str:
        """Convert to JSON string for WebSocket transmission."""
        return self.model_dump_json()


logger = logging.getLogger()
router = APIRouter()


@router.websocket("/public")
@websocket_endpoint(public=True)
async def public_websocket(websocket: WebSocket):
    """Public WebSocket endpoint - no auth required"""
    welcome_msg = WebSocketMessage(message="Connected to public WebSocket!")
    welcome_response = WebSocketResponse(type="connection", data=welcome_msg)
    await websocket.send_text(welcome_response.to_json())

    while True:
        data = await websocket.receive_text()
        echo_msg = WebSocketMessage(message="Public WebSocket echo", echo=data)
        echo_response = WebSocketResponse(type="echo", data=echo_msg)
        await websocket.send_text(echo_response.to_json())


@router.websocket("/private")
@websocket_endpoint()
async def private_websocket(websocket: WebSocket):
    """Private WebSocket endpoint - requires authentication"""
    claims = websocket.state.claims  # set by decorator
    welcome_msg = WebSocketMessage(
        message=f"Hello, {claims.get('name', 'Authenticated User')}!",
        user=claims.get("name", "Authenticated User"),
        claims=claims,
    )
    welcome_response = WebSocketResponse(type="connection", data=welcome_msg)
    await websocket.send_text(welcome_response.to_json())

    while True:
        data = await websocket.receive_text()
        echo_msg = WebSocketMessage(
            message="Private WebSocket echo",
            echo=data,
            user=claims.get("name", "Authenticated User"),
        )
        echo_response = WebSocketResponse(type="echo", data=echo_msg)
        await websocket.send_text(echo_response.to_json())
