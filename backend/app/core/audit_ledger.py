"""Tamper-evident audit ledger: a hash-linked, proof-of-work-sealed, append-only log.

What this is, precisely
-----------------------
Each analysed transaction (and each governance action) is appended as a *block*. A block
holds its records, a Merkle root over them, the previous block's hash, and a nonce; its
hash covers all of that. Altering any earlier record changes that block's hash, which
breaks every later ``previous_hash`` link, so **post-hoc edits are detectable** by anyone
who holds a later hash (``validate_chain`` / ``tamper_detection``). Proof-of-work (a
configurable number of leading zero hex digits) makes silently re-sealing a rewritten
history cost real CPU time per block.

What this is not
----------------
It is **not a distributed blockchain and offers no Byzantine fault tolerance.** There is a
single logical writer (this service) and no consensus protocol over the chain: whoever
controls the writer and the database can truncate or rewrite the whole chain and re-mine
it. Proof-of-work here is a speed bump and a tamper-evidence aid, not a consensus
mechanism. Anchoring the latest hash somewhere the operator cannot rewrite would be needed
for stronger guarantees.

Storage and concurrency
-----------------------
* ``storage="file"``: the whole chain is rewritten to a JSON file. **Single process only** -
  two processes would each hold their own in-memory chain and overwrite each other.
* ``storage="db"``: blocks live in the ``chain_blocks`` table. Mining is multi-process
  safe: under Postgres a transaction-scoped advisory lock serialises
  read-tip -> mine -> insert across workers; on any database the ``index`` primary key is
  the arbiter, so a losing writer gets an ``IntegrityError``, reloads the tip, and re-mines.
  The advisory lock is held for the proof-of-work, so higher difficulty means longer waits
  for other writers.

``app.core.blockchain`` re-exports the old names (``Blockchain``, ``get_blockchain``).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError

from app.core.merkle import merkle_root
from app.utils.logger import get_logger

logger = get_logger("audit_ledger")

# Arbitrary constant identifying the ledger's Postgres advisory lock.
_ADVISORY_LOCK_KEY = 0x5EC0F10A
_MAX_MINE_RETRIES = 25


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: list[dict[str, Any]]
    previous_hash: str
    nonce: int = 0
    hash: str = ""
    # Merkle root over ``transactions``. Empty for blocks sealed before it existed; those
    # keep their original hash (the field only enters the hash when present).
    merkle_root: str = ""

    def compute_hash(self) -> str:
        """SHA-256 over the block's content, excluding the stored ``hash``."""
        payload: dict[str, Any] = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        if self.merkle_root:
            payload["merkle_root"] = self.merkle_root
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Block":
        return cls(
            index=data["index"],
            timestamp=data["timestamp"],
            transactions=data["transactions"],
            previous_hash=data["previous_hash"],
            nonce=data.get("nonce", 0),
            hash=data.get("hash", ""),
            merkle_root=data.get("merkle_root") or "",
        )

    def merkle_ok(self) -> bool:
        """True if the stored Merkle root (when present) matches the records."""
        return not self.merkle_root or self.merkle_root == merkle_root(self.transactions)


class AuditLedger:
    """An append-only, hash-linked, proof-of-work-sealed log of audit records."""

    def __init__(
        self,
        path: str,
        difficulty: int = 2,
        storage: str = "file",
        pow_enabled: bool = True,
    ) -> None:
        self.path = path
        self.storage = storage  # "file" (single process) or "db" (chain_blocks table)
        self.pow_enabled = pow_enabled
        self.difficulty = max(1, difficulty) if pow_enabled else 0
        self._lock = threading.Lock()
        self.chain: list[Block] = []
        self.pending: list[dict[str, Any]] = []
        self._load_or_init()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_or_init(self) -> None:
        loaded = self._load_from_db() if self.storage == "db" else self._load_from_file()
        if not loaded:
            self._create_genesis()

    def _load_from_file(self) -> bool:
        """Load the chain from the JSON file. Returns True if a chain was loaded."""
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self.chain = [Block.from_dict(b) for b in data.get("chain", [])]
                if self.pow_enabled:
                    self.difficulty = data.get("difficulty", self.difficulty)
                if self.chain:
                    logger.info("Loaded ledger with %d block(s) from file", len(self.chain))
                    return True
            except (json.JSONDecodeError, OSError, KeyError) as exc:
                logger.error("Failed to load ledger (%s) - recreating genesis", exc)
        return False

    @staticmethod
    def _row_to_block(r: Any) -> Block:
        return Block(
            index=r.index,
            timestamp=r.timestamp,
            transactions=r.transactions,
            previous_hash=r.previous_hash,
            nonce=r.nonce,
            hash=r.hash,
            merkle_root=r.merkle_root or "",
        )

    def _load_from_db(self) -> bool:
        """Load the chain from the ``chain_blocks`` table. Returns True if loaded."""
        from sqlalchemy import select

        from app.database import ChainBlock, SessionLocal

        db = SessionLocal()
        try:
            rows = db.execute(select(ChainBlock).order_by(ChainBlock.index)).scalars().all()
            self.chain = [self._row_to_block(r) for r in rows]
            if self.chain:
                logger.info("Loaded ledger with %d block(s) from DB", len(self.chain))
                return True
        except Exception as exc:  # noqa: BLE001 - fall back to genesis on any DB error
            logger.error("Failed to load ledger from DB (%s) - recreating genesis", exc)
        finally:
            db.close()
        return False

    def _create_genesis(self) -> None:
        genesis = Block(
            index=0,
            timestamp=time.time(),
            transactions=[{"note": "SecureFlow genesis block"}],
            previous_hash="0" * 64,
        )
        genesis.merkle_root = merkle_root(genesis.transactions)
        genesis.hash = self._mine(genesis)
        self.chain = [genesis]
        if self.storage == "db":
            try:
                self._insert_block_db(genesis)
            except IntegrityError:
                # Another worker created genesis first: adopt its chain, discard ours.
                logger.info("Genesis already created by another worker - loading it")
                self._load_from_db()
        else:
            self._persist_to_file()
        logger.info("Created genesis block")

    def _persist_to_file(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)) or ".", exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {"difficulty": self.difficulty, "chain": [b.to_dict() for b in self.chain]},
                fh,
                indent=2,
                default=str,
            )
        os.replace(tmp, self.path)

    def _insert_block_db(self, block: Block, db: Any = None) -> None:
        """INSERT one block; the ``index`` primary key rejects a duplicate (``IntegrityError``)."""
        from app.database import ChainBlock, SessionLocal

        own = db is None
        db = db or SessionLocal()
        try:
            db.add(
                ChainBlock(
                    index=block.index,
                    timestamp=block.timestamp,
                    transactions=block.transactions,
                    previous_hash=block.previous_hash,
                    nonce=block.nonce,
                    hash=block.hash,
                    merkle_root=block.merkle_root,
                )
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise
        finally:
            if own:
                db.close()

    # ── Mining ───────────────────────────────────────────────────────────────

    def _mine(self, block: Block) -> str:
        """Seal ``block``: find a nonce so the hash has ``difficulty`` leading zeroes.

        With proof-of-work disabled (``difficulty == 0``) the first hash is accepted.
        """
        prefix = "0" * self.difficulty
        block.nonce = 0
        computed = block.compute_hash()
        while not computed.startswith(prefix):
            block.nonce += 1
            computed = block.compute_hash()
        return computed

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, transaction: dict[str, Any]) -> None:
        """Add a record to the pending pool (sealed on the next ``mine_block``)."""
        with self._lock:
            self.pending.append(transaction)

    def mine_block(self, transaction: Optional[dict[str, Any]] = None) -> Block:
        """Seal pending records (plus an optional one) into a new block."""
        with self._lock:
            if transaction is not None:
                self.pending.append(transaction)
            if not self.pending:
                self.pending.append({"note": "empty block"})
            records = list(self.pending)

            if self.storage == "db":
                block = self._mine_block_db(records)
            else:
                block = Block(
                    index=self.last_block.index + 1,
                    timestamp=time.time(),
                    transactions=records,
                    previous_hash=self.last_block.hash,
                    merkle_root=merkle_root(records),
                )
                block.hash = self._mine(block)
                self.chain.append(block)
                self._persist_to_file()
            self.pending = []
            logger.info("Sealed block #%d (hash %s...)", block.index, block.hash[:12])
            return block

    def _mine_block_db(self, records: list[dict[str, Any]]) -> Block:
        """Multi-process-safe append: lock -> read tip -> mine -> insert, retrying on a lost race."""
        from sqlalchemy import select, text

        from app.database import ChainBlock, SessionLocal

        for attempt in range(1, _MAX_MINE_RETRIES + 1):
            db = SessionLocal()
            try:
                if db.get_bind().dialect.name == "postgresql":
                    # Released automatically at commit/rollback. Others block here instead
                    # of wasting proof-of-work on a tip that is about to move.
                    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})

                tip = db.execute(
                    select(ChainBlock).order_by(ChainBlock.index.desc()).limit(1)
                ).scalar_one_or_none()
                if tip is not None:
                    self._sync_from_db(db, tip.index)
                prev = self.last_block

                block = Block(
                    index=prev.index + 1,
                    timestamp=time.time(),
                    transactions=records,
                    previous_hash=prev.hash,
                    merkle_root=merkle_root(records),
                )
                block.hash = self._mine(block)
                self._insert_block_db(block, db)  # commits (and so releases the advisory lock)
                self.chain.append(block)
                return block
            except IntegrityError:
                logger.info("Lost the race for block #%d (attempt %d) - reloading tip", prev.index + 1, attempt)
                continue
            finally:
                db.close()
        raise RuntimeError(f"Could not append to the ledger after {_MAX_MINE_RETRIES} attempts")

    def _sync_from_db(self, db: Any, tip_index: int) -> None:
        """Bring this process's in-memory chain up to the database tip."""
        from sqlalchemy import select

        from app.database import ChainBlock

        if self.last_block.index >= tip_index:
            return
        rows = db.execute(
            select(ChainBlock)
            .where(ChainBlock.index > self.last_block.index)
            .order_by(ChainBlock.index)
        ).scalars().all()
        for r in rows:
            self.chain.append(self._row_to_block(r))

    def sync(self) -> None:
        """Reload any blocks other processes have appended (db storage only)."""
        if self.storage != "db":
            return
        from sqlalchemy import func, select

        from app.database import ChainBlock, SessionLocal

        db = SessionLocal()
        try:
            tip = db.scalar(select(func.max(ChainBlock.index)))
            if tip is not None:
                self._sync_from_db(db, int(tip))
        finally:
            db.close()

    def get_chain(self) -> list[dict[str, Any]]:
        return [b.to_dict() for b in self.chain]

    def get_block(self, index: int) -> Optional[dict[str, Any]]:
        if 0 <= index < len(self.chain):
            return self.chain[index].to_dict()
        return None

    def validate_chain(self) -> bool:
        """True iff every block hashes correctly, links to its parent, and meets PoW."""
        prefix = "0" * self.difficulty
        for i, block in enumerate(self.chain):
            if block.hash != block.compute_hash():
                return False
            if not block.merkle_ok():
                return False
            if not block.hash.startswith(prefix):
                return False
            if i > 0 and block.previous_hash != self.chain[i - 1].hash:
                return False
        return True

    def tamper_detection(self) -> Optional[int]:
        """Return the index of the first tampered/broken block, or ``None``."""
        for i, block in enumerate(self.chain):
            if block.hash != block.compute_hash() or not block.merkle_ok():
                return i
            if i > 0 and block.previous_hash != self.chain[i - 1].hash:
                return i
        return None

    def stats(self) -> dict[str, Any]:
        total_txns = sum(len(b.transactions) for b in self.chain)
        return {
            "blocks": len(self.chain),
            "total_transactions": total_txns,
            "difficulty": self.difficulty,
            "proof_of_work": self.pow_enabled,
            "valid": self.validate_chain(),
            "genesis_timestamp": self.chain[0].timestamp if self.chain else None,
            "latest_hash": self.last_block.hash if self.chain else None,
        }


_ledger: Optional[AuditLedger] = None
_init_lock = threading.Lock()


def get_ledger() -> AuditLedger:
    """Return the process-wide ledger singleton (lazy, thread-safe)."""
    global _ledger
    if _ledger is None:
        with _init_lock:
            if _ledger is None:
                from app.config import get_settings

                settings = get_settings()
                _ledger = AuditLedger(
                    settings.blockchain_path,
                    settings.blockchain_difficulty,
                    storage=settings.blockchain_storage,
                    pow_enabled=settings.ledger_pow_enabled,
                )
    return _ledger
