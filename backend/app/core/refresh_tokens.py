"""Refresh-token rotation, reuse detection and revocation.

Every refresh JWT carries a unique ``jti`` and a ``fid`` (family id, constant across
rotations of one login). Redis holds the server-side truth::

    rt:{jti}        active token   -> {"uid", "fid"}      (TTL = refresh lifetime)
    rt_used:{jti}   rotated away   -> {"fid", "at"}        (TTL = refresh lifetime)
    rt_fam_dead:{fid}  family revoked                       (TTL = refresh lifetime)

* ``/auth/refresh`` accepts a token only if ``rt:{jti}`` is active, then retires it
  (``rt_used``) and issues a successor in the same family.
* Presenting a token that is already ``rt_used`` means it was copied (a thief and the
  victim both hold it): the whole family is revoked and both must log in again - the
  standard refresh-token-reuse detection.
* ``/auth/logout`` revokes the family.

Redis down => refresh tokens are unverifiable, so none are issued (the user gets only the
short-lived access token and must re-login when it expires) and any presented refresh
token is rejected. This fails closed, unlike the cache paths which fail open.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.config import get_settings
from app.core.redis_client import redis_client


class RefreshState(str, Enum):
    ACTIVE = "active"
    REUSED = "reused"          # already rotated: a copied token
    RACED = "raced"            # rotated moments ago: almost certainly a concurrent refresh
    REVOKED = "revoked"        # family killed (logout / earlier reuse)
    UNKNOWN = "unknown"        # never issued, expired, or evicted
    UNAVAILABLE = "unavailable"  # Redis down: cannot verify


@dataclass(frozen=True)
class RefreshIdentity:
    jti: str
    fid: str


def _ttl() -> int:
    return get_settings().refresh_token_expire_days * 86400


def new_family() -> str:
    return uuid.uuid4().hex


def new_jti() -> str:
    return uuid.uuid4().hex


def register(jti: str, fid: str, user_id: str) -> bool:
    """Record a freshly issued token as active. False => could not be stored."""
    return redis_client.key_set(f"rt:{jti}", json.dumps({"uid": user_id, "fid": fid}), _ttl())


def check(jti: str, fid: str) -> RefreshState:
    if not redis_client.available:
        return RefreshState.UNAVAILABLE
    if redis_client.key_get(f"rt_fam_dead:{fid}") is not None:
        return RefreshState.REVOKED
    if redis_client.key_get(f"rt:{jti}") is not None:
        return RefreshState.ACTIVE
    used = redis_client.key_get(f"rt_used:{jti}")
    if used is not None:
        try:
            age = time.time() - float(json.loads(used)["at"])
        except (ValueError, KeyError, TypeError):
            age = float("inf")
        if age < get_settings().refresh_reuse_grace_seconds:
            return RefreshState.RACED
        return RefreshState.REUSED
    return RefreshState.UNKNOWN


def retire(jti: str, fid: str) -> None:
    """Mark ``jti`` as rotated away (a later presentation is reuse)."""
    redis_client.key_delete(f"rt:{jti}")
    redis_client.key_set(f"rt_used:{jti}", json.dumps({"fid": fid, "at": time.time()}), _ttl())


def revoke_family(fid: str) -> None:
    redis_client.key_set(f"rt_fam_dead:{fid}", "1", _ttl())


def identity_from_payload(payload: dict) -> Optional[RefreshIdentity]:
    jti, fid = payload.get("jti"), payload.get("fid")
    return RefreshIdentity(jti, fid) if jti and fid else None
