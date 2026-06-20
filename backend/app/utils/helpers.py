"""Small, dependency-free helper functions shared across the app."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    """Timezone-aware current UTC timestamp."""
    return datetime.now(timezone.utc)


def stable_hash(payload: Any) -> str:
    """Deterministic SHA-256 hex digest of a JSON-serialisable payload.

    Used to derive a cache key for an ML prediction from transaction inputs.
    Keys are sorted so logically-identical payloads hash identically.
    """
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometres."""
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range."""
    return max(low, min(high, value))
