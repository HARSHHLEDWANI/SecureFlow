"""Train the SecureFlow fraud models and write an honest metrics file.

Two kinds of run, because two different questions are asked of the data:

* ``--dataset paysim`` - the **benchmark**. A real payments dataset at its true base
  rate (~0.13%), split chronologically 70/15/15 on ``time_step``. Metrics from this run
  are the only ones that may be quoted as model performance. Writes
  ``benchmark_metrics_path`` / ``benchmark_model_path`` and leaves the live model alone
  (PaySim has no geo/device signal, so a model fitted on it would blind the UPI Lab).
* ``--dataset synthetic`` (default) - the **demo/Lab model**. Trained on the synthetic
  generator, written to ``model_path`` / ``model_metrics_path`` together with the frozen
  ``holdout`` and ``train_pool`` the feedback loop retrains against. Its metrics are
  flagged ``reportable: false``: on this data ``extract_features`` builds both the
  signals and the features, which is how it reached precision 1.000.

Pipeline: chronological split -> train-only negative undersampling -> RandomForest
(grid search on PR-AUC unless ``fast``) -> isotonic calibration and cost-optimal
thresholds on validation -> one-shot evaluation on the untouched test split, alongside
logistic-regression / gradient-boosting baselines and a random-split comparison.

Run from the ``backend`` directory::

    python -m app.ml.training --dataset paysim          # benchmark (needs PAYSIM_PATH)
    python -m app.ml.training                           # demo model (synthetic)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from typing import Any, Optional

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from app.config import get_settings
from app.ml.baselines import compare_models, fit_timed, make_baselines
from app.ml.bundle import FAST_PARAMS, build_bundle, evaluate_bundle, to_matrix
from app.ml.calibration import brier_before_after
from app.ml.datasets import get_dataset
from app.ml.evaluation import compute_metrics, feature_importance
from app.ml.features import FEATURE_COLUMNS
from app.ml.splits import chronological_split, random_split, undersample_negatives
from app.ml.thresholds import CostMatrix, sweep_probability_threshold

MODEL_VERSION = "3.0.0"

# Kept for callers that imported the old private name.
_FAST_PARAMS = FAST_PARAMS


def _split_summary(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(df)),
        "fraud": int(df["is_fraud"].sum()),
        "fraud_rate": round(float(df["is_fraud"].mean()), 6),
        "time_step_min": int(df["time_step"].min()),
        "time_step_max": int(df["time_step"].max()),
    }


def file_digest(path: str) -> str:
    """Short SHA-256 of a file - identifies the frozen holdout a metric was scored on."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def _quick_split_eval(
    train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, ratio: int, cost: CostMatrix
) -> dict[str, Any]:
    """Raw RandomForest on one split scheme - only to compare split schemes fairly."""
    train = undersample_negatives(train, ratio)
    clf = RandomForestClassifier(random_state=42, class_weight="balanced", n_jobs=-1, **FAST_PARAMS)
    clf.fit(to_matrix(train), train["is_fraud"].to_numpy())
    thr = sweep_probability_threshold(
        val["is_fraud"].to_numpy(), clf.predict_proba(to_matrix(val))[:, 1], cost
    )["threshold"]
    proba = clf.predict_proba(to_matrix(test))[:, 1]
    y = test["is_fraud"].to_numpy()
    m = compute_metrics(y, (proba >= thr).astype(int), proba, threshold=thr)
    return {k: m[k] for k in (
        "pr_auc", "auc_roc", "precision", "recall", "f1", "precision_at_k",
        "recall_at_fpr", "confusion_matrix", "support",
    )}


def freeze_artifacts(train_fit: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame) -> str:
    """Write the frozen holdout (test split) and train pool (train + val); return the hash.

    Every later candidate model - and the live model - is scored on exactly these holdout
    rows, and a candidate trains only on the pool. Nothing is regenerated.
    """
    s = get_settings()
    for path in (s.holdout_path, s.train_pool_path):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    test.to_parquet(s.holdout_path, index=False)
    pool = pd.concat(
        [train_fit.assign(split="train"), val.assign(split="val")], ignore_index=True
    )
    pool.to_parquet(s.train_pool_path, index=False)
    return file_digest(s.holdout_path)


def run_training(
    fast: bool = False,
    dataset: str = "synthetic",
    split: str = "chronological",
    write_artifacts: bool = True,
    adapter: Optional[Any] = None,
) -> dict[str, Any]:
    """Train, evaluate and (optionally) persist; returns the metrics dict.

    ``fast=True`` skips the cross-validated grid search (fixed hyperparameters) so test
    fixtures train in seconds. ``split="random"`` makes the random split the primary one
    (leaky; for comparison only). ``adapter`` overrides the dataset lookup (tests).
    """
    settings = get_settings()
    cost = CostMatrix.from_settings()
    ratio = settings.train_negative_ratio
    adapter = adapter or get_dataset(dataset)
    is_benchmark = bool(adapter.is_benchmark)

    print(f"Loading dataset '{adapter.name}'...")
    df = adapter.load()
    print(f"  rows={len(df)}  fraud={int(df['is_fraud'].sum())} "
          f"({100 * df['is_fraud'].mean():.3f}%)")

    split_fn = chronological_split if split == "chronological" else random_split
    train, val, test = split_fn(df)
    train_fit = undersample_negatives(train, ratio)
    print(f"  split={split}: train={len(train)} (fit on {len(train_fit)}) "
          f"val={len(val)} test={len(test)}")

    live = not is_benchmark
    version = MODEL_VERSION if live else f"{MODEL_VERSION}-{adapter.name}"
    print("Fitting RandomForest + IsolationForest, calibrating, sweeping thresholds...")
    bundle, report = build_bundle(
        train_fit, val, fast=fast, version=version, dataset=adapter.name, cost=cost
    )

    X_train, y_train = to_matrix(train_fit), train_fit["is_fraud"].to_numpy()
    X_val, y_val = to_matrix(val), val["is_fraud"].to_numpy()
    X_test, y_test = to_matrix(test), test["is_fraud"].to_numpy()

    print("Fitting baselines (logistic regression, gradient boosting)...")
    fit_seconds: dict[str, float] = {"random_forest": report["fit_seconds"]}
    models = {"random_forest": bundle["base_model"]}
    for name, model in make_baselines().items():
        models[name] = fit_timed(name, model, X_train, y_train, fit_seconds)
    comparison = compare_models(models, X_val, y_val, X_test, y_test, fit_seconds)

    test_metrics = evaluate_bundle(bundle, test)
    calib = dict(report["calibration"])
    if calib.get("applied"):
        calib["brier_test"] = brier_before_after(
            bundle["base_model"], bundle["model"], X_test, y_test
        )

    print("Comparing split schemes (raw RandomForest)...")
    alt_name = "random" if split == "chronological" else "chronological"
    alt_fn = random_split if split == "chronological" else chronological_split
    split_comparison = {
        split: _quick_split_eval(train, val, test, ratio, cost),
        alt_name: _quick_split_eval(*alt_fn(df), ratio, cost),
    }

    metrics_out: dict[str, Any] = {
        **test_metrics,
        "dataset": {
            "name": adapter.name,
            "is_benchmark": is_benchmark,
            "reportable": is_benchmark,
            **_split_summary(df),
        },
        "metric_source": adapter.name,
        "reportable": is_benchmark,
        "split": {
            "strategy": split,
            "train": _split_summary(train),
            "train_fit": _split_summary(train_fit),
            "validation": _split_summary(val),
            "test": _split_summary(test),
            "train_negative_ratio_cap": ratio,
        },
        "calibration": calib,
        "operating_threshold": report["operating_threshold"],
        "risk_thresholds": report["risk_thresholds"],
        "threshold_sweep": report["threshold_sweep"],
        "cost_matrix": report["cost_matrix"],
        "model_comparison": comparison,
        "split_comparison": split_comparison,
        "feature_importance": feature_importance(bundle["base_model"], FEATURE_COLUMNS),
        "best_params": report["best_params"],
        "n_train": int(len(train_fit)),
        "n_test": int(len(test)),
        "trained_at": bundle["trained_at"],
        "version": version,
    }

    print("\n-- Test metrics (headline: PR-AUC) --")
    print(f"  pr_auc   : {test_metrics['pr_auc']}")
    print(f"  precision: {test_metrics['precision']}  recall: {test_metrics['recall']}")
    print(f"  confusion: {test_metrics['confusion_matrix']}")
    print(f"  risk cutoffs (cost-optimal): {report['risk_thresholds']['low_max']}/"
          f"{report['risk_thresholds']['medium_max']}")

    if write_artifacts:
        if live:
            model_path, metrics_path = settings.model_path, settings.model_metrics_path
            metrics_out["holdout_hash"] = freeze_artifacts(train_fit, val, test)
        else:
            model_path = settings.benchmark_model_path
            metrics_path = settings.benchmark_metrics_path
        for path in (model_path, metrics_path):
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        joblib.dump(bundle, model_path)
        with open(metrics_path, "w", encoding="utf-8") as fh:
            json.dump(metrics_out, fh, indent=2)
        print(f"\nSaved model   -> {model_path}\nSaved metrics -> {metrics_path}")
    return metrics_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Train SecureFlow fraud models.")
    parser.add_argument("--dataset", choices=["synthetic", "paysim"], default="synthetic")
    parser.add_argument("--split", choices=["chronological", "random"], default="chronological")
    parser.add_argument("--fast", action="store_true", help="skip grid search (fixed params)")
    args = parser.parse_args()
    run_training(fast=args.fast, dataset=args.dataset, split=args.split)


if __name__ == "__main__":
    main()
