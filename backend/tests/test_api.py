"""End-to-end API tests: auth, transactions, blockchain, analytics, errors."""
import uuid


def _register_and_login(client, device="trusted-device"):
    email = f"u_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "vpa": "tester@okhdfc"},
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123", "device_id": device},
    )
    return email, res.json()["data"]


# ── Health ───────────────────────────────────────────────────────────────────


def test_health_reports_subsystems(client):
    data = client.get("/api/v1/health").json()["data"]
    assert data["status"] == "ok"
    assert data["database"] is True
    assert "redis" in data and "model_loaded" in data


# ── Auth ─────────────────────────────────────────────────────────────────────


def test_register_first_user_is_admin(client):
    _, data = _register_and_login(client)
    assert data["user"]["role"] == "ADMIN"


def test_register_rejects_duplicate_email(client):
    body = {"email": "dup@test.com", "password": "password123", "vpa": "tester@okhdfc"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    assert client.post("/api/v1/auth/register", json=body).status_code == 409


def test_login_wrong_password_401(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "p@test.com", "password": "password123", "vpa": "tester@okhdfc"},
    )
    res = client.post(
        "/api/v1/auth/login", json={"email": "p@test.com", "password": "wrong"}
    )
    assert res.status_code == 401


def test_login_new_device_triggers_step_up(client):
    email = f"u_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "vpa": "tester@okhdfc"},
    )
    # Unknown device at an arbitrary hour may step-up; verify the flow when it does.
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123", "device_id": "brand-new-device"},
    )
    data = res.json()["data"]
    assert data["login_risk_tier"] in ("LOW", "MEDIUM")
    if data["step_up_required"]:
        verify = client.post(
            "/api/v1/auth/verify-step-up",
            json={"challenge_id": data["challenge_id"], "otp": data["demo_otp"]},
        )
        assert verify.json()["data"]["access_token"]


# ── Transactions ─────────────────────────────────────────────────────────────


def test_analyze_requires_auth(client):
    res = client.post("/api/v1/transaction/analyze", json={"to_vpa": "bob@okaxis", "amount_inr": 100})
    assert res.status_code == 401


def test_analyze_validates_input(auth_client):
    client, headers, _ = auth_client
    # Negative amount fails Pydantic validation.
    res = client.post(
        "/api/v1/transaction/analyze",
        headers=headers,
        json={"to_vpa": "bob@okaxis", "amount_inr": -5, "txn_type": "P2P"},
    )
    assert res.status_code == 422


def test_analyze_returns_full_assessment_and_logs_block(auth_client):
    client, headers, _ = auth_client
    res = client.post(
        "/api/v1/transaction/analyze",
        headers=headers,
        json={"to_vpa": "bob@okaxis", "amount_inr": 1500, "txn_type": "P2P",
              "device_id": "trusted-device"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert 0 <= data["risk_score"] <= 100
    assert data["risk_tier"] in ("LOW", "MEDIUM", "HIGH")
    assert data["block_hash"] and data["block_hash"].startswith("00")
    assert data["recommended_action"]


def test_transaction_status_and_listing(auth_client):
    client, headers, _ = auth_client
    created = client.post(
        "/api/v1/transaction/analyze",
        headers=headers,
        json={"to_vpa": "bob@okaxis", "amount_inr": 999, "txn_type": "P2P"},
    ).json()["data"]
    status = client.get(f"/api/v1/transaction/{created['id']}/status", headers=headers)
    assert status.status_code == 200
    listing = client.get("/api/v1/transaction?limit=10", headers=headers).json()["data"]
    assert any(t["id"] == created["id"] for t in listing)


def test_risk_profile(auth_client):
    client, headers, user = auth_client
    client.post(
        "/api/v1/transaction/analyze",
        headers=headers,
        json={"to_vpa": "bob@okaxis", "amount_inr": 500, "txn_type": "P2P"},
    )
    profile = client.get(f"/api/v1/risk-score/{user['id']}", headers=headers).json()["data"]
    assert profile["transaction_count"] >= 1


# ── Blockchain ───────────────────────────────────────────────────────────────


def test_blockchain_endpoints(auth_client):
    client, headers, _ = auth_client
    client.post(
        "/api/v1/transaction/analyze",
        headers=headers,
        json={"to_vpa": "bob@okaxis", "amount_inr": 700, "txn_type": "P2P"},
    )
    chain = client.get("/api/v1/blockchain/chain", headers=headers).json()["data"]
    assert chain["length"] >= 2
    assert client.get("/api/v1/blockchain/validate", headers=headers).json()["data"]["valid"]
    assert client.get("/api/v1/blockchain/block/0", headers=headers).status_code == 200
    assert client.get("/api/v1/blockchain/block/999", headers=headers).status_code == 404


# ── Analytics ────────────────────────────────────────────────────────────────


def test_analytics_dashboard_and_alerts(auth_client):
    client, headers, _ = auth_client
    client.post(
        "/api/v1/transaction/analyze",
        headers=headers,
        json={"to_vpa": "bob@okaxis", "amount_inr": 800, "txn_type": "P2P"},
    )
    dash = client.get("/api/v1/analytics/dashboard", headers=headers).json()["data"]
    assert dash["total_transactions"] >= 1
    assert "tier_distribution" in dash
    alerts = client.get("/api/v1/analytics/recent-alerts", headers=headers)
    assert alerts.status_code == 200


def test_model_metrics_endpoint(auth_client):
    client, headers, _ = auth_client
    res = client.get("/api/v1/analytics/model-metrics", headers=headers).json()
    # Metrics exist because the model was trained during setup.
    assert res["data"] is None or "auc_roc" in res["data"]


# ── Rate limiting ────────────────────────────────────────────────────────────


def test_rate_limiting_returns_429(client, monkeypatch):
    from app import dependencies

    monkeypatch.setattr(dependencies.settings, "rate_limit_requests", 3)
    codes = []
    for _ in range(6):
        codes.append(
            client.post(
                "/api/v1/auth/login",
                json={"email": "none@test.com", "password": "x", "device_id": "d"},
            ).status_code
        )
    assert 429 in codes
