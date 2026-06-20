"""Model evaluation metrics used by the training script and reporting endpoint."""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray
) -> dict[str, Any]:
    """Return the standard binary-classification metric suite as a dict."""
    cm = confusion_matrix(y_true, y_pred)
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "auc_roc": round(float(roc_auc_score(y_true, y_proba)), 4),
        "confusion_matrix": cm.tolist(),
        "support": {"legit": int((y_true == 0).sum()), "fraud": int((y_true == 1).sum())},
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
