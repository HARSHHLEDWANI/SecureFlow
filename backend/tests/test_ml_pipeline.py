"""Thresholds, calibration, training artifacts and the benchmark path."""
import itertools
import json
import os

import numpy as np
import pandas as pd
import pytest

from app.config import get_settings
from app.ml import thresholds
from app.ml.calibration import fit_isotonic
from app.ml.thresholds import (
    CostMatrix,
    sweep_probability_threshold,
    sweep_tier_thresholds,
    tier_cost,
)

COST = CostMatrix(false_positive=1.0, false_negative=50.0, stepup_legit=0.1, stepup_fraud_leak=0.2)


def _brute_force_tiers(y, scores, cost):
    legit = np.bincount(scores[y == 0], minlength=101)
    fraud = np.bincount(scores[y == 1], minlength=101)
    return min(
        tier_cost(legit, fraud, low, med, cost)
        for low, med in itertools.combinations(range(101), 2)
    )


# ── Threshold sweeps ────────────────────────────────────────────────────────────


def test_tier_sweep_finds_the_known_optimum_on_a_synthetic_cost_surface():
    rng = np.random.default_rng(0)
    # Legit cluster 5-25, ambiguous overlap 40-60 (mixed), fraud cluster 80-100.
    legit = np.concatenate([rng.integers(5, 26, 800), rng.integers(40, 61, 60)])
    fraud = np.concatenate([rng.integers(80, 101, 90), rng.integers(40, 61, 20)])
    y = np.concatenate([np.zeros(len(legit), int), np.ones(len(fraud), int)])
    scores = np.concatenate([legit, fraud])

    out = sweep_tier_thresholds(y, scores, COST)
    assert out["expected_cost"] == pytest.approx(_brute_force_tiers(y, scores, COST), abs=1e-3)
    # At 1:50 the overlap band is cheaper to block than to allow, so the optimum sits at
    # its lower edge: it still allows the whole clean legit cluster and blocks the fraud.
    assert 25 <= out["low_max"] < 60 and out["medium_max"] < 80
    assert out["expected_cost"] <= out["default_expected_cost"]
    assert len(out["sweep"]) == 100 * 101 // 2  # exhaustive over 0 <= low < medium <= 100


def test_tier_sweep_ties_go_to_the_legacy_cutoffs():
    # Perfectly separated and nothing scores near the cutoffs: every pair in a wide
    # region costs 0, so the result must be the zero-cost pair closest to (30, 70).
    y = np.array([0] * 50 + [1] * 50)
    scores = np.array([2] * 50 + [98] * 50)
    out = sweep_tier_thresholds(y, scores, COST)
    assert out["expected_cost"] == 0.0
    assert (out["low_max"], out["medium_max"]) == (30, 70)


def test_probability_threshold_matches_bruteforce_and_theory():
    rng = np.random.default_rng(1)
    p = rng.random(200_000) ** 3          # skewed toward 0 like a fraud score
    y = (rng.random(len(p)) < p).astype(int)   # perfectly calibrated by construction
    out = sweep_probability_threshold(y, p, COST)

    grid = np.linspace(0, 1, 2001)
    brute = min(
        COST.false_positive * ((p >= t) & (y == 0)).sum() + COST.false_negative * ((p < t) & (y == 1)).sum()
        for t in grid
    )
    assert out["expected_cost"] <= brute + 1e-6
    # For calibrated scores the optimal cut is fp / (fp + fn) = 1/51.
    assert out["threshold"] == pytest.approx(1 / 51, abs=0.01)
    assert out["expected_cost"] < out["flag_nothing_cost"]


def test_risk_threshold_loader_precedence(tmp_path, monkeypatch):
    settings = get_settings()
    metrics = tmp_path / "m.json"
    metrics.write_text(json.dumps({"risk_thresholds": {"low_max": 12, "medium_max": 44}}))
    monkeypatch.setattr(settings, "model_metrics_path", str(metrics))
    monkeypatch.setattr(settings, "use_learned_thresholds", False)
    monkeypatch.setattr(settings, "risk_low_max", None)
    monkeypatch.setattr(settings, "risk_medium_max", None)
    thresholds.reset_threshold_cache()

    assert thresholds.load_risk_thresholds() == (30, 70)        # learned values are opt-in
    monkeypatch.setattr(settings, "use_learned_thresholds", True)
    thresholds.reset_threshold_cache()
    assert thresholds.load_risk_thresholds() == (12, 44)        # then learned
    monkeypatch.setattr(settings, "risk_medium_max", 60)
    assert thresholds.load_risk_thresholds() == (12, 60)        # explicit config wins

    monkeypatch.setattr(settings, "risk_medium_max", None)
    metrics.write_text("not json")                               # corrupt -> fallback, no crash
    thresholds.reset_threshold_cache()
    assert thresholds.load_risk_thresholds() == (30, 70)
    monkeypatch.setattr(settings, "model_metrics_path", str(tmp_path / "missing.json"))
    thresholds.reset_threshold_cache()
    assert thresholds.load_risk_thresholds() == (30, 70)
    thresholds.reset_threshold_cache()


def test_risk_engine_uses_loaded_thresholds(monkeypatch):
    from app.core import risk_engine
    from app.database import RiskTier

    monkeypatch.setattr(risk_engine, "load_risk_thresholds", lambda: (5, 10))
    assert risk_engine._tier_and_status(7)[0] == RiskTier.MEDIUM
    assert risk_engine._tier_and_status(11)[0] == RiskTier.HIGH
    assert risk_engine.tier_and_status_for(30, 30, 70)[0] == RiskTier.LOW


# ── Calibration ─────────────────────────────────────────────────────────────────


def test_isotonic_calibration_fixes_an_overconfident_model_and_skips_tiny_validation():
    from sklearn.ensemble import RandomForestClassifier

    rng = np.random.default_rng(2)
    X = rng.normal(size=(6000, 4))
    y = (rng.random(6000) < 1 / (1 + np.exp(-(X[:, 0] * 1.2 - 2)))).astype(int)
    clf = RandomForestClassifier(n_estimators=50, class_weight="balanced", random_state=0)
    clf.fit(X[:3000], y[:3000])

    calibrated, info = fit_isotonic(clf, X[3000:4500], y[3000:4500])
    assert info["applied"] is True
    from app.ml.evaluation import brier

    raw_b = brier(y[4500:], clf.predict_proba(X[4500:])[:, 1])
    cal_b = brier(y[4500:], calibrated.predict_proba(X[4500:])[:, 1])
    assert cal_b < raw_b  # balanced RF is overconfident; isotonic on validation repairs it

    same, info2 = fit_isotonic(clf, X[:50], np.zeros(50, int))
    assert same is clf and info2["applied"] is False


# ── The live (demo) model's metrics file ────────────────────────────────────────


def test_demo_training_writes_honest_and_complete_metrics(tmp_path, monkeypatch):
    """Train into a temp dir: other tests promote candidates over the shared live files."""
    from app.ml.training import run_training

    settings = get_settings()
    for name in ("model_path", "model_metrics_path", "holdout_path", "train_pool_path"):
        monkeypatch.setattr(settings, name, str(tmp_path / name))
    run_training(fast=True)

    with open(settings.model_metrics_path, encoding="utf-8") as fh:
        m = json.load(fh)
    assert m["headline"]["metric"] == "pr_auc"
    assert m["metric_source"] == "synthetic" and m["reportable"] is False
    assert m["split"]["strategy"] == "chronological"
    assert m["calibration"]["applied"] is True
    assert {"before", "after"} <= set(m["calibration"]["brier_test"])
    assert {"low_max", "medium_max", "expected_cost", "default_expected_cost"} <= set(m["risk_thresholds"])
    assert len(m["threshold_sweep"]) == 5050 and m["cost_matrix"]["false_negative"] == 50.0
    assert {r["model"] for r in m["model_comparison"]} == {
        "random_forest", "logistic_regression", "hist_gradient_boosting"
    }
    assert {"chronological", "random"} == set(m["split_comparison"])

    pool = pd.read_parquet(settings.train_pool_path)
    holdout = pd.read_parquet(settings.holdout_path)
    assert set(pool["split"]) == {"train", "val"}
    # Holdout is strictly later than everything the pool trained or calibrated on.
    assert holdout["time_step"].min() > pool["time_step"].max()
    from app.ml.training import file_digest

    assert m["holdout_hash"] == file_digest(settings.holdout_path)


# ── Benchmark path (PaySim-shaped data, not real PaySim) ────────────────────────


def _fake_paysim(path, n=24_000, seed=3):
    rng = np.random.default_rng(seed)
    types = rng.choice(["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT"], n, p=[0.5, 0.2, 0.25, 0.05])
    fraud_prone = np.isin(types, ["TRANSFER", "CASH_OUT"])
    is_fraud = (fraud_prone & (rng.random(n) < 0.06)).astype(int)
    # Fraud skews to large amounts but overlaps heavily with big legitimate transfers.
    amount = np.where(is_fraud == 1, rng.lognormal(10.5, 1.0, n), rng.lognormal(9.0, 1.4, n))
    df = pd.DataFrame(
        {
            "step": np.sort(rng.integers(1, 700, n)),
            "type": types,
            "amount": amount,
            "nameOrig": [f"C{i}" for i in rng.integers(0, 6000, n)],
            "nameDest": [f"C{i}" for i in rng.integers(0, 900, n)],
            "isFraud": is_fraud,
        }
    )
    df.to_csv(path, index=False)


def test_paysim_benchmark_run_writes_benchmark_artifacts_and_leaves_live_model_alone(
    tmp_path, monkeypatch
):
    from app.ml.training import run_training

    settings = get_settings()
    csv = tmp_path / "paysim.csv"
    _fake_paysim(csv)
    monkeypatch.setattr(settings, "paysim_path", str(csv))
    monkeypatch.setattr(settings, "benchmark_model_path", str(tmp_path / "bench.joblib"))
    monkeypatch.setattr(settings, "benchmark_metrics_path", str(tmp_path / "bench.json"))
    live_before = open(settings.model_metrics_path, "rb").read()
    holdout_before = open(settings.holdout_path, "rb").read()

    m = run_training(fast=True, dataset="paysim")

    assert m["headline"]["metric"] == "pr_auc" and m["reportable"] is True
    assert m["metric_source"] == "paysim" and m["version"].endswith("-paysim")
    assert m["precision"] < 1.0 and m["confusion_matrix"][0][1] > 0  # real false positives
    s = m["split"]
    assert s["train"]["time_step_max"] < s["validation"]["time_step_min"]
    assert s["validation"]["time_step_max"] < s["test"]["time_step_min"]
    assert os.path.exists(settings.benchmark_metrics_path)
    assert json.load(open(settings.benchmark_metrics_path))["metric_source"] == "paysim"
    # The Lab's live model, metrics and frozen holdout are untouched by a benchmark run.
    assert open(settings.model_metrics_path, "rb").read() == live_before
    assert open(settings.holdout_path, "rb").read() == holdout_before
