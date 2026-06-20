"""Transaction analysis schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TransactionAnalyzeRequest(BaseModel):
    to_vpa: str = Field(..., pattern=r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$")
    amount_inr: float = Field(..., gt=0, le=10_000_000)
    txn_type: str = Field(default="P2P", pattern=r"^(P2P|P2M|BILL_PAY)$")
    device_id: str = Field(default="web-default", max_length=120)
    location_lat: float = Field(default=19.0760, ge=-90, le=90)
    location_lon: float = Field(default=72.8777, ge=-180, le=180)


class RiskComponents(BaseModel):
    ml_fraud: float
    anomaly: float
    velocity: float
    geo: float
    new_device: float
    amount: float
    time: float


class FeatureContribution(BaseModel):
    feature: str
    value: float
    importance: float


class TransactionResult(BaseModel):
    id: str
    from_vpa: str
    to_vpa: str
    amount_inr: float
    txn_type: str
    risk_score: int
    risk_tier: str
    status: str
    ml_fraud_prob: float
    anomaly_score: float
    ml_confidence: float
    components: RiskComponents
    feature_contributions: list[FeatureContribution]
    block_index: Optional[int] = None
    block_hash: Optional[str] = None
    recommended_action: str
    created_at: datetime


class TransactionSummary(BaseModel):
    id: str
    from_vpa: str
    to_vpa: str
    amount_inr: float
    txn_type: str
    risk_score: int
    risk_tier: str
    status: str
    block_hash: Optional[str] = None
    created_at: datetime


class UserRiskProfile(BaseModel):
    user_id: str
    transaction_count: int
    average_risk_score: float
    flagged_count: int
    last_risk_score: Optional[int] = None
    cached: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)
