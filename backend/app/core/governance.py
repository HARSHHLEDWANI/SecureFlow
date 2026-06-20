"""Multi-admin consensus governance for fraud-decision overrides.

Reversing a transaction's fraud decision (e.g. unblocking a BLOCKED payment) is
the most security-sensitive admin action in SecureFlow — a single compromised
admin could quietly wave through fraud. This module makes that impossible
without collusion:

  * A change is a *proposal*, not an immediate write.
  * It commits only on **unanimous approval** from the admin council.
  * Each vote independently attests to the record's current state hash, so any
    out-of-band tampering between proposal and vote is detected (divergence).
  * Applied overrides are sealed onto the blockchain. The chain is the source of
    truth: an :func:`verify_integrity` post-check compares the live DB against
    the on-chain agreed state and :func:`rollback_from_chain` restores it if a
    rogue admin edited the database directly — the blockchain's immutability is
    what makes the rollback authoritative.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.blockchain import get_blockchain
from app.core.security import hash_password
from app.database import (
    AuditLog,
    OverrideProposal,
    ProposalStatus,
    ProposalVote,
    Role,
    SessionLocal,
    Transaction,
    TxnStatus,
    User,
    VoteType,
)
from app.utils.helpers import stable_hash, utcnow
from app.utils.logger import get_logger

logger = get_logger("governance")

COUNCIL_PASSWORD = "council123"  # demo only — shared password for the 4 council admins

# The fixed 4-member governance council (real, separately-loggable admin accounts).
# Uses a real TLD (.io) because login validates with EmailStr, which rejects the
# reserved ``.local`` domain used by the lab demo users.
GOVERNANCE_COUNCIL: list[dict[str, str]] = [
    {"email": "admin1@secureflow.io", "vpa": "council.aarav@upi", "name": "Aarav (Council)"},
    {"email": "admin2@secureflow.io", "vpa": "council.diya@upi", "name": "Diya (Council)"},
    {"email": "admin3@secureflow.io", "vpa": "council.kabir@upi", "name": "Kabir (Council)"},
    {"email": "admin4@secureflow.io", "vpa": "council.meera@upi", "name": "Meera (Council)"},
]
COUNCIL_EMAILS = {c["email"] for c in GOVERNANCE_COUNCIL}


class GovernanceError(ValueError):
    """Raised for invalid governance operations (mapped to HTTP 400/403)."""


# ── Council membership ────────────────────────────────────────────────────────


def seed_council() -> int:
    """Idempotently create the 4 council admin accounts. Returns count created."""
    db: Session = SessionLocal()
    created = 0
    try:
        for spec in GOVERNANCE_COUNCIL:
            exists = db.scalar(select(User).where(User.email == spec["email"]))
            if exists:
                continue
            db.add(
                User(
                    email=spec["email"],
                    password_hash=hash_password(COUNCIL_PASSWORD),
                    vpa=spec["vpa"],
                    role=Role.ADMIN,
                    home_city="Mumbai",
                )
            )
            created += 1
        db.commit()
        if created:
            logger.info("Seeded %d governance council admins", created)
        return created
    finally:
        db.close()


def council_members(db: Session) -> list[User]:
    return list(
        db.execute(select(User).where(User.email.in_(COUNCIL_EMAILS))).scalars()
    )


def council_size(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(User.email.in_(COUNCIL_EMAILS))
    ) or 0


def is_council(user: User) -> bool:
    return user.email in COUNCIL_EMAILS


def main_admin(db: Session) -> Optional[User]:
    """The primary admin: the oldest real (non-seeded) ADMIN account.

    This is the first human who registered and was auto-promoted to ADMIN.
    Seeded system accounts (lab demo users + the council) are excluded.
    """
    return db.execute(
        select(User)
        .where(
            User.role == Role.ADMIN,
            ~User.email.like("%@secureflow.io"),
            ~User.email.like("%@secureflow.local"),
        )
        .order_by(User.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()


def is_main_admin(db: Session, user: User) -> bool:
    m = main_admin(db)
    return m is not None and m.id == user.id


def has_governance_access(db: Session, user: User) -> bool:
    """Only the council members and the main admin may use governance."""
    return is_council(user) or is_main_admin(db, user)


def _system_actor(db: Session) -> Optional[User]:
    """A real user id to attribute automatic actions to (audit FK requires one)."""
    admin = main_admin(db)
    if admin is not None:
        return admin
    members = council_members(db)
    return members[0] if members else None


# ── Governed state + immutable checkpoint ─────────────────────────────────────


def governed_state(txn: Transaction) -> dict[str, Any]:
    """The transaction fields under governance (what tampering would touch)."""
    return {
        "transaction_id": txn.id,
        "status": txn.status.value,
        "risk_tier": txn.risk_tier.value,
        "risk_score": txn.risk_score,
    }


def state_hash(txn: Transaction) -> str:
    return stable_hash(governed_state(txn))


def agreed_state_from_chain(txn_id: str) -> Optional[dict[str, Any]]:
    """The last consensus-agreed governed state for a txn, read off the chain.

    Scans every block for records referencing this transaction (the original
    analyze block and any applied-override blocks) and returns the newest one's
    governed fields. This is the immutable source of truth used to detect and
    repair tampering.
    """
    latest: Optional[tuple[int, dict[str, Any]]] = None
    for block in get_blockchain().chain:
        for rec in block.transactions:
            if isinstance(rec, dict) and rec.get("transaction_id") == txn_id:
                if latest is None or block.index >= latest[0]:
                    latest = (block.index, rec)
    if latest is None:
        return None
    rec = latest[1]
    if "status" not in rec:
        return None
    return {
        "transaction_id": txn_id,
        "status": rec["status"],
        "risk_tier": rec.get("risk_tier"),
        "risk_score": rec.get("risk_score"),
    }


# ── Proposals ─────────────────────────────────────────────────────────────────


def create_proposal(
    db: Session, proposer: User, txn_id: str, proposed_status: str, reason: str
) -> OverrideProposal:
    if not is_council(proposer):
        raise GovernanceError("Only governance council admins may propose overrides")
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise GovernanceError("Transaction not found")
    try:
        target = TxnStatus(proposed_status)
    except ValueError:
        raise GovernanceError(f"Invalid proposed status '{proposed_status}'")
    if target == txn.status:
        raise GovernanceError("Proposed decision is identical to the current one")
    if not reason or len(reason.strip()) < 3:
        raise GovernanceError("A justification (reason) is required")

    # Block a second open proposal for the same transaction.
    open_exists = db.scalar(
        select(func.count())
        .select_from(OverrideProposal)
        .where(
            OverrideProposal.transaction_id == txn_id,
            OverrideProposal.status == ProposalStatus.PENDING,
        )
    )
    if open_exists:
        raise GovernanceError("An open proposal already exists for this transaction")

    proposal = OverrideProposal(
        transaction_id=txn_id,
        proposed_by=proposer.id,
        current_status=txn.status,
        proposed_status=target,
        reason=reason.strip(),
        state_hash=state_hash(txn),
        required_approvals=max(council_size(db), 1),
    )
    db.add(proposal)
    db.flush()
    # The proposer implicitly casts the first APPROVE.
    _record_vote(db, proposal, proposer, txn, VoteType.APPROVE)
    db.commit()
    db.refresh(proposal)
    logger.info("Proposal %s created by %s (%s→%s)", proposal.id, proposer.email,
                proposal.current_status.value, target.value)
    return proposal


def cast_vote(db: Session, admin: User, proposal_id: str, vote: str) -> OverrideProposal:
    if not is_council(admin):
        raise GovernanceError("Only governance council admins may vote")
    proposal = db.get(OverrideProposal, proposal_id)
    if proposal is None:
        raise GovernanceError("Proposal not found")
    if proposal.status != ProposalStatus.PENDING:
        raise GovernanceError(f"Proposal is already {proposal.status.value}")

    already = db.scalar(
        select(ProposalVote).where(
            ProposalVote.proposal_id == proposal_id, ProposalVote.admin_id == admin.id
        )
    )
    if already is not None:
        raise GovernanceError("You have already voted on this proposal")

    try:
        vt = VoteType(vote)
    except ValueError:
        raise GovernanceError(f"Invalid vote '{vote}'")

    txn = db.get(Transaction, proposal.transaction_id)
    if txn is None:
        raise GovernanceError("Transaction no longer exists")

    _record_vote(db, proposal, admin, txn, vt)
    _evaluate(db, proposal, txn)
    db.commit()
    db.refresh(proposal)
    return proposal


def _record_vote(
    db: Session, proposal: OverrideProposal, admin: User, txn: Transaction, vote: VoteType
) -> ProposalVote:
    """Record a vote with the admin's independent attestation of current state."""
    attested = state_hash(txn)
    diverged = attested != proposal.state_hash
    pv = ProposalVote(
        proposal_id=proposal.id,
        admin_id=admin.id,
        vote=vote,
        attested_state_hash=attested,
        diverged=diverged,
    )
    db.add(pv)
    if diverged:
        # The record changed since the proposal was raised — treat as tampering.
        proposal.diverged = True
        logger.warning("Divergence on proposal %s: %s's view differs from snapshot",
                       proposal.id, admin.email)
    db.flush()
    return pv


def _evaluate(db: Session, proposal: OverrideProposal, txn: Transaction) -> None:
    """Resolve the proposal once enough votes are in (unanimous rule)."""
    votes = list(
        db.execute(
            select(ProposalVote).where(ProposalVote.proposal_id == proposal.id)
        ).scalars()
    )
    if any(v.vote == VoteType.REJECT for v in votes):
        proposal.status = ProposalStatus.REJECTED
        proposal.resolved_at = utcnow()
        _audit(db, proposal, txn, "GOVERNANCE_REJECTED", None)
        logger.info("Proposal %s REJECTED", proposal.id)
        return

    if proposal.diverged:
        proposal.status = ProposalStatus.DIVERGED
        proposal.resolved_at = utcnow()
        _audit(db, proposal, txn, "GOVERNANCE_DIVERGED", None)
        logger.warning("Proposal %s DIVERGED — change discarded", proposal.id)
        return

    approvals = sum(1 for v in votes if v.vote == VoteType.APPROVE)
    if approvals >= proposal.required_approvals:
        _apply(db, proposal, txn)


def _apply(db: Session, proposal: OverrideProposal, txn: Transaction) -> None:
    """Commit a unanimously-approved override and seal it on-chain."""
    # Final guard: ensure nobody mutated the record between the last vote and now.
    if state_hash(txn) != proposal.state_hash:
        proposal.status = ProposalStatus.DIVERGED
        proposal.diverged = True
        proposal.resolved_at = utcnow()
        _audit(db, proposal, txn, "GOVERNANCE_DIVERGED", None)
        return

    old_status = txn.status.value
    txn.status = proposal.proposed_status

    block = get_blockchain().mine_block(
        {
            "kind": "GOVERNANCE_OVERRIDE",
            "proposal_id": proposal.id,
            "transaction_id": txn.id,
            # Full governed state so the chain remains a complete checkpoint.
            "status": txn.status.value,
            "risk_tier": txn.risk_tier.value,
            "risk_score": txn.risk_score,
            "previous_status": old_status,
            "approved_by": [v.admin_id for v in proposal.votes if v.vote == VoteType.APPROVE],
        }
    )
    proposal.status = ProposalStatus.APPLIED
    proposal.block_index = block.index
    proposal.block_hash = block.hash
    proposal.resolved_at = utcnow()
    _audit(db, proposal, txn, "GOVERNANCE_APPLIED", block.hash)
    logger.info("Proposal %s APPLIED (%s→%s) block #%d",
                proposal.id, old_status, txn.status.value, block.index)


def _audit(
    db: Session, proposal: OverrideProposal, txn: Transaction, action: str, block_hash: Optional[str]
) -> None:
    db.add(
        AuditLog(
            transaction_id=txn.id,
            actor_id=proposal.proposed_by,
            action=action,
            risk_score=txn.risk_score,
            block_hash=block_hash,
            audit_metadata={
                "proposal_id": proposal.id,
                "from": proposal.current_status.value,
                "to": proposal.proposed_status.value,
            },
        )
    )


# ── Integrity (post-check) + rollback ─────────────────────────────────────────


def verify_integrity(db: Session, txn_id: str) -> dict[str, Any]:
    """Compare the live DB record against the immutable on-chain agreed state."""
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise GovernanceError("Transaction not found")
    agreed = agreed_state_from_chain(txn_id)
    current = governed_state(txn)
    if agreed is None:
        return {"transaction_id": txn_id, "verified": True, "tampered": False,
                "reason": "no on-chain checkpoint", "current": current, "agreed": None}

    tampered = (
        str(agreed.get("status")) != current["status"]
        or str(agreed.get("risk_tier")) != current["risk_tier"]
        or int(agreed.get("risk_score") or 0) != current["risk_score"]
    )
    return {
        "transaction_id": txn_id,
        "verified": not tampered,
        "tampered": tampered,
        "current": current,
        "agreed": agreed,
    }


def rollback_from_chain(
    db: Session, txn_id: str, actor: Optional[User], *, auto: bool = False
) -> dict[str, Any]:
    """Restore a tampered transaction to its on-chain agreed state.

    ``auto=True`` attributes the action to the watchdog (system actor) and emits
    a live alert, used by the automatic self-healing loop.
    """
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise GovernanceError("Transaction not found")
    agreed = agreed_state_from_chain(txn_id)
    if agreed is None:
        raise GovernanceError("No on-chain checkpoint to restore from")

    actor_id = actor.id if actor is not None else None
    if actor_id is None:
        sys_actor = _system_actor(db)
        actor_id = sys_actor.id if sys_actor is not None else None
    if actor_id is None:
        raise GovernanceError("No actor available to attribute the rollback")

    before = governed_state(txn)
    txn.status = TxnStatus(agreed["status"])
    if agreed.get("risk_tier") is not None:
        from app.database import RiskTier

        txn.risk_tier = RiskTier(agreed["risk_tier"])
    if agreed.get("risk_score") is not None:
        txn.risk_score = int(agreed["risk_score"])

    block = get_blockchain().mine_block(
        {
            "kind": "GOVERNANCE_AUTOHEAL" if auto else "GOVERNANCE_ROLLBACK",
            "transaction_id": txn.id,
            "status": txn.status.value,
            "risk_tier": txn.risk_tier.value,
            "risk_score": txn.risk_score,
            "restored_from_block": agreed.get("status"),
        }
    )
    db.add(
        AuditLog(
            transaction_id=txn.id,
            actor_id=actor_id,
            action="GOVERNANCE_AUTOHEAL" if auto else "GOVERNANCE_ROLLBACK",
            risk_score=txn.risk_score,
            block_hash=block.hash,
            audit_metadata={"before": before, "after": governed_state(txn), "auto": auto},
        )
    )
    db.commit()
    logger.warning("%s txn %s to on-chain state (block #%d)",
                   "Auto-healed" if auto else "Rolled back", txn_id, block.index)
    return {"transaction_id": txn_id, "restored": True, "auto": auto, "before": before,
            "after": governed_state(txn), "block_index": block.index}


def _is_tampered(txn: Transaction, agreed: dict[str, Any]) -> bool:
    cur = governed_state(txn)
    return (
        str(agreed.get("status")) != cur["status"]
        or str(agreed.get("risk_tier")) != cur["risk_tier"]
        or int(agreed.get("risk_score") or 0) != cur["risk_score"]
    )


# ── Automatic self-healing watchdog ───────────────────────────────────────────

watchdog_state: dict[str, Any] = {
    "enabled": False,
    "interval_seconds": 0,
    "last_run": None,
    "runs": 0,
    "checked": 0,
    "healed_total": 0,
    "recent": [],  # last few auto-heal events
}


def scan_and_heal_once() -> dict[str, Any]:
    """Verify every chain-anchored transaction and auto-restore any tampering.

    This is the automatic "post-check with the others, and if it differs go back
    to the backup" — the blockchain is the immutable backup. Returns a summary.
    """
    db: Session = SessionLocal()
    healed: list[dict[str, Any]] = []
    checked = 0
    try:
        txns = db.execute(select(Transaction)).scalars().all()
        for txn in txns:
            agreed = agreed_state_from_chain(txn.id)
            if agreed is None:
                continue  # no on-chain checkpoint (e.g. pre-seeded history)
            checked += 1
            if _is_tampered(txn, agreed):
                res = rollback_from_chain(db, txn.id, None, auto=True)
                event = {
                    "transaction_id": txn.id,
                    "from_status": res["before"]["status"],
                    "to_status": res["after"]["status"],
                    "block_index": res["block_index"],
                    "at": utcnow().isoformat(),
                }
                healed.append(event)
                _emit_heal_alert(txn, event)
    finally:
        db.close()

    watchdog_state["last_run"] = utcnow().isoformat()
    watchdog_state["runs"] += 1
    watchdog_state["checked"] = checked
    watchdog_state["healed_total"] += len(healed)
    if healed:
        watchdog_state["recent"] = (healed + watchdog_state["recent"])[:10]
    return {"checked": checked, "healed": healed}


def _emit_heal_alert(txn: Transaction, event: dict[str, Any]) -> None:
    """Push a live alert so the dashboard/governance UI sees auto-heals in real time."""
    try:
        from app.api.websockets.alerts import dispatch_alert

        dispatch_alert(
            {
                "type": "integrity_autoheal",
                "transaction_id": txn.id,
                "from_status": event["from_status"],
                "to_status": event["to_status"],
                "block_index": event["block_index"],
                "created_at": event["at"],
            }
        )
    except Exception:  # noqa: BLE001 - alerting is best-effort
        logger.debug("auto-heal alert dispatch failed", exc_info=True)


async def integrity_watchdog() -> None:
    """Background loop: periodically scan + self-heal tampered records."""
    import asyncio

    from app.config import get_settings

    settings = get_settings()
    if not settings.integrity_watchdog_enabled:
        logger.info("Integrity watchdog disabled")
        return

    interval = max(5, settings.integrity_watchdog_interval_seconds)
    watchdog_state["enabled"] = True
    watchdog_state["interval_seconds"] = interval
    logger.info("Integrity watchdog active (every %ds)", interval)

    loop = asyncio.get_running_loop()
    while True:
        try:
            await asyncio.sleep(interval)
            summary = await loop.run_in_executor(None, scan_and_heal_once)
            if summary["healed"]:
                logger.warning("Watchdog auto-healed %d tampered record(s)", len(summary["healed"]))
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001 - never let the watchdog die
            logger.exception("Integrity watchdog cycle failed")
    watchdog_state["enabled"] = False


def simulate_tamper(db: Session, txn_id: str, new_status: str) -> dict[str, Any]:
    """DEMO-ONLY: rogue direct DB edit that bypasses consensus, to show detection."""
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise GovernanceError("Transaction not found")
    try:
        target = TxnStatus(new_status)
    except ValueError:
        raise GovernanceError(f"Invalid status '{new_status}'")
    before = txn.status.value
    txn.status = target  # deliberately NOT mined onto the chain
    db.commit()
    logger.warning("DEMO tamper: txn %s status %s→%s (no consensus, no chain)",
                   txn_id, before, target.value)
    return {"transaction_id": txn_id, "tampered_to": target.value, "was": before}
