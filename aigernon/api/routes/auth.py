"""Authentication routes."""

import secrets
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import hashlib

from aigernon.api.deps import get_db, get_api_config, get_current_user_optional
from aigernon.api.auth import create_access_token, get_oauth_provider
from aigernon.api.db.database import Database
from aigernon.api.config import APIConfig

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory state storage (for OAuth flow)
_oauth_states: dict[str, str] = {}


class LoginResponse(BaseModel):
    """Login response."""
    redirect_url: str


class UserResponse(BaseModel):
    """Current user response."""
    id: str
    email: str
    name: Optional[str]
    picture_url: Optional[str]
    theme: str


@router.get("/login")
async def login(
    request: Request,
    config: APIConfig = Depends(get_api_config),
) -> LoginResponse:
    """Start OAuth login flow."""
    if not config.oauth.client_id:
        raise HTTPException(status_code=500, detail="OAuth not configured")

    # Generate state token
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "pending"

    # Build redirect URI
    redirect_uri = str(request.url_for("oauth_callback"))

    provider = get_oauth_provider(
        config.oauth.provider,
        config.oauth.client_id,
        config.oauth.client_secret,
        redirect_uri,
    )

    auth_url = provider.get_authorization_url(state)
    return LoginResponse(redirect_url=auth_url)


@router.get("/callback")
async def oauth_callback(
    request: Request,
    response: Response,
    code: str,
    state: str,
    config: APIConfig = Depends(get_api_config),
    db: Database = Depends(get_db),
):
    """OAuth callback handler."""
    # Verify state
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    del _oauth_states[state]

    # Build redirect URI (must match login)
    redirect_uri = str(request.url_for("oauth_callback"))

    provider = get_oauth_provider(
        config.oauth.provider,
        config.oauth.client_id,
        config.oauth.client_secret,
        redirect_uri,
    )

    # Exchange code for token
    access_token = await provider.exchange_code(code)
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    # Get user info
    user_info = await provider.get_user_info(access_token)
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # Check allowed emails
    if config.oauth.allowed_emails and user_info.email not in config.oauth.allowed_emails:
        raise HTTPException(status_code=403, detail="Email not allowed")

    # Create user ID from email
    user_id = hashlib.sha256(user_info.email.encode()).hexdigest()[:16]

    # Upsert user
    await db.upsert_user(
        user_id=user_id,
        email=user_info.email,
        name=user_info.name,
        picture_url=user_info.picture,
        oauth_provider=config.oauth.provider,
        oauth_sub=user_info.sub,
    )

    # Create JWT
    jwt_token = create_access_token(
        user_id=user_id,
        email=user_info.email,
        secret_key=config.jwt_secret,
        algorithm=config.jwt_algorithm,
        expire_days=config.jwt_expire_days,
    )

    # Redirect to frontend callback with token
    # Frontend will store the token and redirect to /chat
    frontend_url = config.frontend_url or "http://localhost:3000"
    callback_url = f"{frontend_url}/callback?token={jwt_token}"

    return RedirectResponse(url=callback_url, status_code=302)


@router.post("/logout")
async def logout(response: Response):
    """Logout and clear auth cookie."""
    response.delete_cookie("auth_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """Get current authenticated user."""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user.get("name"),
        picture_url=user.get("picture_url"),
        theme=user.get("theme", "system"),
    )


class UpdateThemeRequest(BaseModel):
    """Update theme request."""
    theme: str


@router.patch("/me/theme")
async def update_theme(
    request: UpdateThemeRequest,
    user: dict = Depends(get_current_user_optional),
    db: Database = Depends(get_db),
):
    """Update user theme preference."""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if request.theme not in ["light", "dark", "system"]:
        raise HTTPException(status_code=400, detail="Invalid theme")

    await db.update_user_theme(user["id"], request.theme)
    return {"theme": request.theme}
