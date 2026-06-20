"""Real-time fraud-alert WebSocket, bridged to Redis Pub/Sub.

Design:
  * A process-wide :class:`ConnectionManager` tracks connected clients.
  * A background task subscribes to the Redis ``fraud:alerts`` channel and
    fans messages out to every client — this is the message bus.
  * :func:`dispatch_alert` is the single entry point the request path uses. It
    publishes to Redis; if Redis is unavailable it falls back to broadcasting
    in-process so a single-node deployment still gets live alerts.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.core.redis_client import ALERTS_CHANNEL, redis_client
from app.core.security import decode_token
from app.utils.logger import get_logger

logger = get_logger("ws")
router = APIRouter()


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts messages to them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        logger.info("WS client connected (%d active)", len(self._clients))

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        logger.info("WS client disconnected (%d active)", len(self._clients))

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def broadcast_threadsafe(self, message: dict[str, Any]) -> None:
        """Schedule a broadcast from synchronous (threadpool) code."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)


manager = ConnectionManager()


def dispatch_alert(alert: dict[str, Any]) -> None:
    """Send a fraud alert via Redis pub/sub, falling back to in-process fan-out."""
    delivered = redis_client.publish_alert(alert)
    if not delivered:
        manager.broadcast_threadsafe(alert)


async def redis_alert_listener() -> None:
    """Background task: subscribe to Redis and relay alerts to WS clients."""
    settings = get_settings()
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(ALERTS_CHANNEL)
        logger.info("Subscribed to Redis channel %s", ALERTS_CHANNEL)
    except Exception as exc:  # noqa: BLE001 - any connection failure degrades gracefully
        logger.warning("Alert listener disabled (Redis unavailable: %s)", exc)
        return

    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                alert = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue
            await manager.broadcast(alert)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Alert listener stopped: %s", exc)
    finally:
        try:
            await pubsub.close()
            await client.close()
        except Exception:  # noqa: BLE001
            pass


@router.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket) -> None:
    """Stream live fraud alerts. Optional ``?token=`` for authenticated clients."""
    token = websocket.query_params.get("token")
    if token:
        try:
            decode_token(token, "access")
        except Exception:  # noqa: BLE001 - invalid token => anonymous read-only stream
            pass

    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "channel": "fraud:alerts"})
        while True:
            # Keep the connection alive; clients are not required to send data.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:  # noqa: BLE001
        manager.disconnect(websocket)
