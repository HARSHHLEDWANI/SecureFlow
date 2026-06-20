"""Idempotent seeding of UPI Lab demo users + their transaction history.

Demo users are real :class:`User` rows so the pipeline's foreign keys, amount
statistics, velocity, new-device, and new-beneficiary signals all work exactly
as in production — and so Lab transactions appear in the dashboard/analytics.

Historical rows are inserted directly (not mined onto the chain) to give the
model 30 days of context cheaply; *live* Lab transactions then flow through the
real pipeline and get real blocks.
"""
from __future__ import annotations

import random
import uuid
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.demo_data import CITIES, DEMO_PASSWORD, DEMO_USER_BY_VPA, DEMO_USERS
from app.core.redis_client import redis_client
from app.core.security import hash_password
from app.database import (
    AuditLog,
    Role,
    RiskTier,
    SessionLocal,
    Transaction,
    TxnStatus,
    TxnType,
    User,
)
from app.utils.helpers import utcnow
from app.utils.logger import get_logger

logger = get_logger("demo_seed")

# Stable, deterministic user IDs derived from the VPA so reseeding is consistent
# and the frontend can reference users predictably.
_DEMO_NS = uuid.UUID("5ec0f10w-0000-0000-0000-000000000000".replace("w", "0"))


def demo_user_id(vpa: str) -> str:
    return str(uuid.uuid5(_DEMO_NS, vpa))


def is_demo_user(user: User) -> bool:
    return user.email.endswith("@secureflow.local")


def _seed_history(db: Session, user: User, spec: dict, rng: random.Random) -> None:
    """Insert ~30 days of low-risk historical transactions for one demo user."""
    lat, lon = CITIES[spec["home_city"]]
    lo, hi = spec["usual_hours"]
    now = utcnow()
    payees = spec["usual_payees"]
    # ~1.5 transactions/day over 30 days.
    for day in range(30):
        for _ in range(rng.choice([1, 1, 2, 2, 3])):
            amount = max(20.0, rng.gauss(spec["avg_transaction"], spec["amount_spread"]))
            hour = rng.randint(lo, min(hi, 23))
            created = now - timedelta(
                days=day, hours=rng.randint(0, 6), minutes=rng.randint(0, 59)
            )
            created = created.replace(hour=hour)
            db.add(
                Transaction(
                    user_id=user.id,
                    from_vpa=user.vpa,
                    to_vpa=rng.choice(payees),
                    amount_inr=round(amount, 2),
                    txn_type=rng.choice([TxnType.P2P, TxnType.P2M, TxnType.P2M]),
                    device_id=spec["known_device"],
                    location_lat=lat,
                    location_lon=lon,
                    risk_score=rng.randint(4, 22),
                    risk_tier=RiskTier.LOW,
                    ml_fraud_prob=round(rng.uniform(0.01, 0.18), 4),
                    anomaly_score=round(rng.uniform(0.02, 0.2), 4),
                    status=TxnStatus.ALLOWED,
                    created_at=created,
                )
            )


def _prime_redis(spec: dict, user_id: str) -> None:
    """Prime Redis with the demo user's known device + home location."""
    lat, lon = CITIES[spec["home_city"]]
    redis_client.add_device(user_id, spec["known_device"])
    redis_client.set_last_geo(user_id, lat, lon)


def seed_demo_users(force: bool = False) -> int:
    """Ensure demo users + history exist. Returns the number of users seeded.

    Idempotent: a no-op when already present unless ``force`` is set (which wipes
    and rebuilds their history — used by the Lab's reset endpoint).
    """
    db: Session = SessionLocal()
    try:
        existing = {
            u.vpa
            for u in db.execute(
                select(User).where(User.email.like("%@secureflow.local"))
            ).scalars()
        }
        if existing and not force:
            for spec in DEMO_USERS:
                _prime_redis(spec, demo_user_id(spec["vpa"]))
            logger.info("Demo users already present (%d) - reprimed Redis", len(existing))
            return 0

        rng = random.Random(42)  # deterministic history
        seeded = 0
        for spec in DEMO_USERS:
            uid = demo_user_id(spec["vpa"])
            user = db.get(User, uid)
            if user is None:
                user = User(
                    id=uid,
                    email=spec["email"],
                    password_hash=hash_password(DEMO_PASSWORD),
                    vpa=spec["vpa"],
                    role=Role.VIEWER,
                    home_city=spec["home_city"],
                )
                db.add(user)
                db.flush()
            else:
                # force=True path — wipe prior transactions/audit for a clean slate.
                txn_ids = [
                    t.id
                    for t in db.execute(
                        select(Transaction.id).where(Transaction.user_id == uid)
                    )
                ]
                if txn_ids:
                    db.execute(
                        delete(AuditLog).where(AuditLog.transaction_id.in_(txn_ids))
                    )
                    db.execute(delete(Transaction).where(Transaction.user_id == uid))
                db.flush()

            _seed_history(db, user, spec, rng)
            _reset_velocity(uid)
            _prime_redis(spec, uid)
            seeded += 1

        db.commit()
        logger.info("Seeded %d demo users with history", seeded)
        return seeded
    finally:
        db.close()


def _reset_velocity(user_id: str) -> None:
    """Clear a demo user's rolling velocity + cached risk profile in Redis."""
    fn = getattr(redis_client, "_client", None)
    if fn is None:
        return
    try:
        fn.delete(f"velocity:user:{user_id}")
        fn.delete(f"risk:user:{user_id}")
    except Exception:  # noqa: BLE001 - best-effort cache clear
        pass


def reset_sender_baseline(vpa: str) -> None:
    """Reset a demo sender's rolling state to baseline before a scenario run.

    Clears accumulated velocity and re-primes the known device + home location,
    so each preset scenario is evaluated against the user's *normal* history and
    is fully repeatable (independent of whatever scenarios ran before it).
    Manual ``/upi/pay`` calls deliberately skip this so state evolves live.
    """
    spec = DEMO_USER_BY_VPA.get(vpa)
    uid = demo_user_id(vpa)
    _reset_velocity(uid)
    if spec is not None:
        _prime_redis(spec, uid)


def reset_demo() -> int:
    """Reset all demo data to the initial seeded state (Lab 'Reset Session')."""
    redis_client.cache_set_json("analytics:dashboard", {}, ttl=1)  # bust dashboard cache
    fn = getattr(redis_client, "_client", None)
    if fn is not None:
        try:
            fn.delete("analytics:dashboard")
        except Exception:  # noqa: BLE001
            pass
    return seed_demo_users(force=True)
