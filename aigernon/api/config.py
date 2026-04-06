"""API configuration."""

from pydantic import BaseModel
from typing import Optional


class OAuthConfig(BaseModel):
    """OAuth provider configuration."""
    provider: str = "google"  # google, github
    client_id: str = ""
    client_secret: str = ""
    allowed_emails: list[str] = []  # Empty = allow all


class APIConfig(BaseModel):
    """API-specific configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]
    frontend_url: str = "http://localhost:3000"  # For OAuth redirects
    jwt_secret: str = ""  # Auto-generated if not set
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    oauth: OAuthConfig = OAuthConfig()
