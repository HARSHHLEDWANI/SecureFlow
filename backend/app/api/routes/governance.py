"""Multi-admin consensus governance endpoints (ADMIN-gated).

Council admins propose and unanimously approve fraud-decision overrides; the
blockchain anchors the result and an integrity post-check repairs any out-of-band
tampering. See :mod:`app.core.governance`.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import governance as gov
from app.database import OverrideProposal, ProposalStatus, Transaction, User, get_db
from app.dependencies import envelope, get_current_user
from app.models.governance import ProposalCreate, TamperRequest, VoteRequest
from app.utils.logger import get_logger

logger = get_logger("governance_api")
router = APIRouter(prefix="/governance", tags=["governance"])


def gov_access(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    """Allow only the governance council and the main admin."""
    if not gov.has_governance_access(db, user):
        from fastapi import status as st

        raise HTTPException(
            st.HTTP_403_FORBIDDEN,
            "Governance is restricted to the council and the main admin",
        )
    return user


AdminOnly = Depends(gov_access)


def _vote_dict(v) -> dict[str, Any]:
    return {
        "admin_id": v.admin_id,
        "vote": v.vote.value,
        "diverged": v.diverged,
        "attested_state_hash": v.attested_state_hash,
        "created_at": v.created_at.isoformat(),
    }


def _proposal_dict(db: Session, p: OverrideProposal, *, full: bool = False) -> dict[str, Any]:
    txn = db.get(Transaction, p.transaction_id)
    approvals = sum(1 for v in p.votes if v.vote.value == "APPROVE")
    rejects = sum(1 for v in p.votes if v.vote.value == "REJECT")
    out: dict[str, Any] = {
        "id": p.id,
        "transaction_id": p.transaction_id,
        "proposed_by": p.proposed_by,
        "current_status": p.current_status.value,
        "proposed_status": p.proposed_status.value,
        "reason": p.reason,
        "status": p.status.value,
        "required_approvals": p.required_approvals,
        "approvals": approvals,
        "rejects": rejects,
        "diverged": p.diverged,
        "block_index": p.block_index,
        "block_hash": p.block_hash,
        "created_at": p.created_at.isoformat(),
        "resolved_at": p.resolved_at.isoformat() if p.resolved_at else None,
        "txn": None
        if txn is None
        else {
            "from_vpa": txn.from_vpa,
            "to_vpa": txn.to_vpa,
            "amount_inr": float(txn.amount_inr),
            "risk_score": txn.risk_score,
            "risk_tier": txn.risk_tier.value,
            "status": txn.status.value,
        },
    }
    if full:
        out["votes"] = [_vote_dict(v) for v in p.votes]
    return out


@router.get("/council")
def council(db: Session = Depends(get_db), _: User = AdminOnly) -> dict:
    """The governance council roster (and demo login password)."""
    members = [
        {"id": u.id, "name": _name_for(u.email), "email": u.email, "vpa": u.vpa, "role": u.role.value}
        for u in gov.council_members(db)
    ]
    return envelope(
        {
            "members": members,
            "size": len(members),
            "threshold": "unanimous",
            "demo_password": gov.COUNCIL_PASSWORD,
        }
    )


def _name_for(email: str) -> str:
    for c in gov.GOVERNANCE_COUNCIL:
        if c["email"] == email:
            return c["name"]
    return email


@router.get("/proposals")
def list_proposals(
    db: Session = Depends(get_db),
    _: User = AdminOnly,
    status_filter: Optional[str] = Query(default=None, alias="status",
                                         pattern=r"^(PENDING|APPLIED|REJECTED|DIVERGED)$"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    stmt = select(OverrideProposal).order_by(OverrideProposal.created_at.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(OverrideProposal.status == ProposalStatus(status_filter))
    rows = db.execute(stmt).scalars().all()
    return envelope([_proposal_dict(db, p) for p in rows])


@router.post("/proposals", status_code=status.HTTP_201_CREATED)
def create_proposal(
    body: ProposalCreate, db: Session = Depends(get_db), user: User = AdminOnly
) -> dict:
    try:
        p = gov.create_proposal(db, user, body.transaction_id, body.proposed_status, body.reason)
    except gov.GovernanceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return envelope(_proposal_dict(db, p, full=True))


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str, db: Session = Depends(get_db), _: User = AdminOnly) -> dict:
    p = db.get(OverrideProposal, proposal_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    return envelope(_proposal_dict(db, p, full=True))


@router.post("/proposals/{proposal_id}/vote")
def vote(
    proposal_id: str, body: VoteRequest, db: Session = Depends(get_db), user: User = AdminOnly
) -> dict:
    try:
        p = gov.cast_vote(db, user, proposal_id, body.vote)
    except gov.GovernanceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return envelope(_proposal_dict(db, p, full=True))


@router.get("/integrity/{txn_id}")
def integrity(txn_id: str, db: Session = Depends(get_db), _: User = AdminOnly) -> dict:
    try:
        return envelope(gov.verify_integrity(db, txn_id))
    except gov.GovernanceError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.post("/integrity/{txn_id}/rollback")
def rollback(txn_id: str, db: Session = Depends(get_db), user: User = AdminOnly) -> dict:
    try:
        return envelope(gov.rollback_from_chain(db, txn_id, user))
    except gov.GovernanceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.post("/integrity/{txn_id}/simulate-tamper")
def simulate_tamper(
    txn_id: str, body: TamperRequest, db: Session = Depends(get_db), _: User = AdminOnly
) -> dict:
    """DEMO: a rogue admin edits the DB directly, bypassing consensus + chain."""
    try:
        return envelope(gov.simulate_tamper(db, txn_id, body.new_status))
    except gov.GovernanceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/watchdog")
def watchdog_status(_: User = AdminOnly) -> dict:
    """State of the automatic integrity self-healing watchdog."""
    return envelope(gov.watchdog_state)


@router.post("/watchdog/scan")
def watchdog_scan(_: User = AdminOnly) -> dict:
    """Run one integrity scan immediately (auto-heals any tampering found)."""
    return envelope(gov.scan_and_heal_once())
