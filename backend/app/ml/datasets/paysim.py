"""PaySim mobile-money dataset adapter (Kaggle ``ealaxi/paysim1``).

PaySim simulates a month of mobile-money transactions (~6.3M rows, ~0.13% fraud,
one ``step`` per simulated hour). It is the closest public analogue of UPI P2P:
account-to-account transfers with a real class imbalance and a time axis.

The CSV is **never downloaded** by this code. Put ``PS_20174392719_1491204439457_Log.csv``
somewhere local and point the ``PAYSIM_PATH`` setting at it. ``PAYSIM_MAX_ROWS``
(optional) keeps only the first N raw CSV rows in chronological order (before
CASH_IN rows are dropped) - a prefix of the month, so the base rate stays realistic but the time range shrinks.

Column mapping (PaySim -> raw signal -> ``extract_features``)
------------------------------------------------------------
``step``            -> ``time_step`` (the chronological split key) and
                       ``hour = step % 24``.
``type``            -> ``txn_type``: TRANSFER, CASH_OUT -> ``P2P``; PAYMENT -> ``P2M``;
                       DEBIT -> ``BILL_PAY``. CASH_IN rows are dropped: an inbound
                       deposit is not a payment decision. All PaySim fraud is
                       TRANSFER or CASH_OUT, so type alone separates a lot of
                       legitimate volume - a genuine property of the data.
``amount``          -> ``amount_inr`` (PaySim currency units, treated as INR).
``nameOrig``        -> the account whose history drives the state features:
  * ``velocity_1h``        = prior txns by this account in the same step.
  * ``velocity_24h``       = prior txns by this account in steps [step-23, step].
  * ``minutes_since_last`` = (step - previous step of this account) * 60; first
                             txn uses 1440, the ``extract_features`` default.
  * ``is_new_beneficiary`` = first time this (nameOrig, nameDest) pair appears.
  * ``user_avg_amount`` / ``user_std_amount`` = expanding mean / std over the
                             account's *prior* amounts only (no look-ahead); with
                             no history the amount itself and 0 are used, which
                             ``extract_features`` turns into ``amount_zscore = 0``.
``isFraud``         -> ``is_fraud``.

Not mappable, set to neutral constants (and therefore uninformative):
``geo_distance_km = 0`` and ``is_new_device = 0`` (PaySim has no location or
device), ``is_weekend = 0`` (the simulation publishes no calendar anchor).
``oldbalance*`` / ``newbalance*`` / ``nameDest`` balances / ``isFlaggedFraud`` are
unused: balances have no counterpart in the UPI feature space, and
``isFlaggedFraud`` is the simulator's own rule output.

Known limitation: in PaySim almost every ``nameOrig`` appears exactly once, so the
per-account history features are degenerate for most rows (velocity ~0,
``is_new_beneficiary`` ~1, z-score 0). That is a property of the source, not of this
mapping; the model card states it.
"""
from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

from app.config import get_settings
from app.ml.datasets import CANONICAL_COLUMNS
from app.ml.features import extract_features

REQUIRED_COLUMNS = ["step", "type", "amount", "nameOrig", "nameDest", "isFraud"]

TYPE_MAP = {"TRANSFER": "P2P", "CASH_OUT": "P2P", "PAYMENT": "P2M", "DEBIT": "BILL_PAY"}

_FIRST_TXN_MINUTES = 24 * 60.0
_CHUNK = 100_000


class DatasetNotFoundError(FileNotFoundError):
    """Raised when the PaySim CSV is not configured or missing."""


def build_raw_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Derive per-transaction raw signals (the ``extract_features`` input) from PaySim rows.

    Returns a frame sorted chronologically with columns: the keys documented in
    :func:`app.ml.features.extract_features`, plus ``is_fraud`` and ``time_step``.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"PaySim CSV is missing required columns: {missing}")

    df = df[df["type"].isin(TYPE_MAP)].copy()
    # Stable sort: the CSV is already step-ordered; ties keep file order.
    df = df.sort_values("step", kind="stable").reset_index(drop=True)

    step = df["step"].to_numpy(dtype=np.int64)
    amount = df["amount"].to_numpy(dtype=float)
    orig = pd.factorize(df["nameOrig"])[0].astype(np.int64)
    dest = pd.factorize(df["nameDest"])[0].astype(np.int64)

    # Per-account ordinal within the account's own history (file order within a step).
    g_orig = df.groupby(orig, sort=False)
    prior_count = g_orig.cumcount().to_numpy()
    same_step_prior = df.groupby([orig, step], sort=False).cumcount().to_numpy()

    # velocity_24h: prior txns by the same account in steps [step-23, step].
    big = int(step.max()) + 30
    key = orig * big + step
    sorted_keys = np.sort(key)
    lo = orig * big + np.maximum(step - 23, 0)
    in_window_before_step = np.searchsorted(sorted_keys, key, "left") - np.searchsorted(
        sorted_keys, lo, "left"
    )
    velocity_24h = in_window_before_step + same_step_prior

    prev_step = g_orig["step"].shift(1).to_numpy(dtype=float)
    minutes_since_last = np.where(
        np.isnan(prev_step), _FIRST_TXN_MINUTES, (step - prev_step) * 60.0
    )

    is_new_beneficiary = (df.groupby([orig, dest], sort=False).cumcount().to_numpy() == 0)

    # Expanding mean/std over strictly prior amounts of the same account.
    s1 = pd.Series(amount).groupby(orig, sort=False).cumsum().to_numpy() - amount
    s2 = pd.Series(amount**2).groupby(orig, sort=False).cumsum().to_numpy() - amount**2
    cnt = np.maximum(prior_count, 1)
    mean = s1 / cnt
    var = np.maximum(s2 / cnt - mean**2, 0.0)
    has_history = prior_count >= 1
    user_avg = np.where(has_history, mean, amount)
    user_std = np.where(has_history, np.sqrt(var), 0.0)

    return pd.DataFrame(
        {
            "amount_inr": amount,
            "txn_type": df["type"].map(TYPE_MAP).to_numpy(),
            "hour": step % 24,
            "is_weekend": 0,
            "velocity_1h": same_step_prior,
            "velocity_24h": velocity_24h,
            "geo_distance_km": 0.0,
            "minutes_since_last": minutes_since_last,
            "is_new_device": 0,
            "is_new_beneficiary": is_new_beneficiary.astype(int),
            "user_avg_amount": user_avg,
            "user_std_amount": user_std,
            "is_fraud": df["isFraud"].to_numpy(dtype=int),
            "time_step": step,
        }
    )


def featurise(signals: pd.DataFrame) -> pd.DataFrame:
    """Run every row through the shared :func:`extract_features` (chunked for memory)."""
    meta = ["is_fraud", "time_step"]
    raw_cols = [c for c in signals.columns if c not in meta]
    parts: list[pd.DataFrame] = []
    for start in range(0, len(signals), _CHUNK):
        chunk = signals.iloc[start : start + _CHUNK]
        records: list[dict[str, Any]] = chunk[raw_cols].to_dict("records")
        feats = pd.DataFrame([extract_features(r) for r in records]).astype("float32")
        feats["is_fraud"] = chunk["is_fraud"].to_numpy(dtype=np.int8)
        feats["time_step"] = chunk["time_step"].to_numpy(dtype=np.int64)
        parts.append(feats)
    out = pd.concat(parts, ignore_index=True)
    return out[CANONICAL_COLUMNS]


class PaySimDataset:
    """Dataset adapter for the local PaySim CSV."""

    name = "paysim"
    is_benchmark = True

    def __init__(self, path: str | None = None, max_rows: int | None = None) -> None:
        settings = get_settings()
        self.path = path if path is not None else settings.paysim_path
        self.max_rows = max_rows if max_rows is not None else settings.paysim_max_rows

    def load(self) -> pd.DataFrame:
        if not self.path or not os.path.isfile(self.path):
            raise DatasetNotFoundError(
                "PaySim CSV not found. Download 'ealaxi/paysim1' from Kaggle "
                "(https://www.kaggle.com/datasets/ealaxi/paysim1), place the CSV on "
                "disk (e.g. backend/data/paysim.csv) and set PAYSIM_PATH to its path. "
                f"Current PAYSIM_PATH={self.path!r}."
            )
        usecols = [*REQUIRED_COLUMNS]
        raw = pd.read_csv(self.path, usecols=usecols)
        if self.max_rows and self.max_rows > 0:
            raw = raw.sort_values("step", kind="stable").head(self.max_rows)
        return featurise(build_raw_signals(raw))
