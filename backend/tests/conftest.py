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
# Isolate the model + feedback candidates to the temp dir so tests (esp. model
# promotion) never touch the developer's real ./data model. The autouse
# ensure_trained_model fixture fast-trains into these paths if absent.
os.environ["MODEL_PATH"] = os.path.join(_TMP, "fraud_model.joblib")
os.environ["MODEL_METRICS_PATH"] = os.path.join(_TMP, "model_metrics.json")
os.environ["FEEDBACK_MODEL_DIR"] = os.path.join(_TMP, "models")
# Frozen holdout / train pool written by training; benchmark outputs kept apart.
os.environ["HOLDOUT_PATH"] = os.path.join(_TMP, "holdout.parquet")
os.environ["TRAIN_POOL_PATH"] = os.path.join(_TMP, "train_pool.parquet")
os.environ["BENCHMARK_MODEL_PATH"] = os.path.join(_TMP, "benchmark_model.joblib")
os.environ["BENCHMARK_METRICS_PATH"] = os.path.join(_TMP, "benchmark_metrics.json")
os.environ["FEEDBACK_RETRAIN_FAST"] = "true"

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def ensure_trained_model():
    """Guarantee a trained fraud model exists before any test runs.

    The model artifact (``settings.model_path``) is gitignored, so on a fresh
    clone it is absent and ``ModelService`` would silently fall back to the
    interpretable heuristic — which scores severe attack patterns lower than the
    trained RandomForest, breaking the scenario-decision tests. We train a real
    model here (fast path: fixed hyperparameters, no grid search — a few seconds)
    so a bare ``pytest`` on a fresh clone goes green with no manual step. If a
    full model already exists (e.g. from ``python -m app.ml.training``) it is
    left untouched.
    """
    settings = get_settings()
    if not os.path.exists(settings.model_path):
        from app.ml.training import run_training

        run_training(fast=True)
    yield


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


def _set_role(email: str, role_name: str) -> None:
    """Force a registered user's role directly in the DB (test setup helper)."""
    from app.database import Role, SessionLocal, User
    from sqlalchemy import select

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        user.role = Role(role_name)
        db.commit()
    finally:
        db.close()


def _register_login(client, email, role="ANALYST", device="trusted-device"):
    """Register a user, set their role, and return (headers, user)."""
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "vpa": "tester@okhdfc"},
    )
    _set_role(email, role)
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123", "device_id": device},
    )
    data = res.json()["data"]
    if data["step_up_required"]:
        res = client.post(
            "/api/v1/auth/verify-step-up",
            json={"challenge_id": data["challenge_id"], "otp": data["demo_otp"]},
        )
        data = res.json()["data"]
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return headers, data["user"]


@pytest.fixture
def auth_client(client):
    """A TestClient with an authenticated ANALYST user.

    Returns ``(client, headers, user)``. ANALYST is used (rather than the default
    VIEWER) so the fraud-ops read endpoints — analytics, blockchain explorer,
    full transaction listing — are accessible, matching how a fraud analyst uses
    the tool. Ownership/deny-path behaviour is covered by ``viewer_client``.
    """
    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    headers, user = _register_login(client, email, role="ANALYST")
    return client, headers, user


@pytest.fixture
def viewer_client(client):
    """A TestClient with an authenticated VIEWER user (least privilege).

    Returns ``(client, headers, user)``. A VIEWER may only see their own
    transactions/risk profile and is denied analytics + blockchain endpoints.
    """
    email = f"viewer_{uuid.uuid4().hex[:8]}@test.com"
    headers, user = _register_login(client, email, role="VIEWER", device="viewer-device")
    return client, headers, user
