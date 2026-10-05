"""Model evaluation metrics used by the training script and reporting endpoint.

At a realistic fraud base rate (~0.1%) accuracy and AUC-ROC are nearly meaningless:
predicting "legit" always scores 99.9% accuracy, and AUC-ROC barely moves with the
false-positive count that dominates real cost. The headline metric is therefore
**PR-AUC (average precision)**, backed by precision@k, recall at a fixed false-positive
rate, and calibration (Brier + reliability). Accuracy and AUC-ROC are still computed
but are never the headline.
"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

PRECISION_AT_K = (100, 500, 1000)
FPR_TARGETS = (0.001, 0.005, 0.01)
HEADLINE_METRIC = "pr_auc"


def pr_auc(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """Average precision: sum over thresholds of (recall step) x precision."""
    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(average_precision_score(y_true, y_proba))


def precision_at_k(y_true: np.ndarray, y_proba: np.ndarray, k: int) -> float:
    """Share of true frauds among the ``k`` highest-scored transactions.

    ``k`` is clamped to the sample size so small splits still return a value.
    """
    k = min(int(k), len(y_true))
    if k <= 0:
        return float("nan")
    top = np.argsort(-np.asarray(y_proba), kind="stable")[:k]
    return float(np.asarray(y_true)[top].mean())


def recall_at_fpr(y_true: np.ndarray, y_proba: np.ndarray, max_fpr: float) -> float:
    """Highest recall achievable while the false-positive rate stays <= ``max_fpr``."""
    if len(np.unique(y_true)) < 2:
        return float("nan")
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    return float(tpr[fpr <= max_fpr].max())


def reliability_table(
    y_true: np.ndarray, y_proba: np.ndarray, bins: int = 10
) -> list[dict[str, Any]]:
    """Equal-width probability bins: mean predicted vs observed fraud rate per bin."""
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(y_proba, edges[1:-1], right=False), 0, bins - 1)
    table: list[dict[str, Any]] = []
    for b in range(bins):
        mask = idx == b
        n = int(mask.sum())
        table.append(
            {
                "bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}",
                "count": n,
                "mean_predicted": round(float(y_proba[mask].mean()), 6) if n else None,
                "observed_rate": round(float(y_true[mask].mean()), 6) if n else None,
            }
        )
    return table


def brier(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    return float(brier_score_loss(y_true, y_proba))


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    threshold: float | None = None,
    ks: Sequence[int] = PRECISION_AT_K,
    fprs: Sequence[float] = FPR_TARGETS,
) -> dict[str, Any]:
    """Return the full metric suite. ``pr_auc`` is the headline.

    ``y_pred`` are hard labels at the operating ``threshold`` (recorded for
    reference); ranking metrics use ``y_proba`` only.
    """
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    auc = (
        float(roc_auc_score(y_true, y_proba)) if len(np.unique(y_true)) == 2 else float("nan")
    )
    return {
        "headline": {"metric": HEADLINE_METRIC, "value": round(pr_auc(y_true, y_proba), 4)},
        "pr_auc": round(pr_auc(y_true, y_proba), 4),
        "precision_at_k": {
            str(k): round(precision_at_k(y_true, y_proba, k), 4) for k in ks
        },
        "recall_at_fpr": {
            f"{f:g}": round(recall_at_fpr(y_true, y_proba, f), 4) for f in fprs
        },
        "brier": round(brier(y_true, y_proba), 6),
        "reliability": reliability_table(y_true, y_proba),
        # Reference metrics - not headline numbers at imbalanced base rates.
        "threshold": None if threshold is None else round(float(threshold), 6),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "auc_roc": round(auc, 4),
        "confusion_matrix": cm.tolist(),
        "support": {"legit": int((y_true == 0).sum()), "fraud": int((y_true == 1).sum())},
        "fraud_rate": round(float(y_true.mean()), 6),
    }


def feature_importance(model: Any, feature_columns: list[str]) -> list[dict[str, Any]]:
    """Return features ranked by importance (descending)."""
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return []
    ranked = sorted(
        ({"feature": c, "importance": round(float(v), 4)} for c, v in zip(feature_columns, importances)),
        key=lambda d: d["importance"],
        reverse=True,
    )
    return ranked
