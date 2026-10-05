"""Synthetic UPI generator - seeds the UPI Lab demo model ONLY.

Fraud labels come from independent latent behaviours (account takeover, scam
payments, impossible travel, micro-testing). Even so, ``extract_features`` is used
both to build the signals and to featurise them and the fraud rate (13%) is ~100x
the real-world base rate, so a held-out score on this data measures how well a
tree recovers its own generator, not fraud detection. Reported metrics come from
:mod:`app.ml.datasets.paysim`; this module only provides the demo/Lab model's
training data and the fallback used when no benchmark dataset is configured.

The generator body is unchanged from the original ``training.py``; only the public
entry point was renamed to :func:`generate_synthetic_lab_dataset`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

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


def generate_synthetic_lab_dataset(n_rows: int = 12_000, fraud_rate: float = 0.13) -> pd.DataFrame:
    """Generate a labelled synthetic UPI dataset as a feature DataFrame.

    Seeds the live demo model and the UPI Lab only. Metrics measured on this data
    must never be reported as model performance: ``extract_features`` both builds
    the signals the labels come from and featurises them, so a tree can recover
    the generator exactly (hence precision 1.000 at a 13% fraud rate).
    """
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


class SyntheticDataset:
    """Dataset adapter over the synthetic generator (Lab/demo use only)."""

    name = "synthetic"
    is_benchmark = False

    def __init__(
        self, n_rows: int = 12_000, fraud_rate: float = 0.13, seed: int | None = 42
    ) -> None:
        self.n_rows = n_rows
        self.fraud_rate = fraud_rate
        self.seed = seed

    def load(self) -> pd.DataFrame:
        global RNG
        if self.seed is not None:
            # The generator draws from a module-level RNG that advances on every call;
            # re-seeding makes each load() reproducible regardless of call history.
            RNG = np.random.default_rng(self.seed)
        df = generate_synthetic_lab_dataset(self.n_rows, self.fraud_rate)
        # Rows are i.i.d. draws, so generation order is the only "time" there is.
        df["time_step"] = np.arange(len(df), dtype=np.int64)
        return df[[*FEATURE_COLUMNS, "is_fraud", "time_step"]]
