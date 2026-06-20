"""Feature engineering for UPI transaction fraud detection.

A single :func:`extract_features` function turns the *raw signals* of a
transaction (amount, type, timing, and per-user history context) into the
ordered numeric feature vector consumed by the models. Using one function for
both training and inference guarantees the two never drift apart.
"""
from __future__ import annotations

import math
from typing import Any

# Speed above which consecutive transactions imply physically impossible travel.
IMPOSSIBLE_TRAVEL_KMH = 700.0

FEATURE_COLUMNS: list[str] = [
    "amount_inr",
    "amount_log",
    "is_high_value",
    "is_micro",
    "txn_p2p",
    "txn_p2m",
    "txn_billpay",
    "hour_of_day",
    "is_night",
    "is_weekend",
    "velocity_1h",
    "velocity_24h",
    "high_velocity",
    "geo_distance_km",
    "impossible_travel",
    "is_new_device",
    "is_new_beneficiary",
    "amount_zscore",
    "minutes_since_last",
]


def extract_features(raw: dict[str, Any]) -> dict[str, float]:
    """Build the full feature dict from raw transaction signals.

    Expected ``raw`` keys (all optional, sensible defaults applied):
    ``amount_inr, txn_type, hour, is_weekend, velocity_1h, velocity_24h,
    geo_distance_km, minutes_since_last, is_new_device, is_new_beneficiary,
    user_avg_amount, user_std_amount``.
    """
    amount = float(raw.get("amount_inr", 0.0))
    txn_type = str(raw.get("txn_type", "P2P")).upper()
    hour = int(raw.get("hour", 12))
    velocity_1h = int(raw.get("velocity_1h", 0))
    velocity_24h = int(raw.get("velocity_24h", 0))
    geo_distance = float(raw.get("geo_distance_km", 0.0))
    minutes_since_last = float(raw.get("minutes_since_last", 24 * 60))

    user_avg = float(raw.get("user_avg_amount", amount or 1.0)) or 1.0
    user_std = float(raw.get("user_std_amount", 0.0))

    # Impossible-travel: implied speed exceeds a physical threshold.
    hours_elapsed = max(minutes_since_last / 60.0, 1e-3)
    implied_speed = geo_distance / hours_elapsed
    impossible_travel = 1.0 if implied_speed > IMPOSSIBLE_TRAVEL_KMH else 0.0

    amount_zscore = (amount - user_avg) / user_std if user_std > 1.0 else 0.0
    # Cap to keep extreme synthetic values from dominating the model.
    amount_zscore = max(-10.0, min(10.0, amount_zscore))

    return {
        "amount_inr": amount,
        "amount_log": math.log1p(max(amount, 0.0)),
        "is_high_value": 1.0 if amount > 50_000 else 0.0,
        "is_micro": 1.0 if amount < 10 else 0.0,
        "txn_p2p": 1.0 if txn_type == "P2P" else 0.0,
        "txn_p2m": 1.0 if txn_type == "P2M" else 0.0,
        "txn_billpay": 1.0 if txn_type == "BILL_PAY" else 0.0,
        "hour_of_day": float(hour),
        "is_night": 1.0 if (hour < 6 or hour >= 22) else 0.0,
        "is_weekend": 1.0 if raw.get("is_weekend") else 0.0,
        "velocity_1h": float(velocity_1h),
        "velocity_24h": float(velocity_24h),
        "high_velocity": 1.0 if velocity_1h > 5 else 0.0,
        "geo_distance_km": geo_distance,
        "impossible_travel": impossible_travel,
        "is_new_device": 1.0 if raw.get("is_new_device") else 0.0,
        "is_new_beneficiary": 1.0 if raw.get("is_new_beneficiary") else 0.0,
        "amount_zscore": amount_zscore,
        "minutes_since_last": min(minutes_since_last, 7 * 24 * 60),
    }


def to_vector(features: dict[str, float]) -> list[float]:
    """Order a feature dict into the canonical model input vector."""
    return [features[col] for col in FEATURE_COLUMNS]
