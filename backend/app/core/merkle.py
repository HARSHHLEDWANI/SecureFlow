"""Merkle tree over a block's transaction records.

Gives every ledger block a ``merkle_root`` so that one record's membership can be proved
with O(log n) hashes instead of shipping or scanning the whole record list.

Domain separation (``0x00`` for leaves, ``0x01`` for inner nodes) stops a leaf from being
passed off as an inner node (the second-preimage trick). An unpaired node at any level is
promoted unchanged rather than duplicated, which avoids the duplicate-leaf ambiguity of
Bitcoin's construction (where ``[a, b, c]`` and ``[a, b, c, c]`` share a root).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

EMPTY_ROOT = "0" * 64


def _canonical(record: Any) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def leaf_hash(record: Any) -> str:
    return hashlib.sha256(b"\x00" + _canonical(record)).hexdigest()


def node_hash(left: str, right: str) -> str:
    return hashlib.sha256(b"\x01" + bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


def _levels(records: Sequence[Any]) -> list[list[str]]:
    level = [leaf_hash(r) for r in records]
    levels = [level]
    while len(level) > 1:
        nxt = [node_hash(level[i], level[i + 1]) for i in range(0, len(level) - 1, 2)]
        if len(level) % 2:
            nxt.append(level[-1])  # unpaired node is promoted as-is
        levels.append(nxt)
        level = nxt
    return levels


def merkle_root(records: Sequence[Any]) -> str:
    if not records:
        return EMPTY_ROOT
    return _levels(records)[-1][0]


def merkle_proof(records: Sequence[Any], index: int) -> list[tuple[str, str]]:
    """Inclusion proof for ``records[index]``: ``[(sibling_hash, "L"|"R"), ...]`` leaf -> root.

    ``"L"`` means the sibling sits to the left of the running hash.
    """
    if not 0 <= index < len(records):
        raise IndexError("record index out of range")
    proof: list[tuple[str, str]] = []
    for level in _levels(records)[:-1]:
        sibling = index ^ 1
        if sibling < len(level):
            proof.append((level[sibling], "L" if sibling < index else "R"))
        index //= 2
    return proof


def verify_proof(record: Any, proof: Sequence[tuple[str, str]], root: str) -> bool:
    """True iff ``record`` hashes up through ``proof`` to ``root``."""
    running = leaf_hash(record)
    for sibling, side in proof:
        running = node_hash(sibling, running) if side == "L" else node_hash(running, sibling)
    return running == root
