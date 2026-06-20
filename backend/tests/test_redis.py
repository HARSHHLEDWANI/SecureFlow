"""Redis helper operations (against fakeredis) and graceful fallback."""
from app.core.redis_client import RedisClient, redis_client


def test_json_cache_roundtrip(fake_redis):
    redis_client.cache_set_json("k1", {"a": 1, "b": "x"}, ttl=60)
    assert redis_client.cache_get_json("k1") == {"a": 1, "b": "x"}


def test_rate_limit_increments(fake_redis):
    key = "ratelimit:1.2.3.4:test"
    assert redis_client.rate_limit_hit(key, 60) == 1
    assert redis_client.rate_limit_hit(key, 60) == 2


def test_velocity_tracking(fake_redis):
    redis_client.record_velocity("user-1")
    redis_client.record_velocity("user-1")
    assert redis_client.velocity_count("user-1", 3600) >= 2


def test_device_set(fake_redis):
    assert redis_client.is_known_device("user-2", "dev-1") is False
    redis_client.add_device("user-2", "dev-1")
    assert redis_client.is_known_device("user-2", "dev-1") is True


def test_session_lifecycle(fake_redis):
    redis_client.set_session("tok", {"user_id": "u1"}, ttl=60)
    assert redis_client.get_session("tok") == {"user_id": "u1"}
    redis_client.delete_session("tok")
    assert redis_client.get_session("tok") is None


def test_geo_roundtrip(fake_redis):
    redis_client.set_last_geo("user-3", 19.07, 72.87)
    geo = redis_client.get_last_geo("user-3")
    assert geo["lat"] == 19.07 and geo["lon"] == 72.87


def test_graceful_fallback_when_unavailable():
    """A client with no connection must not raise — it returns neutral values."""
    down = RedisClient.__new__(RedisClient)
    down._client = None
    down._warned = False
    assert down.cache_get_json("x") is None
    assert down.rate_limit_hit("x", 60) == 0  # fail-open
    assert down.velocity_count("u", 3600) is None
    assert down.publish_alert({"a": 1}) is False
