from __future__ import annotations

from factpy.core.store.ledger import Ledger


def is_active(ledger: Ledger, asrt_id: str) -> bool:
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    if not isinstance(asrt_id, str) or not asrt_id:
        raise ValueError("asrt_id must be non-empty string")
    return not ledger.has_active_revocation(asrt_id)
