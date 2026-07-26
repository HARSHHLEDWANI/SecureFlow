"""A minimal but genuine proof-of-work blockchain for audit logging.

Each analysed transaction is recorded as an immutable block. Blocks are linked
by SHA-256 hashes and sealed with proof-of-work (a configurable number of
leading zeroes). The chain is persisted to disk as JSON so it survives
restarts, and exposes integrity validation + tamper detection.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

from app.utils.logger import get_logger

logger = get_logger("blockchain")


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: list[dict[str, Any]]
    previous_hash: str
    nonce: int = 0
    hash: str = ""

    def compute_hash(self) -> str:
        """SHA-256 over the block's content, excluding the stored ``hash``."""
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
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
        )


class Blockchain:
    """An append-only, proof-of-work secured chain of audit records."""

    def __init__(self, path: str, difficulty: int = 2, storage: str = "file") -> None:
        self.path = path
        self.storage = storage  # "file" (local JSON) or "db" (chain_blocks table)
        self.difficulty = max(1, difficulty)
        self._lock = threading.Lock()
        self.chain: list[Block] = []
        self.pending: list[dict[str, Any]] = []
        self._load_or_init()

    # ── Persistence ──────────────────────────────────────────────────────────
    #
    # Two interchangeable backends. "file" writes the whole chain to JSON on disk
    # (fast, zero-dependency — used in dev/tests). "db" appends blocks to a
    # ``chain_blocks`` table in the persistent database (used in production so the
    # audit trail survives redeploys on ephemeral hosting). In both cases the
    # in-memory hashing / proof-of-work / tamper-detection logic is identical.

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
                self.difficulty = data.get("difficulty", self.difficulty)
                if self.chain:
                    logger.info("Loaded blockchain with %d block(s) from file", len(self.chain))
                    return True
            except (json.JSONDecodeError, OSError, KeyError) as exc:
                logger.error("Failed to load chain (%s) - recreating genesis", exc)
        return False

    def _load_from_db(self) -> bool:
        """Load the chain from the ``chain_blocks`` table. Returns True if loaded."""
        from sqlalchemy import select

        from app.database import ChainBlock, SessionLocal

        db = SessionLocal()
        try:
            rows = db.execute(select(ChainBlock).order_by(ChainBlock.index)).scalars().all()
            self.chain = [
                Block(
                    index=r.index,
                    timestamp=r.timestamp,
                    transactions=r.transactions,
                    previous_hash=r.previous_hash,
                    nonce=r.nonce,
                    hash=r.hash,
                )
                for r in rows
            ]
            if self.chain:
                logger.info("Loaded blockchain with %d block(s) from DB", len(self.chain))
                return True
        except Exception as exc:  # noqa: BLE001 - fall back to genesis on any DB error
            logger.error("Failed to load chain from DB (%s) - recreating genesis", exc)
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
        genesis.hash = self._mine(genesis)
        self.chain = [genesis]
        self._persist()
        logger.info("Created genesis block")

    def _persist(self) -> None:
        if self.storage == "db":
            self._persist_to_db()
        else:
            self._persist_to_file()

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

    def _persist_to_db(self) -> None:
        """Append any not-yet-persisted blocks to the DB (the chain is append-only)."""
        from sqlalchemy import func, select

        from app.database import ChainBlock, SessionLocal

        db = SessionLocal()
        try:
            max_index = db.scalar(select(func.max(ChainBlock.index)))
            start = -1 if max_index is None else int(max_index)
            for block in self.chain:
                if block.index > start:
                    db.add(
                        ChainBlock(
                            index=block.index,
                            timestamp=block.timestamp,
                            transactions=block.transactions,
                            previous_hash=block.previous_hash,
                            nonce=block.nonce,
                            hash=block.hash,
                        )
                    )
            db.commit()
        finally:
            db.close()

    # ── Mining ───────────────────────────────────────────────────────────────

    def _mine(self, block: Block) -> str:
        """Brute-force a nonce until the hash has ``difficulty`` leading zeroes."""
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
        """Add a record to the pending pool (mined on the next ``mine_block``)."""
        with self._lock:
            self.pending.append(transaction)

    def mine_block(self, transaction: Optional[dict[str, Any]] = None) -> Block:
        """Seal pending transactions (plus an optional one) into a new block."""
        with self._lock:
            if transaction is not None:
                self.pending.append(transaction)
            if not self.pending:
                self.pending.append({"note": "empty block"})

            block = Block(
                index=self.last_block.index + 1,
                timestamp=time.time(),
                transactions=list(self.pending),
                previous_hash=self.last_block.hash,
            )
            block.hash = self._mine(block)
            self.chain.append(block)
            self.pending = []
            self._persist()
            logger.info("Mined block #%d (hash %s...)", block.index, block.hash[:12])
            return block

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
            if not block.hash.startswith(prefix):
                return False
            if i > 0 and block.previous_hash != self.chain[i - 1].hash:
                return False
        return True

    def tamper_detection(self) -> Optional[int]:
        """Return the index of the first tampered/broken block, or ``None``."""
        for i, block in enumerate(self.chain):
            if block.hash != block.compute_hash():
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
            "valid": self.validate_chain(),
            "genesis_timestamp": self.chain[0].timestamp if self.chain else None,
            "latest_hash": self.last_block.hash if self.chain else None,
        }


_blockchain: Optional[Blockchain] = None
_init_lock = threading.Lock()


def get_blockchain() -> Blockchain:
    """Return the process-wide blockchain singleton (lazy, thread-safe)."""
    global _blockchain
    if _blockchain is None:
        with _init_lock:
            if _blockchain is None:
                from app.config import get_settings

                settings = get_settings()
                _blockchain = Blockchain(
                    settings.blockchain_path,
                    settings.blockchain_difficulty,
                    storage=settings.blockchain_storage,
                )
    return _blockchain
