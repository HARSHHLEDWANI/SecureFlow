"""Blockchain response schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class BlockOut(BaseModel):
    index: int
    timestamp: float
    transactions: list[dict[str, Any]]
    previous_hash: str
    nonce: int
    hash: str


class ChainOut(BaseModel):
    length: int
    chain: list[BlockOut]


class ChainValidation(BaseModel):
    valid: bool
    tampered_block: int | None = None
    message: str


class ChainStats(BaseModel):
    blocks: int
    total_transactions: int
    difficulty: int
    valid: bool
    genesis_timestamp: float | None = None
    latest_hash: str | None = None
