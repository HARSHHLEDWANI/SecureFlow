"""Audit ledger: Merkle roots, tamper evidence, PoW mode, multi-writer safety, route aliases."""
import os
import tempfile
import threading

import pytest
from sqlalchemy import delete

from app.core.audit_ledger import AuditLedger, Block
from app.core.merkle import EMPTY_ROOT, leaf_hash, merkle_proof, merkle_root, node_hash, verify_proof

API = "/api/v1"


def _ledger(**kw) -> AuditLedger:
    return AuditLedger(os.path.join(tempfile.mkdtemp(), "chain.json"), difficulty=2, **kw)


# ── Merkle tree ─────────────────────────────────────────────────────────────────


def test_merkle_root_small_cases_by_hand():
    a, b, c = {"id": "a"}, {"id": "b"}, {"id": "c"}
    assert merkle_root([]) == EMPTY_ROOT
    assert merkle_root([a]) == leaf_hash(a)
    assert merkle_root([a, b]) == node_hash(leaf_hash(a), leaf_hash(b))
    # Odd node is promoted unchanged: root([a,b,c]) = H(H(a,b), c)
    assert merkle_root([a, b, c]) == node_hash(node_hash(leaf_hash(a), leaf_hash(b)), leaf_hash(c))


def test_merkle_root_is_order_and_content_sensitive_and_key_order_independent():
    a, b = {"x": 1, "y": 2}, {"x": 3}
    assert merkle_root([a, b]) != merkle_root([b, a])
    assert merkle_root([a]) != merkle_root([{"x": 1, "y": 3}])
    assert merkle_root([{"y": 2, "x": 1}]) == merkle_root([a])  # canonical JSON


def test_odd_leaf_is_not_ambiguous_with_a_duplicated_leaf():
    a, b, c = {"id": "a"}, {"id": "b"}, {"id": "c"}
    assert merkle_root([a, b, c]) != merkle_root([a, b, c, c])  # Bitcoin's construction collides here


def test_inclusion_proofs_verify_for_every_index_and_size():
    for n in range(1, 12):
        records = [{"id": i, "amount": i * 10} for i in range(n)]
        root = merkle_root(records)
        for i, rec in enumerate(records):
            proof = merkle_proof(records, i)
            assert len(proof) <= max(n - 1, 0).bit_length()  # O(log n) hashes
            assert verify_proof(rec, proof, root), (n, i)


def test_proofs_reject_tampered_records_wrong_roots_and_bad_index():
    records = [{"id": i} for i in range(5)]
    root, proof = merkle_root(records), merkle_proof(records, 2)
    assert not verify_proof({"id": 99}, proof, root)
    assert not verify_proof(records[2], proof, merkle_root(records[:4]))
    assert not verify_proof(records[3], proof, root)  # proof belongs to index 2
    with pytest.raises(IndexError):
        merkle_proof(records, 5)


# ── Ledger blocks ───────────────────────────────────────────────────────────────


def test_every_block_carries_a_merkle_root_over_its_records():
    ledger = _ledger()
    assert ledger.chain[0].merkle_root == merkle_root(ledger.chain[0].transactions)
    block = ledger.mine_block({"transaction_id": "t1"})
    assert block.merkle_root == merkle_root(block.transactions) != ""
    assert ledger.validate_chain() and ledger.tamper_detection() is None


def test_editing_a_record_is_detected_even_if_the_block_hash_is_recomputed():
    ledger = _ledger()
    ledger.mine_block({"transaction_id": "t1", "amount_inr": 100})
    ledger.mine_block({"transaction_id": "t2", "amount_inr": 200})
    blk = ledger.chain[1]
    blk.transactions[0]["amount_inr"] = 999_999
    blk.hash = blk.compute_hash()  # attacker fixes the hash (ignoring PoW)
    assert ledger.tamper_detection() == 1  # Merkle root no longer matches the records
    assert ledger.validate_chain() is False


def test_blocks_sealed_before_merkle_roots_still_validate():
    ledger = _ledger()
    legacy = Block(index=1, timestamp=1.0, transactions=[{"transaction_id": "old"}],
                   previous_hash=ledger.last_block.hash)  # no merkle_root: pre-Phase-2 shape
    legacy.hash = ledger._mine(legacy)
    ledger.chain.append(legacy)
    assert legacy.merkle_root == "" and ledger.validate_chain() is True
    assert Block.from_dict({k: v for k, v in legacy.to_dict().items() if k != "merkle_root"}).merkle_root == ""


def test_proof_of_work_is_a_configurable_sealing_mode():
    on, off = _ledger(), _ledger(pow_enabled=False)
    assert on.difficulty == 2 and on.stats()["proof_of_work"] is True
    assert off.difficulty == 0 and off.stats()["proof_of_work"] is False
    blk = off.mine_block({"transaction_id": "t"})
    assert off.validate_chain() and blk.nonce == 0  # first hash accepted, still hash-linked
    off.chain[1].transactions[0]["transaction_id"] = "forged"
    assert off.validate_chain() is False  # tamper-evidence does not depend on PoW


# ── Multi-writer safety (db storage) ────────────────────────────────────────────


@pytest.fixture
def db_chain_table():
    from app.database import ChainBlock, SessionLocal, init_db

    init_db()

    def clear():
        db = SessionLocal()
        db.execute(delete(ChainBlock))
        db.commit()
        db.close()

    clear()
    yield
    clear()


def _db_ledger() -> AuditLedger:
    return AuditLedger("unused", difficulty=2, storage="db")


def test_losing_writer_reloads_the_tip_and_remines(db_chain_table, monkeypatch):
    """Worker A is mid-proof-of-work when worker B appends: A must not fork the chain."""
    a, b = _db_ledger(), _db_ledger()
    assert len(a.chain) == len(b.chain) == 1  # both adopt the single genesis

    a_mining, b_done, calls = threading.Event(), threading.Event(), []
    real_mine = a._mine

    def slow_mine(block):
        calls.append(block.index)
        if len(calls) == 1:           # first attempt: still sealing block #1 ...
            a_mining.set()
            assert b_done.wait(10)    # ... while B appends its own block #1
        return real_mine(block)

    monkeypatch.setattr(a, "_mine", slow_mine)
    result = {}
    t = threading.Thread(target=lambda: result.update(block=a.mine_block({"transaction_id": "from-A"})))
    t.start()
    assert a_mining.wait(10)
    b_block = b.mine_block({"transaction_id": "from-B"})
    b_done.set()
    t.join(15)

    assert b_block.index == 1
    assert calls == [1, 2]                     # A sealed #1, lost the PK race, re-mined as #2
    assert result["block"].index == 2 and result["block"].previous_hash == b_block.hash

    fresh = _db_ledger()
    assert [blk.index for blk in fresh.chain] == [0, 1, 2]
    assert fresh.validate_chain() and fresh.tamper_detection() is None
    assert [blk.transactions[0].get("transaction_id") for blk in fresh.chain[1:]] == ["from-B", "from-A"]
    assert [blk.index for blk in a.chain] == [0, 1, 2]  # A synced B's block into memory


def test_two_concurrent_writers_still_produce_a_valid_chain(db_chain_table):
    writers = [_db_ledger(), _db_ledger()]
    per_writer = 6
    errors = []

    def work(w, tag):
        try:
            for i in range(per_writer):
                w.mine_block({"transaction_id": f"{tag}-{i}"})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(w, t)) for w, t in zip(writers, "AB")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert errors == []

    fresh = _db_ledger()
    assert len(fresh.chain) == 1 + 2 * per_writer
    assert [b.index for b in fresh.chain] == list(range(1 + 2 * per_writer))  # no gaps, no forks
    assert fresh.validate_chain() is True
    ids = [b.transactions[0]["transaction_id"] for b in fresh.chain[1:]]
    assert sorted(ids) == sorted(f"{t}-{i}" for t in "AB" for i in range(per_writer))  # none lost


# ── Public surface ──────────────────────────────────────────────────────────────


def test_audit_ledger_routes_and_blockchain_alias_serve_the_same_data(auth_client):
    client, headers, _ = auth_client
    for path in ("stats", "validate", "chain", "block/0"):
        new = client.get(f"{API}/audit-ledger/{path}", headers=headers)
        old = client.get(f"{API}/blockchain/{path}", headers=headers)
        assert new.status_code == old.status_code == 200, path
        assert new.json() == old.json(), path
    assert client.get(f"{API}/audit-ledger/block/0", headers=headers).json()["data"]["merkle_root"]
    assert "proof_of_work" in client.get(f"{API}/audit-ledger/stats", headers=headers).json()["data"]


def test_ledger_routes_still_require_staff(viewer_client):
    client, headers, _ = viewer_client
    assert client.get(f"{API}/audit-ledger/stats", headers=headers).status_code == 403
    assert client.get(f"{API}/blockchain/stats", headers=headers).status_code == 403
    assert client.get(f"{API}/audit-ledger/stats").status_code == 401


def test_old_import_names_still_resolve():
    from app.core.audit_ledger import get_ledger
    from app.core.blockchain import Blockchain, get_blockchain

    assert Blockchain is AuditLedger and get_blockchain is get_ledger
