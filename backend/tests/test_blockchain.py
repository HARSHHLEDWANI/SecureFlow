"""Blockchain creation, mining, validation, tamper detection, persistence."""
import os
import tempfile

from app.core.blockchain import Blockchain


def _fresh_chain() -> Blockchain:
    path = os.path.join(tempfile.mkdtemp(), "chain.json")
    return Blockchain(path, difficulty=2)


def test_genesis_block_created():
    bc = _fresh_chain()
    assert len(bc.chain) == 1
    assert bc.chain[0].index == 0
    assert bc.chain[0].previous_hash == "0" * 64


def test_mining_links_blocks_and_meets_pow():
    bc = _fresh_chain()
    b1 = bc.mine_block({"transaction_id": "t1", "amount_inr": 100})
    b2 = bc.mine_block({"transaction_id": "t2", "amount_inr": 200})
    assert b1.index == 1 and b2.index == 2
    assert b2.previous_hash == b1.hash
    assert b1.hash.startswith("00") and b2.hash.startswith("00")
    assert bc.validate_chain() is True


def test_tamper_detection():
    bc = _fresh_chain()
    bc.mine_block({"transaction_id": "t1", "amount_inr": 100})
    bc.mine_block({"transaction_id": "t2", "amount_inr": 200})
    assert bc.tamper_detection() is None

    bc.chain[1].transactions[0]["amount_inr"] = 999_999  # tamper
    assert bc.validate_chain() is False
    assert bc.tamper_detection() == 1


def test_persistence_survives_reload():
    path = os.path.join(tempfile.mkdtemp(), "chain.json")
    bc = Blockchain(path, difficulty=2)
    bc.mine_block({"transaction_id": "t1"})
    original_len = len(bc.chain)
    original_hash = bc.last_block.hash

    reloaded = Blockchain(path, difficulty=2)
    assert len(reloaded.chain) == original_len
    assert reloaded.last_block.hash == original_hash
    assert reloaded.validate_chain() is True


def test_get_block_bounds():
    bc = _fresh_chain()
    bc.mine_block({"transaction_id": "t1"})
    assert bc.get_block(0) is not None
    assert bc.get_block(99) is None


def test_db_storage_backend_persists_and_reloads():
    """The 'db' storage backend persists blocks durably and reloads correctly."""
    from sqlalchemy import delete

    from app.database import ChainBlock, SessionLocal, init_db

    init_db()  # ensure chain_blocks table exists

    def _clear():
        db = SessionLocal()
        db.execute(delete(ChainBlock))
        db.commit()
        db.close()

    _clear()
    try:
        bc = Blockchain(path="unused-for-db", difficulty=2, storage="db")
        assert len(bc.chain) == 1  # genesis persisted to the DB
        bc.mine_block({"transaction_id": "t1", "amount_inr": 100})
        bc.mine_block({"transaction_id": "t2", "amount_inr": 200})
        assert bc.validate_chain() is True

        # A fresh instance reads the chain back out of the database.
        reloaded = Blockchain(path="unused-for-db", difficulty=2, storage="db")
        assert len(reloaded.chain) == 3
        assert reloaded.last_block.hash == bc.last_block.hash
        assert reloaded.validate_chain() is True
    finally:
        _clear()
