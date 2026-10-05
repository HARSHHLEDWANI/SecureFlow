"""Chronological splitting and imbalance-aware metrics, checked on hand-computed cases."""
import numpy as np
import pandas as pd
import pytest

from app.ml.evaluation import (
    brier,
    compute_metrics,
    pr_auc,
    precision_at_k,
    recall_at_fpr,
    reliability_table,
)
from app.ml.splits import chronological_split, random_split, undersample_negatives


def _frame(n=1000, per_step=5, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "x": rng.normal(size=n),
            "is_fraud": (rng.random(n) < 0.1).astype(int),
            "time_step": np.arange(n) // per_step,
        }
    )


# ── Splits ──────────────────────────────────────────────────────────────────────


def test_chronological_split_never_leaks_a_later_step_into_train():
    # Shuffle row order: the split must depend on time_step, not on row position.
    df = _frame().sample(frac=1.0, random_state=3).reset_index(drop=True)
    train, val, test = chronological_split(df)
    assert train["time_step"].max() < val["time_step"].min()
    assert val["time_step"].max() < test["time_step"].min()
    assert len(train) + len(val) + len(test) == len(df)
    assert abs(len(train) / len(df) - 0.70) < 0.02
    assert abs(len(val) / len(df) - 0.15) < 0.02


def test_chronological_split_keeps_a_step_in_one_partition():
    df = _frame(per_step=50)  # large steps straddle the nominal 70/85% cut
    train, val, test = chronological_split(df)
    for a, b in [(train, val), (val, test), (train, test)]:
        assert set(a["time_step"]).isdisjoint(set(b["time_step"]))


def test_chronological_split_rejects_degenerate_input():
    df = _frame()
    df["time_step"] = 1  # one step -> cannot split by time
    with pytest.raises(ValueError):
        chronological_split(df)
    with pytest.raises(ValueError):
        chronological_split(_frame(), train_frac=0.9, val_frac=0.2)


def test_random_split_differs_from_chronological_and_leaks_time():
    df = _frame()
    train, _, test = random_split(df)
    assert train["time_step"].max() > test["time_step"].min()  # the leak the flag exists to show


def test_undersample_keeps_all_positives_and_caps_ratio():
    df = _frame(n=5000)
    out = undersample_negatives(df, max_ratio=3)
    assert out["is_fraud"].sum() == df["is_fraud"].sum()
    assert (out["is_fraud"] == 0).sum() == 3 * df["is_fraud"].sum()
    assert undersample_negatives(df, max_ratio=10_000) is df  # nothing to cap


# ── Metrics ─────────────────────────────────────────────────────────────────────


def test_pr_auc_on_a_known_toy_case():
    # Ranked: .8(1) .4(0) .35(1) .1(0). Precision at the two positives: 1/1 and 2/3,
    # each worth 0.5 recall -> AP = 0.5*1 + 0.5*(2/3) = 5/6.
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.4, 0.35, 0.8])
    assert pr_auc(y, p) == pytest.approx(5 / 6)


def test_pr_auc_perfect_and_single_class():
    y = np.array([0, 0, 1, 1])
    assert pr_auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert np.isnan(pr_auc(np.zeros(4), np.array([0.1, 0.2, 0.3, 0.4])))


def test_precision_at_k():
    y = np.array([1, 0, 1, 0, 0, 1])
    p = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.1])
    assert precision_at_k(y, p, 2) == 0.5      # top2 = {1,0}
    assert precision_at_k(y, p, 3) == pytest.approx(2 / 3)
    assert precision_at_k(y, p, 1000) == 0.5   # clamped to n=6: 3 frauds / 6


def test_recall_at_fixed_false_positive_rate():
    # 10 legit, 4 fraud. At FPR<=0.1 we may allow exactly 1 false positive.
    y = np.array([0] * 10 + [1] * 4)
    p = np.array([0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.9,   # one legit at .9
                  0.95, 0.92, 0.5, 0.2])
    # Sorted fraud scores .95,.92 beat the .9 legit; .5 (0.5>0.45) needs 1 FP allowed.
    assert recall_at_fpr(y, p, 0.0) == 0.5
    assert recall_at_fpr(y, p, 0.1) == 0.75


def test_brier_and_reliability_on_known_values():
    y = np.array([0, 1, 1, 0])
    p = np.array([0.0, 1.0, 0.5, 0.5])
    assert brier(y, p) == pytest.approx((0 + 0 + 0.25 + 0.25) / 4)
    table = reliability_table(y, p, bins=10)
    assert len(table) == 10 and sum(r["count"] for r in table) == 4
    top = table[-1]
    assert top["count"] == 1 and top["observed_rate"] == 1.0  # p=1.0 lands in the last bin


def test_compute_metrics_headline_is_pr_auc_and_not_accuracy():
    y = np.array([0] * 98 + [1] * 2)
    p = np.linspace(0, 1, 100)
    m = compute_metrics(y, (p > 0.5).astype(int), p, threshold=0.5)
    assert m["headline"]["metric"] == "pr_auc" and m["headline"]["value"] == m["pr_auc"]
    for key in ("precision_at_k", "recall_at_fpr", "brier", "reliability", "auc_roc", "accuracy"):
        assert key in m
    assert set(m["precision_at_k"]) == {"100", "500", "1000"}
    assert set(m["recall_at_fpr"]) == {"0.001", "0.005", "0.01"}
    assert m["confusion_matrix"][0][1] > 0  # this toy classifier makes false positives
