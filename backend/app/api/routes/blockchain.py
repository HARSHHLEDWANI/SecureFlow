"""Audit-ledger explorer endpoints.

Primary prefix ``/audit-ledger``; ``/blockchain`` is kept as a hidden alias so existing
clients keep working. Both serve the same handlers. The ledger is a hash-linked,
proof-of-work-sealed append-only log: tamper-evident, not a distributed blockchain
(see ``app/core/audit_ledger.py``).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.audit_ledger import get_ledger
from app.database import User
from app.dependencies import envelope, require_staff

router = APIRouter(prefix="/audit-ledger", tags=["audit-ledger"])
legacy_router = APIRouter(prefix="/blockchain", include_in_schema=False)


def get_chain(user: User = Depends(require_staff)) -> dict:
    """Return the full audit ledger."""
    chain = get_ledger()
    return envelope({"length": len(chain.chain), "chain": chain.get_chain()})


def validate_chain(user: User = Depends(require_staff)) -> dict:
    """Validate ledger integrity and report any tampered block."""
    chain = get_ledger()
    tampered = chain.tamper_detection()
    valid = tampered is None and chain.validate_chain()
    message = (
        "Ledger is valid: all hashes link correctly, Merkle roots match, and blocks meet the sealing difficulty."
        if valid
        else f"Ledger integrity check FAILED at block {tampered}."
    )
    return envelope({"valid": valid, "tampered_block": tampered, "message": message})


def chain_stats(user: User = Depends(require_staff)) -> dict:
    """Return summary statistics for the ledger."""
    return envelope(get_ledger().stats())


def get_block(index: int, user: User = Depends(require_staff)) -> dict:
    """Return a single block by index."""
    block = get_ledger().get_block(index)
    if block is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Block not found")
    return envelope(block)


for _r in (router, legacy_router):
    _r.get("/chain")(get_chain)
    _r.get("/validate")(validate_chain)
    _r.get("/stats")(chain_stats)
    _r.get("/block/{index}")(get_block)
