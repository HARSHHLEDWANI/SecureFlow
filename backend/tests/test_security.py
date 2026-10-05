"""Phase 2 security and correctness regressions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from app.config import get_settings
from app.core import refresh_tokens as rt
from app.core import redis_client as rc
from app.database import RiskTier, SessionLocal, Transaction, TxnStatus, TxnType, User
from app.dependencies import RateLimiter, client_ip

API = "/api/v1"
PW = "password123"


def _noon(monkeypatch):
    """Pin the login-risk 'unusual hour' signal so tests do not depend on wall-clock time."""
    from app.api.routes import auth

    monkeypatch.setattr(auth, "utcnow", lambda: datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))


def _register(client, email=None):
    email = email or f"sec_{uuid.uuid4().hex[:8]}@test.com"
    res = client.post(f"{API}/auth/register",
                      json={"email": email, "password": PW, "vpa": "sec@okhdfc"})
    assert res.status_code == 201, res.text
    return email, res.json()["data"]


def _login(client, email, device="dev-1", password=PW):
    return client.post(f"{API}/auth/login",
                       json={"email": email, "password": password, "device_id": device})


def _full_login(client, email, device="dev-1"):
    """Log in through step-up if required; leaves the refresh cookie in the client jar."""
    data = _login(client, email, device).json()["data"]
    if data["step_up_required"]:
        data = client.post(f"{API}/auth/verify-step-up",
                           json={"challenge_id": data["challenge_id"], "otp": data["demo_otp"]}).json()["data"]
    return data


def _redis_down(monkeypatch):
    monkeypatch.setattr(rc.redis_client, "_client", None)


def _add_txn(email, device):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).one()
        db.add(Transaction(
            user_id=u.id, from_vpa=u.vpa, to_vpa="x@ybl", amount_inr=100, txn_type=TxnType.P2P,
            device_id=device, location_lat=0.0, location_lon=0.0, risk_score=5,
            risk_tier=RiskTier.LOW, status=TxnStatus.ALLOWED))
        db.commit()
    finally:
        db.close()


# ── 2. Login risk fails closed ──────────────────────────────────────────────────


def test_redis_down_unknown_device_is_not_scored_low(client, monkeypatch):
    _noon(monkeypatch)
    email, _ = _register(client)
    _redis_down(monkeypatch)
    data = _login(client, email, device="never-seen").json()["data"]
    assert data["login_risk_tier"] == "MEDIUM" and data["step_up_required"] is True
    assert data["login_risk_score"] >= 45


def test_redis_down_falls_back_to_database_device_history(client, monkeypatch):
    _noon(monkeypatch)
    email, _ = _register(client)
    _add_txn(email, "dev-known")
    _redis_down(monkeypatch)
    ok = _login(client, email, device="dev-known").json()["data"]
    assert ok["login_risk_tier"] == "LOW" and ok["step_up_required"] is False
    other = _login(client, email, device="dev-other").json()["data"]
    assert other["login_risk_tier"] == "MEDIUM"


def test_redis_and_database_both_unavailable_forces_step_up(monkeypatch):
    from app.api.routes.auth import _assess_login_risk

    _noon(monkeypatch)
    _redis_down(monkeypatch)

    class DeadDB:
        def scalar(self, *_a, **_k):
            raise OperationalError("select", {}, Exception("db down"))

    class U:
        id = "u1"

    score, tier = _assess_login_risk(U(), "dev-1", DeadDB())
    assert tier == "MEDIUM" and score >= 45


# ── 3. Bootstrap admin ──────────────────────────────────────────────────────────


def test_non_bootstrap_first_registrant_is_viewer(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "bootstrap_admin_email", "")
    _, user = _register(client)
    assert user["role"] == "VIEWER"


def test_only_the_bootstrap_email_is_promoted(client, monkeypatch):
    boot = f"boot_{uuid.uuid4().hex[:6]}@test.com"
    monkeypatch.setattr(get_settings(), "bootstrap_admin_email", boot.upper())  # case-insensitive
    _, stranger = _register(client)
    _, admin = _register(client, boot)
    assert stranger["role"] == "VIEWER" and admin["role"] == "ADMIN"


# ── 4. demo_otp ─────────────────────────────────────────────────────────────────


def test_demo_otp_returned_outside_production(client, monkeypatch):
    _noon(monkeypatch)
    email, _ = _register(client)
    data = _login(client, email, device="new-dev").json()["data"]
    assert data["step_up_required"] and data["demo_otp"] and len(data["demo_otp"]) == 6


def test_demo_otp_absent_in_production(client, monkeypatch, caplog):
    _noon(monkeypatch)
    email, _ = _register(client)
    monkeypatch.setattr(get_settings(), "environment", "production")
    import logging

    app_logger = logging.getLogger("secureflow")  # does not propagate to root, so attach directly
    app_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level("INFO", logger="secureflow.auth"):
            data = _login(client, email, device="new-dev").json()["data"]
    finally:
        app_logger.removeHandler(caplog.handler)
    assert data["step_up_required"] is True
    assert data["challenge_id"] and data["demo_otp"] is None
    assert "Step-up OTP" in caplog.text  # delivered out-of-band (logged), not returned


# ── 5. Refresh rotation / reuse / revocation ────────────────────────────────────


def test_refresh_rotates_and_old_token_is_single_use(client, monkeypatch):
    _noon(monkeypatch)
    email, _ = _register(client)
    _full_login(client, email)
    first = client.cookies.get("sf_refresh")
    assert first

    ok = client.post(f"{API}/auth/refresh")
    assert ok.status_code == 200 and ok.json()["data"]["accessToken"]
    second = client.cookies.get("sf_refresh")
    assert second and second != first  # rotated

    # Replaying the rotated-away token is theft: rejected AND the family is revoked...
    client.cookies.set("sf_refresh", first)
    replay = client.post(f"{API}/auth/refresh")
    assert replay.status_code == 401 and "reuse" in replay.json()["error"].lower()
    # ...so even the legitimate successor no longer works.
    client.cookies.set("sf_refresh", second)
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_logout_revokes_the_refresh_token_server_side(client, monkeypatch):
    _noon(monkeypatch)
    email, _ = _register(client)
    _full_login(client, email)
    stolen = client.cookies.get("sf_refresh")
    assert client.post(f"{API}/auth/logout").status_code == 200
    client.cookies.set("sf_refresh", stolen)  # attacker kept a copy: still a valid JWT for 7 days
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_refresh_without_redis_is_rejected_not_trusted(client, monkeypatch):
    _noon(monkeypatch)
    email, _ = _register(client)
    _full_login(client, email)
    _redis_down(monkeypatch)
    res = client.post(f"{API}/auth/refresh")
    assert res.status_code == 401
    assert rt.register("j", "f", "u") is False  # nothing can be issued as verifiable either


def test_pre_rotation_refresh_tokens_are_rejected(client):
    from app.core.security import create_token

    old_style = create_token("some-user", "refresh")  # no jti / fid
    client.cookies.set("sf_refresh", old_style)
    assert client.post(f"{API}/auth/refresh").status_code == 401


# ── 6. Rate limiter keying ──────────────────────────────────────────────────────


def _req(peer, xff=None):
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": (peer, 5555)})


def test_forwarded_ip_used_only_from_trusted_proxy(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "trusted_proxies", "10.0.0.0/8")
    assert client_ip(_req("10.1.2.3", "203.0.113.9")) == "203.0.113.9"
    assert client_ip(_req("10.1.2.3", "203.0.113.9, 10.9.9.9")) == "203.0.113.9"
    # An untrusted peer cannot choose its own key.
    assert client_ip(_req("198.51.100.7", "203.0.113.9")) == "198.51.100.7"
    # A client prepending fake hops cannot forge the key: the last untrusted hop wins.
    assert client_ip(_req("10.1.2.3", "6.6.6.6, 203.0.113.9")) == "203.0.113.9"
    assert client_ip(_req("10.1.2.3", "garbage")) == "10.1.2.3"
    assert client_ip(_req("10.1.2.3")) == "10.1.2.3"
    monkeypatch.setattr(s, "trusted_proxies", "")
    assert client_ip(_req("10.1.2.3", "203.0.113.9")) == "10.1.2.3"


def test_rate_limit_is_per_forwarded_client_not_per_proxy(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8")
    limiter = RateLimiter("probe", limit=2)
    for _ in range(2):
        limiter(_req("10.0.0.2", "203.0.113.1"))
    with pytest.raises(HTTPException) as exc:
        limiter(_req("10.0.0.2", "203.0.113.1"))
    assert exc.value.status_code == 429
    limiter(_req("10.0.0.2", "203.0.113.2"))  # a different user behind the same proxy is fine


def test_per_account_login_throttle_spans_ips(client, monkeypatch):
    _noon(monkeypatch)
    monkeypatch.setattr(get_settings(), "login_account_limit", 3)
    email, _ = _register(client)
    for i in range(3):  # credential stuffing from rotating addresses
        r = client.post(f"{API}/auth/login", json={"email": email, "password": "wrong-pw-1", "device_id": "d"},
                        headers={"X-Forwarded-For": f"203.0.113.{i}"})
        assert r.status_code == 401
    locked = _login(client, email, password=PW)  # even the right password is refused now
    assert locked.status_code == 429


def test_successful_login_clears_the_account_counter(client, monkeypatch):
    _noon(monkeypatch)
    monkeypatch.setattr(get_settings(), "login_account_limit", 3)
    email, _ = _register(client)
    for _ in range(2):
        assert _login(client, email, password="wrong-pw-1").status_code == 401
    assert _login(client, email).status_code == 200
    for _ in range(2):  # counter restarted from zero
        assert _login(client, email, password="wrong-pw-1").status_code == 401
    assert _login(client, email).status_code == 200


# ── 9. Error envelope ───────────────────────────────────────────────────────────


def test_http_exceptions_use_the_envelope_with_unchanged_status(client):
    res = client.get(f"{API}/analytics/dashboard")  # no token
    assert res.status_code == 401
    body = res.json()
    assert body == {"success": False, "data": None, "error": "Missing bearer token"}
    assert "detail" not in body

    missing = client.get(f"{API}/no/such/route")
    assert missing.status_code == 404 and missing.json()["success"] is False


def test_validation_errors_use_the_envelope(client):
    res = client.post(f"{API}/auth/register", json={"email": "not-an-email", "password": "x", "vpa": "y"})
    assert res.status_code == 422
    body = res.json()
    assert body["success"] is False and body["error"].startswith("Validation failed")
    assert {e["field"] for e in body["data"]["errors"]} >= {"email", "password"}
