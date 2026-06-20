"""Authentication primitives: password hashing and JWT issue/verify.

Passwords are hashed with bcrypt directly (no passlib, to avoid its known
incompatibility with bcrypt 4.x). Tokens are signed with PyJWT.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.config import get_settings
from app.utils.helpers import utcnow

settings = get_settings()

ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]


# ── Password hashing ─────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Return a bcrypt hash of ``password`` (utf-8, salted)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check of a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────


def _secret(token_type: TokenType) -> str:
    return settings.jwt_refresh_secret if token_type == "refresh" else settings.jwt_secret


def create_token(subject: str, token_type: TokenType = "access", **claims: Any) -> str:
    """Create a signed JWT for ``subject`` with the configured expiry."""
    if token_type == "refresh":
        expires = timedelta(days=settings.refresh_token_expire_days)
    else:
        expires = timedelta(minutes=settings.access_token_expire_minutes)

    now = utcnow()
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        **claims,
    }
    return jwt.encode(payload, _secret(token_type), algorithm=ALGORITHM)


def decode_token(token: str, token_type: TokenType = "access") -> dict[str, Any]:
    """Decode and validate a JWT. Raises ``jwt.PyJWTError`` on failure."""
    payload = jwt.decode(token, _secret(token_type), algorithms=[ALGORITHM])
    if payload.get("type") != token_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload
