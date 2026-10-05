"""Baseline classifiers trained alongside the RandomForest on identical splits.

The comparison table makes the model choice a decision with evidence. The served model
stays the RandomForest because the serving path needs per-feature importances for
explanations and ~20 ms single-row latency; if a baseline wins on validation PR-AUC the
table says so and the model card must discuss it.
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.evaluation import (
    FPR_TARGETS,
    PRECISION_AT_K,
    brier,
    pr_auc,
    precision_at_k,
    recall_at_fpr,
)


def make_baselines() -> dict[str, Any]:
    return {
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42),
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.1, random_state=42
        ),
    }


def score_row(name: str, model: Any, X: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """Uncalibrated ranking metrics for one model on one split."""
    p = model.predict_proba(X)[:, 1]
    return {
        "pr_auc": round(pr_auc(y, p), 4),
        "precision_at_k": {str(k): round(precision_at_k(y, p, k), 4) for k in PRECISION_AT_K},
        "recall_at_fpr": {f"{f:g}": round(recall_at_fpr(y, p, f), 4) for f in FPR_TARGETS},
        "brier": round(brier(y, p), 6),
    }


def compare_models(
    models: dict[str, Any],
    X_val: np.ndarray, y_val: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray,
    fit_seconds: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """One row per model: validation and test metrics from raw (uncalibrated) scores."""
    rows = []
    for name, model in models.items():
        rows.append(
            {
                "model": name,
                "fit_seconds": None if not fit_seconds else round(fit_seconds.get(name, 0.0), 2),
                "validation": score_row(name, model, X_val, y_val),
                "test": score_row(name, model, X_test, y_test),
            }
        )
    best = max(rows, key=lambda r: r["validation"]["pr_auc"])
    for r in rows:
        r["best_validation_pr_auc"] = r is best
    return rows


def fit_timed(name: str, model: Any, X: np.ndarray, y: np.ndarray, out: dict[str, float]) -> Any:
    start = time.perf_counter()
    model.fit(X, y)
    out[name] = time.perf_counter() - start
    return model
