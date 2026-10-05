"""Fit, calibrate and evaluate a serving bundle.

Shared by ``training.py`` (benchmark / demo training) and ``feedback.py`` (retrain with
governance corrections) so a candidate model is built *exactly* like the live one.

A bundle is the joblib dict ``ModelService`` loads: the (calibrated) classifier, its raw
``base_model`` (feature importances), the IsolationForest and its score range, the
cost-optimal probability cutoff and risk-tier cutoffs, and provenance.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

from app.core.risk_engine import compute_risk
from app.ml.calibration import fit_isotonic
from app.ml.evaluation import compute_metrics
from app.ml.features import FEATURE_COLUMNS
from app.ml.thresholds import CostMatrix, sweep_probability_threshold, sweep_tier_thresholds

# Fixed hyperparameters for the fast path (tests / dev): skips the grid search.
FAST_PARAMS = {"n_estimators": 200, "max_depth": 16, "min_samples_leaf": 1}

_GRID = {
    "n_estimators": [150, 250],
    "max_depth": [10, 16, None],
    "min_samples_leaf": [1, 3],
}


def to_matrix(df: pd.DataFrame) -> np.ndarray:
    return df[FEATURE_COLUMNS].to_numpy(dtype=np.float32)


def fit_forest(
    X: np.ndarray,
    y: np.ndarray,
    *,
    fast: bool,
    sample_weight: Optional[np.ndarray] = None,
) -> tuple[RandomForestClassifier, dict[str, Any]]:
    """Fit the RandomForest; returns ``(classifier, best_params)``.

    The full path grid-searches on **PR-AUC** with a forward-chaining ``TimeSeriesSplit``
    (rows must be time-ordered), not random-fold F1.
    """
    if fast:
        clf = RandomForestClassifier(
            random_state=42, class_weight="balanced", n_jobs=-1, **FAST_PARAMS
        )
        clf.fit(X, y, sample_weight=sample_weight)
        return clf, dict(FAST_PARAMS)

    grid = GridSearchCV(
        RandomForestClassifier(random_state=42, class_weight="balanced", n_jobs=-1),
        param_grid=_GRID,
        scoring="average_precision",
        cv=TimeSeriesSplit(n_splits=3),
        n_jobs=-1,
    )
    grid.fit(X, y, sample_weight=sample_weight)
    return grid.best_estimator_, dict(grid.best_params_)


def normalise_anomaly(raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Scale raw ``-decision_function`` scores to [0, 1] with the training range."""
    if hi - lo < 1e-9:
        return np.clip(raw, 0.0, 1.0)
    return np.clip((raw - lo) / (hi - lo), 0.0, 1.0)


def score_frame(bundle: dict[str, Any], df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(fraud_probability, anomaly_score)`` arrays for every row of ``df``."""
    X = to_matrix(df)
    proba = bundle["model"].predict_proba(X)[:, 1]
    raw = -bundle["iso"].decision_function(X)
    anomaly = normalise_anomaly(raw, bundle["iso_score_min"], bundle["iso_score_max"])
    return proba, anomaly


def composite_risk_scores(df: pd.DataFrame, proba: np.ndarray, anomaly: np.ndarray) -> np.ndarray:
    """0-100 composite risk score per row, from the same ``compute_risk`` used live."""
    out = np.empty(len(df), dtype=int)
    for i, row in enumerate(to_matrix(df)):
        feats = dict(zip(FEATURE_COLUMNS, row.tolist()))
        out[i] = compute_risk(
            feats, {"fraud_prob": float(proba[i]), "anomaly_score": float(anomaly[i])}
        )["risk_score"]
    return out


def build_bundle(
    train: pd.DataFrame,
    val: pd.DataFrame,
    *,
    fast: bool,
    version: str,
    dataset: str,
    sample_weight: Optional[np.ndarray] = None,
    cost: Optional[CostMatrix] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Train on ``train``; calibrate and pick cutoffs on ``val``.

    Returns ``(bundle, report)``; ``report`` carries calibration info and both threshold
    sweeps for the metrics file.
    """
    cost = cost or CostMatrix.from_settings()
    X_tr, y_tr = to_matrix(train), train["is_fraud"].to_numpy()
    X_val, y_val = to_matrix(val), val["is_fraud"].to_numpy()

    t0 = time.perf_counter()
    base, best_params = fit_forest(X_tr, y_tr, fast=fast, sample_weight=sample_weight)
    fit_seconds = time.perf_counter() - t0
    model, calibration = fit_isotonic(base, X_val, y_val)

    iso = IsolationForest(
        n_estimators=200,
        contamination=min(max(float(y_tr.mean()), 1e-3), 0.5),
        random_state=42,
        n_jobs=-1,
    )
    iso.fit(X_tr)
    raw_train = -iso.decision_function(X_tr)

    bundle: dict[str, Any] = {
        "model": model,
        "base_model": base,
        "iso": iso,
        "iso_score_min": float(raw_train.min()),
        "iso_score_max": float(raw_train.max()),
        "feature_columns": FEATURE_COLUMNS,
        "best_params": best_params,
        "calibration": calibration,
        "version": version,
        "dataset": dataset,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "operating_threshold": 0.5,
    }

    # Cutoffs are chosen on validation scores from the *final* (calibrated) model.
    proba_val, anomaly_val = score_frame(bundle, val)
    op = sweep_probability_threshold(y_val, proba_val, cost)
    bundle["operating_threshold"] = op["threshold"]

    scores_val = composite_risk_scores(val, proba_val, anomaly_val)
    tiers = sweep_tier_thresholds(y_val, scores_val, cost)
    bundle["risk_thresholds"] = {"low_max": tiers["low_max"], "medium_max": tiers["medium_max"]}

    report = {
        "calibration": calibration,
        "operating_threshold": {k: v for k, v in op.items()},
        "risk_thresholds": {k: v for k, v in tiers.items() if k != "sweep"},
        "threshold_sweep": tiers["sweep"],
        "cost_matrix": cost.as_dict(),
        "best_params": best_params,
        "fit_seconds": fit_seconds,
    }
    return bundle, report


def evaluate_bundle(bundle: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    """Full metric suite for ``bundle`` on ``df`` at the bundle's operating threshold."""
    proba, _ = score_frame(bundle, df)
    thr = float(bundle.get("operating_threshold", 0.5))
    y = df["is_fraud"].to_numpy()
    return compute_metrics(y, (proba >= thr).astype(int), proba, threshold=thr)
