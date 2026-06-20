"""Shared fraud-analysis pipeline.

This is the single source of truth for the transaction-analysis flow:
gather signals → ML predict (Redis-cached) → composite risk → persist → mine a
blockchain block → audit log → update Redis history → dispatch alerts.

Both the authenticated ``/transaction/analyze`` route and the UPI Simulation Lab
call :func:`run_pipeline`, so every Lab transaction is scored by the *real* model,
recorded on the *real* chain, and shows up in the dashboard/analytics like any
other transaction. The Lab only differs in how it *builds the signals* (it may
inject deterministic overrides for reproducible attack scenarios).
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.websockets.alerts import dispatch_alert
from app.core.blockchain import get_blockchain
from app.core.redis_client import redis_client
from app.core.risk_engine import compute_risk
from app.database import (
    AuditLog,
    RiskTier,
    Transaction,
    TxnStatus,
    TxnType,
    User,
)
from app.ml.model import get_model_service
from app.utils.helpers import haversine_km, stable_hash, utcnow

_ACTION_BY_STATUS = {
    TxnStatus.ALLOWED: "Allow transaction",
    TxnStatus.STEP_UP: "Require step-up authentication (OTP)",
    TxnStatus.BLOCKED: "Block transaction and alert fraud team",
}

# Canonical order the Lab visualizer renders.
STAGE_ORDER = [
    "initiated",
    "validated",
    "features_extracted",
    "ml_prediction",
    "risk_scored",
    "blockchain_logged",
    "decision",
]


# ── Stage tracking (for the Lab's live pipeline visualizer) ───────────────────


class StageTracker:
    """Records per-stage timing and mirrors it into Redis for live polling.

    Used only by the UPI Lab; the normal analyze route passes ``tracker=None``
    so there is zero overhead on the production path.
    """

    def __init__(self, txn_id: str) -> None:
        self.txn_id = txn_id
        self.stages: dict[str, dict[str, Any]] = {}
        self._t0 = time.perf_counter()
        self._last = self._t0

    def mark(self, stage: str, **data: Any) -> None:
        now = time.perf_counter()
        self.stages[stage] = {
            "status": "complete",
            "timestamp": utcnow().isoformat(),
            "duration_ms": round((now - self._last) * 1000, 2),
            **data,
        }
        self._last = now
        self._persist()

    def rekey(self, new_id: str) -> None:
        """Re-publish the snapshot under the final transaction id (was temporary)."""
        self.txn_id = new_id
        self._persist()

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self._t0) * 1000, 2)

    def snapshot(self) -> dict[str, Any]:
        return {
            "txn_id": self.txn_id,
            "stages": self.stages,
            "stage_order": STAGE_ORDER,
            "total_duration_ms": self.total_ms,
        }

    def _persist(self) -> None:
        redis_client.cache_set_json(f"pipeline:{self.txn_id}", self.snapshot(), ttl=900)


# ── Helpers ───────────────────────────────────────────────────────────────────


def aware(dt: datetime) -> datetime:
    """Normalise a possibly-naive DB datetime to aware UTC for subtraction."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _user_amount_stats(db: Session, user_id: str) -> tuple[float, float]:
    """Return (avg, std) of a user's historical transaction amounts."""
    rows = db.execute(
        select(Transaction.amount_inr).where(Transaction.user_id == user_id)
    ).scalars().all()
    amounts = [float(a) for a in rows]
    if not amounts:
        return 0.0, 0.0
    avg = sum(amounts) / len(amounts)
    var = sum((a - avg) ** 2 for a in amounts) / len(amounts)
    return avg, var**0.5


def _db_velocity(db: Session, user_id: str, window_seconds: int, now: datetime) -> int:
    """Count a user's transactions within the trailing window (DB fallback)."""
    since = now - timedelta(seconds=window_seconds)
    return int(
        db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.user_id == user_id, Transaction.created_at >= since)
        )
        or 0
    )


def gather_signals(
    db: Session,
    user: User,
    *,
    to_vpa: str,
    amount_inr: float,
    txn_type: str,
    device_id: str,
    location_lat: float,
    location_lon: float,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Assemble raw fraud signals from Redis history (DB fallback).

    ``overrides`` lets the UPI Lab force a few signals deterministically without
    bypassing the rest of the (real) computation:

    ``now`` (datetime), ``hour`` (int), ``prev_lat``/``prev_lon`` +
    ``minutes_since_last`` (geo-velocity injection), ``is_new_device`` (bool),
    ``is_new_beneficiary`` (bool), ``velocity_1h``/``velocity_24h`` (int),
    ``user_avg_amount``/``user_std_amount`` (float).
    """
    overrides = overrides or {}
    now = overrides.get("now") or utcnow()

    # Velocity — prefer Redis sorted set, fall back to DB counts by time window.
    velocity_1h = redis_client.velocity_count(user.id, 3600)
    velocity_24h = redis_client.velocity_count(user.id, 86400)
    if velocity_1h is None:
        velocity_1h = _db_velocity(db, user.id, 3600, now)
    if velocity_24h is None:
        velocity_24h = _db_velocity(db, user.id, 86400, now)
    velocity_1h = int(overrides.get("velocity_1h", velocity_1h))
    velocity_24h = int(overrides.get("velocity_24h", velocity_24h))

    # Geo-velocity + recency. An override of a prior location/time makes
    # "impossible travel" reproducible regardless of seeded history.
    if "prev_lat" in overrides and "prev_lon" in overrides:
        geo_distance = haversine_km(
            overrides["prev_lat"], overrides["prev_lon"], location_lat, location_lon
        )
        minutes_since_last = float(overrides.get("minutes_since_last", 24 * 60.0))
    else:
        last_txn = db.execute(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        last_geo = redis_client.get_last_geo(user.id)
        if last_geo:
            geo_distance = haversine_km(
                last_geo["lat"], last_geo["lon"], location_lat, location_lon
            )
            minutes_since_last = 24 * 60.0
            if last_txn is not None:
                delta = (now - aware(last_txn.created_at)).total_seconds() / 60.0
                minutes_since_last = max(delta, 0.1)
        elif last_txn is not None:
            geo_distance = haversine_km(
                last_txn.location_lat, last_txn.location_lon, location_lat, location_lon
            )
            minutes_since_last = max(
                (now - aware(last_txn.created_at)).total_seconds() / 60.0, 0.1
            )
        else:
            geo_distance, minutes_since_last = 0.0, 24 * 60.0

    # New-device flag — Redis device set, DB fallback, override wins.
    if "is_new_device" in overrides:
        is_new_device = 1 if overrides["is_new_device"] else 0
    else:
        known = redis_client.is_known_device(user.id, device_id)
        if known is None:
            known = (
                db.scalar(
                    select(func.count())
                    .select_from(Transaction)
                    .where(Transaction.user_id == user.id, Transaction.device_id == device_id)
                )
                or 0
            ) > 0
        is_new_device = 0 if known else 1

    # New-beneficiary flag (always DB — small, exact — override wins).
    if "is_new_beneficiary" in overrides:
        is_new_beneficiary = 1 if overrides["is_new_beneficiary"] else 0
    else:
        seen_to = db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.user_id == user.id, Transaction.to_vpa == to_vpa)
        )
        is_new_beneficiary = 0 if (seen_to or 0) > 0 else 1

    avg, std = _user_amount_stats(db, user.id)
    avg = float(overrides.get("user_avg_amount", avg))
    std = float(overrides.get("user_std_amount", std))

    hour = int(overrides.get("hour", now.hour))

    return {
        "amount_inr": amount_inr,
        "txn_type": txn_type,
        "hour": hour,
        "is_weekend": int(now.weekday() >= 5),
        "velocity_1h": velocity_1h,
        "velocity_24h": velocity_24h,
        "geo_distance_km": float(geo_distance),
        "minutes_since_last": float(minutes_since_last),
        "is_new_device": is_new_device,
        "is_new_beneficiary": is_new_beneficiary,
        "user_avg_amount": avg,
        "user_std_amount": std,
    }


def predict_cached(signals: dict[str, Any]) -> dict[str, Any]:
    """ML prediction with the same Redis cache the analyze route uses."""
    cache_key = f"prediction:{stable_hash(signals)}"
    ml_result = redis_client.cache_get_json(cache_key)
    if ml_result is None:
        ml_result = get_model_service().predict(signals)
        redis_client.cache_set_json(cache_key, ml_result, ttl=600)
    return ml_result


# ── The pipeline ──────────────────────────────────────────────────────────────


def run_pipeline(
    db: Session,
    user: User,
    *,
    to_vpa: str,
    amount_inr: float,
    txn_type: str,
    device_id: str,
    location_lat: float,
    location_lon: float,
    signals: dict[str, Any],
    actor_id: Optional[str] = None,
    tracker: Optional[StageTracker] = None,
    note: Optional[str] = None,
) -> tuple[Transaction, dict[str, Any], dict[str, Any]]:
    """Run the full fraud-analysis pipeline and persist the result on-chain.

    Returns ``(transaction, ml_result, risk)``. ``signals`` is pre-built by the
    caller (the analyze route derives it from history; the Lab may inject
    deterministic overrides). The mechanics — model, scoring, persistence, chain,
    audit, Redis, alerting — are identical for both.
    """
    ml_result = predict_cached(signals)
    if tracker:
        feats = ml_result["features"]
        tracker.mark(
            "features_extracted",
            features_count=len(feats),
            amount_zscore=feats.get("amount_zscore"),
            impossible_travel=feats.get("impossible_travel"),
            high_velocity=feats.get("high_velocity"),
            is_new_device=feats.get("is_new_device"),
        )

    features = ml_result["features"]
    risk = compute_risk(features, ml_result)
    if tracker:
        tracker.mark(
            "ml_prediction",
            fraud_prob=ml_result["fraud_prob"],
            anomaly_score=ml_result["anomaly_score"],
            label="suspicious" if ml_result["fraud_prob"] >= 0.5 else "normal",
        )
        tracker.mark(
            "risk_scored",
            score=risk["risk_score"],
            tier=risk["risk_tier"].value,
        )

    txn = Transaction(
        user_id=user.id,
        from_vpa=user.vpa,
        to_vpa=to_vpa,
        amount_inr=amount_inr,
        txn_type=TxnType(txn_type),
        device_id=device_id,
        location_lat=location_lat,
        location_lon=location_lon,
        risk_score=risk["risk_score"],
        risk_tier=risk["risk_tier"],
        ml_fraud_prob=ml_result["fraud_prob"],
        anomaly_score=ml_result["anomaly_score"],
        status=risk["status"],
    )
    db.add(txn)
    db.flush()  # assign txn.id

    block = get_blockchain().mine_block(
        {
            "transaction_id": txn.id,
            "from_vpa": txn.from_vpa,
            "to_vpa": txn.to_vpa,
            "amount_inr": float(txn.amount_inr),
            "txn_type": txn.txn_type.value,
            "risk_score": txn.risk_score,
            "risk_tier": txn.risk_tier.value,
            "status": txn.status.value,
        }
    )
    txn.block_index = block.index
    txn.block_hash = block.hash
    if tracker:
        tracker.mark("blockchain_logged", block_index=block.index, block_hash=block.hash)

    db.add(
        AuditLog(
            transaction_id=txn.id,
            actor_id=actor_id or user.id,
            action=f"ANALYZE_{txn.status.value}",
            risk_score=txn.risk_score,
            block_hash=block.hash,
            audit_metadata={
                "components": risk["components"],
                "txn_type": txn.txn_type.value,
                **({"note": note} if note else {}),
            },
        )
    )
    db.commit()
    db.refresh(txn)

    # Update Redis history + caches (best-effort).
    redis_client.record_velocity(user.id)
    redis_client.set_last_geo(user.id, location_lat, location_lon)
    redis_client.add_device(user.id, device_id)
    refresh_risk_cache(db, user.id, txn.risk_score)

    if tracker:
        tracker.mark(
            "decision",
            action=txn.status.value,
            reason=_ACTION_BY_STATUS[txn.status],
        )

    if txn.risk_tier == RiskTier.HIGH:
        dispatch_alert(
            {
                "type": "fraud_alert",
                "transaction_id": txn.id,
                "from_vpa": txn.from_vpa,
                "to_vpa": txn.to_vpa,
                "amount_inr": float(txn.amount_inr),
                "risk_score": txn.risk_score,
                "risk_tier": txn.risk_tier.value,
                "status": txn.status.value,
                "created_at": txn.created_at.isoformat(),
            }
        )

    return txn, ml_result, risk


def recommended_action(status: TxnStatus) -> str:
    return _ACTION_BY_STATUS[status]


def refresh_risk_cache(db: Session, user_id: str, last_score: int) -> None:
    profile = compute_risk_profile(db, user_id, last_score)
    redis_client.cache_set_json(f"risk:user:{user_id}", profile, ttl=300)


def compute_risk_profile(
    db: Session, user_id: str, last_score: Optional[int] = None
) -> dict[str, Any]:
    count = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.user_id == user_id)
    ) or 0
    avg = db.scalar(
        select(func.avg(Transaction.risk_score)).where(Transaction.user_id == user_id)
    )
    flagged = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.user_id == user_id, Transaction.risk_tier != RiskTier.LOW)
    ) or 0
    return {
        "user_id": user_id,
        "transaction_count": int(count),
        "average_risk_score": round(float(avg), 2) if avg is not None else 0.0,
        "flagged_count": int(flagged),
        "last_risk_score": last_score,
    }
