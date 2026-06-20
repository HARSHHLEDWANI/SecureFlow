"""Database connection, session management, and ORM models.

Uses SQLAlchemy 2.0 (synchronous). SQLite is used for local development and
PostgreSQL in production — selected purely by ``DATABASE_URL``.
"""
from __future__ import annotations

import enum
import os
import uuid
from datetime import datetime
from typing import Generator

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.types import JSON

from app.config import get_settings
from app.utils.helpers import utcnow

settings = get_settings()

# SQLite needs check_same_thread disabled for FastAPI's threadpool execution.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# Ensure the SQLite directory exists before the engine opens the file.
if settings.database_url.startswith("sqlite"):
    db_file = settings.database_url.split("///", 1)[-1]
    os.makedirs(os.path.dirname(os.path.abspath(db_file)) or ".", exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ── Enums ────────────────────────────────────────────────────────────────────


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class TxnType(str, enum.Enum):
    P2P = "P2P"
    P2M = "P2M"
    BILL_PAY = "BILL_PAY"


class RiskTier(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TxnStatus(str, enum.Enum):
    ALLOWED = "ALLOWED"
    STEP_UP = "STEP_UP"
    BLOCKED = "BLOCKED"


class ProposalStatus(str, enum.Enum):
    PENDING = "PENDING"    # awaiting unanimous council approval
    APPLIED = "APPLIED"    # approved by all, change committed + on-chain
    REJECTED = "REJECTED"  # at least one admin rejected
    DIVERGED = "DIVERGED"  # underlying record changed mid-vote (tamper)


class VoteType(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Models ───────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    vpa: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.VIEWER, nullable=False)
    home_city: Mapped[str] = mapped_column(String(120), default="Mumbai")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    from_vpa: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    to_vpa: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_inr: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    txn_type: Mapped[TxnType] = mapped_column(SAEnum(TxnType), nullable=False)
    device_id: Mapped[str] = mapped_column(String(120), nullable=False)
    location_lat: Mapped[float] = mapped_column(Float, nullable=False)
    location_lon: Mapped[float] = mapped_column(Float, nullable=False)

    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_tier: Mapped[RiskTier] = mapped_column(SAEnum(RiskTier), default=RiskTier.LOW)
    ml_fraud_prob: Mapped[float] = mapped_column(Float, default=0.0)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[TxnStatus] = mapped_column(SAEnum(TxnStatus), default=TxnStatus.ALLOWED)

    block_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    user: Mapped["User"] = relationship(back_populates="transactions")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="transaction")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id"), index=True, nullable=False
    )
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    block_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    transaction: Mapped["Transaction"] = relationship(back_populates="audit_logs")


class OverrideProposal(Base):
    """A proposed reversal of a transaction's fraud decision.

    Requires unanimous approval from the admin governance council before it is
    applied. ``state_hash`` snapshots the transaction's governed state at
    proposal time so divergence (out-of-band tampering) can be detected.
    """

    __tablename__ = "override_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id"), index=True, nullable=False
    )
    proposed_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    current_status: Mapped[TxnStatus] = mapped_column(SAEnum(TxnStatus), nullable=False)
    proposed_status: Mapped[TxnStatus] = mapped_column(SAEnum(TxnStatus), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(ProposalStatus), default=ProposalStatus.PENDING, index=True
    )
    required_approvals: Mapped[int] = mapped_column(Integer, default=4)
    diverged: Mapped[bool] = mapped_column(default=False)
    block_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    votes: Mapped[list["ProposalVote"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )


class ProposalVote(Base):
    """One council admin's independent attestation + vote on a proposal."""

    __tablename__ = "proposal_votes"
    __table_args__ = (UniqueConstraint("proposal_id", "admin_id", name="uq_vote_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("override_proposals.id"), index=True, nullable=False
    )
    admin_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    vote: Mapped[VoteType] = mapped_column(SAEnum(VoteType), nullable=False)
    attested_state_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    diverged: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    proposal: Mapped["OverrideProposal"] = relationship(back_populates="votes")


def init_db() -> None:
    """Create all tables if they do not yet exist (idempotent)."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session, closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
