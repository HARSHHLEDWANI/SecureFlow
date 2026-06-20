"""Tests for multi-admin consensus governance of fraud-decision overrides."""
from __future__ import annotations

import uuid

import pytest

from app.core.governance import COUNCIL_PASSWORD, GOVERNANCE_COUNCIL

API = "/api/v1"
COUNCIL_EMAILS = [c["email"] for c in GOVERNANCE_COUNCIL]


def _data(res):
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]


def _login(client, email, password=COUNCIL_PASSWORD, device="gov-device"):
    res = client.post(f"{API}/auth/login", json={"email": email, "password": password, "device_id": device})
    data = res.json()["data"]
    if data.get("step_up_required"):
        res = client.post(
            f"{API}/auth/verify-step-up",
            json={"challenge_id": data["challenge_id"], "otp": data["demo_otp"]},
        )
        data = res.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}


def _council_headers(client):
    return [_login(client, e, device=f"dev-{i}") for i, e in enumerate(COUNCIL_EMAILS)]


# UPI Lab decision labels → underlying TxnStatus stored on the transaction/chain.
_DECISION_TO_STATUS = {"APPROVED": "ALLOWED", "STEP_UP": "STEP_UP", "BLOCKED": "BLOCKED"}


def _make_txn(client):
    """Create a real transaction via the UPI Lab and return its id + TxnStatus."""
    d = _data(client.post(f"{API}/upi/pay", json={
        "sender_vpa": "harsh@upi", "receiver_vpa": "shop@ybl", "amount_inr": 500, "txn_type": "P2M"}))
    return d["txn_id"], _DECISION_TO_STATUS[d["decision"]]


def _make_admin(client):
    """An ADMIN-role user that is NOT a council member (created directly)."""
    from app.core.security import hash_password
    from app.database import Role, SessionLocal, User

    email = f"boss_{uuid.uuid4().hex[:8]}@test.com"
    db = SessionLocal()
    db.add(User(email=email, password_hash=hash_password("password123"),
                vpa="bossadmin@okhdfc", role=Role.ADMIN))
    db.commit()
    db.close()
    return _login(client, email, password="password123", device="boss-dev")


# ── Council + access control ──────────────────────────────────────────────────


def test_council_has_four_members(client):
    headers = _login(client, COUNCIL_EMAILS[0])
    d = _data(client.get(f"{API}/governance/council", headers=headers))
    assert d["size"] == 4
    assert d["threshold"] == "unanimous"


def test_viewer_cannot_access_governance(client):
    # A fresh non-first user is a VIEWER.
    client.post(f"{API}/auth/register", json={"email": "boss1@test.com", "password": "password123", "vpa": "boss1@okhdfc"})
    email = f"v_{uuid.uuid4().hex[:6]}@test.com"
    client.post(f"{API}/auth/register", json={"email": email, "password": "password123", "vpa": "viewer1@okhdfc"})
    h = _login(client, email, password="password123", device="viewer-dev")
    assert client.get(f"{API}/governance/proposals", headers=h).status_code == 403


def test_secondary_admin_has_no_governance_access(client):
    # An older real admin exists, so this second admin is neither main nor council.
    _make_admin(client)
    boss = _make_admin(client)
    txn_id, _ = _make_txn(client)
    # Blocked at the access layer (403) — restricted to council + main admin.
    assert client.get(f"{API}/governance/proposals", headers=boss).status_code == 403
    res = client.post(f"{API}/governance/proposals", headers=boss,
                      json={"transaction_id": txn_id, "proposed_status": "BLOCKED", "reason": "test"})
    assert res.status_code == 403


def test_council_member_cannot_be_outvoted_alone(client):
    # A council member proposing still needs the *other three* — proves no unilateral change.
    council = _council_headers(client)
    txn_id, decision = _make_txn(client)
    target = "BLOCKED" if decision != "BLOCKED" else "ALLOWED"
    p = _data(client.post(f"{API}/governance/proposals", headers=council[0],
                          json={"transaction_id": txn_id, "proposed_status": target, "reason": "solo"}))
    assert p["status"] == "PENDING"  # 1/4 — not applied
    assert p["txn"]["status"] == decision


# ── Consensus flow ────────────────────────────────────────────────────────────


def test_unanimous_approval_applies_and_records_on_chain(client):
    from app.core.blockchain import get_blockchain

    council = _council_headers(client)
    txn_id, decision = _make_txn(client)
    target = "BLOCKED" if decision != "BLOCKED" else "ALLOWED"

    p = _data(client.post(f"{API}/governance/proposals", headers=council[0],
                          json={"transaction_id": txn_id, "proposed_status": target, "reason": "Confirmed fraud"}))
    assert p["status"] == "PENDING"
    assert p["approvals"] == 1  # proposer auto-approves

    blocks_before = len(get_blockchain().chain)
    # Remaining three approve.
    last = p
    for h in council[1:]:
        last = _data(client.post(f"{API}/governance/proposals/{p['id']}/vote", headers=h, json={"vote": "APPROVE"}))

    assert last["status"] == "APPLIED"
    assert last["approvals"] == 4
    assert last["block_index"] is not None
    assert len(get_blockchain().chain) == blocks_before + 1
    # The transaction decision actually changed.
    assert last["txn"]["status"] == target


def test_single_rejection_blocks_the_change(client):
    council = _council_headers(client)
    txn_id, decision = _make_txn(client)
    target = "BLOCKED" if decision != "BLOCKED" else "ALLOWED"
    p = _data(client.post(f"{API}/governance/proposals", headers=council[0],
                          json={"transaction_id": txn_id, "proposed_status": target, "reason": "maybe"}))
    _data(client.post(f"{API}/governance/proposals/{p['id']}/vote", headers=council[1], json={"vote": "APPROVE"}))
    res = _data(client.post(f"{API}/governance/proposals/{p['id']}/vote", headers=council[2], json={"vote": "REJECT"}))
    assert res["status"] == "REJECTED"
    assert res["txn"]["status"] == decision  # unchanged


def test_duplicate_vote_rejected(client):
    council = _council_headers(client)
    txn_id, _ = _make_txn(client)
    p = _data(client.post(f"{API}/governance/proposals", headers=council[0],
                          json={"transaction_id": txn_id, "proposed_status": "BLOCKED", "reason": "dup test"}))
    # Proposer already auto-approved; voting again must fail.
    res = client.post(f"{API}/governance/proposals/{p['id']}/vote", headers=council[0], json={"vote": "APPROVE"})
    assert res.status_code == 400


def test_identical_status_rejected(client):
    council = _council_headers(client)
    txn_id, decision = _make_txn(client)
    res = client.post(f"{API}/governance/proposals", headers=council[0],
                      json={"transaction_id": txn_id, "proposed_status": decision, "reason": "noop"})
    assert res.status_code == 400


# ── Divergence + integrity + rollback ─────────────────────────────────────────


def test_midvote_tamper_causes_divergence(client):
    council = _council_headers(client)
    txn_id, decision = _make_txn(client)
    target = "BLOCKED" if decision != "BLOCKED" else "ALLOWED"
    p = _data(client.post(f"{API}/governance/proposals", headers=council[0],
                          json={"transaction_id": txn_id, "proposed_status": target, "reason": "race"}))
    # Rogue out-of-band edit AFTER the proposal snapshot.
    other = "STEP_UP" if decision != "STEP_UP" else "ALLOWED"
    _data(client.post(f"{API}/governance/integrity/{txn_id}/simulate-tamper", headers=council[0],
                      json={"new_status": other}))
    res = _data(client.post(f"{API}/governance/proposals/{p['id']}/vote", headers=council[1], json={"vote": "APPROVE"}))
    assert res["status"] == "DIVERGED"
    assert res["diverged"] is True


def test_integrity_detects_tamper_and_rollback_restores(client):
    council = _council_headers(client)
    txn_id, decision = _make_txn(client)

    clean = _data(client.get(f"{API}/governance/integrity/{txn_id}", headers=council[0]))
    assert clean["tampered"] is False

    tamper_to = "BLOCKED" if decision != "BLOCKED" else "ALLOWED"
    _data(client.post(f"{API}/governance/integrity/{txn_id}/simulate-tamper", headers=council[0],
                      json={"new_status": tamper_to}))

    bad = _data(client.get(f"{API}/governance/integrity/{txn_id}", headers=council[0]))
    assert bad["tampered"] is True
    assert bad["current"]["status"] == tamper_to
    assert bad["agreed"]["status"] == decision

    rb = _data(client.post(f"{API}/governance/integrity/{txn_id}/rollback", headers=council[0]))
    assert rb["restored"] is True
    assert rb["after"]["status"] == decision

    healed = _data(client.get(f"{API}/governance/integrity/{txn_id}", headers=council[0]))
    assert healed["tampered"] is False


# ── Automatic self-healing watchdog ───────────────────────────────────────────


def test_watchdog_status_shape(client):
    council = _council_headers(client)
    d = _data(client.get(f"{API}/governance/watchdog", headers=council[0]))
    for k in ("enabled", "interval_seconds", "healed_total", "recent", "checked"):
        assert k in d


def test_watchdog_auto_heals_tampering(client):
    council = _council_headers(client)
    txn_id, decision = _make_txn(client)
    tamper_to = "BLOCKED" if decision != "BLOCKED" else "ALLOWED"

    _data(client.post(f"{API}/governance/integrity/{txn_id}/simulate-tamper",
                      headers=council[0], json={"new_status": tamper_to}))

    # The watchdog scan finds and auto-restores it from the chain.
    res = _data(client.post(f"{API}/governance/watchdog/scan", headers=council[0]))
    healed_ids = [h["transaction_id"] for h in res["healed"]]
    assert txn_id in healed_ids

    after = _data(client.get(f"{API}/governance/integrity/{txn_id}", headers=council[0]))
    assert after["tampered"] is False
    assert after["current"]["status"] == decision


def test_watchdog_scan_requires_access(client):
    # A secondary admin (no governance access) cannot trigger the watchdog.
    _make_admin(client)
    boss = _make_admin(client)
    assert client.post(f"{API}/governance/watchdog/scan", headers=boss).status_code == 403
