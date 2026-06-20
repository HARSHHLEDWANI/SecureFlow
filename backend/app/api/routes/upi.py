"""UPI Simulation Lab endpoints.

A demonstration surface that drives realistic UPI payments through SecureFlow's
real fraud-detection pipeline. These endpoints are intentionally unauthenticated
so the in-browser "Guided Demo" is one click; they act on the *selected demo
user*, never on a real account.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.demo_data import CITIES, DEMO_PASSWORD, DEMO_USERS
from app.core.demo_seed import demo_user_id, reset_demo
from app.core.redis_client import redis_client
from app.core.upi_simulator import UPIValidationError, scenarios_public, simulator
from app.database import Transaction, User, get_db
from app.dependencies import RateLimiter, envelope
from app.models.upi import UPIPayRequest, UPIPayResult
from app.utils.logger import get_logger

logger = get_logger("upi")
router = APIRouter(prefix="/upi", tags=["upi-lab"])


@router.get("/users")
def list_demo_users(db: Session = Depends(get_db)) -> dict:
    """Demo user profiles with a live transaction count + last risk score."""
    out = []
    for spec in DEMO_USERS:
        uid = demo_user_id(spec["vpa"])
        last = db.execute(
            select(Transaction)
            .where(Transaction.user_id == uid)
            .order_by(Transaction.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        count = db.scalar(
            select(Transaction.id).where(Transaction.user_id == uid).limit(1)
        )
        lat, lon = CITIES[spec["home_city"]]
        out.append(
            {
                "vpa": spec["vpa"],
                "name": spec["name"],
                "home_city": spec["home_city"],
                "lat": lat,
                "lon": lon,
                "avg_transaction": spec["avg_transaction"],
                "risk_profile": spec["risk_profile"],
                "known_device": spec["known_device"],
                "seeded": count is not None,
                "last_risk_score": last.risk_score if last else None,
            }
        )
    return envelope({"users": out, "demo_password": DEMO_PASSWORD, "cities": CITIES})


@router.get("/scenarios")
def list_scenarios() -> dict:
    """All preset attack/behaviour scenarios for the Lab."""
    return envelope({"scenarios": scenarios_public()})


@router.post("/pay", dependencies=[Depends(RateLimiter("upi_pay"))])
def upi_pay(req: UPIPayRequest, db: Session = Depends(get_db)) -> dict:
    """Process a single UPI payment through the real detection pipeline."""
    try:
        result = simulator.process_payment(
            db,
            sender_vpa=req.sender_vpa,
            receiver_vpa=req.receiver_vpa,
            amount_inr=req.amount_inr,
            txn_type=req.txn_type,
            note=req.note,
            city=req.city,
            device_id=req.device_id,
        )
    except UPIValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return envelope(UPIPayResult(**result).model_dump())


@router.post("/scenario/{scenario_id}", dependencies=[Depends(RateLimiter("upi_pay"))])
def run_scenario(scenario_id: str, db: Session = Depends(get_db)) -> dict:
    """Run one preset scenario end-to-end through the pipeline."""
    try:
        payload = simulator.run_scenario(db, scenario_id)
    except UPIValidationError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return envelope(payload)


@router.post("/rapid-fire", dependencies=[Depends(RateLimiter("upi_pay"))])
def rapid_fire(db: Session = Depends(get_db)) -> dict:
    """Run the rapid-fire burst and return the full sequence of results."""
    results = simulator.run_rapid_fire(db)
    return envelope({"results": results})


@router.get("/user/{vpa}/history")
def user_history(
    vpa: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict:
    """Recent transactions for a demo user (newest first)."""
    uid = demo_user_id(vpa)
    rows = db.execute(
        select(Transaction)
        .where(Transaction.user_id == uid)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    ).scalars().all()
    items = [
        {
            "id": t.id,
            "from_vpa": t.from_vpa,
            "to_vpa": t.to_vpa,
            "amount_inr": float(t.amount_inr),
            "txn_type": t.txn_type.value,
            "risk_score": t.risk_score,
            "risk_tier": t.risk_tier.value,
            "status": t.status.value,
            "block_index": t.block_index,
            "block_hash": t.block_hash,
            "created_at": t.created_at.isoformat(),
        }
        for t in rows
    ]
    return envelope({"vpa": vpa, "transactions": items})


@router.get("/pipeline-status/{txn_id}")
def pipeline_status(txn_id: str) -> dict:
    """Live per-stage pipeline timing for a transaction (from Redis)."""
    snap = redis_client.cache_get_json(f"pipeline:{txn_id}")
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pipeline data for this transaction")
    return envelope(snap)


@router.post("/reset")
def reset() -> dict:
    """Reset all demo data (users + history) to the initial seeded state."""
    count = reset_demo()
    return envelope({"reset": True, "users_seeded": count})
