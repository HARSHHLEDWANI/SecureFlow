"""Access-control tests for role- and ownership-based authorization.

A VIEWER may only see their own transactions/risk profile and is denied the
aggregate fraud-ops surfaces (analytics, blockchain explorer). ANALYST/ADMIN
have full visibility. These cover both the allow and the deny paths.
"""
from __future__ import annotations


def _analyze(client, headers, amount=1234):
    res = client.post(
        "/api/v1/transaction/analyze",
        headers=headers,
        json={"to_vpa": "bob@okaxis", "amount_inr": amount, "txn_type": "P2P",
              "device_id": "trusted-device"},
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]


# ── VIEWER: deny paths ────────────────────────────────────────────────────────


def test_viewer_denied_analytics(viewer_client):
    client, headers, _ = viewer_client
    assert client.get("/api/v1/analytics/dashboard", headers=headers).status_code == 403
    assert client.get("/api/v1/analytics/recent-alerts", headers=headers).status_code == 403
    assert client.get("/api/v1/analytics/model-metrics", headers=headers).status_code == 403


def test_viewer_denied_blockchain(viewer_client):
    client, headers, _ = viewer_client
    assert client.get("/api/v1/blockchain/chain", headers=headers).status_code == 403
    assert client.get("/api/v1/blockchain/validate", headers=headers).status_code == 403
    assert client.get("/api/v1/blockchain/stats", headers=headers).status_code == 403
    assert client.get("/api/v1/blockchain/block/0", headers=headers).status_code == 403


def test_viewer_cannot_read_another_users_transaction(auth_client, viewer_client):
    client, analyst_headers, _ = auth_client
    _, viewer_headers, _ = viewer_client
    # Analyst creates a transaction the viewer does not own.
    txn = _analyze(client, analyst_headers, amount=4321)

    # Cross-user read is 404 (does not leak the id's existence).
    res = client.get(f"/api/v1/transaction/{txn['id']}/status", headers=viewer_headers)
    assert res.status_code == 404


def test_viewer_cannot_read_another_users_risk_profile(auth_client, viewer_client):
    client, _, analyst = auth_client
    _, viewer_headers, viewer = viewer_client
    # Another user's profile → 403.
    denied = client.get(f"/api/v1/risk-score/{analyst['id']}", headers=viewer_headers)
    assert denied.status_code == 403
    # Own profile → 200.
    own = client.get(f"/api/v1/risk-score/{viewer['id']}", headers=viewer_headers)
    assert own.status_code == 200


def test_viewer_listing_is_scoped_to_own_transactions(auth_client, viewer_client):
    client, analyst_headers, _ = auth_client
    _, viewer_headers, _ = viewer_client
    other = _analyze(client, analyst_headers, amount=8888)

    listing = client.get("/api/v1/transaction?limit=200", headers=viewer_headers).json()["data"]
    # The viewer created no transactions, so the analyst's must not appear.
    assert all(t["id"] != other["id"] for t in listing)


# ── ANALYST/ADMIN: allow paths ────────────────────────────────────────────────


def test_analyst_can_read_any_transaction_and_analytics(auth_client, viewer_client):
    client, analyst_headers, _ = auth_client
    _, viewer_headers, viewer = viewer_client
    # Viewer creates a transaction.
    owned = _analyze(client, viewer_headers, amount=777)

    # Analyst can read the viewer's transaction, risk profile, analytics + chain.
    assert client.get(
        f"/api/v1/transaction/{owned['id']}/status", headers=analyst_headers
    ).status_code == 200
    assert client.get(
        f"/api/v1/risk-score/{viewer['id']}", headers=analyst_headers
    ).status_code == 200
    assert client.get("/api/v1/analytics/dashboard", headers=analyst_headers).status_code == 200
    assert client.get("/api/v1/blockchain/chain", headers=analyst_headers).status_code == 200
