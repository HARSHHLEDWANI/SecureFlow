"""Pytest fixtures: isolated DB/chain, fake Redis, and authenticated clients."""
import os
import tempfile
import uuid

# Configure an isolated environment BEFORE the app modules are imported.
_TMP = tempfile.mkdtemp(prefix="sf_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ["BLOCKCHAIN_PATH"] = os.path.join(_TMP, "chain.json")
os.environ["BLOCKCHAIN_DIFFICULTY"] = "2"
os.environ["RATE_LIMIT_REQUESTS"] = "1000"
os.environ["ENVIRONMENT"] = "development"

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Back the Redis client with an in-memory fakeredis for every test."""
    from app.core import redis_client as rc

    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(rc.redis_client, "_client", fake)
    monkeypatch.setattr(rc.redis_client, "_warned", False)
    yield fake
    fake.flushall()


@pytest.fixture
def client():
    """A TestClient with the application lifespan active (tables created)."""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client):
    """A TestClient with an authenticated user; returns (client, headers, user)."""
    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "vpa": "tester@okhdfc"},
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123", "device_id": "trusted-device"},
    )
    data = res.json()["data"]
    if data["step_up_required"]:
        res = client.post(
            "/api/v1/auth/verify-step-up",
            json={"challenge_id": data["challenge_id"], "otp": data["demo_otp"]},
        )
        data = res.json()["data"]
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return client, headers, data["user"]
