"""Composite risk engine: the five crafted scenarios from the build spec."""
from app.core.risk_engine import compute_risk
from app.database import RiskTier
from app.ml.features import extract_features


def _assess(signals, fraud_prob, anomaly=0.1):
    features = extract_features(signals)
    ml = {"fraud_prob": fraud_prob, "anomaly_score": anomaly}
    return compute_risk(features, ml)


def test_normal_transaction_is_low():
    r = _assess(
        {"amount_inr": 1200, "txn_type": "P2P", "hour": 13, "velocity_1h": 1,
         "user_avg_amount": 1500, "user_std_amount": 400},
        fraud_prob=0.05,
    )
    assert r["risk_tier"] == RiskTier.LOW


def test_impossible_travel_raises_geo_component():
    r = _assess(
        {"amount_inr": 5000, "geo_distance_km": 1800, "minutes_since_last": 5},
        fraud_prob=0.4,
    )
    assert r["components"]["geo"] == 1.0
    # Geo alone lifts the score above the no-signal baseline (~18).
    assert r["risk_score"] >= 30


def test_new_device_contributes():
    r = _assess({"amount_inr": 5000, "is_new_device": 1}, fraud_prob=0.3)
    assert r["components"]["new_device"] == 1.0


def test_known_fraud_pattern_is_high():
    r = _assess(
        {"amount_inr": 400_000, "txn_type": "P2M", "hour": 3, "velocity_1h": 14,
         "is_new_device": 1, "is_new_beneficiary": 1, "geo_distance_km": 1500,
         "minutes_since_last": 4, "user_avg_amount": 2000, "user_std_amount": 500},
        fraud_prob=0.95,
        anomaly=0.9,
    )
    assert r["risk_tier"] == RiskTier.HIGH
    assert r["risk_score"] > 70


def test_score_is_bounded():
    r = _assess({"amount_inr": 1_000_000, "velocity_1h": 50}, fraud_prob=1.0, anomaly=1.0)
    assert 0 <= r["risk_score"] <= 100
