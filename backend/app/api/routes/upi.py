"""UPI Simulation Lab endpoints.

A demonstration surface that drives realistic UPI payments through SecureFlow's
real fraud-detection pipeline. They act on the *selected demo user*, never on a real
account, and every row they create is flagged ``is_demo``.

Reads are public. Every mutating route (pay, scenario, rapid-fire, reset) requires a
short-lived demo session token from ``POST /upi/session`` (sent as ``X-Demo-Session``;
the frontend fetches one on page load, so the demo stays one click), is rate-limited far
more tightly than the rest of the API, and counts against per-session and global caps.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.demo_data import CITIES, DEMO_PASSWORD, DEMO_USERS, SCENARIO_BY_ID
from app.config import get_settings
from app.core.demo_seed import demo_user_id, reset_demo
from app.core.demo_session import enforce_quota, issue_session, require_demo_session
from app.core.redis_client import redis_client
from app.core.upi_simulator import UPIValidationError, scenarios_public, simulator
from app.database import Transaction, User, get_db
from app.dependencies import RateLimiter, envelope
from app.models.upi import UPIPayRequest, UPIPayResult
from app.utils.logger import get_logger

logger = get_logger("upi")
router = APIRouter(prefix="/upi", tags=["upi-lab"])
settings = get_settings()

# Lab writes are limited far below the global 60/min; reset (a bulk delete + reseed) more still.
_lab_write_limit = RateLimiter("upi_pay", limit=settings.demo_rate_limit_requests)
_lab_reset_limit = RateLimiter("upi_reset", limit=5)
_session_limit = RateLimiter("upi_session", limit=settings.demo_session_rate_limit)


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


@router.post("/session", dependencies=[Depends(_session_limit)])
def create_session() -> dict:
    """Issue a short-lived demo session token for the Lab's mutating endpoints."""
    return envelope(issue_session())


@router.post("/pay", dependencies=[Depends(_lab_write_limit)])
def upi_pay(
    req: UPIPayRequest,
    db: Session = Depends(get_db),
    sid: str = Depends(require_demo_session),
) -> dict:
    """Process a single UPI payment through the real detection pipeline."""
    enforce_quota(db, sid, 1)
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


@router.post("/scenario/{scenario_id}", dependencies=[Depends(_lab_write_limit)])
def run_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    sid: str = Depends(require_demo_session),
) -> dict:
    """Run one preset scenario end-to-end through the pipeline."""
    scn = SCENARIO_BY_ID.get(scenario_id)
    if scn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown scenario '{scenario_id}'")
    enforce_quota(db, sid, _rapid_fire_len(scn) if "rapid_fire" in scn else 1)
    try:
        payload = simulator.run_scenario(db, scenario_id)
    except UPIValidationError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return envelope(payload)


@router.post("/rapid-fire", dependencies=[Depends(_lab_write_limit)])
def rapid_fire(db: Session = Depends(get_db), sid: str = Depends(require_demo_session)) -> dict:
    """Run the rapid-fire burst and return the full sequence of results."""
    enforce_quota(db, sid, _rapid_fire_len(SCENARIO_BY_ID["rapid_fire"]))
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


@router.post("/reset", dependencies=[Depends(_lab_reset_limit)])
def reset(sid: str = Depends(require_demo_session)) -> dict:
    """Reset demo data to the seeded state. Deletes only ``is_demo`` rows."""
    count = reset_demo()
    return envelope({"reset": True, "users_seeded": count})


def _rapid_fire_len(scn: dict) -> int:
    """How many transactions a rapid-fire scenario will create (for quota accounting)."""
    return len((scn.get("rapid_fire") or {}).get("amounts") or range(10))
