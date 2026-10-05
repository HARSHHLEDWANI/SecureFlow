"""Train/validation/test splitting.

A random split lets the *future* behaviour of an account leak into training (the
same account's later transactions train the model that scores its earlier ones).
The benchmark path therefore splits chronologically on ``time_step``; the random
split is kept only so the two can be compared in the metrics file.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

Split = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]


def chronological_split(
    df: pd.DataFrame, train_frac: float = 0.70, val_frac: float = 0.15
) -> Split:
    """Earliest ``train_frac`` -> train, next ``val_frac`` -> validation, rest -> test.

    Boundaries fall on whole ``time_step`` values: every row of a step lands in one
    split, so ``max(train.time_step) < min(val.time_step) <= max(val.time_step) <
    min(test.time_step)`` strictly. Fractions are therefore approximate when many
    rows share a step. Raises ``ValueError`` if a split would be empty.
    """
    if not 0 < train_frac < 1 or not 0 < val_frac < 1 or train_frac + val_frac >= 1:
        raise ValueError("train_frac and val_frac must be in (0,1) and sum to < 1")
    steps = df["time_step"].to_numpy()
    order = np.argsort(steps, kind="stable")
    sorted_steps = steps[order]
    n = len(df)
    train_end = sorted_steps[max(int(n * train_frac) - 1, 0)]
    val_end = sorted_steps[max(int(n * (train_frac + val_frac)) - 1, 0)]

    train = df[df["time_step"] <= train_end]
    val = df[(df["time_step"] > train_end) & (df["time_step"] <= val_end)]
    test = df[df["time_step"] > val_end]
    if min(len(train), len(val), len(test)) == 0:
        raise ValueError(
            "Chronological split produced an empty partition - not enough distinct "
            "time steps for the requested fractions."
        )
    return train.sort_values("time_step", kind="stable"), val.sort_values(
        "time_step", kind="stable"
    ), test.sort_values("time_step", kind="stable")


def random_split(
    df: pd.DataFrame, train_frac: float = 0.70, val_frac: float = 0.15, seed: int = 42
) -> Split:
    """Stratified random split with the same proportions (leaks time; comparison only)."""
    test_frac = 1.0 - train_frac - val_frac
    train, rest = train_test_split(
        df, train_size=train_frac, random_state=seed, stratify=df["is_fraud"]
    )
    val, test = train_test_split(
        rest,
        train_size=val_frac / (val_frac + test_frac),
        random_state=seed,
        stratify=rest["is_fraud"],
    )
    return train, val, test


def undersample_negatives(df: pd.DataFrame, max_ratio: int, seed: int = 42) -> pd.DataFrame:
    """Cap negatives at ``max_ratio`` x positives (train split only).

    Keeps every positive. Probabilities from a model fitted on the result are
    shifted upward; fit calibration on an *untouched* validation split to undo it.
    """
    pos = df[df["is_fraud"] == 1]
    neg = df[df["is_fraud"] == 0]
    cap = max_ratio * max(len(pos), 1)
    if len(neg) <= cap:
        return df
    kept = neg.sample(n=cap, random_state=seed)
    return pd.concat([pos, kept]).sort_values("time_step", kind="stable")
