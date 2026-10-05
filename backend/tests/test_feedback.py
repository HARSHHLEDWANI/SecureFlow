"""Tests for the governance → model feedback loop (Feature B)."""
from __future__ import annotations

import json
import os
import uuid

import pytest

from app.config import get_settings
from app.core.security import hash_password
from app.database import (
    OverrideProposal,
    ProposalStatus,
    Role,
    RiskTier,
    SessionLocal,
    Transaction,
    TxnStatus,
    TxnType,
    User,
    init_db,
)
from app.ml import feedback
from app.ml.features import extract_features

API = "/api/v1"


@pytest.fixture(autouse=True)
def _clean_proposals():
    """Clear override proposals before each feedback test (the DB is shared)."""
    from sqlalchemy import delete

    from app.database import ProposalVote

    init_db()  # ensure tables exist (autouse runs before the client fixture)
    db = SessionLocal()
    try:
        db.execute(delete(ProposalVote))
        db.execute(delete(OverrideProposal))
        db.commit()
    finally:
        db.close()
    yield


def _set_scores(path: str, auc: float, recall: float) -> None:
    """Force the auc_roc/recall in a metrics json (deterministic guard inputs)."""
    m = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            m = json.load(fh)
    m["auc_roc"], m["recall"] = auc, recall
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(m, fh)


def _snapshot() -> dict:
    return extract_features(
        {
            "amount_inr": 90000, "txn_type": "P2P", "hour": 3, "velocity_1h": 9,
            "geo_distance_km": 1400, "minutes_since_last": 5, "is_new_device": 1,
            "is_new_beneficiary": 1, "user_avg_amount": 500, "user_std_amount": 200,
        }
    )


def _make_applied_proposal(
    proposed=TxnStatus.BLOCKED, *, snapshot=True, consumed=False, status=ProposalStatus.APPLIED,
):
    """Seed a user + transaction (with feature snapshot) + a resolved proposal."""
    init_db()
    db = SessionLocal()
    try:
        u = User(
            email=f"fb_{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("password123"),
            vpa="fb@okhdfc",
            role=Role.VIEWER,
        )
        db.add(u)
        db.flush()
        txn = Transaction(
            user_id=u.id, from_vpa=u.vpa, to_vpa="x@ybl", amount_inr=90000,
            txn_type=TxnType.P2P, device_id="d", location_lat=0.0, location_lon=0.0,
            risk_score=25, risk_tier=RiskTier.LOW, status=TxnStatus.ALLOWED,
            feature_snapshot=(_snapshot() if snapshot else None),
        )
        db.add(txn)
        db.flush()
        p = OverrideProposal(
            transaction_id=txn.id, proposed_by=u.id, current_status=TxnStatus.ALLOWED,
            proposed_status=proposed, reason="confirmed fraud", state_hash="x",
            status=status, consumed_for_training=consumed,
        )
        db.add(p)
        db.commit()
        return p.id, txn.id
    finally:
        db.close()


# ── Collection ──────────────────────────────────────────────────────────────────


def test_collect_only_returns_approved_unconsumed_with_snapshot(client):
    pid, _ = _make_applied_proposal()                               # eligible
    _make_applied_proposal(consumed=True)                           # already consumed
    _make_applied_proposal(snapshot=False)                          # no feature snapshot
    _make_applied_proposal(status=ProposalStatus.PENDING)           # not approved

    db = SessionLocal()
    try:
        examples = feedback.collect_feedback_examples(db)
    finally:
        db.close()

    from app.ml.features import FEATURE_COLUMNS

    ids = {e["proposal_id"] for e in examples}
    assert pid in ids
    assert len(examples) == 1
    assert examples[0]["label"] == 1  # BLOCKED → fraud
    # The stored snapshot is the real, complete feature vector.
    assert all(col in examples[0]["features"] for col in FEATURE_COLUMNS)


# ── Retrain (versioned candidate; never touches the live model) ─────────────────


def test_retrain_produces_candidate_without_touching_live(client):
    _make_applied_proposal()
    settings = get_settings()
    live_before = os.path.getmtime(settings.model_path)
    live_bytes = open(settings.model_path, "rb").read()

    db = SessionLocal()
    try:
        res = feedback.run_feedback_retrain(db, fast=True)
    finally:
        db.close()

    # A real, loadable candidate model + metrics was written.
    assert os.path.exists(res["model_path"])
    assert os.path.exists(res["metrics_path"])
    import joblib
    bundle = joblib.load(res["model_path"])
    assert "model" in bundle and "iso" in bundle
    assert res["metrics"]["n_corrections"] == 1

    # The live model file is completely untouched.
    assert os.path.getmtime(settings.model_path) == live_before
    assert open(settings.model_path, "rb").read() == live_bytes


def test_retrain_requires_min_examples(client):
    db = SessionLocal()
    try:
        with pytest.raises(feedback.FeedbackError):
            feedback.run_feedback_retrain(db, fast=True)  # no corrections seeded
    finally:
        db.close()


# ── Regression guard + promotion ────────────────────────────────────────────────


def test_regressing_candidate_blocked_without_force(client):
    _make_applied_proposal()
    settings = get_settings()
    db = SessionLocal()
    try:
        res = feedback.run_feedback_retrain(db, fast=True)
    finally:
        db.close()
    version = res["version"]
    _, metrics_path = feedback.candidate_paths(version)

    # Strong live baseline, deliberately weak candidate → guard trips deterministically.
    _set_scores(settings.model_metrics_path, auc=0.95, recall=0.90)
    _set_scores(metrics_path, auc=0.50, recall=0.10)

    db = SessionLocal()
    try:
        with pytest.raises(feedback.FeedbackError):
            feedback.promote_candidate(db, version, force=False)
        # ...but succeeds with the explicit override.
        out = feedback.promote_candidate(db, version, force=True)
        assert out["forced"] is True
        assert out["promoted_version"] == version
    finally:
        db.close()


def test_promotion_consumes_corrections_only_on_success(client):
    pid, _ = _make_applied_proposal()
    settings = get_settings()
    db = SessionLocal()
    try:
        res = feedback.run_feedback_retrain(db, fast=True)
        version = res["version"]
        _, metrics_path = feedback.candidate_paths(version)

        # A blocked (regressing, unforced) promote must NOT consume the correction.
        _set_scores(settings.model_metrics_path, auc=0.95, recall=0.90)
        _set_scores(metrics_path, auc=0.50, recall=0.10)
        with pytest.raises(feedback.FeedbackError):
            feedback.promote_candidate(db, version, force=False)
        assert db.get(OverrideProposal, pid).consumed_for_training is False

        # A successful (forced) promote consumes it.
        feedback.promote_candidate(db, version, force=True)
        db.expire_all()
        assert db.get(OverrideProposal, pid).consumed_for_training is True
    finally:
        db.close()


# ── Routes are governance-gated ─────────────────────────────────────────────────


def test_feedback_summary_denied_to_viewer(viewer_client):
    client, headers, _ = viewer_client
    assert client.get(f"{API}/governance/feedback/summary", headers=headers).status_code == 403


# ── Frozen holdout: the regression guard compares like with like ────────────────


def _retrain(fast=True):
    db = SessionLocal()
    try:
        return feedback.run_feedback_retrain(db, fast=fast)
    finally:
        db.close()


def test_guard_scores_candidate_and_live_on_the_same_frozen_rows(client):
    _make_applied_proposal()
    res = _retrain()

    frozen = feedback.holdout_hash()
    assert frozen is not None
    assert res["metrics"]["holdout_hash"] == frozen
    assert feedback.live_metrics()["holdout_hash"] == frozen
    assert res["regression"]["same_holdout"] is True
    assert res["metrics"]["n_test"] == len(feedback.load_frozen_sets()[1])


def test_stale_live_metrics_are_rescored_on_the_frozen_holdout(client, monkeypatch):
    """A live metrics file scored on some other rows is not trusted - rescore on the holdout."""
    settings = get_settings()
    path = settings.model_metrics_path
    with open(path, "r", encoding="utf-8") as fh:
        original = json.load(fh)
    stale = dict(original, holdout_hash="deadbeefdeadbeef", pr_auc=0.123)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(stale, fh)

    seen = {}
    real_eval = feedback.evaluate_bundle

    def spy(bundle, df):
        seen["rows"] = len(df)
        seen["steps"] = (int(df["time_step"].min()), int(df["time_step"].max()))
        return real_eval(bundle, df)

    monkeypatch.setattr(feedback, "evaluate_bundle", spy)
    try:
        live = feedback.live_metrics()
    finally:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(original, fh)

    holdout = feedback.load_frozen_sets()[1]
    assert live["rescored_on_holdout"] is True
    assert live["holdout_hash"] == feedback.holdout_hash()
    assert live["pr_auc"] != 0.123
    assert seen["rows"] == len(holdout)
    assert seen["steps"] == (int(holdout["time_step"].min()), int(holdout["time_step"].max()))


def test_guard_rejects_a_candidate_scored_on_different_rows(client):
    _make_applied_proposal()
    cand = _retrain()["metrics"]
    cand = dict(cand, holdout_hash="0123456789abcdef")
    guard = feedback.evaluate_regression_guard(cand)
    assert guard["ok"] is False and guard["same_holdout"] is False
    assert any("same frozen holdout" in r for r in guard["reasons"])


def test_retrain_without_frozen_sets_fails_clearly(client, monkeypatch):
    _make_applied_proposal()
    monkeypatch.setattr(get_settings(), "holdout_path", "/nonexistent/holdout.parquet")
    db = SessionLocal()
    try:
        with pytest.raises(feedback.FeedbackError, match="python -m app.ml.training"):
            feedback.run_feedback_retrain(db, fast=True)
    finally:
        db.close()


# ── Corrections must be able to move the model ──────────────────────────────────


def test_correction_weight_arithmetic():
    # S=8,400 rows, 1 correction: weight 5 buys 0.06% of the mass; the target buys 5%.
    w5, share5 = feedback.correction_weight(1, 8400, floor=5.0, target_share=0.0, cap=500.0)
    assert w5 == 5.0 and share5 == pytest.approx(5 / 8405)
    w, share = feedback.correction_weight(1, 8400, floor=5.0, target_share=0.05, cap=500.0)
    assert w == pytest.approx(0.05 * 8400 / 0.95) and share == pytest.approx(0.05)
    w20, share20 = feedback.correction_weight(20, 8400, floor=5.0, target_share=0.05, cap=500.0)
    assert w20 == pytest.approx(22.1, abs=0.1) and share20 == pytest.approx(0.05)
    # Plenty of corrections: the floor already exceeds the target and applies unchanged.
    w_many, _ = feedback.correction_weight(200, 8400, floor=5.0, target_share=0.05, cap=500.0)
    assert w_many == 5.0
    # The cap bounds a single correction's influence.
    assert feedback.correction_weight(1, 10**7, 5.0, 0.05, 500.0)[0] == 500.0
    assert feedback.correction_weight(0, 8400, 5.0, 0.05, 500.0) == (5.0, 0.0)


def test_adaptive_weight_pulls_a_correction_harder_than_the_floor_weight(client, monkeypatch):
    """Council says an extreme fraud-looking vector is actually legitimate (label 0)."""
    from app.ml.features import FEATURE_COLUMNS

    settings = get_settings()
    probe = [[_snapshot()[c] for c in FEATURE_COLUMNS]]

    def candidate_prob(target_share):
        monkeypatch.setattr(settings, "feedback_correction_target_share", target_share)
        _make_applied_proposal(proposed=TxnStatus.ALLOWED)
        res = _retrain()
        bundle = joblib.load(res["model_path"])
        return (
            float(bundle["base_model"].predict_proba(probe)[0][1]),
            res["metrics"]["correction_mass_share"],
        )

    import joblib

    p_floor, share_floor = candidate_prob(0.0)       # weight 5 -> ~0.06% of mass
    p_adaptive, share_adaptive = candidate_prob(0.05)  # weight ~442 -> 5% of mass
    assert share_floor < 0.001 and share_adaptive == pytest.approx(0.05, abs=0.001)
    # Even weight 5 moves the exact vector (a fully grown forest memorises it: live ~0.99),
    # but only the adaptive weight pulls it decisively toward the council's label.
    assert p_floor < 0.9
    assert p_adaptive < p_floor - 0.1 and p_adaptive < 0.3
