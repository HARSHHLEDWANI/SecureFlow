"""Tests for the UPI Simulation Lab endpoints and engine.

These exercise the real pipeline end-to-end (ML + risk + blockchain) via the
demo users seeded on app startup. Scenario *decisions* are asserted at the tier
level (APPROVED / STEP_UP / BLOCKED) rather than exact scores, since the score
is produced by the real model.
"""
from __future__ import annotations

import pytest

PREFIX = "/api/v1/upi"


def _data(res):
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    return body["data"]


# ── Demo data endpoints ───────────────────────────────────────────────────────


def test_demo_users_are_seeded(client):
    data = _data(client.get(f"{PREFIX}/users"))
    vpas = {u["vpa"] for u in data["users"]}
    assert "harsh@upi" in vpas
    assert all(u["seeded"] for u in data["users"])


def test_scenarios_listed(client):
    data = _data(client.get(f"{PREFIX}/scenarios"))
    ids = {s["id"] for s in data["scenarios"]}
    assert {"normal", "impossible_travel", "account_takeover", "rapid_fire"} <= ids


def test_user_history_returns_seeded_transactions(client):
    data = _data(client.get(f"{PREFIX}/user/harsh@upi/history"))
    assert data["vpa"] == "harsh@upi"
    assert len(data["transactions"]) > 0


# ── Payment processing ────────────────────────────────────────────────────────


def test_pay_normal_is_approved(client):
    data = _data(
        client.post(
            f"{PREFIX}/pay",
            json={
                "sender_vpa": "harsh@upi",
                "receiver_vpa": "kirana@okaxis",
                "amount_inr": 350,
                "txn_type": "P2M",
                "city": "Pune",
            },
        )
    )
    assert data["decision"] == "APPROVED"
    assert data["risk_tier"] == "LOW"
    assert data["block_index"] is not None
    # Real per-stage timing must be present.
    assert set(data["pipeline"]["stages"]) >= {
        "initiated", "ml_prediction", "risk_scored", "blockchain_logged", "decision"
    }


def test_pay_missing_field_is_422(client):
    res = client.post(
        f"{PREFIX}/pay", json={"sender_vpa": "harsh@upi", "amount_inr": 100}
    )
    assert res.status_code == 422


def test_pay_invalid_vpa_is_422(client):
    res = client.post(
        f"{PREFIX}/pay",
        json={"sender_vpa": "harsh@upi", "receiver_vpa": "nope-no-at", "amount_inr": 100},
    )
    assert res.status_code == 422


def test_pay_unknown_sender_is_422(client):
    res = client.post(
        f"{PREFIX}/pay",
        json={"sender_vpa": "ghost@upi", "receiver_vpa": "x@ybl", "amount_inr": 100},
    )
    assert res.status_code == 422


# ── Scenarios ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "scenario_id,expected_decision",
    [
        ("normal", "APPROVED"),
        ("high_amount", "STEP_UP"),
        ("impossible_travel", "BLOCKED"),
        ("new_device_high_value", "STEP_UP"),
        ("midnight_anomaly", "STEP_UP"),
        ("account_takeover", "BLOCKED"),
    ],
)
def test_scenario_decisions(client, scenario_id, expected_decision):
    data = _data(client.post(f"{PREFIX}/scenario/{scenario_id}"))
    assert data["rapid_fire"] is False
    assert data["result"]["decision"] == expected_decision
    assert data["match"] is True


def test_scenarios_are_repeatable_regardless_of_order(client):
    """Running an attack then 'normal' must not contaminate 'normal'."""
    client.post(f"{PREFIX}/scenario/account_takeover")
    client.post(f"{PREFIX}/scenario/impossible_travel")
    data = _data(client.post(f"{PREFIX}/scenario/normal"))
    assert data["result"]["decision"] == "APPROVED"


def test_unknown_scenario_is_404(client):
    res = client.post(f"{PREFIX}/scenario/does_not_exist")
    assert res.status_code == 404


def test_rapid_fire_escalates_to_blocked(client):
    client.post(f"{PREFIX}/reset")  # clean baseline (tests share one DB)
    data = _data(client.post(f"{PREFIX}/scenario/rapid_fire"))
    assert data["rapid_fire"] is True
    decisions = [r["decision"] for r in data["results"]]
    assert decisions[0] == "APPROVED"          # first clears
    assert "BLOCKED" in decisions[-3:]         # burst is blocked by the end
    # Scores should be non-trivially rising overall (velocity + amount).
    scores = [r["risk_score"] for r in data["results"]]
    assert scores[-1] > scores[0]


def test_rapid_fire_endpoint(client):
    data = _data(client.post(f"{PREFIX}/rapid-fire"))
    assert len(data["results"]) == 10


# ── Pipeline tracking + integration ───────────────────────────────────────────


def test_pipeline_status_available_after_pay(client):
    pay = _data(
        client.post(
            f"{PREFIX}/pay",
            json={"sender_vpa": "amit@upi", "receiver_vpa": "bigbasket@ybl", "amount_inr": 1500},
        )
    )
    snap = _data(client.get(f"{PREFIX}/pipeline-status/{pay['txn_id']}"))
    assert snap["txn_id"] == pay["txn_id"]
    assert snap["stages"]["decision"]["status"] == "complete"


def test_pipeline_status_unknown_is_404(client):
    assert client.get(f"{PREFIX}/pipeline-status/nope").status_code == 404


def test_lab_transactions_appear_on_blockchain(client):
    from app.core.blockchain import get_blockchain

    before = len(get_blockchain().chain)
    client.post(
        f"{PREFIX}/pay",
        json={"sender_vpa": "harsh@upi", "receiver_vpa": "shop@ybl", "amount_inr": 500},
    )
    after = len(get_blockchain().chain)
    assert after == before + 1


def test_reset_reseeds_demo_users(client):
    data = _data(client.post(f"{PREFIX}/reset"))
    assert data["reset"] is True
    assert data["users_seeded"] >= 5
