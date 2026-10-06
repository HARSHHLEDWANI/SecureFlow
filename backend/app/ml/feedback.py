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
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import OverrideProposal, ProposalStatus, SessionLocal, Transaction, TxnStatus
from app.ml.bundle import build_bundle, evaluate_bundle
from app.ml.evaluation import feature_importance
from app.ml.features import FEATURE_COLUMNS, to_vector
from app.ml.model import reload_model_service
from app.ml.thresholds import reset_threshold_cache
from app.ml.training import file_digest
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


def correction_weight(
    n_corrections: int, n_pool: int, floor: float, target_share: float, cap: float
) -> tuple[float, float]:
    """Per-correction sample weight and the share of total sample mass it buys.

    A weight of 5 against a pool of S rows is a rounding error in aggregate: with
    S = 8,400 training rows and N = 1 correction, mass share = 5 / (8,400 + 5) = 0.06%.
    (Measured here, a lone weight-5 correction still shifts a fully grown forest's
    probability for that exact vector 0.995 -> 0.365, because ``min_samples_leaf=1``
    lets one sample own a leaf - but only inside its own leaf neighbourhood, and the
    effect on a near neighbour is similar; it is a local memorisation, not a learned
    shift.) The weight is therefore raised so corrections hold at least
    ``target_share`` of the effective mass::

        w = target_share * S / (N * (1 - target_share))     # solves N*w/(S+N*w) = share
        w = clamp(w, floor, cap)

    e.g. S = 8,400, share = 5%: N = 1 -> w = 442; N = 20 -> w = 22; from N ~ 89 the
    ``floor`` (5) already exceeds the target and applies unchanged. At w = 221 (what the
    tests use, class-weighted) the same probe falls to 0.13 and its near neighbour to
    0.26 - a markedly stronger pull. ``cap`` bounds the influence of a single, possibly
    mistaken, human label.
    """
    if n_corrections <= 0:
        return floor, 0.0
    needed = target_share * n_pool / (n_corrections * (1.0 - target_share))
    weight = float(min(max(floor, needed), cap))
    share = n_corrections * weight / (n_pool + n_corrections * weight)
    return weight, share


def load_frozen_sets() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(train_pool, holdout)`` frozen at training time; error if absent."""
    settings = get_settings()
    if not (os.path.exists(settings.train_pool_path) and os.path.exists(settings.holdout_path)):
        raise FeedbackError(
            "No frozen train pool / holdout found. Run `python -m app.ml.training` first: "
            "retraining and the regression guard both score on those exact rows."
        )
    return pd.read_parquet(settings.train_pool_path), pd.read_parquet(settings.holdout_path)


_hash_cache: dict[tuple[str, int, int], str] = {}


def holdout_hash() -> Optional[str]:
    """Digest of the frozen holdout, recomputed only if the file's mtime/size change."""
    path = get_settings().holdout_path
    if not os.path.exists(path):
        return None
    st = os.stat(path)
    key = (path, st.st_mtime_ns, st.st_size)
    if key not in _hash_cache:
        _hash_cache.clear()
        _hash_cache[key] = file_digest(path)
    return _hash_cache[key]


def run_feedback_retrain(db: Session, fast: bool = False) -> dict[str, Any]:
    """Retrain on the frozen pool + weighted corrections; write a versioned candidate.

    The candidate trains only on the pool saved at training time (train + validation
    splits) plus the corrections, and is scored on the **frozen holdout** - the same rows
    the live model was scored on. (Previously this called ``generate_dataset()`` fresh on
    every retrain with a module-level RNG that had already advanced, so the candidate's
    and the live model's test sets were different random draws and the regression guard
    compared noise.) Corrections get an adaptive weight (see :func:`correction_weight`).
    Never overwrites the live model.
    """
    settings = get_settings()
    examples = collect_feedback_examples(db)
    if len(examples) < settings.feedback_min_examples:
        raise FeedbackError(
            f"Need at least {settings.feedback_min_examples} approved correction(s) "
            f"with a feature snapshot; have {len(examples)}."
        )

    pool, holdout = load_frozen_sets()
    train = pool[pool["split"] == "train"].drop(columns="split")
    val = pool[pool["split"] == "val"].drop(columns="split")

    # Real corrections: the exact vector the model scored, newest in time.
    corr = pd.DataFrame(
        [to_vector(ex["features"]) for ex in examples], columns=FEATURE_COLUMNS
    ).astype("float32")
    corr["is_fraud"] = np.array([ex["label"] for ex in examples], dtype=train["is_fraud"].dtype)
    corr["time_step"] = int(train["time_step"].max()) + 1
    train_all = pd.concat([train, corr[train.columns]], ignore_index=True)

    weight, share = correction_weight(
        len(examples), len(train), settings.feedback_correction_weight,
        settings.feedback_correction_target_share, settings.feedback_max_correction_weight,
    )
    weights = np.concatenate([np.ones(len(train)), np.full(len(corr), weight)])

    version = _next_version(settings.feedback_model_dir)
    trained_at = datetime.now(timezone.utc).isoformat()
    bundle, report = build_bundle(
        train_all, val, fast=fast, version=f"feedback-v{version}",
        dataset="feedback", sample_weight=weights,
    )
    metrics = evaluate_bundle(bundle, holdout)

    model_path, metrics_path = candidate_paths(version)
    joblib.dump(bundle, model_path)

    metrics_out = {
        **metrics,
        "calibration": report["calibration"],
        "risk_thresholds": report["risk_thresholds"],
        "feature_importance": feature_importance(bundle["base_model"], FEATURE_COLUMNS),
        "best_params": report["best_params"],
        "n_train": int(len(train_all)),
        "n_test": int(len(holdout)),
        "n_corrections": len(examples),
        "n_synthetic": int(len(train)),     # pool rows (kept under its old key for the API)
        "correction_weight": weight,
        "correction_mass_share": round(share, 4),
        "holdout_hash": holdout_hash(),
        "trained_at": trained_at,
        "version": f"feedback-v{version}",
        "source": "feedback_retrain",
    }
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics_out, fh, indent=2)

    logger.info(
        "Feedback retrain -> candidate v%d (%d corrections, weight %.1f = %.1f%% of mass)",
        version, len(examples), weight, 100 * share,
    )
    return {
        "version": version,
        "model_path": model_path,
        "metrics_path": metrics_path,
        "metrics": metrics_out,
        "n_corrections": len(examples),
        "n_synthetic": int(len(train)),
        "proposal_ids": [ex["proposal_id"] for ex in examples],
        "regression": evaluate_regression_guard(metrics_out),
    }


# ── Regression guard ────────────────────────────────────────────────────────────


def _read_json(path: str) -> Optional[dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def live_metrics() -> Optional[dict[str, Any]]:
    """Metrics of the live model **on the frozen holdout**.

    The stored metrics file is trusted only if it was scored on the current holdout
    (matching ``holdout_hash``); otherwise the live model is re-scored on the holdout
    here, so the guard never compares models evaluated on different rows.
    """
    settings = get_settings()
    stored = _read_json(settings.model_metrics_path)
    current = holdout_hash()
    if stored is None or current is None or stored.get("holdout_hash") == current:
        return stored
    try:
        bundle = joblib.load(settings.model_path)
        holdout = pd.read_parquet(settings.holdout_path)
    except (OSError, ValueError, KeyError):
        return stored
    rescored = evaluate_bundle(bundle, holdout)
    rescored.update(
        holdout_hash=current, version=bundle.get("version"), rescored_on_holdout=True
    )
    return rescored


def evaluate_regression_guard(candidate: dict[str, Any]) -> dict[str, Any]:
    """Compare a candidate to the live model on the same frozen holdout; block on a drop.

    PR-AUC is the primary signal; AUC-ROC and recall are kept as secondary checks.
    """
    settings = get_settings()
    live = live_metrics()
    if live is None:
        return {"ok": True, "reasons": [], "pr_auc_drop": 0.0, "auc_drop": 0.0,
                "recall_drop": 0.0, "same_holdout": None, "live": None,
                "candidate": _slim(candidate)}

    reasons: list[str] = []
    cand_hash, live_hash = candidate.get("holdout_hash"), live.get("holdout_hash")
    same_holdout = bool(cand_hash and cand_hash == live_hash)
    if holdout_hash() is not None and not same_holdout:
        reasons.append("candidate and live model were not scored on the same frozen holdout")

    pr_drop = float(live.get("pr_auc", 0.0) or 0.0) - float(candidate.get("pr_auc", 0.0) or 0.0)
    auc_drop = float(live.get("auc_roc", 0.0)) - float(candidate.get("auc_roc", 0.0))
    recall_drop = float(live.get("recall", 0.0)) - float(candidate.get("recall", 0.0))
    if pr_drop > settings.feedback_regression_prauc_drop:
        reasons.append(f"PR-AUC dropped {pr_drop:.3f} (> {settings.feedback_regression_prauc_drop})")
    if auc_drop > settings.feedback_regression_auc_drop:
        reasons.append(f"AUC-ROC dropped {auc_drop:.3f} (> {settings.feedback_regression_auc_drop})")
    if recall_drop > settings.feedback_regression_recall_drop:
        reasons.append(f"Recall dropped {recall_drop:.3f} (> {settings.feedback_regression_recall_drop})")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "pr_auc_drop": round(pr_drop, 4),
        "auc_drop": round(auc_drop, 4),
        "recall_drop": round(recall_drop, 4),
        "same_holdout": same_holdout,
        "live": _slim(live),
        "candidate": _slim(candidate),
    }


def _slim(m: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if m is None:
        return None
    return {k: m.get(k) for k in
            ("pr_auc", "auc_roc", "recall", "precision", "f1", "accuracy", "version")}


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
    reset_threshold_cache()

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
