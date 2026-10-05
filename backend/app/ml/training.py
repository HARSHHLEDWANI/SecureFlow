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
from app.ml.datasets.synthetic import SyntheticDataset
from app.ml.features import FEATURE_COLUMNS

# Fixed hyperparameters used by the fast training path (skips grid search). These
# are a strong, previously-observed configuration for this synthetic dataset — good
# enough for tests/dev while avoiding the ~25–30s cross-validated grid search.
_FAST_PARAMS = {"n_estimators": 200, "max_depth": 16, "min_samples_leaf": 1}


def run_training(fast: bool = False) -> dict:
    """Train and persist the fraud models, returning the evaluation metrics.

    ``fast=True`` skips the cross-validated :class:`GridSearchCV` and trains a
    single RandomForest with fixed hyperparameters (:data:`_FAST_PARAMS`). This
    is used by the test fixtures so a bare ``pytest`` on a fresh clone still gets
    a genuinely trained model in a few seconds instead of ~30s. The full
    grid-search path (``fast=False``) is used by ``python -m app.ml.training`` at
    deploy/build time.
    """
    settings = get_settings()
    print("Generating synthetic UPI dataset...")
    df = SyntheticDataset().load()
    print(f"  rows={len(df)}  fraud={int(df['is_fraud'].sum())} "
          f"({100 * df['is_fraud'].mean():.1f}%)")

    X = df[FEATURE_COLUMNS].to_numpy()
    y = df["is_fraud"].to_numpy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    if fast:
        print(f"Fast path: training RandomForest with fixed params {_FAST_PARAMS}...")
        clf = RandomForestClassifier(
            random_state=42, class_weight="balanced", n_jobs=-1, **_FAST_PARAMS
        )
        clf.fit(X_train, y_train)
        best_params = dict(_FAST_PARAMS)
        cv_scores = np.array([0.0])  # not computed on the fast path
    else:
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
        best_params = grid.best_params_
        print(f"  best params: {best_params}")

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
        "best_params": best_params,
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
        "best_params": best_params,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "trained_at": bundle["trained_at"],
        "version": bundle["version"],
    }
    with open(settings.model_metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics_out, fh, indent=2)
    print(f"Saved metrics -> {settings.model_metrics_path}")
    return metrics_out


def main() -> None:
    run_training(fast=False)


if __name__ == "__main__":
    main()
