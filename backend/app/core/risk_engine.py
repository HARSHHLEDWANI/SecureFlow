"""Composite risk scoring engine.

Combines the ML signals with deterministic behavioural signals (velocity,
geo-velocity, device trust, amount/time anomaly) into a single 0–100 score and
a tiered action: LOW → ALLOWED, MEDIUM → STEP_UP (OTP), HIGH → BLOCKED.
"""
from __future__ import annotations

from typing import Any

from app.database import RiskTier, TxnStatus
from app.utils.helpers import clamp

# Signal weights (sum = 100). See ARCHITECTURE.md §8.
WEIGHTS = {
    "ml_fraud": 40.0,
    "anomaly": 15.0,
    "velocity": 15.0,
    "geo": 12.0,
    "new_device": 8.0,
    "amount": 6.0,
    "time": 4.0,
}

LOW_MAX = 30
MEDIUM_MAX = 70


def _tier_and_status(score: int) -> tuple[RiskTier, TxnStatus]:
    if score <= LOW_MAX:
        return RiskTier.LOW, TxnStatus.ALLOWED
    if score <= MEDIUM_MAX:
        return RiskTier.MEDIUM, TxnStatus.STEP_UP
    return RiskTier.HIGH, TxnStatus.BLOCKED


def compute_risk(features: dict[str, float], ml_result: dict[str, Any]) -> dict[str, Any]:
    """Return the composite risk assessment for a transaction.

    ``features`` is the engineered feature dict; ``ml_result`` is the output of
    :meth:`ModelService.predict`.
    """
    velocity_signal = clamp(features.get("velocity_1h", 0.0) / 10.0, 0.0, 1.0)

    if features.get("impossible_travel", 0.0) >= 1.0:
        geo_signal = 1.0
    else:
        geo_signal = clamp(features.get("geo_distance_km", 0.0) / 1500.0, 0.0, 0.5)

    amount_signal = clamp(features.get("amount_zscore", 0.0) / 5.0, 0.0, 1.0)

    components = {
        "ml_fraud": float(ml_result.get("fraud_prob", 0.0)),
        "anomaly": float(ml_result.get("anomaly_score", 0.0)),
        "velocity": velocity_signal,
        "geo": geo_signal,
        "new_device": features.get("is_new_device", 0.0),
        "amount": amount_signal,
        "time": features.get("is_night", 0.0),
    }

    weighted = {k: round(components[k] * WEIGHTS[k], 2) for k in WEIGHTS}
    score = int(round(clamp(sum(weighted.values()), 0.0, 100.0)))
    tier, status = _tier_and_status(score)

    return {
        "risk_score": score,
        "risk_tier": tier,
        "status": status,
        "components": components,
        "weighted_contributions": weighted,
    }
