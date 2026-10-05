"""Generate a PaySim-SHAPED CSV for offline testing of the benchmark pipeline.

THIS IS NOT PAYSIM. It reproduces PaySim's published schema and coarse statistics
(type mix, ~0.13% fraud confined to TRANSFER/CASH_OUT, mostly-unique ``nameOrig``,
heavy-tailed amounts, 743 hourly steps with a diurnal legit pattern, fraud that
targets large amounts) so the adapter / training / calibration / threshold code can
be exercised at realistic scale and imbalance without the Kaggle download. Any metric
measured on this file is a pipeline smoke result and must NEVER be quoted as PaySim
performance - the fraud signal here is whatever this script puts in.

    python scripts/simulate_paysim.py --rows 1500000 --out data/paysim_simulated.csv
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

TYPES = ["CASH_OUT", "PAYMENT", "CASH_IN", "TRANSFER", "DEBIT"]
TYPE_P = [0.352, 0.338, 0.220, 0.084, 0.006]


def simulate(rows: int, fraud_rate: float = 0.0013, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    types = rng.choice(TYPES, rows, p=TYPE_P)

    # Diurnal legit pattern: few events in the small hours of each simulated day.
    hour_w = np.array([0.2] * 8 + [1.0] * 16)
    hour_w /= hour_w.sum()
    day = rng.integers(0, 31, rows)
    step = np.minimum(day * 24 + rng.choice(24, rows, p=hour_w) + 1, 743)

    fraud_prone = np.isin(types, ["TRANSFER", "CASH_OUT"])
    n_fraud = int(rows * fraud_rate)
    idx = rng.choice(np.flatnonzero(fraud_prone), n_fraud, replace=False)
    is_fraud = np.zeros(rows, dtype=np.int8)
    is_fraud[idx] = 1
    # Fraud is spread uniformly over the month and ignores the diurnal pattern.
    step[idx] = rng.integers(1, 744, n_fraud)

    amount = np.where(
        types == "PAYMENT", rng.lognormal(8.7, 1.0, rows),
        np.where(types == "DEBIT", rng.lognormal(7.5, 1.0, rows),
                 np.where(types == "CASH_IN", rng.lognormal(11.8, 1.1, rows),
                          rng.lognormal(11.9, 1.5, rows))))
    # Fraud empties accounts: large amounts that overlap the heavy tail of legit transfers.
    amount[idx] = np.clip(rng.lognormal(13.1, 1.1, n_fraud), 100, 1e7)

    # Origins are almost all unique (as in PaySim); a small returning population.
    orig_id = np.where(rng.random(rows) < 0.003, rng.integers(0, 20_000, rows), rng.integers(0, 10**9, rows))
    dest_pref = np.where(types == "PAYMENT", "M", "C")
    dest_id = np.where(types == "PAYMENT", rng.integers(0, 40_000, rows), rng.integers(0, 2_000_000, rows))

    df = pd.DataFrame(
        {
            "step": step,
            "type": types,
            "amount": amount.round(2),
            "nameOrig": ["C" + str(i) for i in orig_id],
            "nameDest": [p + str(i) for p, i in zip(dest_pref, dest_id)],
            "isFraud": is_fraud,
        }
    )
    return df.sort_values("step", kind="stable").reset_index(drop=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_500_000)
    ap.add_argument("--rate", type=float, default=0.0013)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="data/paysim_simulated.csv")
    a = ap.parse_args()
    d = simulate(a.rows, a.rate, a.seed)
    d.to_csv(a.out, index=False)
    print(f"wrote {a.out}: {len(d):,} rows, {int(d.isFraud.sum()):,} fraud ({100*d.isFraud.mean():.3f}%)")
