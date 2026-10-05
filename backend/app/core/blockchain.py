"""Backward-compatible names for the audit ledger.

The implementation lives in :mod:`app.core.audit_ledger`. It is a hash-linked,
proof-of-work-sealed, append-only ledger - tamper-evident, not a distributed blockchain
and not Byzantine fault tolerant (see that module's docstring). The old ``Blockchain`` /
``get_blockchain`` names are kept so existing imports and tests keep working.
"""
from app.core.audit_ledger import AuditLedger, Block, get_ledger  # noqa: F401

Blockchain = AuditLedger
get_blockchain = get_ledger
