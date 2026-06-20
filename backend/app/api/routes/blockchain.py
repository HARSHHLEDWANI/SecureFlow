"""Blockchain explorer endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.blockchain import get_blockchain
from app.database import User
from app.dependencies import envelope, get_current_user

router = APIRouter(prefix="/blockchain", tags=["blockchain"])


@router.get("/chain")
def get_chain(user: User = Depends(get_current_user)) -> dict:
    """Return the full audit blockchain."""
    chain = get_blockchain()
    return envelope({"length": len(chain.chain), "chain": chain.get_chain()})


@router.get("/validate")
def validate_chain(user: User = Depends(get_current_user)) -> dict:
    """Validate chain integrity and report any tampered block."""
    chain = get_blockchain()
    tampered = chain.tamper_detection()
    valid = tampered is None and chain.validate_chain()
    message = (
        "Chain is valid: all hashes link correctly and meet proof-of-work."
        if valid
        else f"Chain integrity check FAILED at block {tampered}."
    )
    return envelope({"valid": valid, "tampered_block": tampered, "message": message})


@router.get("/stats")
def chain_stats(user: User = Depends(get_current_user)) -> dict:
    """Return summary statistics for the chain."""
    return envelope(get_blockchain().stats())


@router.get("/block/{index}")
def get_block(index: int, user: User = Depends(get_current_user)) -> dict:
    """Return a single block by index."""
    block = get_blockchain().get_block(index)
    if block is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Block not found")
    return envelope(block)
