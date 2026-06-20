"""Aggregated fraud analytics endpoints."""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.redis_client import redis_client
from app.database import RiskTier, Transaction, TxnStatus, User, get_db
from app.dependencies import envelope, get_current_user
from app.utils.helpers import utcnow

router = APIRouter(prefix="/analytics", tags=["analytics"])
settings = get_settings()

DASHBOARD_CACHE_KEY = "analytics:dashboard"


def _aware(dt):
    from datetime import timezone

    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """Aggregated fraud KPIs for the dashboard (Redis-cached for 60s)."""
    cached = redis_client.cache_get_json(DASHBOARD_CACHE_KEY)
    if cached is not None:
        return envelope(cached)

    txns = db.execute(select(Transaction)).scalars().all()
    total = len(txns)
    tiers = Counter(t.risk_tier.value for t in txns)
    fraud_detected = tiers.get("HIGH", 0)
    blocked = sum(1 for t in txns if t.status == TxnStatus.BLOCKED)
    step_up = sum(1 for t in txns if t.status == TxnStatus.STEP_UP)
    avg_risk = round(sum(t.risk_score for t in txns) / total, 2) if total else 0.0

    # Daily volume for the trailing 7 days (computed in Python for DB portability).
    today = utcnow().date()
    volume = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for t in txns:
        d = _aware(t.created_at).date()
        if (today - d).days < 7:
            key = d.isoformat()
            volume[key]["count"] += 1
            volume[key]["amount"] += float(t.amount_inr)
    daily_volume = [
        {"date": (today - timedelta(days=i)).isoformat(),
         **volume.get((today - timedelta(days=i)).isoformat(), {"count": 0, "amount": 0.0})}
        for i in range(6, -1, -1)
    ]

    # Risk-score histogram in 10-point buckets.
    buckets = Counter(min(t.risk_score // 10, 9) for t in txns)
    histogram = [
        {"range": f"{b*10}-{b*10+9}", "count": buckets.get(b, 0)} for b in range(10)
    ]

    data = {
        "total_transactions": total,
        "fraud_detected": fraud_detected,
        "fraud_rate": round(fraud_detected / total, 4) if total else 0.0,
        "average_risk_score": avg_risk,
        "blocked_count": blocked,
        "step_up_count": step_up,
        "tier_distribution": {
            "LOW": tiers.get("LOW", 0),
            "MEDIUM": tiers.get("MEDIUM", 0),
            "HIGH": tiers.get("HIGH", 0),
        },
        "daily_volume": daily_volume,
        "risk_score_histogram": histogram,
    }
    redis_client.cache_set_json(DASHBOARD_CACHE_KEY, data, ttl=60)
    return envelope(data)


@router.get("/recent-alerts")
def recent_alerts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Most recent HIGH/MEDIUM-risk transactions, newest first."""
    rows = db.execute(
        select(Transaction)
        .where(Transaction.risk_tier != RiskTier.LOW)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    ).scalars().all()
    alerts = [
        {
            "transaction_id": t.id,
            "from_vpa": t.from_vpa,
            "to_vpa": t.to_vpa,
            "amount_inr": float(t.amount_inr),
            "risk_score": t.risk_score,
            "risk_tier": t.risk_tier.value,
            "status": t.status.value,
            "created_at": t.created_at.isoformat(),
        }
        for t in rows
    ]
    return envelope(alerts)


@router.get("/model-metrics")
def model_metrics(user: User = Depends(get_current_user)) -> dict:
    """Return the stored evaluation metrics from the last training run."""
    path = settings.model_metrics_path
    if not os.path.exists(path):
        return envelope(None, error="Model metrics not available — train the model first.")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return envelope(json.load(fh))
    except (OSError, json.JSONDecodeError):
        return envelope(None, error="Could not read model metrics file.")
