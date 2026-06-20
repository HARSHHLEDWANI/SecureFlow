"""Model loading and real-time inference.

A single :class:`ModelService` loads the joblib bundle once and serves fraud
probability + anomaly score per transaction. If no trained model is present it
falls back to a transparent heuristic so the API still functions.
"""
from __future__ import annotations

import os
import threading
from typing import Any, Optional

import joblib
import numpy as np

from app.config import get_settings
from app.ml.features import FEATURE_COLUMNS, extract_features, to_vector
from app.utils.helpers import clamp
from app.utils.logger import get_logger

logger = get_logger("ml")


class ModelService:
    """Loads the trained models and produces predictions."""

    def __init__(self) -> None:
        self._bundle: Optional[dict[str, Any]] = None
        self._importance: dict[str, float] = {}

    def load(self) -> None:
        path = get_settings().model_path
        if not os.path.exists(path):
            logger.warning("No model at %s - using heuristic fallback", path)
            self._bundle = None
            return
        try:
            self._bundle = joblib.load(path)
            model = self._bundle["model"]
            # Single-row inference is fastest single-threaded: parallel tree
            # dispatch (n_jobs=-1 from training) adds overhead per call.
            model.n_jobs = 1
            if self._bundle.get("iso") is not None:
                self._bundle["iso"].n_jobs = 1
            self._importance = dict(zip(FEATURE_COLUMNS, model.feature_importances_))
            logger.info("Loaded model v%s", self._bundle.get("version", "?"))
        except (OSError, KeyError, ValueError) as exc:
            logger.error("Failed to load model (%s) - using heuristic fallback", exc)
            self._bundle = None

    @property
    def loaded(self) -> bool:
        return self._bundle is not None

    @property
    def version(self) -> Optional[str]:
        return self._bundle.get("version") if self._bundle else None

    # ── Inference ────────────────────────────────────────────────────────────

    def predict(self, raw_signals: dict[str, Any]) -> dict[str, Any]:
        """Return fraud probability, anomaly score, confidence, and drivers."""
        features = extract_features(raw_signals)
        vector = np.array([to_vector(features)], dtype=float)

        if self._bundle is None:
            fraud_prob = self._heuristic(features)
            anomaly = clamp(fraud_prob + 0.05, 0.0, 1.0)
            confidence = 0.5
        else:
            model = self._bundle["model"]
            fraud_prob = float(model.predict_proba(vector)[0][1])
            anomaly = self._anomaly_score(vector)
            confidence = round(0.5 + abs(fraud_prob - 0.5), 4)

        return {
            "fraud_prob": round(fraud_prob, 4),
            "anomaly_score": round(anomaly, 4),
            "confidence": confidence,
            "feature_contributions": self._contributions(features),
            "features": {k: round(v, 4) for k, v in features.items()},
        }

    def _anomaly_score(self, vector: np.ndarray) -> float:
        iso = self._bundle["iso"]
        raw = float(-iso.decision_function(vector)[0])
        lo = self._bundle.get("iso_score_min", -0.5)
        hi = self._bundle.get("iso_score_max", 0.5)
        if hi - lo < 1e-9:
            return clamp(raw, 0.0, 1.0)
        return round(clamp((raw - lo) / (hi - lo), 0.0, 1.0), 4)

    def _contributions(self, features: dict[str, float]) -> list[dict[str, Any]]:
        """Top feature drivers for this prediction (importance × elevated state)."""
        if not self._importance:
            return []
        scored = []
        for col in FEATURE_COLUMNS:
            scored.append(
                {
                    "feature": col,
                    "value": round(features[col], 4),
                    "importance": round(self._importance.get(col, 0.0), 4),
                }
            )
        scored.sort(key=lambda d: d["importance"], reverse=True)
        return scored[:6]

    @staticmethod
    def _heuristic(features: dict[str, float]) -> float:
        """Interpretable fallback when no trained model is available."""
        score = (
            0.30 * features["impossible_travel"]
            + 0.20 * features["high_velocity"]
            + 0.15 * features["is_new_device"]
            + 0.12 * features["is_new_beneficiary"]
            + 0.10 * features["is_high_value"]
            + 0.08 * features["is_night"]
            + 0.05 * features["is_micro"]
        )
        return clamp(score, 0.0, 1.0)


_service: Optional[ModelService] = None
_lock = threading.Lock()


def get_model_service() -> ModelService:
    """Return the process-wide model singleton (lazy, thread-safe)."""
    global _service
    if _service is None:
        with _lock:
            if _service is None:
                svc = ModelService()
                svc.load()
                _service = svc
    return _service
