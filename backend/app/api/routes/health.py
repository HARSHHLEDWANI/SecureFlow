"""Health-check endpoint reporting subsystem status."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.core.blockchain import get_blockchain
from app.core.redis_client import redis_client
from app.database import engine
from app.dependencies import envelope
from app.ml.model import get_model_service

router = APIRouter(tags=["health"])


def _db_ok() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - any DB error means unhealthy
        return False


@router.get("/health")
def health() -> dict:
    """Liveness probe with Redis, database, model, and chain status."""
    model = get_model_service()
    data = {
        "status": "ok",
        "version": __version__,
        "redis": redis_client.ping(),
        "database": _db_ok(),
        "model_loaded": model.loaded,
        "model_version": model.version,
        "blockchain_blocks": len(get_blockchain().chain),
    }
    return envelope(data)
