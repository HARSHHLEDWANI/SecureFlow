"""Train the SecureFlow fraud-detection models on synthetic UPI data.

Generates a realistic UPI transaction dataset where fraud labels come from
*independent latent behaviours* (account takeover, scam payments, impossible
travel, micro-testing) rather than from thresholding the engineered features -
so the model must genuinely learn the patterns instead of re-deriving a rule.

Trains:
  * a supervised ``RandomForestClassifier`` (fraud probability), tuned with
    5-fold cross-validated grid search, and
  * an unsupervised ``IsolationForest`` (anomaly score).

Run from the ``backend`` directory:  ``python -m app.ml.training``
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import GridSearchCV, cross_val_score, train_test_split

from app.config import get_settings
from app.ml.evaluation import compute_metrics, feature_importance
from app.ml.features import FEATURE_COLUMNS, extract_features

RNG = np.random.default_rng(42)

# A handful of Indian city centroids for realistic geo signals.
CITIES = {
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Bengaluru": (12.9716, 77.5946),
    "Kolkata": (22.5726, 88.3639),
    "Chennai": (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
}
CITY_NAMES = list(CITIES.keys())
TXN_TYPES = ["P2P", "P2M", "BILL_PAY"]


def _make_user_profiles(n_users: int) -> list[dict]:
    profiles = []
    for _ in range(n_users):
        avg = float(np.clip(RNG.lognormal(mean=6.5, sigma=0.8), 50, 80_000))
        city = CITY_NAMES[int(RNG.integers(0, len(CITY_NAMES)))]
        profiles.append(
            {
                "avg_amount": avg,
                "std_amount": avg * 0.4 + 50,
                "home": CITIES[city],
                "active_hours": sorted(RNG.choice(range(7, 23), size=8, replace=False).tolist()),
            }
        )
    return profiles


def _legit_signals(p: dict) -> dict:
    amount = float(np.clip(RNG.normal(p["avg_amount"], p["std_amount"]), 1, 200_000))
    hour = int(RNG.choice(p["active_hours"]))
    return {
        "amount_inr": amount,
        "txn_type": str(RNG.choice(TXN_TYPES, p=[0.5, 0.4, 0.1])),
        "hour": hour,
        "is_weekend": int(RNG.random() < 0.28),
        "velocity_1h": int(RNG.integers(0, 4)),
        "velocity_24h": int(RNG.integers(1, 15)),
        "geo_distance_km": float(abs(RNG.normal(3, 8))),
        "minutes_since_last": float(np.clip(RNG.exponential(240), 2, 4320)),
        "is_new_device": int(RNG.random() < 0.05),
        "is_new_beneficiary": int(RNG.random() < 0.25),
        "user_avg_amount": p["avg_amount"],
        "user_std_amount": p["std_amount"],
    }


def _fraud_signals(p: dict) -> dict:
    """One of four independent fraud archetypes."""
    archetype = RNG.choice(["takeover", "scam", "travel", "micro"], p=[0.35, 0.3, 0.2, 0.15])
    base = _legit_signals(p)

    if archetype == "takeover":
        base.update(
            amount_inr=float(np.clip(RNG.normal(p["avg_amount"] * 6, p["avg_amount"]), 5_000, 500_000)),
            hour=int(RNG.choice([0, 1, 2, 3, 4, 23])),
            velocity_1h=int(RNG.integers(6, 16)),
            velocity_24h=int(RNG.integers(10, 40)),
            is_new_device=1,
            is_new_beneficiary=1,
            minutes_since_last=float(RNG.uniform(0.5, 8)),
        )
    elif archetype == "scam":
        # Looks almost normal - victim authorises a payment to a fraudster.
        base.update(
            amount_inr=float(RNG.choice([10_000, 25_000, 49_999, 75_000, 99_999])),
            txn_type=str(RNG.choice(["P2P", "P2M"])),
            is_new_beneficiary=1,
            is_new_device=int(RNG.random() < 0.2),
        )
    elif archetype == "travel":
        base.update(
            geo_distance_km=float(RNG.uniform(400, 2000)),
            minutes_since_last=float(RNG.uniform(1, 30)),
            is_new_device=int(RNG.random() < 0.6),
        )
    else:  # micro-testing
        base.update(
            amount_inr=float(RNG.uniform(1, 9)),
            velocity_1h=int(RNG.integers(8, 25)),
            velocity_24h=int(RNG.integers(20, 60)),
            is_new_device=1,
            is_new_beneficiary=1,
            minutes_since_last=float(RNG.uniform(0.2, 3)),
        )
    return base


def generate_dataset(n_rows: int = 12_000, fraud_rate: float = 0.13) -> pd.DataFrame:
    """Generate a labelled synthetic UPI dataset as a feature DataFrame."""
    profiles = _make_user_profiles(max(50, n_rows // 30))
    rows: list[dict] = []
    for _ in range(n_rows):
        p = profiles[int(RNG.integers(0, len(profiles)))]
        is_fraud = RNG.random() < fraud_rate
        signals = _fraud_signals(p) if is_fraud else _legit_signals(p)

        # Inject label noise so the problem isn't trivially separable: a small
        # fraction of frauds look benign and vice-versa.
        label = int(is_fraud)
        if is_fraud and RNG.random() < 0.10:
            signals = _legit_signals(p)  # stealthy fraud that looks normal
        elif not is_fraud and RNG.random() < 0.04:
            label = 0  # noisy-but-legit; keep label 0

        features = extract_features(signals)
        features["is_fraud"] = label
        rows.append(features)

    return pd.DataFrame(rows)


def main() -> None:
    settings = get_settings()
    print("Generating synthetic UPI dataset...")
    df = generate_dataset()
    print(f"  rows={len(df)}  fraud={int(df['is_fraud'].sum())} "
          f"({100 * df['is_fraud'].mean():.1f}%)")

    X = df[FEATURE_COLUMNS].to_numpy()
    y = df["is_fraud"].to_numpy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("Grid-searching RandomForest (5-fold CV)...")
    grid = GridSearchCV(
        RandomForestClassifier(random_state=42, class_weight="balanced", n_jobs=-1),
        param_grid={
            "n_estimators": [150, 250],
            "max_depth": [10, 16, None],
            "min_samples_leaf": [1, 3],
        },
        scoring="f1",
        cv=5,
        n_jobs=-1,
    )
    grid.fit(X_train, y_train)
    clf = grid.best_estimator_
    print(f"  best params: {grid.best_params_}")

    cv_scores = cross_val_score(clf, X_train, y_train, cv=5, scoring="roc_auc")
    print(f"  5-fold CV AUC: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]
    metrics = compute_metrics(y_test, y_pred, y_proba)
    importance = feature_importance(clf, FEATURE_COLUMNS)

    print("\n-- Test metrics --")
    for k in ("accuracy", "precision", "recall", "f1", "auc_roc"):
        print(f"  {k:10s}: {metrics[k]}")
    print(f"  confusion : {metrics['confusion_matrix']}")
    print("  top features:", ", ".join(f["feature"] for f in importance[:5]))

    print("\nFitting IsolationForest (anomaly detector)...")
    iso = IsolationForest(
        n_estimators=200, contamination=float(y_train.mean()), random_state=42, n_jobs=-1
    )
    iso.fit(X_train)
    raw_scores = -iso.decision_function(X_train)  # higher = more anomalous
    iso_min, iso_max = float(raw_scores.min()), float(raw_scores.max())

    bundle = {
        "model": clf,
        "iso": iso,
        "iso_score_min": iso_min,
        "iso_score_max": iso_max,
        "feature_columns": FEATURE_COLUMNS,
        "best_params": grid.best_params_,
        "version": "2.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(os.path.abspath(settings.model_path)) or ".", exist_ok=True)
    joblib.dump(bundle, settings.model_path)
    print(f"\nSaved model -> {settings.model_path}")

    metrics_out = {
        **metrics,
        "cv_auc_mean": round(float(cv_scores.mean()), 4),
        "cv_auc_std": round(float(cv_scores.std()), 4),
        "feature_importance": importance,
        "best_params": grid.best_params_,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "trained_at": bundle["trained_at"],
        "version": bundle["version"],
    }
    with open(settings.model_metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics_out, fh, indent=2)
    print(f"Saved metrics -> {settings.model_metrics_path}")


if __name__ == "__main__":
    main()
