"""Shared FastAPI dependencies: auth, rate limiting, response envelope."""
from typing import Any, Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.redis_client import redis_client
from app.core.security import decode_token
from app.database import User, get_db

settings = get_settings()


def envelope(data: Any = None, error: Optional[str] = None, meta: Optional[dict] = None) -> dict:
    """Standard API response envelope ``{success, data, error, meta?}``."""
    body: dict[str, Any] = {"success": error is None, "data": data, "error": error}
    if meta is not None:
        body["meta"] = meta
    return body


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Bearer access token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, "access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


def require_role(*roles: str):
    """Dependency factory enforcing that the current user has one of ``roles``."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if roles and user.role.value not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return _checker


class RateLimiter:
    """Per-IP, per-endpoint fixed-window rate limiter (fail-open via Redis)."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}:{self.endpoint}"
        count = redis_client.rate_limit_hit(key, settings.rate_limit_window_seconds)
        if count > settings.rate_limit_requests:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit exceeded ({settings.rate_limit_requests}/"
                f"{settings.rate_limit_window_seconds}s)",
            )
