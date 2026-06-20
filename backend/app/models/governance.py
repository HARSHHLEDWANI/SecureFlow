"""Schemas for the multi-admin governance feature."""
from __future__ import annotations

from pydantic import BaseModel, Field

STATUS_PATTERN = r"^(ALLOWED|STEP_UP|BLOCKED)$"


class ProposalCreate(BaseModel):
    transaction_id: str
    proposed_status: str = Field(..., pattern=STATUS_PATTERN)
    reason: str = Field(..., min_length=3, max_length=500)


class VoteRequest(BaseModel):
    vote: str = Field(..., pattern=r"^(APPROVE|REJECT)$")


class TamperRequest(BaseModel):
    new_status: str = Field(..., pattern=STATUS_PATTERN)
