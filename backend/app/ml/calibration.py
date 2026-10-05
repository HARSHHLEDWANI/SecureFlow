"""Probability calibration for the fraud classifier.

``RandomForestClassifier.predict_proba`` is a vote share, not a probability, and
training on an undersampled (or class-balanced) set shifts it further upward. The risk
engine multiplies ``fraud_prob`` by a weight as though it were a probability, so the
classifier is wrapped in an isotonic calibrator fitted on the *validation* split - data
the forest never saw and that keeps the true base rate.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV

from app.ml.evaluation import brier

try:  # scikit-learn >= 1.6: the supported way to calibrate an already-fitted model
    from sklearn.frozen import FrozenEstimator
except ImportError:  # pragma: no cover - older scikit-learn
    FrozenEstimator = None  # type: ignore[assignment,misc]

MIN_VALIDATION_POSITIVES = 20


def fit_isotonic(clf: Any, X_val: np.ndarray, y_val: np.ndarray) -> tuple[Any, dict[str, Any]]:
    """Calibrate fitted ``clf`` on ``(X_val, y_val)``; return ``(model, info)``.

    Equivalent to ``CalibratedClassifierCV(method="isotonic", cv="prefit")`` (the
    spelling deprecated in scikit-learn 1.6 in favour of ``FrozenEstimator``). If the
    validation split has too few positives for isotonic regression to be trustworthy,
    ``clf`` is returned unchanged and ``info["applied"]`` is False.
    """
    n_pos = int(np.asarray(y_val).sum())
    info: dict[str, Any] = {
        "method": "isotonic",
        "fitted_on": "validation",
        "n_validation": int(len(y_val)),
        "n_validation_positives": n_pos,
    }
    if n_pos < MIN_VALIDATION_POSITIVES or n_pos == len(y_val):
        info.update(applied=False, reason=f"fewer than {MIN_VALIDATION_POSITIVES} validation positives")
        return clf, info

    if FrozenEstimator is not None:
        calibrated = CalibratedClassifierCV(FrozenEstimator(clf), method="isotonic")
    else:  # pragma: no cover
        calibrated = CalibratedClassifierCV(clf, method="isotonic", cv="prefit")
    calibrated.fit(X_val, y_val)
    info["applied"] = True
    return calibrated, info


def brier_before_after(
    raw_model: Any, calibrated_model: Any, X: np.ndarray, y: np.ndarray
) -> dict[str, float]:
    """Brier score of the raw vs calibrated probabilities on the same rows."""
    return {
        "before": round(brier(y, raw_model.predict_proba(X)[:, 1]), 6),
        "after": round(brier(y, calibrated_model.predict_proba(X)[:, 1]), 6),
    }
