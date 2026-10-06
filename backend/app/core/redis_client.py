"""Redis integration with connection pooling and graceful degradation.

Every operation is wrapped so that a Redis outage never breaks a request: on
failure the helper logs once and returns a neutral fallback value, letting the
caller recompute from the database. Implements the key patterns cache,
rate-limit, velocity, geo, device, session, queue, and pub/sub.
"""
from __future__ import annotations

import json
import threading
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


class _LocalStore:
    """Process-local, TTL'd, size-bounded stand-in used ONLY while Redis is unavailable.

    Security controls (rate limits, the account login throttle, step-up challenges) must not
    silently switch off with Redis, so they degrade to per-process state instead: weaker (not
    shared across workers, lost on restart) but still enforced.
    """

    MAX_KEYS = 20_000

    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        if len(self._data) >= self.MAX_KEYS:
            self._data = {k: v for k, v in self._data.items() if v[1] > now}
            if len(self._data) >= self.MAX_KEYS:  # still full of live keys: drop the oldest half
                keep = sorted(self._data.items(), key=lambda kv: kv[1][1])[len(self._data) // 2:]
                self._data = dict(keep)

    def incr(self, key: str, window: int, amount: int = 1) -> int:
        now = time.monotonic()
        with self._lock:
            value, expires = self._data.get(key, (0, 0.0))
            if expires <= now:
                self._purge(now)
                value, expires = 0, now + window
            value += amount
            self._data[key] = (value, expires)
            return value

    def get(self, key: str) -> Any:
        now = time.monotonic()
        with self._lock:
            value, expires = self._data.get(key, (None, 0.0))
            return value if expires > now else None

    def set(self, key: str, value: Any, ttl: int) -> None:
        now = time.monotonic()
        with self._lock:
            self._purge(now)
            self._data[key] = (value, now + ttl)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


class RedisClient:
    """Thin wrapper around a pooled synchronous Redis connection.

    Cache paths fail open (neutral default, recompute from the DB). Security-sensitive state
    - rate-limit counters, the login throttle, step-up challenges - falls back to a
    process-local store instead, so an outage degrades protection rather than removing it.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Optional[redis.Redis] = None
        self._warned = False
        self._local = _LocalStore()
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

        With Redis unavailable the count is kept in-process (per worker) rather than
        returning 0, so rate limits keep working, just not across workers.
        """

        def _do(c: redis.Redis) -> int:
            count = c.incr(key)
            if count == 1:
                c.expire(key, window_seconds)
            return int(count)

        result = self._safe(_do, default=None)
        return result if result is not None else self._local.incr(key, window_seconds)

    def counter_get(self, key: str) -> int:
        """Current value of a counter (0 if absent), from Redis or the local fallback."""
        if self._client is None:
            return int(self._local.get(key) or 0)
        raw = self._safe(lambda c: c.get(key), default=self._local.get(key))
        try:
            return int(raw) if raw is not None else 0
        except (TypeError, ValueError):
            return 0

    # ── Plain keys with an explicit success signal (token stores) ────────────

    def incr_by(self, key: str, amount: int, ttl: int) -> Optional[int]:
        """Add ``amount`` to a counter (TTL set on creation). None if Redis is unavailable."""

        def _do(c: redis.Redis) -> int:
            total = int(c.incrby(key, amount))
            if total == amount:
                c.expire(key, ttl)
            return total

        return self._safe(_do, default=None)

    def flag_set(self, key: str, ttl: int) -> None:
        """Remember a boolean for ``ttl`` seconds (Redis, or process memory if unavailable)."""
        if not self._safe(lambda c: bool(c.setex(key, ttl, "1")), default=False):
            self._local.set(key, 1, ttl)

    def flag_get(self, key: str) -> bool:
        if self._safe(lambda c: c.get(key)) is not None:
            return True
        return self._local.get(key) is not None

    def key_set(self, key: str, value: str, ttl: int) -> bool:
        """Store ``value`` for ``ttl`` seconds. False if Redis is unavailable."""
        return bool(self._safe(lambda c: c.setex(key, ttl, value), default=False))

    def key_get(self, key: str) -> Optional[str]:
        return self._safe(lambda c: c.get(key))

    def key_delete(self, key: str) -> None:
        self._local.delete(key)
        self._safe(lambda c: c.delete(key))

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
        """Store a session/challenge. Falls back to process memory if Redis is unavailable."""
        ok = self._safe(lambda c: bool(c.setex(f"session:{token}", ttl, json.dumps(data))), default=False)
        if not ok:
            self._local.set(f"session:{token}", json.dumps(data), ttl)

    def get_session(self, token: str) -> Optional[dict]:
        raw = self._safe(lambda c: c.get(f"session:{token}"))
        if raw is None:
            raw = self._local.get(f"session:{token}")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def delete_session(self, token: str) -> None:
        self._local.delete(f"session:{token}")
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
