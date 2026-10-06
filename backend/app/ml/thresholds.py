"""Cost-based decision thresholds.

``LOW_MAX = 30`` / ``MEDIUM_MAX = 70`` were picked by hand. Here they are chosen by
sweeping every candidate pair against an explicit cost matrix on the *validation*
split and keeping the one with the lowest expected cost.

Cost matrix (per transaction, configurable in settings; default 1:50 FP:FN)::

                       legitimate payment          fraudulent payment
    ALLOWED (LOW)      0                           cost_false_negative        (50)
    STEP_UP (MEDIUM)   cost_stepup_legit   (0.1)   cost_false_negative x leak (50 x 0.2)
    BLOCKED (HIGH)     cost_false_positive (1)     0

``stepup_fraud_leak`` is the share of step-up frauds that still get through (an OTP
stops account takeover but not a victim who authorises the payment themselves).

The risk score is an integer 0-100, so the sweep is exhaustive over ``0 <= low <
medium <= 100`` (5,050 pairs) via cumulative histograms - no sampling.

For a calibrated probability the cost-optimal binary cut is ``fp / (fp + fn)``
(= 1/51 ~ 0.0196 at 1:50); :func:`sweep_probability_threshold` finds it empirically.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from app.config import get_settings

# Fallbacks used when no learned thresholds are available (the original constants).
DEFAULT_LOW_MAX = 30
DEFAULT_MEDIUM_MAX = 70


@dataclass(frozen=True)
class CostMatrix:
    false_positive: float = 1.0
    false_negative: float = 50.0
    stepup_legit: float = 0.1
    stepup_fraud_leak: float = 0.2

    @classmethod
    def from_settings(cls) -> "CostMatrix":
        s = get_settings()
        return cls(
            false_positive=s.cost_false_positive,
            false_negative=s.cost_false_negative,
            stepup_legit=s.cost_stepup_legit,
            stepup_fraud_leak=s.stepup_fraud_leak,
        )

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def sweep_probability_threshold(
    y_true: np.ndarray, proba: np.ndarray, cost: CostMatrix, max_candidates: int = 200_000
) -> dict[str, Any]:
    """Pick the probability cutoff (flag fraud if ``p >= t``) minimising expected cost."""
    y_true = np.asarray(y_true)
    proba = np.asarray(proba, dtype=float)
    legit = np.sort(proba[y_true == 0])
    fraud = np.sort(proba[y_true == 1])
    # Every distinct score is a candidate cut (exact optimum); only a huge, almost
    # all-distinct score set falls back to a dense quantile grid.
    distinct = np.unique(proba)
    if len(distinct) > max_candidates:
        distinct = np.unique(np.quantile(proba, np.linspace(0.0, 1.0, max_candidates)))
    candidates = np.concatenate([distinct, [np.nextafter(proba.max(), 2.0)]])

    fp = len(legit) - np.searchsorted(legit, candidates, side="left")   # legit with p >= t
    fn = np.searchsorted(fraud, candidates, side="left")                # fraud with p < t
    total = cost.false_positive * fp + cost.false_negative * fn
    # Among equal-cost cutoffs prefer the highest (flags fewer customers).
    best = len(total) - 1 - int(np.argmin(total[::-1]))
    stride = max(len(candidates) // 200, 1)
    return {
        "threshold": float(candidates[best]),
        "expected_cost": float(total[best]),
        "cost_per_txn": float(total[best] / len(y_true)),
        "false_positives": int(fp[best]),
        "false_negatives": int(fn[best]),
        "flag_nothing_cost": float(cost.false_negative * len(fraud)),
        "sweep": [
            [round(float(candidates[i]), 6), float(total[i])]
            for i in range(0, len(candidates), stride)
        ],
    }


def tier_cost(
    legit_hist: np.ndarray, fraud_hist: np.ndarray, low: int, medium: int, cost: CostMatrix
) -> float:
    """Expected total cost of one ``(low, medium)`` pair, from per-score histograms."""
    l_cum = np.cumsum(legit_hist)
    f_cum = np.cumsum(fraud_hist)
    fraud_allowed = f_cum[low]  # legit allowed costs nothing
    legit_step = l_cum[medium] - l_cum[low]
    fraud_step = f_cum[medium] - f_cum[low]
    legit_block = l_cum[-1] - l_cum[medium]
    return float(
        cost.false_negative * fraud_allowed
        + cost.stepup_legit * legit_step
        + cost.false_negative * cost.stepup_fraud_leak * fraud_step
        + cost.false_positive * legit_block
    )


def sweep_tier_thresholds(
    y_true: np.ndarray, scores: np.ndarray, cost: CostMatrix
) -> dict[str, Any]:
    """Exhaustively pick ``(low_max, medium_max)`` over integer scores 0-100.

    Tiers: ``score <= low`` ALLOWED, ``low < score <= medium`` STEP_UP, else BLOCKED.
    Ties go to the pair closest to the legacy ``(30, 70)`` so behaviour only moves when
    the data says it should.
    """
    y_true = np.asarray(y_true)
    scores = np.clip(np.rint(np.asarray(scores, dtype=float)), 0, 100).astype(int)
    legit_hist = np.bincount(scores[y_true == 0], minlength=101)
    fraud_hist = np.bincount(scores[y_true == 1], minlength=101)

    sweep: list[list[float]] = []
    best: tuple[float, int, int, int] | None = None
    for low in range(0, 100):
        for medium in range(low + 1, 101):
            c = tier_cost(legit_hist, fraud_hist, low, medium, cost)
            sweep.append([low, medium, round(c, 4)])
            dist = abs(low - DEFAULT_LOW_MAX) + abs(medium - DEFAULT_MEDIUM_MAX)
            if best is None or (c, dist) < (best[0], best[1]):
                best = (c, dist, low, medium)
    assert best is not None
    n = max(len(y_true), 1)
    default_cost = tier_cost(legit_hist, fraud_hist, DEFAULT_LOW_MAX, DEFAULT_MEDIUM_MAX, cost)
    return {
        "low_max": best[2],
        "medium_max": best[3],
        "expected_cost": round(best[0], 4),
        "cost_per_txn": round(best[0] / n, 6),
        "default_pair": [DEFAULT_LOW_MAX, DEFAULT_MEDIUM_MAX],
        "default_expected_cost": round(default_cost, 4),
        "cost_matrix": cost.as_dict(),
        "n_validation": int(len(y_true)),
        "sweep": sweep,
    }


# ── Runtime loading ─────────────────────────────────────────────────────────────

_CACHE: dict[str, Any] = {"key": None, "value": (DEFAULT_LOW_MAX, DEFAULT_MEDIUM_MAX), "at": 0.0}
_TTL_SECONDS = 2.0


def _valid(low: int, medium: int) -> bool:
    return 0 <= low < medium <= 100


def load_risk_thresholds() -> tuple[int, int]:
    """Return ``(low_max, medium_max)``.

    Precedence: explicit ``RISK_LOW_MAX`` / ``RISK_MEDIUM_MAX`` settings, then (only when
    ``USE_LEARNED_THRESHOLDS`` is on) ``risk_thresholds`` from the live model's metrics,
    then the legacy 30/70. A missing, corrupt or invalid metrics file silently falls
    back, so it can never break scoring.
    """
    settings = get_settings()
    low, medium = DEFAULT_LOW_MAX, DEFAULT_MEDIUM_MAX
    if settings.use_learned_thresholds:
        now = time.monotonic()
        path = settings.model_metrics_path
        if _CACHE["key"] == path and now - _CACHE["at"] < _TTL_SECONDS:
            low, medium = _CACHE["value"]
        else:
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    rt = json.load(fh).get("risk_thresholds") or {}
                cand = (int(rt["low_max"]), int(rt["medium_max"]))
                if _valid(*cand):
                    low, medium = cand
            except (OSError, ValueError, KeyError, TypeError):
                pass
            _CACHE.update(key=path, value=(low, medium), at=now)

    low = settings.risk_low_max if settings.risk_low_max is not None else low
    medium = settings.risk_medium_max if settings.risk_medium_max is not None else medium
    return (low, medium) if _valid(low, medium) else (DEFAULT_LOW_MAX, DEFAULT_MEDIUM_MAX)


def reset_threshold_cache() -> None:
    """Drop the cached thresholds (after a model promotion or in tests)."""
    _CACHE.update(key=None, at=0.0)


__all__ = [
    "CostMatrix",
    "DEFAULT_LOW_MAX",
    "DEFAULT_MEDIUM_MAX",
    "load_risk_thresholds",
    "reset_threshold_cache",
    "sweep_probability_threshold",
    "sweep_tier_thresholds",
    "tier_cost",
]
