"""Governance → model feedback loop (Feature B).

When the governance council unanimously approves overturning a transaction's
status, that is a human-verified label correction. This module captures those
corrections as training data and lets an admin retrain the model from them, on
top of the synthetic dataset — producing a **separately versioned** candidate
model that is **never auto-promoted**. A regression guard blocks promoting a
candidate that is materially worse than the live model unless explicitly forced.

Key constraint: retraining uses the **exact feature vector the model saw at
scoring time** (``Transaction.feature_snapshot``), not a recomputed one — several
features are time-/state-dependent, so a recomputed vector would not match what
the model actually scored and would quietly corrupt training. Only transactions
scored after the snapshot column shipped are eligible.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Optional

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import GridSearchCV, train_test_split
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import OverrideProposal, ProposalStatus, SessionLocal, Transaction, TxnStatus
from app.ml.evaluation import compute_metrics, feature_importance
from app.ml.features import FEATURE_COLUMNS, to_vector
from app.ml.model import reload_model_service
from app.ml.datasets.synthetic import SyntheticDataset
from app.ml.training import _FAST_PARAMS
from app.utils.helpers import utcnow
from app.utils.logger import get_logger

logger = get_logger("feedback")


class FeedbackError(ValueError):
    """Raised for invalid feedback-loop operations (mapped to HTTP 400)."""


# The council's corrected decision → binary fraud label the model learns.
# BLOCKED/STEP_UP mean the council judged the payment risky (positive class);
# ALLOWED means they judged it legitimate (negative class).
_LABEL = {TxnStatus.BLOCKED: 1, TxnStatus.STEP_UP: 1, TxnStatus.ALLOWED: 0}


# ── Collection ────────────────────────────────────────────────────────────────


def _approved_unconsumed(db: Session) -> list[OverrideProposal]:
    return list(
        db.execute(
            select(OverrideProposal).where(
                OverrideProposal.status == ProposalStatus.APPLIED,
                OverrideProposal.consumed_for_training.is_(False),
            )
        ).scalars()
    )


def collect_feedback_examples(db: Session) -> list[dict[str, Any]]:
    """Return labeled examples from approved, not-yet-consumed corrections.

    Only proposals whose transaction has a persisted ``feature_snapshot`` are
    included — the loop trains on the real scored vector, never a recomputed one.
    """
    examples: list[dict[str, Any]] = []
    for p in _approved_unconsumed(db):
        txn = db.get(Transaction, p.transaction_id)
        if txn is None or not txn.feature_snapshot:
            continue
        label = _LABEL.get(p.proposed_status)
        if label is None:
            continue
        examples.append(
            {
                "proposal_id": p.id,
                "transaction_id": txn.id,
                "features": txn.feature_snapshot,
                "label": int(label),
            }
        )
    return examples


def unconsumed_count(db: Session) -> int:
    return len(collect_feedback_examples(db))


# ── Retrain (produces a versioned candidate; never touches the live model) ──────


def _next_version(model_dir: str) -> int:
    os.makedirs(model_dir, exist_ok=True)
    nums: list[int] = []
    for path in glob.glob(os.path.join(model_dir, "fraud_model_v*.joblib")):
        stem = os.path.basename(path)[len("fraud_model_v"):-len(".joblib")]
        if stem.isdigit():
            nums.append(int(stem))
    return (max(nums) + 1) if nums else 1


def candidate_paths(version: int) -> tuple[str, str]:
    d = get_settings().feedback_model_dir
    return (
        os.path.join(d, f"fraud_model_v{version}.joblib"),
        os.path.join(d, f"model_metrics_v{version}.json"),
    )


def run_feedback_retrain(db: Session, fast: bool = False) -> dict[str, Any]:
    """Retrain on synthetic data + weighted corrections; write a versioned candidate.

    Real corrections are given more weight than synthetic examples via
    ``sample_weight`` on ``fit`` (RandomForest supports it). Produces a new
    ``fraud_model_v{n}.joblib`` + metrics json — it never overwrites the live
    model. Returns the candidate metrics and the regression-guard verdict.
    """
    settings = get_settings()
    examples = collect_feedback_examples(db)
    if len(examples) < settings.feedback_min_examples:
        raise FeedbackError(
            f"Need at least {settings.feedback_min_examples} approved correction(s) "
            f"with a feature snapshot; have {len(examples)}."
        )

    # Synthetic base dataset.
    df = SyntheticDataset().load()
    X_syn = df[FEATURE_COLUMNS].to_numpy()
    y_syn = df["is_fraud"].to_numpy()

    # Real corrections, ordered to the canonical feature vector.
    X_corr = np.array([to_vector(ex["features"]) for ex in examples], dtype=float)
    y_corr = np.array([ex["label"] for ex in examples], dtype=int)

    X = np.vstack([X_syn, X_corr])
    y = np.concatenate([y_syn, y_corr])
    weights = np.concatenate(
        [np.ones(len(y_syn)), np.full(len(y_corr), settings.feedback_correction_weight)]
    )

    X_tr, X_te, y_tr, y_te, w_tr, _ = train_test_split(
        X, y, weights, test_size=0.2, random_state=42, stratify=y
    )

    if fast:
        clf = RandomForestClassifier(
            random_state=42, class_weight="balanced", n_jobs=-1, **_FAST_PARAMS
        )
        clf.fit(X_tr, y_tr, sample_weight=w_tr)
        best_params = dict(_FAST_PARAMS)
    else:
        grid = GridSearchCV(
            RandomForestClassifier(random_state=42, class_weight="balanced", n_jobs=-1),
            param_grid={"n_estimators": [150, 250], "max_depth": [10, 16, None],
                        "min_samples_leaf": [1, 3]},
            scoring="f1", cv=5, n_jobs=-1,
        )
        grid.fit(X_tr, y_tr, sample_weight=w_tr)
        clf = grid.best_estimator_
        best_params = grid.best_params_

    y_pred = clf.predict(X_te)
    y_proba = clf.predict_proba(X_te)[:, 1]
    metrics = compute_metrics(y_te, y_pred, y_proba)
    importance = feature_importance(clf, FEATURE_COLUMNS)

    iso = IsolationForest(
        n_estimators=200, contamination=max(float(y_tr.mean()), 1e-3), random_state=42, n_jobs=-1
    )
    iso.fit(X_tr)
    raw = -iso.decision_function(X_tr)

    version = _next_version(settings.feedback_model_dir)
    trained_at = datetime.now(timezone.utc).isoformat()
    bundle = {
        "model": clf,
        "iso": iso,
        "iso_score_min": float(raw.min()),
        "iso_score_max": float(raw.max()),
        "feature_columns": FEATURE_COLUMNS,
        "best_params": best_params,
        "version": f"feedback-v{version}",
        "trained_at": trained_at,
    }
    model_path, metrics_path = candidate_paths(version)
    joblib.dump(bundle, model_path)

    metrics_out = {
        **metrics,
        "feature_importance": importance,
        "best_params": best_params,
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
        "n_corrections": len(examples),
        "n_synthetic": int(len(y_syn)),
        "correction_weight": settings.feedback_correction_weight,
        "trained_at": trained_at,
        "version": f"feedback-v{version}",
        "source": "feedback_retrain",
    }
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics_out, fh, indent=2)

    logger.info("Feedback retrain -> candidate v%d (%d corrections)", version, len(examples))
    return {
        "version": version,
        "model_path": model_path,
        "metrics_path": metrics_path,
        "metrics": metrics_out,
        "n_corrections": len(examples),
        "n_synthetic": int(len(y_syn)),
        "proposal_ids": [ex["proposal_id"] for ex in examples],
        "regression": evaluate_regression_guard(metrics_out),
    }


# ── Regression guard ────────────────────────────────────────────────────────────


def live_metrics() -> Optional[dict[str, Any]]:
    path = get_settings().model_metrics_path
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def evaluate_regression_guard(candidate: dict[str, Any]) -> dict[str, Any]:
    """Compare a candidate's AUC/recall to the live model; block on a big drop."""
    settings = get_settings()
    live = live_metrics()
    if live is None:
        return {"ok": True, "reasons": [], "auc_drop": 0.0, "recall_drop": 0.0,
                "live": None, "candidate": _slim(candidate)}

    auc_drop = float(live.get("auc_roc", 0.0)) - float(candidate.get("auc_roc", 0.0))
    recall_drop = float(live.get("recall", 0.0)) - float(candidate.get("recall", 0.0))
    reasons: list[str] = []
    if auc_drop > settings.feedback_regression_auc_drop:
        reasons.append(f"AUC-ROC dropped {auc_drop:.3f} (> {settings.feedback_regression_auc_drop})")
    if recall_drop > settings.feedback_regression_recall_drop:
        reasons.append(f"Recall dropped {recall_drop:.3f} (> {settings.feedback_regression_recall_drop})")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "auc_drop": round(auc_drop, 4),
        "recall_drop": round(recall_drop, 4),
        "live": _slim(live),
        "candidate": _slim(candidate),
    }


def _slim(m: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if m is None:
        return None
    return {k: m.get(k) for k in ("auc_roc", "recall", "precision", "f1", "accuracy", "version")}


# ── Promotion (the only thing that makes a candidate live) ──────────────────────


def promote_candidate(db: Session, version: int, force: bool = False) -> dict[str, Any]:
    """Make candidate ``version`` the live model, honoring the regression guard.

    Marks the folded-in corrections ``consumed_for_training=True`` only on success,
    so an aborted/rejected candidate's corrections remain available next time.
    """
    settings = get_settings()
    model_path, metrics_path = candidate_paths(version)
    if not os.path.exists(model_path) or not os.path.exists(metrics_path):
        raise FeedbackError(f"Candidate v{version} not found — retrain first.")

    with open(metrics_path, "r", encoding="utf-8") as fh:
        metrics = json.load(fh)
    guard = evaluate_regression_guard(metrics)
    if not guard["ok"] and not force:
        raise FeedbackError(
            "Candidate regresses vs the live model: " + "; ".join(guard["reasons"])
            + ". Re-run with force=true to override."
        )

    # Swap in the new model (never done automatically — this is the manual gate).
    os.makedirs(os.path.dirname(os.path.abspath(settings.model_path)) or ".", exist_ok=True)
    shutil.copyfile(model_path, settings.model_path)
    shutil.copyfile(metrics_path, settings.model_metrics_path)
    reload_model_service()

    consumed = 0
    for ex in collect_feedback_examples(db):
        proposal = db.get(OverrideProposal, ex["proposal_id"])
        if proposal is not None:
            proposal.consumed_for_training = True
            consumed += 1
    db.commit()

    logger.warning("Promoted feedback model v%d (%d corrections consumed)", version, consumed)
    return {
        "promoted_version": version,
        "consumed": consumed,
        "forced": bool(force and not guard["ok"]),
        "regression": guard,
    }


def list_candidates() -> list[dict[str, Any]]:
    """Metadata for all versioned candidate models on disk, newest first."""
    settings = get_settings()
    out: list[dict[str, Any]] = []
    for path in glob.glob(os.path.join(settings.feedback_model_dir, "model_metrics_v*.json")):
        stem = os.path.basename(path)[len("model_metrics_v"):-len(".json")]
        if not stem.isdigit():
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        out.append(
            {
                "version": int(stem),
                "metrics": _slim(m),
                "n_corrections": m.get("n_corrections"),
                "trained_at": m.get("trained_at"),
                "regression": evaluate_regression_guard(m),
            }
        )
    return sorted(out, key=lambda c: c["version"], reverse=True)


# ── Background retrain job + pollable status ────────────────────────────────────

retrain_status: dict[str, Any] = {
    "state": "idle",  # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}


def run_retrain_job() -> None:
    """Background entry point: retrain and record a pollable status."""
    retrain_status.update(state="running", started_at=utcnow().isoformat(), error=None, result=None)
    db = SessionLocal()
    try:
        res = run_feedback_retrain(db, fast=get_settings().feedback_retrain_fast)
        retrain_status.update(
            state="done",
            finished_at=utcnow().isoformat(),
            result={
                "version": res["version"],
                "metrics": _slim(res["metrics"]),
                "n_corrections": res["n_corrections"],
                "n_synthetic": res["n_synthetic"],
                "regression": res["regression"],
            },
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the poller
        logger.exception("Feedback retrain job failed")
        retrain_status.update(state="error", finished_at=utcnow().isoformat(), error=str(exc))
    finally:
        db.close()
