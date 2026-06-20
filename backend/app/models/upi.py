"""Schemas for the UPI Simulation Lab."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

VPA_PATTERN = r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$"


class UPIPayRequest(BaseModel):
    sender_vpa: str = Field(..., pattern=VPA_PATTERN)
    receiver_vpa: str = Field(..., pattern=VPA_PATTERN)
    amount_inr: float = Field(..., gt=0, le=10_000_000)
    txn_type: str = Field(default="P2P", pattern=r"^(P2P|P2M|BILL_PAY)$")
    note: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, max_length=60)
    device_id: Optional[str] = Field(default=None, max_length=120)


class UPIPayResult(BaseModel):
    txn_id: str
    sender_vpa: str
    receiver_vpa: str
    amount_inr: float
    txn_type: str
    note: Optional[str] = None
    decision: str          # APPROVED | STEP_UP | BLOCKED
    decision_label: str    # human-friendly
    risk_score: int
    risk_tier: str
    ml_fraud_prob: float
    anomaly_score: float
    ml_confidence: float
    components: dict[str, float]
    feature_contributions: list[dict[str, Any]]
    block_index: Optional[int] = None
    block_hash: Optional[str] = None
    recommended_action: str
    total_duration_ms: float
    pipeline: dict[str, Any]
    created_at: str
