"""ML feature engineering and model inference."""
import time

from app.ml.features import FEATURE_COLUMNS, extract_features, to_vector
from app.ml.model import get_model_service


def test_features_cover_all_columns():
    feats = extract_features({"amount_inr": 1000, "txn_type": "P2P", "hour": 14})
    assert set(FEATURE_COLUMNS).issubset(feats.keys())
    assert len(to_vector(feats)) == len(FEATURE_COLUMNS)


def test_impossible_travel_flag():
    feats = extract_features(
        {"amount_inr": 500, "geo_distance_km": 1500, "minutes_since_last": 10}
    )
    assert feats["impossible_travel"] == 1.0


def test_high_value_and_micro_flags():
    assert extract_features({"amount_inr": 100_000})["is_high_value"] == 1.0
    assert extract_features({"amount_inr": 2})["is_micro"] == 1.0


def test_model_loads_and_predicts():
    svc = get_model_service()
    result = svc.predict(
        {"amount_inr": 2500, "txn_type": "P2P", "hour": 14, "user_avg_amount": 3000}
    )
    assert 0.0 <= result["fraud_prob"] <= 1.0
    assert 0.0 <= result["anomaly_score"] <= 1.0
    assert isinstance(result["feature_contributions"], list)


def test_prediction_latency_under_100ms():
    svc = get_model_service()
    payload = {"amount_inr": 2500, "txn_type": "P2P", "hour": 14, "user_avg_amount": 3000}
    svc.predict(payload)  # warm up
    start = time.perf_counter()
    for _ in range(20):
        svc.predict(payload)
    avg_ms = (time.perf_counter() - start) / 20 * 1000
    assert avg_ms < 100, f"prediction too slow: {avg_ms:.1f}ms"


def test_fraud_pattern_scores_higher_than_normal():
    svc = get_model_service()
    normal = svc.predict(
        {"amount_inr": 1500, "txn_type": "P2P", "hour": 14, "velocity_1h": 1,
         "user_avg_amount": 2000, "user_std_amount": 500}
    )
    fraud = svc.predict(
        {"amount_inr": 300_000, "txn_type": "P2M", "hour": 3, "velocity_1h": 12,
         "is_new_device": 1, "is_new_beneficiary": 1, "geo_distance_km": 1800,
         "minutes_since_last": 5, "user_avg_amount": 2000, "user_std_amount": 500}
    )
    assert fraud["fraud_prob"] > normal["fraud_prob"]
