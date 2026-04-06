"""System routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from aigernon.api.deps import get_current_user, get_ws_manager
from aigernon.api.websocket import WebSocketManager
from aigernon import __version__

router = APIRouter(prefix="/system", tags=["system"])


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str


class StatusResponse(BaseModel):
    """System status response."""
    version: str
    uptime: Optional[str]
    websocket_connections: int
    connected_users: int


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version=__version__,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/status", response_model=StatusResponse)
async def get_status(
    user: dict = Depends(get_current_user),
    ws_manager: WebSocketManager = Depends(get_ws_manager),
):
    """Get system status."""
    return StatusResponse(
        version=__version__,
        uptime=None,  # TODO: Track uptime
        websocket_connections=ws_manager.connections.get_connection_count(),
        connected_users=ws_manager.connections.get_user_count(),
    )


class ConfigResponse(BaseModel):
    """Public config response."""
    oauth_provider: str
    features: dict


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get public configuration."""
    from aigernon.config.loader import load_config

    config = load_config()

    return ConfigResponse(
        oauth_provider=config.api.oauth.provider,
        features={
            "coaching": True,
            "projects": True,
            "vector_memory": config.vector.enabled,
        },
    )
