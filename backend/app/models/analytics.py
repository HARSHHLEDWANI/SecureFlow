"""Analytics + health schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_transactions: int
    fraud_detected: int
    fraud_rate: float
    average_risk_score: float
    blocked_count: int
    step_up_count: int
    tier_distribution: dict[str, int]
    daily_volume: list[dict[str, Any]]
    risk_score_histogram: list[dict[str, Any]]


class AlertOut(BaseModel):
    transaction_id: str
    from_vpa: str
    to_vpa: str
    amount_inr: float
    risk_score: int
    risk_tier: str
    status: str
    created_at: str


class HealthStatus(BaseModel):
    status: str
    version: str
    redis: bool
    database: bool
    model_loaded: bool
    model_version: str | None = None
    blockchain_blocks: int
