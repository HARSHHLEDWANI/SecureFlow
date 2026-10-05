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
from app.config import get_settings
from app.core.explain import explain_decision
from app.core.redis_client import redis_client
from app.database import AuditLog, RiskTier, Transaction, User, get_db
from app.dependencies import RateLimiter, envelope, get_current_user, is_staff
from app.models.transaction import (
    ExplanationResult,
    TransactionAnalyzeRequest,
    TransactionResult,
    TransactionSummary,
    UserRiskProfile,
)
from app.utils.logger import get_logger

logger = get_logger("transaction")
settings = get_settings()
router = APIRouter(prefix="/transaction", tags=["transaction"])


def _txn_or_404(db: Session, txn_id: str, user: User) -> Transaction:
    """Fetch a transaction, enforcing the ownership rule.

    A VIEWER may only access their own transaction; ANALYST/ADMIN may access any.
    A missing transaction *and* a cross-user access by a VIEWER both return 404,
    so the endpoint never leaks the existence of another user's transaction id.
    Shared by the status and explain endpoints so they use one identical check.
    """
    txn = db.get(Transaction, txn_id)
    if txn is None or (not is_staff(user) and txn.user_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    return txn


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
    """Fetch a stored transaction analysis result.

    A VIEWER may only read their own transactions; ANALYST/ADMIN may read any.
    Cross-user reads by a VIEWER return 404 (not 403) so the endpoint does not
    leak the existence of other users' transaction ids.
    """
    txn = _txn_or_404(db, txn_id, user)
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
    include_demo: bool = Query(default=False, description="Staff only: include UPI Lab rows"),
) -> dict:
    """List recent transactions, newest first, optionally filtered by tier.

    ANALYST/ADMIN see every user's transactions (this is a fraud-ops tool); a
    VIEWER is scoped to their own transactions only. UPI Lab rows are hidden from the staff
    view unless ``include_demo=true``.
    """
    stmt = select(Transaction).order_by(Transaction.created_at.desc()).limit(limit)
    if not is_staff(user):
        stmt = stmt.where(Transaction.user_id == user.id)
    elif not include_demo:
        stmt = stmt.where(Transaction.is_demo.is_(False))
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


@router.post(
    "/{txn_id}/explain",
    dependencies=[Depends(RateLimiter("explain", limit=settings.explain_rate_limit_requests))],
)
def explain_transaction(
    txn_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Return a plain-English explanation of an already-made fraud decision.

    Access uses the *same* ownership rule as ``/{txn_id}/status``. The LLM only
    explains the decision — it never influences the score, tier, or action. The
    result is cached in Redis per transaction so repeat clicks don't re-spend the
    API budget; the endpoint is rate-limited more tightly than the others because
    it has a real per-call cost. Falls back to a deterministic template when the
    LLM is unavailable (``source`` says which path produced the text).
    """
    txn = _txn_or_404(db, txn_id, user)

    cache_key = f"explain:{txn_id}"
    cached = redis_client.cache_get_json(cache_key)
    if cached is not None:
        return envelope(ExplanationResult(**cached, cached=True).model_dump())

    # Reconstruct the decision context from the stored ANALYZE audit log.
    log = db.execute(
        select(AuditLog)
        .where(AuditLog.transaction_id == txn.id, AuditLog.action.like("ANALYZE_%"))
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    meta = (log.audit_metadata if log else None) or {}
    components = meta.get("components", {})
    feature_contributions = meta.get("feature_contributions", [])

    result = explain_decision(txn, components, feature_contributions)
    redis_client.cache_set_json(cache_key, result, ttl=settings.explain_cache_ttl_seconds)
    return envelope(ExplanationResult(**result, cached=False).model_dump())


risk_router = APIRouter(prefix="/risk-score", tags=["transaction"])


@risk_router.get("/{user_id}")
def user_risk_profile(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Return a user's risk profile, served from Redis cache when warm.

    A VIEWER may only read their own profile; ANALYST/ADMIN may read any user's.
    """
    if not is_staff(user) and user_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You may only view your own risk profile"
        )
    cached = redis_client.cache_get_json(f"risk:user:{user_id}")
    if cached is not None:
        cached["cached"] = True
        return envelope(UserRiskProfile(**cached).model_dump())

    profile = compute_risk_profile(db, user_id)
    redis_client.cache_set_json(f"risk:user:{user_id}", profile, ttl=300)
    profile["cached"] = False
    return envelope(UserRiskProfile(**profile).model_dump())
