"""FastAPI application factory."""

import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from aigernon.api.config import APIConfig, OAuthConfig
from aigernon.api.db.database import Database
from aigernon.api.websocket import WebSocketManager, ConnectionManager
from aigernon.api import deps
from aigernon.api.routes import (
    auth_router,
    chat_router,
    sessions_router,
    projects_router,
    memory_router,
    notifications_router,
    system_router,
    coaching_router,
)
from aigernon import __version__


def create_app(
    config: APIConfig = None,
    workspace: Path = None,
    agent_loop=None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    # Load from aigernon config if not provided
    if config is None:
        from aigernon.config.loader import load_config
        aigernon_config = load_config()

        # Build APIConfig from aigernon config
        config = APIConfig(
            host=aigernon_config.api.host,
            port=aigernon_config.api.port,
            cors_origins=aigernon_config.api.cors_origins,
            frontend_url=aigernon_config.api.frontend_url,
            jwt_secret=aigernon_config.api.jwt_secret,
            jwt_expire_days=aigernon_config.api.jwt_expire_days,
            oauth=OAuthConfig(
                provider=aigernon_config.api.oauth.provider,
                client_id=aigernon_config.api.oauth.client_id,
                client_secret=aigernon_config.api.oauth.client_secret,
                allowed_emails=aigernon_config.api.oauth.allowed_emails,
            ),
        )

    # Generate JWT secret if not set
    if not config.jwt_secret:
        config.jwt_secret = secrets.token_urlsafe(32)

    # Database path
    if workspace is None:
        from aigernon.config.loader import load_config
        aigernon_config = load_config()
        workspace = aigernon_config.workspace_path

    data_dir = Path.home() / ".aigernon" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "users.db"

    # Create instances
    db = Database(db_path)
    connection_manager = ConnectionManager()
    ws_manager = WebSocketManager(connection_manager)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan handler."""
        # Startup
        logger.info(f"Starting AIGernon API v{__version__}")
        await db.connect()

        # Set dependencies
        deps.set_db(db)
        deps.set_api_config(config)
        deps.set_ws_manager(ws_manager)
        deps.set_workspace(workspace)

        if agent_loop:
            deps.set_agent_loop(agent_loop)

        # Set up project store
        from aigernon.projects.store import ProjectStore
        project_store = ProjectStore(workspace)
        deps.set_project_store(project_store)

        logger.info(f"API ready on {config.host}:{config.port}")

        yield

        # Shutdown
        logger.info("Shutting down AIGernon API")
        await db.close()

    # Create app
    app = FastAPI(
        title="AIGernon API",
        description="API for AIGernon cognitive companion",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(sessions_router)
    app.include_router(projects_router)
    app.include_router(memory_router)
    app.include_router(notifications_router)
    app.include_router(system_router)
    app.include_router(coaching_router)

    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    workers: int = 1,
):
    """Run the API server."""
    import uvicorn

    uvicorn.run(
        "aigernon.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        factory=True,
    )
