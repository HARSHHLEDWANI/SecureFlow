"""WebSocket fraud-alert stream and the dispatch bridge."""
import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.websockets.alerts import dispatch_alert
from app.core.redis_client import redis_client
from app.core.security import create_token


def _token() -> str:
    """A valid access token for an arbitrary subject (WS only decodes it)."""
    return create_token("ws-test-user", "access", role="ANALYST", email="ws@test.com")


def test_ws_connects_and_receives_alert(client):
    """A connected (authenticated) client receives an alert via the in-process bridge."""
    # Force the in-process fallback path (no live Redis pub/sub subscriber in tests).
    redis_client._client = None

    with client.websocket_connect(f"/ws/alerts?token={_token()}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "connected"

        dispatch_alert(
            {"type": "fraud_alert", "transaction_id": "t-123", "risk_score": 88}
        )
        alert = ws.receive_json()
        assert alert["type"] == "fraud_alert"
        assert alert["transaction_id"] == "t-123"


def test_ws_rejects_missing_token(client):
    """Connecting without a token is rejected (no anonymous feed)."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/alerts") as ws:
            ws.receive_json()


def test_ws_rejects_invalid_token(client):
    """Connecting with a bad token is rejected."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/alerts?token=not-a-real-token") as ws:
            ws.receive_json()


def test_dispatch_via_redis_publish(fake_redis):
    """When Redis is available, dispatch publishes to the channel (returns True)."""
    redis_client._client = fake_redis
    # publish_alert returns True even with zero subscribers as long as Redis accepts it.
    assert redis_client.publish_alert({"type": "fraud_alert"}) is True
