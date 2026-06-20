"""SecureFlow FastAPI application.

Wires together CORS, the REST routers, the WebSocket alert stream, and the
application lifespan (database init, model loading, blockchain genesis, and the
Redis → WebSocket alert bridge).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import analytics, auth, blockchain, governance, health, transaction, upi
from app.api.websockets import alerts
from app.config import get_settings
from app.core.blockchain import get_blockchain
from app.database import init_db
from app.dependencies import envelope
from app.ml.model import get_model_service
from app.utils.logger import get_logger

logger = get_logger("main")
settings = get_settings()

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise subsystems on startup, clean up on shutdown."""
    logger.info("Starting %s v%s (%s)", settings.app_name, __version__, settings.environment)
    init_db()
    get_blockchain()  # ensure genesis block exists
    get_model_service()  # load model once

    # Seed UPI Lab demo users + history (idempotent; safe on every boot).
    try:
        from app.core.demo_seed import seed_demo_users
        from app.core.governance import seed_council

        seed_demo_users()
        seed_council()  # 4-admin governance council
    except Exception:  # noqa: BLE001 - never let demo seeding block startup
        logger.exception("Demo seeding failed (Lab may be empty)")

    alerts.manager.set_loop(asyncio.get_running_loop())
    listener = asyncio.create_task(alerts.redis_alert_listener())

    # Automatic integrity self-healing watchdog (auto-detect + rollback tampering).
    from app.core.governance import integrity_watchdog

    watchdog = asyncio.create_task(integrity_watchdog())

    yield

    for task in (listener, watchdog):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Shutdown complete")


app = FastAPI(
    title="SecureFlow API",
    description="Fraud detection for UPI transactions via ML, Redis, and blockchain.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Convert unexpected errors into a consistent JSON envelope."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content=envelope(error="Internal server error"))


# REST routers
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(transaction.router, prefix=API_PREFIX)
app.include_router(transaction.risk_router, prefix=API_PREFIX)
app.include_router(blockchain.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(upi.router, prefix=API_PREFIX)
app.include_router(governance.router, prefix=API_PREFIX)

# WebSocket (no version prefix — mounted at /ws/alerts)
app.include_router(alerts.router)


@app.get("/")
def root() -> dict:
    return envelope({"name": settings.app_name, "version": __version__, "docs": "/docs"})
