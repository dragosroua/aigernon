"""JWT token handling."""

from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from jose import JWTError, jwt


class TokenData(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    email: str
    exp: datetime
    iat: datetime


def create_access_token(
    user_id: str,
    email: str,
    secret_key: str,
    algorithm: str = "HS256",
    expire_days: int = 7,
) -> str:
    """Create a JWT access token."""
    now = datetime.utcnow()
    expire = now + timedelta(days=expire_days)

    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": now,
    }

    return jwt.encode(payload, secret_key, algorithm=algorithm)


def verify_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> Optional[TokenData]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return TokenData(
            sub=payload["sub"],
            email=payload["email"],
            exp=datetime.fromtimestamp(payload["exp"]),
            iat=datetime.fromtimestamp(payload["iat"]),
        )
    except JWTError:
        return None
