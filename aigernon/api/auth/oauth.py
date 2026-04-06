"""OAuth provider implementations."""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
import httpx


@dataclass
class OAuthUserInfo:
    """User info from OAuth provider."""
    sub: str  # Provider's user ID
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None


class OAuthProvider(ABC):
    """Abstract OAuth provider."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Get OAuth authorization URL."""
        pass

    @abstractmethod
    async def exchange_code(self, code: str) -> Optional[str]:
        """Exchange authorization code for access token."""
        pass

    @abstractmethod
    async def get_user_info(self, access_token: str) -> Optional[OAuthUserInfo]:
        """Get user info from OAuth provider."""
        pass


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth provider."""

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def get_authorization_url(self, state: str) -> str:
        """Get Google OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"

    async def exchange_code(self, code: str) -> Optional[str]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return data.get("access_token")

    async def get_user_info(self, access_token: str) -> Optional[OAuthUserInfo]:
        """Get user info from Google."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return OAuthUserInfo(
                sub=data["sub"],
                email=data["email"],
                name=data.get("name"),
                picture=data.get("picture"),
            )


class GitHubOAuthProvider(OAuthProvider):
    """GitHub OAuth provider."""

    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"
    EMAILS_URL = "https://api.github.com/user/emails"

    def get_authorization_url(self, state: str) -> str:
        """Get GitHub OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"

    async def exchange_code(self, code: str) -> Optional[str]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                },
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return data.get("access_token")

    async def get_user_info(self, access_token: str) -> Optional[OAuthUserInfo]:
        """Get user info from GitHub."""
        async with httpx.AsyncClient() as client:
            # Get user profile
            response = await client.get(
                self.USERINFO_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )

            if response.status_code != 200:
                return None

            data = response.json()

            # Get primary email if not public
            email = data.get("email")
            if not email:
                emails_response = await client.get(
                    self.EMAILS_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    primary = next((e for e in emails if e.get("primary")), None)
                    if primary:
                        email = primary["email"]

            if not email:
                return None

            return OAuthUserInfo(
                sub=str(data["id"]),
                email=email,
                name=data.get("name") or data.get("login"),
                picture=data.get("avatar_url"),
            )


def get_oauth_provider(
    provider: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> OAuthProvider:
    """Get OAuth provider by name."""
    providers = {
        "google": GoogleOAuthProvider,
        "github": GitHubOAuthProvider,
    }

    provider_class = providers.get(provider)
    if not provider_class:
        raise ValueError(f"Unknown OAuth provider: {provider}")

    return provider_class(client_id, client_secret, redirect_uri)
