"""FastAPI dependencies."""

from typing import Optional
from pathlib import Path
from fastapi import Depends, HTTPException, Request, WebSocket, Cookie
from functools import lru_cache

from aigernon.api.db.database import Database
from aigernon.api.config import APIConfig
from aigernon.api.auth.jwt import verify_token
from aigernon.api.websocket import WebSocketManager, ConnectionManager


# Singletons (set during app startup)
_db: Optional[Database] = None
_api_config: Optional[APIConfig] = None
_ws_manager: Optional[WebSocketManager] = None
_agent_loop = None
_workspace: Optional[Path] = None
_project_store = None


def set_db(db: Database):
    """Set database instance."""
    global _db
    _db = db


def set_api_config(config: APIConfig):
    """Set API config instance."""
    global _api_config
    _api_config = config


def set_ws_manager(manager: WebSocketManager):
    """Set WebSocket manager instance."""
    global _ws_manager
    _ws_manager = manager


def set_agent_loop(agent):
    """Set agent loop instance."""
    global _agent_loop
    _agent_loop = agent


def set_workspace(workspace: Path):
    """Set workspace path."""
    global _workspace
    _workspace = workspace


def set_project_store(store):
    """Set project store instance."""
    global _project_store
    _project_store = store


async def get_db() -> Database:
    """Get database dependency."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return _db


async def get_api_config() -> APIConfig:
    """Get API config dependency."""
    if _api_config is None:
        raise HTTPException(status_code=500, detail="API config not initialized")
    return _api_config


async def get_ws_manager() -> WebSocketManager:
    """Get WebSocket manager dependency."""
    if _ws_manager is None:
        raise HTTPException(status_code=500, detail="WebSocket manager not initialized")
    return _ws_manager


async def get_agent_loop():
    """Get agent loop dependency."""
    if _agent_loop is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    return _agent_loop


async def get_workspace() -> Path:
    """Get workspace path dependency."""
    if _workspace is None:
        raise HTTPException(status_code=500, detail="Workspace not initialized")
    return _workspace


async def get_project_store():
    """Get project store dependency."""
    if _project_store is None:
        raise HTTPException(status_code=500, detail="Project store not initialized")
    return _project_store


async def get_current_user_optional(
    request: Request,
    config: APIConfig = Depends(get_api_config),
    db: Database = Depends(get_db),
) -> Optional[dict]:
    """Get current user from auth token (optional)."""
    from loguru import logger

    token = None

    # Try Authorization header first (more reliable, avoids stale cookies)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        logger.debug(f"Using Authorization header token: {token[:20]}...")

    # Fall back to cookie
    if not token:
        token = request.cookies.get("auth_token")
        if token:
            logger.debug(f"Using cookie token: {token[:20]}...")

    if not token:
        logger.debug("No token found")
        return None

    # Verify token
    token_data = verify_token(token, config.jwt_secret, config.jwt_algorithm)
    if not token_data:
        logger.debug("Token verification failed")
        return None

    logger.debug(f"Token valid, user_id: {token_data.sub}")

    # Get user from database
    user = await db.get_user(token_data.sub)
    logger.debug(f"User from db: {user}")
    return user


async def get_current_user(
    user: Optional[dict] = Depends(get_current_user_optional),
) -> dict:
    """Get current user (required)."""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_current_user_ws(websocket: WebSocket) -> Optional[dict]:
    """Get current user from WebSocket auth."""
    from loguru import logger

    # Try cookie
    token = websocket.cookies.get("auth_token")
    if token:
        logger.debug(f"WS: Using cookie token: {token[:20]}...")

    # Fall back to query param
    if not token:
        token = websocket.query_params.get("token")
        if token:
            logger.debug(f"WS: Using query param token: {token[:20]}...")

    if not token:
        logger.debug("WS: No token found")
        return None

    # Get config and db
    if not _api_config or not _db:
        logger.debug("WS: Config or DB not initialized")
        return None

    # Verify token
    token_data = verify_token(token, _api_config.jwt_secret, _api_config.jwt_algorithm)
    if not token_data:
        logger.debug("WS: Token verification failed")
        return None

    logger.debug(f"WS: Token valid, user_id: {token_data.sub}")

    # Get user from database
    user = await _db.get_user(token_data.sub)
    logger.debug(f"WS: User from db: {user}")
    return user
