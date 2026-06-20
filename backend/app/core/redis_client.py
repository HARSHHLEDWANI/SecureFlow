"""Redis integration with connection pooling and graceful degradation.

Every operation is wrapped so that a Redis outage never breaks a request: on
failure the helper logs once and returns a neutral fallback value, letting the
caller recompute from the database. Implements the key patterns documented in
ARCHITECTURE.md (cache, rate-limit, velocity, geo, device, session, queue,
pub/sub).
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

import redis

from app.config import get_settings
from app.utils.helpers import utcnow
from app.utils.logger import get_logger

logger = get_logger("redis")
settings = get_settings()

# Channel + key prefixes (single source of truth).
ALERTS_CHANNEL = "fraud:alerts"
QUEUE_KEY = "transaction:queue"


class RedisClient:
    """Thin, fail-open wrapper around a pooled synchronous Redis connection."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Optional[redis.Redis] = None
        self._warned = False
        self._connect()

    def _connect(self) -> None:
        try:
            pool = redis.ConnectionPool.from_url(
                self._url, decode_responses=True, max_connections=20, socket_timeout=2
            )
            client = redis.Redis(connection_pool=pool)
            client.ping()
            self._client = client
            logger.info("Connected to Redis at %s", self._url)
        except redis.RedisError as exc:
            self._client = None
            logger.warning("Redis unavailable (%s) - running in degraded mode", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def ping(self) -> bool:
        """Return True if Redis currently responds; attempt one reconnect."""
        if self._client is None:
            self._connect()
        if self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            self._client = None
            return False

    def _safe(self, fn, default: Any = None) -> Any:
        if self._client is None:
            return default
        try:
            return fn(self._client)
        except redis.RedisError as exc:
            if not self._warned:
                logger.warning("Redis operation failed (%s) - degrading", exc)
                self._warned = True
            return default

    # ── JSON cache ───────────────────────────────────────────────────────────

    def cache_get_json(self, key: str) -> Optional[dict]:
        raw = self._safe(lambda c: c.get(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def cache_set_json(self, key: str, value: dict, ttl: int) -> None:
        payload = json.dumps(value, default=str)
        self._safe(lambda c: c.setex(key, ttl, payload))

    # ── Rate limiting (fixed window) ─────────────────────────────────────────

    def rate_limit_hit(self, key: str, window_seconds: int) -> int:
        """Increment a fixed-window counter, returning the new count.

        Returns 0 when Redis is unavailable so the caller fails open (allows).
        """

        def _do(c: redis.Redis) -> int:
            count = c.incr(key)
            if count == 1:
                c.expire(key, window_seconds)
            return int(count)

        return self._safe(_do, default=0)

    # ── Velocity (sorted set of event timestamps) ────────────────────────────

    def record_velocity(self, user_id: str, retention_seconds: int = 3600) -> None:
        key = f"velocity:user:{user_id}"
        now = time.time()

        def _do(c: redis.Redis) -> None:
            # Unique member per event so rapid same-instant calls are not coalesced.
            c.zadd(key, {f"{now}:{uuid.uuid4().hex}": now})
            c.zremrangebyscore(key, 0, now - retention_seconds)
            c.expire(key, retention_seconds)

        self._safe(_do)

    def velocity_count(self, user_id: str, window_seconds: int) -> Optional[int]:
        key = f"velocity:user:{user_id}"
        now = time.time()
        return self._safe(
            lambda c: int(c.zcount(key, now - window_seconds, now)), default=None
        )

    # ── Geo (last known location) ────────────────────────────────────────────

    def set_last_geo(self, user_id: str, lat: float, lon: float) -> None:
        key = f"geo:user:{user_id}:last"
        value = json.dumps({"lat": lat, "lon": lon, "ts": utcnow().isoformat()})
        self._safe(lambda c: c.setex(key, 86400, value))

    def get_last_geo(self, user_id: str) -> Optional[dict]:
        raw = self._safe(lambda c: c.get(f"geo:user:{user_id}:last"))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # ── Device set (new-device detection) ────────────────────────────────────

    def is_known_device(self, user_id: str, device_id: str) -> Optional[bool]:
        return self._safe(
            lambda c: bool(c.sismember(f"device:user:{user_id}", device_id)),
            default=None,
        )

    def add_device(self, user_id: str, device_id: str) -> None:
        key = f"device:user:{user_id}"

        def _do(c: redis.Redis) -> None:
            c.sadd(key, device_id)
            c.expire(key, 30 * 86400)

        self._safe(_do)

    # ── Sessions ─────────────────────────────────────────────────────────────

    def set_session(self, token: str, data: dict, ttl: int = 1800) -> None:
        self._safe(lambda c: c.setex(f"session:{token}", ttl, json.dumps(data)))

    def get_session(self, token: str) -> Optional[dict]:
        raw = self._safe(lambda c: c.get(f"session:{token}"))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def delete_session(self, token: str) -> None:
        self._safe(lambda c: c.delete(f"session:{token}"))

    # ── Queue ────────────────────────────────────────────────────────────────

    def queue_push(self, item: dict) -> None:
        self._safe(lambda c: c.lpush(QUEUE_KEY, json.dumps(item, default=str)))

    def queue_length(self) -> int:
        return self._safe(lambda c: int(c.llen(QUEUE_KEY)), default=0)

    # ── Pub/Sub ──────────────────────────────────────────────────────────────

    def publish_alert(self, alert: dict) -> bool:
        """Publish a fraud alert. Returns True if at least delivered to Redis."""
        result = self._safe(
            lambda c: c.publish(ALERTS_CHANNEL, json.dumps(alert, default=str)),
            default=None,
        )
        return result is not None


# Module-level singleton, constructed lazily on first import.
redis_client = RedisClient(settings.redis_url)
