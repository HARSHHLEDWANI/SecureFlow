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
