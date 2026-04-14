"""Symmetric encryption for sensitive values at rest (GitHub tokens, etc.)."""

import os
import base64
from typing import Optional


def _get_fernet():
    """Lazy-import cryptography and build a Fernet instance from FERNET_KEY env var."""
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError(
            "cryptography package is required for token encryption. "
            "Install it with: pip install cryptography"
        ) from exc

    key = os.environ.get("FERNET_KEY", "")
    if not key:
        raise RuntimeError(
            "FERNET_KEY environment variable is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a plaintext token and return a URL-safe base64 string."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a previously encrypted token."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def decrypt_token_safe(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypt a token, returning None on any failure (missing key, bad data, None input)."""
    if not ciphertext:
        return None
    try:
        return decrypt_token(ciphertext)
    except Exception:
        return None
