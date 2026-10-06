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
    monkeypatch.setattr(get_settings(), "refresh_reuse_grace_seconds", 0)  # no race leniency
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


def test_a_just_rotated_token_is_a_retryable_race_not_theft(client, monkeypatch):
    _noon(monkeypatch)
    monkeypatch.setattr(get_settings(), "refresh_reuse_grace_seconds", 60)
    email, _ = _register(client)
    _full_login(client, email)
    first = client.cookies.get("sf_refresh")
    assert client.post(f"{API}/auth/refresh").status_code == 200
    second = client.cookies.get("sf_refresh")

    client.cookies.set("sf_refresh", first)  # two tabs refreshed in the same instant
    raced = client.post(f"{API}/auth/refresh")
    assert raced.status_code == 409
    client.cookies.set("sf_refresh", second)  # family NOT revoked: the successor still works
    assert client.post(f"{API}/auth/refresh").status_code == 200


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


# ── 1. UPI Lab is no longer an anonymous write path ─────────────────────────────

PAY = {"sender_vpa": "harsh@upi", "receiver_vpa": "kirana@okaxis", "amount_inr": 350,
       "txn_type": "P2M", "city": "Pune"}


def _demo_headers(client):
    token = client.post(f"{API}/upi/session").json()["data"]["token"]
    return {"X-Demo-Session": token}


def test_mutating_lab_routes_reject_missing_or_forged_sessions(client):
    calls = [("post", "/upi/pay", {"json": PAY}), ("post", "/upi/scenario/normal", {}),
             ("post", "/upi/rapid-fire", {}), ("post", "/upi/reset", {})]
    for method, path, kw in calls:
        assert getattr(client, method)(f"{API}{path}", **kw).status_code == 401, path
        forged = getattr(client, method)(f"{API}{path}", headers={"X-Demo-Session": "garbage"}, **kw)
        assert forged.status_code == 401, path


def test_a_user_access_token_is_not_a_demo_session(client):
    from app.core.security import create_token

    for tok in (create_token("someone", "access"), create_token("someone", "refresh")):
        res = client.post(f"{API}/upi/pay", json=PAY, headers={"X-Demo-Session": tok})
        assert res.status_code == 401
    # ...and a demo token is not a user token.
    demo = _demo_headers(client)["X-Demo-Session"]
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {demo}"}).status_code == 401


def test_expired_demo_session_is_rejected(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_session_ttl_minutes", -1)
    headers = _demo_headers(client)
    res = client.post(f"{API}/upi/pay", json=PAY, headers=headers)
    assert res.status_code == 401 and "expired" in res.json()["error"].lower()


def test_lab_reads_stay_public(client):
    assert client.get(f"{API}/upi/users").status_code == 200
    assert client.get(f"{API}/upi/scenarios").status_code == 200


def test_lab_rows_are_flagged_and_hidden_from_analytics_and_staff_list(auth_client):
    client, staff, _ = auth_client
    res = client.post(f"{API}/upi/pay", json=PAY, headers=_demo_headers(client))
    assert res.status_code == 200
    txn_id = res.json()["data"]["txn_id"]

    db = SessionLocal()
    try:
        assert db.get(Transaction, txn_id).is_demo is True
        real = db.query(Transaction).filter(Transaction.is_demo.is_(False)).count()
        everything = db.query(Transaction).count()
    finally:
        db.close()
    assert everything > real

    default = client.get(f"{API}/analytics/dashboard", headers=staff).json()["data"]
    with_demo = client.get(f"{API}/analytics/dashboard?include_demo=true", headers=staff).json()["data"]
    assert default["total_transactions"] == real
    assert with_demo["total_transactions"] == everything

    ids = lambda r: {t["id"] for t in r.json()["data"]}  # noqa: E731
    assert txn_id not in ids(client.get(f"{API}/transaction?limit=200", headers=staff))
    assert txn_id in ids(client.get(f"{API}/transaction?limit=200&include_demo=true", headers=staff))


def test_normal_analyze_rows_are_not_demo(auth_client):
    client, staff, _ = auth_client
    res = client.post(f"{API}/transaction/analyze", headers=staff, json={
        "to_vpa": "shop@okaxis", "amount_inr": 500, "txn_type": "P2M", "device_id": "trusted-device",
        "location_lat": 19.07, "location_lon": 72.87})
    assert res.status_code == 200
    db = SessionLocal()
    try:
        assert db.get(Transaction, res.json()["data"]["id"]).is_demo is False
    finally:
        db.close()


def test_per_session_transaction_cap(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_session_max_transactions", 2)
    h = _demo_headers(client)
    assert client.post(f"{API}/upi/pay", json=PAY, headers=h).status_code == 200
    assert client.post(f"{API}/upi/pay", json=PAY, headers=h).status_code == 200
    third = client.post(f"{API}/upi/pay", json=PAY, headers=h)
    assert third.status_code == 429 and "session limit" in third.json()["error"].lower()
    # A burst is charged for every transaction it would create.
    h2 = _demo_headers(client)
    assert client.post(f"{API}/upi/rapid-fire", headers=h2).status_code == 429
    assert client.post(f"{API}/upi/pay", json=PAY, headers=_demo_headers(client)).status_code == 200


def test_session_cap_still_holds_with_redis_down(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_session_max_transactions", 1)
    h = _demo_headers(client)
    _redis_down(monkeypatch)
    assert client.post(f"{API}/upi/pay", json=PAY, headers=h).status_code == 200
    assert client.post(f"{API}/upi/pay", json=PAY, headers=h).status_code == 429


def test_global_demo_row_cap(client, monkeypatch):
    db = SessionLocal()
    try:
        demo_rows = db.query(Transaction).filter(Transaction.is_demo.is_(True)).count()
    finally:
        db.close()
    monkeypatch.setattr(get_settings(), "demo_max_total_transactions", demo_rows)
    res = client.post(f"{API}/upi/pay", json=PAY, headers=_demo_headers(client))
    assert res.status_code == 429 and "full" in res.json()["error"].lower()


def test_session_issuance_is_rate_limited(client):
    codes = [client.post(f"{API}/upi/session").status_code for _ in range(12)]
    assert codes[:10] == [200] * 10 and 429 in codes[10:]


def test_reset_deletes_only_demo_rows(client):
    real_email, _ = _register(client)
    _add_txn(real_email, "dev-real")  # a genuine (is_demo=False) row
    h = _demo_headers(client)
    client.post(f"{API}/upi/pay", json=PAY, headers=h)

    assert client.post(f"{API}/upi/reset", headers=h).status_code == 200

    db = SessionLocal()
    try:
        real_user = db.query(User).filter(User.email == real_email).one()
        kept = db.query(Transaction).filter(Transaction.user_id == real_user.id).count()
        demo_ids = [u.id for u in db.query(User).filter(User.email.like("%@secureflow.local"))]
        leaked = db.query(Transaction).filter(
            Transaction.user_id.in_(demo_ids), Transaction.is_demo.is_(False)).count()
        reseeded = db.query(Transaction).filter(Transaction.is_demo.is_(True)).count()
    finally:
        db.close()
    assert kept == 1 and leaked == 0 and reseeded > 0


def test_every_state_changing_route_requires_a_user_or_demo_token():
    """Route audit: nothing mutates state anonymously except the auth endpoints themselves."""
    from fastapi.routing import APIRoute

    from app.main import app

    guards = {"get_current_user", "require_staff", "require_demo_session", "_checker"}
    auth_endpoints = {"/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/verify-step-up",
                      "/api/v1/auth/refresh", "/api/v1/auth/logout", "/api/v1/upi/session"}

    def deps(dependant):
        for d in dependant.dependencies:
            yield getattr(d.call, "__name__", "")
            yield from deps(d)

    unguarded = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not (route.methods & {"POST", "PUT", "PATCH", "DELETE"}):
            continue
        if route.path in auth_endpoints:
            continue
        if not guards & set(deps(route.dependant)):
            unguarded.append(f"{sorted(route.methods)} {route.path}")
    assert unguarded == []


# ── Hostile-review regressions ──────────────────────────────────────────────────


def test_case_variant_emails_cannot_duplicate_or_hijack_the_bootstrap_admin(client, monkeypatch):
    boot = f"owner_{uuid.uuid4().hex[:6]}@test.com"
    monkeypatch.setattr(get_settings(), "bootstrap_admin_email", boot)
    local, domain = boot.split("@")
    _, first = _register(client, f"{local.upper()}@{domain.upper()}")  # shouty casing
    assert first["email"] == boot and first["role"] == "ADMIN"        # normalised: it IS the owner
    dup = client.post(f"{API}/auth/register",
                      json={"email": f"{local.title()}@{domain}", "password": PW, "vpa": "xx@okhdfc"})
    assert dup.status_code == 409  # no second account under another casing, so no second ADMIN
    assert _login(client, boot.upper()).status_code == 200  # login is case-insensitive too


def test_legacy_mixed_case_accounts_can_still_log_in(client, monkeypatch):
    _noon(monkeypatch)
    from app.core.security import hash_password

    email = f"Legacy_{uuid.uuid4().hex[:6]}@Test.com"  # stored before normalisation existed
    db = SessionLocal()
    try:
        db.add(User(email=email, password_hash=hash_password(PW), vpa="l@okhdfc"))
        db.commit()
    finally:
        db.close()
    assert _login(client, email.lower()).status_code == 200


def test_step_up_works_when_redis_is_down(client, monkeypatch):
    """Fail-closed login must not become a permanent lockout during a Redis outage."""
    _noon(monkeypatch)
    email, _ = _register(client)
    _redis_down(monkeypatch)
    data = _login(client, email, device="new-dev").json()["data"]
    assert data["step_up_required"] is True
    done = client.post(f"{API}/auth/verify-step-up",
                       json={"challenge_id": data["challenge_id"], "otp": data["demo_otp"]})
    assert done.status_code == 200 and done.json()["data"]["access_token"]
    assert client.cookies.get("sf_refresh") in (None, "")  # nothing verifiable to refresh with


def test_step_up_challenge_is_destroyed_after_too_many_wrong_codes(client, monkeypatch):
    _noon(monkeypatch)
    email, _ = _register(client)
    data = _login(client, email, device="new-dev").json()["data"]
    cid, otp = data["challenge_id"], data["demo_otp"]
    wrong = "000000" if otp != "000000" else "111111"
    codes = [client.post(f"{API}/auth/verify-step-up", json={"challenge_id": cid, "otp": wrong}).status_code
             for _ in range(5)]
    assert codes[:4] == [401] * 4 and codes[4] == 400
    assert client.post(f"{API}/auth/verify-step-up", json={"challenge_id": cid, "otp": otp}).status_code == 400


def test_unknown_email_costs_one_password_verify_like_a_real_one(client, monkeypatch):
    from app.api.routes import auth

    calls = []
    real = auth.verify_password
    monkeypatch.setattr(auth, "verify_password", lambda pw, h: calls.append(h) or real(pw, h))
    email, _ = _register(client)
    _login(client, f"nobody_{uuid.uuid4().hex[:6]}@test.com", password="wrongpass1")
    _login(client, email, password="wrongpass1")
    assert len(calls) == 2  # both paths ran bcrypt, so timing does not reveal which emails exist


def test_account_throttle_and_rate_limits_still_work_with_redis_down(client, monkeypatch):
    from fastapi import HTTPException

    _noon(monkeypatch)
    monkeypatch.setattr(get_settings(), "login_account_limit", 3)
    email, _ = _register(client)
    _redis_down(monkeypatch)
    for _ in range(3):
        assert _login(client, email, password="wrongpass1").status_code == 401
    assert _login(client, email).status_code == 429  # the control did not silently switch off

    limiter = RateLimiter("redis-down-probe", limit=2)
    for _ in range(2):
        limiter(_req("198.51.100.1"))
    with pytest.raises(HTTPException) as exc:
        limiter(_req("198.51.100.1"))
    assert exc.value.status_code == 429


def test_cookie_endpoints_reject_foreign_origins(client):
    for path in ("refresh", "logout"):
        evil = client.post(f"{API}/auth/{path}", headers={"Origin": "https://evil.example"})
        assert evil.status_code == 403, path
    allowed = get_settings().cors_origins_list[0]
    assert client.post(f"{API}/auth/refresh", headers={"Origin": allowed}).status_code == 401  # past the gate
    assert client.post(f"{API}/auth/refresh").status_code == 401  # non-browser client: no Origin


def test_refresh_cookie_supports_cross_site_frontends(client, monkeypatch):
    _noon(monkeypatch)
    monkeypatch.setattr(get_settings(), "refresh_cookie_samesite", "none")
    email, _ = _register(client)
    data = _login(client, email, device="new-dev").json()["data"]
    res = client.post(f"{API}/auth/verify-step-up",
                      json={"challenge_id": data["challenge_id"], "otp": data["demo_otp"]})
    cookie = res.headers["set-cookie"].lower()
    assert "samesite=none" in cookie and "secure" in cookie and "httponly" in cookie


def test_production_refuses_default_or_weak_secrets(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    s = get_settings()
    monkeypatch.setattr(s, "environment", "production")
    monkeypatch.setattr(s, "jwt_secret", "change_me_in_production")
    assert any("JWT_SECRET" in p for p in s.insecure_production_settings())
    with pytest.raises(RuntimeError, match="Refusing to start"):
        with TestClient(app):
            pass

    monkeypatch.setattr(s, "jwt_secret", "a" * 40)
    monkeypatch.setattr(s, "jwt_refresh_secret", "a" * 40)
    assert any("must differ" in p for p in s.insecure_production_settings())
    monkeypatch.setattr(s, "jwt_refresh_secret", "b" * 40)
    assert s.insecure_production_settings() == []


def test_prediction_cache_is_keyed_by_model_version(fake_redis):
    from app.core.pipeline import predict_cached
    from app.ml.model import get_model_service

    predict_cached({"amount_inr": 1234.5, "txn_type": "P2P", "hour": 11})
    version = get_model_service().version
    keys = list(fake_redis.keys("prediction:*"))
    assert keys and all(k.startswith(f"prediction:{version}:") for k in keys)


def _ledger_for_test():
    import os
    import tempfile

    from app.core.audit_ledger import AuditLedger

    return AuditLedger(os.path.join(tempfile.mkdtemp(), "c.json"), difficulty=1)


def test_failed_mine_does_not_strand_a_record_in_pending(monkeypatch):
    ledger = _ledger_for_test()
    real = ledger._persist_to_file

    def boom():
        raise OSError("disk full")

    monkeypatch.setattr(ledger, "_persist_to_file", boom)
    with pytest.raises(OSError):
        ledger.mine_block({"transaction_id": "lost"})
    assert ledger.pending == []
    monkeypatch.setattr(ledger, "_persist_to_file", real)
    assert len(ledger.chain) == 1  # memory did not run ahead of the failed write
    ok = ledger.mine_block({"transaction_id": "next"})
    assert [t.get("transaction_id") for t in ok.transactions] == ["next"]  # not ["lost", "next"]


def test_model_metrics_endpoint_omits_bulky_sweeps(auth_client):
    client, headers, _ = auth_client
    m = client.get(f"{API}/analytics/model-metrics", headers=headers).json()["data"]
    assert "threshold_sweep" not in m and "sweep" not in m.get("operating_threshold", {})
    assert m["headline"]["metric"] == "pr_auc" and "risk_thresholds" in m


def test_attacker_cannot_lock_the_real_user_out_of_their_usual_network(client, monkeypatch):
    from app.api.routes import auth

    _noon(monkeypatch)
    s = get_settings()
    monkeypatch.setattr(s, "login_account_limit", 3)
    monkeypatch.setattr(s, "login_trusted_ip_multiplier", 5)
    where = {"ip": "203.0.113.10"}  # the victim's home network
    monkeypatch.setattr(auth, "client_ip", lambda request: where["ip"])
    email, _ = _register(client)
    _full_login(client, email, device="home-laptop")  # victim logs in once: that IP becomes familiar

    where["ip"] = "198.51.100.66"  # attacker, elsewhere, burns the account's failure budget
    for _ in range(3):
        assert _login(client, email, password="wrongpass1").status_code == 401
    assert _login(client, email).status_code == 429          # the attacker's address is locked out...

    where["ip"] = "203.0.113.10"
    assert _login(client, email, device="home-laptop").status_code == 200  # ...the victim is not

    # A familiar address is not a free pass: guessing from it is bounded at 5x the limit.
    # (The victim's successful login reset the counter; 15 wrong guesses reach 5 x 3.)
    for _ in range(15):
        assert _login(client, email, password="wrongpass1").status_code == 401
    assert _login(client, email, device="home-laptop").status_code == 429
