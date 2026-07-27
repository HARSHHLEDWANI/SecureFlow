"""Tests for the "Explain This Decision" endpoint (Feature A).

Covers the fallback path (no key / LLM error → template), the LLM path (mocked),
the ownership rule (a VIEWER can't explain another user's transaction — same 404
as the status endpoint), caching, and the tighter rate limit.
"""
from __future__ import annotations

from app.config import get_settings
from app.core import explain as explain_mod


def _analyze(client, headers, amount=4200):
    res = client.post(
        "/api/v1/transaction/analyze",
        headers=headers,
        json={"to_vpa": "bob@okaxis", "amount_inr": amount, "txn_type": "P2P",
              "device_id": "trusted-device"},
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]


# ── Fallback path ──────────────────────────────────────────────────────────────


def test_explain_falls_back_to_template_without_key(auth_client):
    """With ANTHROPIC_API_KEY unset (the test default), returns a template result."""
    client, headers, _ = auth_client
    txn = _analyze(client, headers)
    res = client.post(f"/api/v1/transaction/{txn['id']}/explain", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["source"] == "template"
    assert len(data["explanation"]) > 20
    assert str(txn["risk_score"]) in data["explanation"]


def test_explain_llm_failure_falls_back_to_template(auth_client, monkeypatch):
    """Even with a key configured, an LLM error degrades to the template."""
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-test-key")

    def _boom(_facts):
        raise RuntimeError("api unavailable")

    monkeypatch.setattr(explain_mod, "_llm_explanation", _boom)

    client, headers, _ = auth_client
    txn = _analyze(client, headers)
    data = client.post(f"/api/v1/transaction/{txn['id']}/explain", headers=headers).json()["data"]
    assert data["source"] == "template"
    assert len(data["explanation"]) > 20


def test_explain_uses_llm_when_available(auth_client, monkeypatch):
    """When a key is set and the call succeeds, source is 'llm' and text is passed through."""
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-test-key")
    monkeypatch.setattr(explain_mod, "_llm_explanation", lambda _facts: "Blocked: impossible travel.")

    client, headers, _ = auth_client
    txn = _analyze(client, headers)
    data = client.post(f"/api/v1/transaction/{txn['id']}/explain", headers=headers).json()["data"]
    assert data["source"] == "llm"
    assert data["explanation"] == "Blocked: impossible travel."


# ── Ownership + caching ─────────────────────────────────────────────────────────


def test_viewer_cannot_explain_another_users_transaction(auth_client, viewer_client):
    client, analyst_headers, _ = auth_client
    _, viewer_headers, _ = viewer_client
    txn = _analyze(client, analyst_headers)
    # Same 404 as /status — does not leak the transaction's existence.
    res = client.post(f"/api/v1/transaction/{txn['id']}/explain", headers=viewer_headers)
    assert res.status_code == 404


def test_explain_is_cached_per_transaction(auth_client):
    client, headers, _ = auth_client
    txn = _analyze(client, headers)
    first = client.post(f"/api/v1/transaction/{txn['id']}/explain", headers=headers).json()["data"]
    assert first["cached"] is False
    second = client.post(f"/api/v1/transaction/{txn['id']}/explain", headers=headers).json()["data"]
    assert second["cached"] is True
    assert second["explanation"] == first["explanation"]


# ── Rate limiting (tighter than the general limiter) ────────────────────────────


def test_explain_has_a_tighter_rate_limit(auth_client):
    """The explain endpoint is throttled well below the general 1000/window test limit."""
    client, headers, _ = auth_client
    txn = _analyze(client, headers)
    limit = get_settings().explain_rate_limit_requests
    codes = [
        client.post(f"/api/v1/transaction/{txn['id']}/explain", headers=headers).status_code
        for _ in range(limit + 3)
    ]
    assert 429 in codes  # the tight limit fired well before the general 1000/window
