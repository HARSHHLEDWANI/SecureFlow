"""Shared FastAPI dependencies: auth, rate limiting, response envelope."""
from typing import Any, Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.redis_client import redis_client
from app.core.security import decode_token
from app.database import Role, User, get_db

# Roles with full fraud-ops visibility (all transactions, analytics, chain). A
# VIEWER, by contrast, may only see their own transactions/risk profile.
STAFF_ROLES = (Role.ANALYST, Role.ADMIN)

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


def is_staff(user: User) -> bool:
    """True if the user has full fraud-ops visibility (ANALYST or ADMIN)."""
    return user.role in STAFF_ROLES


def require_staff(user: User = Depends(get_current_user)) -> User:
    """Dependency: allow only ANALYST/ADMIN (full-visibility fraud-ops roles).

    Used to gate the aggregate analytics and blockchain-explorer endpoints, which
    expose every user's transaction data and are not appropriate for a VIEWER.
    """
    if not is_staff(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This resource requires an analyst or admin role",
        )
    return user


class RateLimiter:
    """Per-IP, per-endpoint fixed-window rate limiter (fail-open via Redis).

    ``limit`` overrides the global ``rate_limit_requests`` for this endpoint —
    used to throttle the (cost-bearing) explain endpoint more tightly than the
    free endpoints.
    """

    def __init__(self, endpoint: str, limit: Optional[int] = None) -> None:
        self.endpoint = endpoint
        self.limit = limit

    def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}:{self.endpoint}"
        max_requests = self.limit if self.limit is not None else settings.rate_limit_requests
        count = redis_client.rate_limit_hit(key, settings.rate_limit_window_seconds)
        if count > max_requests:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit exceeded ({max_requests}/"
                f"{settings.rate_limit_window_seconds}s)",
            )
