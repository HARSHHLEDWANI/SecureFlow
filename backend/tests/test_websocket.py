"""WebSocket fraud-alert stream and the dispatch bridge."""
from app.api.websockets.alerts import dispatch_alert
from app.core.redis_client import redis_client


def test_ws_connects_and_receives_alert(client):
    """A connected client receives an alert dispatched via the in-process bridge."""
    # Force the in-process fallback path (no live Redis pub/sub subscriber in tests).
    redis_client._client = None

    with client.websocket_connect("/ws/alerts") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "connected"

        dispatch_alert(
            {"type": "fraud_alert", "transaction_id": "t-123", "risk_score": 88}
        )
        alert = ws.receive_json()
        assert alert["type"] == "fraud_alert"
        assert alert["transaction_id"] == "t-123"


def test_dispatch_via_redis_publish(fake_redis):
    """When Redis is available, dispatch publishes to the channel (returns True)."""
    redis_client._client = fake_redis
    # publish_alert returns True even with zero subscribers as long as Redis accepts it.
    assert redis_client.publish_alert({"type": "fraud_alert"}) is True
