"""Generate ``docs/MODEL_CARD.md`` from the metrics JSON files (never hand-typed).

    python -m app.ml.model_card [--live data/model_metrics.json]
                                [--benchmark data/benchmark_metrics.json]
                                [--out ../docs/MODEL_CARD.md]

The card separates two sources of numbers and says so on every table: the PaySim
benchmark (the only metrics that may be quoted as performance) and the synthetic demo
model (reported for transparency, flagged not-reportable).
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Optional

from app.config import get_settings


def _load(path: Optional[str]) -> Optional[dict[str, Any]]:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _pct(x: float) -> str:
    return f"{100 * x:.3f}%"


def _metrics_section(m: dict[str, Any], title: str) -> str:
    cm = m["confusion_matrix"]
    split = m["split"]
    parts = [f"### {title}", ""]
    parts.append(
        f"Source: **{m['metric_source']}** - "
        + ("reportable benchmark." if m["reportable"] else "**not reportable as model performance** (see Limitations).")
    )
    parts += ["", "**Splits** (" + split["strategy"] + f"; train negatives capped at {split['train_negative_ratio_cap']}:1, train only)", ""]
    parts.append(_table(
        ["split", "rows", "fraud", "fraud rate", "time_step range"],
        [[name, f"{s['rows']:,}", f"{s['fraud']:,}", _pct(s["fraud_rate"]),
          f"{s['time_step_min']}-{s['time_step_max']}"]
         for name, s in (("train (all)", split["train"]), ("train (fit)", split["train_fit"]),
                         ("validation", split["validation"]), ("test", split["test"]))],
    ))
    parts += ["", f"**Headline (test split): PR-AUC = {m['headline']['value']}** "
              f"(fraud base rate {_pct(m['fraud_rate'])}; a no-skill model scores ~{m['fraud_rate']:.4f}).", ""]
    parts.append(_table(["metric", "value"], [
        *[[f"precision@{k}", v] for k, v in m["precision_at_k"].items()],
        *[[f"recall @ FPR {k}", v] for k, v in m["recall_at_fpr"].items()],
        ["Brier score", m["brier"]],
    ]))
    parts += ["", f"At the cost-optimal operating threshold p >= {m['threshold']}: "
              f"precision {m['precision']}, recall {m['recall']}, F1 {m['f1']}.", ""]
    parts.append(_table(["", "predicted legit", "predicted fraud"],
                        [["actual legit", f"{cm[0][0]:,}", f"{cm[0][1]:,}"],
                         ["actual fraud", f"{cm[1][0]:,}", f"{cm[1][1]:,}"]]))
    parts += ["", f"Reference only (not headline at this base rate): accuracy {m['accuracy']}, AUC-ROC {m['auc_roc']}.", ""]

    parts += ["**Reliability** (10 equal-width bins, test split, calibrated probabilities)", ""]
    parts.append(_table(["bin", "count", "mean predicted", "observed fraud rate"],
                        [[r["bin"], f"{r['count']:,}", r["mean_predicted"], r["observed_rate"]]
                         for r in m["reliability"]]))

    c = m["calibration"]
    parts += ["", "**Calibration** (isotonic, fitted on the validation split)", ""]
    if c.get("applied"):
        b = c["brier_test"]
        parts.append(f"Brier on the test split: before **{b['before']}** -> after **{b['after']}** "
                     f"(fitted on {c['n_validation']:,} validation rows, {c['n_validation_positives']} positives).")
    else:
        parts.append(f"Not applied: {c.get('reason')}.")

    cm_ = m["cost_matrix"]
    rt = m["risk_thresholds"]
    parts += ["", "**Cost matrix and thresholds**", "",
              _table(["", "legitimate payment", "fraudulent payment"], [
                  ["ALLOWED (LOW)", 0, cm_["false_negative"]],
                  ["STEP_UP (MEDIUM)", cm_["stepup_legit"], f"{cm_['false_negative']} x {cm_['stepup_fraud_leak']} leak"],
                  ["BLOCKED (HIGH)", cm_["false_positive"], 0]]),
              "",
              f"Cost-optimal risk cutoffs on validation ({rt['n_validation']:,} rows, exhaustive over 5,050 pairs): "
              f"**LOW <= {rt['low_max']}, MEDIUM <= {rt['medium_max']}**, expected cost {rt['expected_cost']} "
              f"vs {rt['default_expected_cost']} for the legacy 30/70. Cutoffs are applied at runtime only with "
              f"`USE_LEARNED_THRESHOLDS=true` or explicit `RISK_LOW_MAX`/`RISK_MEDIUM_MAX`; the full sweep is in the metrics JSON.",
              ""]

    parts += ["**Model comparison** (raw, uncalibrated scores; same splits)", ""]
    rows = []
    for r in m["model_comparison"]:
        rows.append([r["model"] + (" *(served)*" if r["model"] == "random_forest" else ""),
                     r["validation"]["pr_auc"], r["test"]["pr_auc"],
                     r["test"]["precision_at_k"].get("100"), r["test"]["recall_at_fpr"].get("0.01"),
                     r["test"]["brier"], r["fit_seconds"], "yes" if r["best_validation_pr_auc"] else ""])
    parts.append(_table(["model", "val PR-AUC", "test PR-AUC", "test p@100", "test recall@FPR 1%",
                         "test Brier", "fit s", "best on val"], rows))

    parts += ["", "**Split comparison** (raw RandomForest, identical settings)", ""]
    parts.append(_table(["split", "PR-AUC", "AUC-ROC", "precision", "recall", "false positives"],
                        [[name, s["pr_auc"], s["auc_roc"], s["precision"], s["recall"], s["confusion_matrix"][0][1]]
                         for name, s in m["split_comparison"].items()]))
    parts += ["", f"Model version `{m['version']}`, trained {m['trained_at']}, hyperparameters `{m['best_params']}`.", ""]
    return "\n".join(parts)


def render(live: Optional[dict[str, Any]], bench: Optional[dict[str, Any]]) -> str:
    out = ["# SecureFlow fraud model card", "",
           "_Generated by `python -m app.ml.model_card` from the metrics JSON files. Do not edit by hand._", "",
           "## Intended use", "",
           "A transaction-level fraud scorer for a UPI-style payments console. It outputs a fraud "
           "probability and an anomaly score that the rule-based risk engine (`core/risk_engine.py`) "
           "combines with velocity, geo, device, amount and time signals into a 0-100 risk score and a "
           "tiered action (ALLOWED / STEP_UP / BLOCKED). It is a portfolio/research system; it has not "
           "been validated against production UPI traffic.", "",
           "## Datasets and provenance", "",
           _table(["dataset", "role", "provenance"], [
               ["PaySim (`ealaxi/paysim1`)", "**benchmark** - the only source of reportable metrics",
                "Simulated mobile-money month, ~6.3M rows, ~0.13% fraud, hourly `step`. Read from a local CSV "
                "(`PAYSIM_PATH`); never downloaded by the code. Column mapping: `app/ml/datasets/paysim.py`."],
               ["Synthetic generator", "seeds the live demo model and the UPI Lab; **never reported**",
                "`app/ml/datasets/synthetic.py`: 13% fraud from four latent archetypes, featurised by the same "
                "`extract_features` that builds its signals."]]), ""]
    out += ["## Results", ""]
    if bench is not None:
        out += [_metrics_section(bench, "PaySim benchmark (reportable)")]
    else:
        out += ["### PaySim benchmark (reportable)", "",
                "**Not yet run.** No PaySim CSV was available when this card was generated, so there is no "
                "reportable performance number yet. Place the CSV locally and run:", "",
                "```", "set PAYSIM_PATH=backend/data/paysim.csv   # optionally PAYSIM_MAX_ROWS=1000000",
                "python -m app.ml.training --dataset paysim", "python -m app.ml.model_card", "```", ""]
    if live is not None:
        out += [_metrics_section(live, "Demo / UPI Lab model (synthetic data - not reportable)")]
    out += ["## Limitations", "",
            "- **Which numbers come from which data.** Every number in the *Demo / UPI Lab model* section "
            "is measured on synthetic data and says nothing about real-world fraud detection: the generator "
            "and the featuriser share `extract_features`, fraud is ~100x the real base rate, and there is no "
            "real temporal structure (the chronological and random splits score the same, as expected). It "
            "exists to drive the Lab. Numbers in the *PaySim benchmark* section (when present) are the only "
            "performance claims.",
            "- **PaySim is a simulation**, not production traffic; its fraud is TRANSFER/CASH_OUT only, so "
            "`txn_type` alone removes most legitimate volume.",
            "- **Degenerate history features on PaySim.** Almost every `nameOrig` appears once, so velocity, "
            "`is_new_beneficiary`, `minutes_since_last` and `amount_zscore` are mostly neutral/constant. "
            "`geo_distance_km`, `is_new_device` and `is_weekend` have no PaySim counterpart and are constant 0. "
            "The benchmark therefore measures amount/type/hour signal, not the full UPI feature set.",
            "- **The benchmark model is not the served model.** The served model is trained on synthetic data "
            "so the Lab's geo/device/velocity scenarios behave; the PaySim model is evaluated and saved "
            "separately (`benchmark_model_path`).",
            "- **Train-only undersampling** (negatives capped, default 50:1) shifts raw probabilities; isotonic "
            "calibration on the untouched validation split corrects it, but calibration quality in the tail "
            "depends on validation positives (skipped below 20).",
            "- **Cost matrix is an assumption** (1:50 FP:FN, step-up friction 0.1, 20% step-up leak), not "
            "measured business cost. Learned risk cutoffs are tuned on the composite score of the model they "
            "ship with and are opt-in at runtime.",
            "- **Model choice.** The RandomForest is served for explainability (feature importances) and "
            "single-row latency; the comparison table reports whether a baseline beats it on validation PR-AUC.",
            "- **Feedback loop.** Corrections are retrained into a versioned candidate scored on the frozen "
            "holdout; the holdout is small and synthetic for the demo model, so the regression guard is a "
            "smoke check, not statistical proof.", ""]
    return "\n".join(out)


def main() -> None:
    s = get_settings()
    parser = argparse.ArgumentParser(description="Generate docs/MODEL_CARD.md")
    parser.add_argument("--live", default=s.model_metrics_path)
    parser.add_argument("--benchmark", default=s.benchmark_metrics_path)
    parser.add_argument("--out", default=os.path.join("..", "docs", "MODEL_CARD.md"))
    args = parser.parse_args()
    text = render(_load(args.live), _load(args.benchmark))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
