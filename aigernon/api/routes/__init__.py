"""API routes."""

from aigernon.api.routes.auth import router as auth_router
from aigernon.api.routes.chat import router as chat_router
from aigernon.api.routes.sessions import router as sessions_router
from aigernon.api.routes.projects import router as projects_router
from aigernon.api.routes.memory import router as memory_router
from aigernon.api.routes.notifications import router as notifications_router
from aigernon.api.routes.system import router as system_router
from aigernon.api.routes.coaching import router as coaching_router

__all__ = [
    "auth_router",
    "chat_router",
    "sessions_router",
    "projects_router",
    "memory_router",
    "notifications_router",
    "system_router",
    "coaching_router",
]
