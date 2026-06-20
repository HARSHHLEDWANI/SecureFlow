"""Transaction fraud-analysis endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pipeline import (
    compute_risk_profile,
    gather_signals,
    recommended_action,
    refresh_risk_cache,
    run_pipeline,
)
from app.core.redis_client import redis_client
from app.database import RiskTier, Transaction, User, get_db
from app.dependencies import RateLimiter, envelope, get_current_user
from app.models.transaction import (
    TransactionAnalyzeRequest,
    TransactionResult,
    TransactionSummary,
    UserRiskProfile,
)
from app.utils.logger import get_logger

logger = get_logger("transaction")
router = APIRouter(prefix="/transaction", tags=["transaction"])


@router.post("/analyze", dependencies=[Depends(RateLimiter("analyze"))])
def analyze_transaction(
    req: TransactionAnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Run the full fraud-analysis pipeline and record the result on-chain."""
    signals = gather_signals(
        db,
        user,
        to_vpa=req.to_vpa,
        amount_inr=req.amount_inr,
        txn_type=req.txn_type,
        device_id=req.device_id,
        location_lat=req.location_lat,
        location_lon=req.location_lon,
    )
    txn, ml_result, risk = run_pipeline(
        db,
        user,
        to_vpa=req.to_vpa,
        amount_inr=req.amount_inr,
        txn_type=req.txn_type,
        device_id=req.device_id,
        location_lat=req.location_lat,
        location_lon=req.location_lon,
        signals=signals,
    )
    return envelope(_to_result(txn, ml_result, risk).model_dump())


def _to_result(txn: Transaction, ml_result: dict, risk: dict) -> TransactionResult:
    return TransactionResult(
        id=txn.id,
        from_vpa=txn.from_vpa,
        to_vpa=txn.to_vpa,
        amount_inr=float(txn.amount_inr),
        txn_type=txn.txn_type.value,
        risk_score=txn.risk_score,
        risk_tier=txn.risk_tier.value,
        status=txn.status.value,
        ml_fraud_prob=ml_result["fraud_prob"],
        anomaly_score=ml_result["anomaly_score"],
        ml_confidence=ml_result["confidence"],
        components=risk["components"],
        feature_contributions=ml_result["feature_contributions"],
        block_index=txn.block_index,
        block_hash=txn.block_hash,
        recommended_action=recommended_action(txn.status),
        created_at=txn.created_at,
    )


@router.get("/{txn_id}/status")
def transaction_status(
    txn_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Fetch a stored transaction analysis result."""
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    summary = TransactionSummary(
        id=txn.id,
        from_vpa=txn.from_vpa,
        to_vpa=txn.to_vpa,
        amount_inr=float(txn.amount_inr),
        txn_type=txn.txn_type.value,
        risk_score=txn.risk_score,
        risk_tier=txn.risk_tier.value,
        status=txn.status.value,
        block_hash=txn.block_hash,
        created_at=txn.created_at,
    )
    return envelope(summary.model_dump())


@router.get("")
def list_transactions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    tier: Optional[str] = Query(default=None, pattern=r"^(LOW|MEDIUM|HIGH)$"),
) -> dict:
    """List recent transactions, newest first, optionally filtered by tier."""
    stmt = select(Transaction).order_by(Transaction.created_at.desc()).limit(limit)
    if tier:
        stmt = stmt.where(Transaction.risk_tier == RiskTier(tier))
    rows = db.execute(stmt).scalars().all()
    items = [
        TransactionSummary(
            id=t.id,
            from_vpa=t.from_vpa,
            to_vpa=t.to_vpa,
            amount_inr=float(t.amount_inr),
            txn_type=t.txn_type.value,
            risk_score=t.risk_score,
            risk_tier=t.risk_tier.value,
            status=t.status.value,
            block_hash=t.block_hash,
            created_at=t.created_at,
        ).model_dump()
        for t in rows
    ]
    return envelope(items)


risk_router = APIRouter(prefix="/risk-score", tags=["transaction"])


@risk_router.get("/{user_id}")
def user_risk_profile(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Return a user's risk profile, served from Redis cache when warm."""
    cached = redis_client.cache_get_json(f"risk:user:{user_id}")
    if cached is not None:
        cached["cached"] = True
        return envelope(UserRiskProfile(**cached).model_dump())

    profile = compute_risk_profile(db, user_id)
    redis_client.cache_set_json(f"risk:user:{user_id}", profile, ttl=300)
    profile["cached"] = False
    return envelope(UserRiskProfile(**profile).model_dump())
