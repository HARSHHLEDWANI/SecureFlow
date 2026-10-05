"""Demo sessions for the public UPI Lab.

The Lab is a one-click demo, but its write endpoints create real transactions and mine real
blocks, so they cannot be anonymous. ``POST /upi/session`` hands out a short-lived signed
token (type ``demo``, accepted nowhere else) that the frontend fetches on page load and
sends as ``X-Demo-Session`` on every mutating Lab call.

Abuse bounds, in order: per-IP rate limits (tight, in the routes) -> a per-session
transaction cap (Redis counter, in-process fallback when Redis is down) -> a global cap on
``is_demo`` rows in the database. ``/upi/reset`` clears the global one, never the session cap.
"""
from __future__ import annotations

import threading
import uuid
from typing import Optional

import jwt
from fastapi import Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.redis_client import redis_client
from app.core.security import create_token, decode_token
from app.database import Transaction

settings = get_settings()

HEADER = "X-Demo-Session"

# Fallback per-session counters when Redis is unavailable (single-process, bounded).
_local: dict[str, int] = {}
_local_lock = threading.Lock()
_LOCAL_MAX_SESSIONS = 10_000


def issue_session() -> dict:
    sid = uuid.uuid4().hex
    return {
        "token": create_token(sid, "demo"),
        "session_id": sid,
        "expires_in": settings.demo_session_ttl_minutes * 60,
        "max_transactions": settings.demo_session_max_transactions,
    }


def require_demo_session(x_demo_session: Optional[str] = Header(default=None)) -> str:
    """Dependency: a valid demo session token, returning its session id."""
    if not x_demo_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Missing {HEADER} (POST /upi/session first)")
    try:
        return str(decode_token(x_demo_session, "demo")["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Demo session expired; request a new one")
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid demo session")


def _session_count(sid: str, n: int) -> int:
    """Add ``n`` to the session's counter and return the new total."""
    ttl = settings.demo_session_ttl_minutes * 60
    total = redis_client.incr_by(f"demo:count:{sid}", n, ttl)
    if total is not None:
        return total
    with _local_lock:
        if len(_local) >= _LOCAL_MAX_SESSIONS:
            _local.clear()
        _local[sid] = _local.get(sid, 0) + n
        return _local[sid]


def enforce_quota(db: Session, sid: str, n: int = 1) -> None:
    """Reserve ``n`` transactions for the session or raise 429."""
    total_demo = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.is_demo.is_(True))
    ) or 0
    if total_demo + n > settings.demo_max_total_transactions:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "The demo database is full. Use Reset Session to clear demo data.",
        )
    if _session_count(sid, n) > settings.demo_session_max_transactions:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Demo session limit reached ({settings.demo_session_max_transactions} transactions). "
            "Start a new session.",
        )

