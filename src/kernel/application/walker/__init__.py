"""Application-layer walker mechanism (Tier 2 advanced importable).

See docs/blueprints/active/2026-05-07_walker-mechanism.md for design.

- B1 (mandatory): IR walker + frozen tuple wrapper protocol.
- B2 (mandatory): evidence cross-reference + per-DTO wrapper views.
- B3 (future-only, NOT B1/B2 acceptance): audit / store stream walker —
  reserved. `UnboundedStreamError` is exported as a dormant placeholder
  per blueprint §4.1 Round 2 to keep the WalkerError hierarchy coherent
  with bundle `#12` / `#14`; B1/B2 has no raise site for it.
"""

from __future__ import annotations

from .errors import (
    UnboundedStreamError,
    WalkerError,
    WalkerFrozenError,
    WalkerLookupError,
    WalkerParseError,
    WalkerReferenceError,
    WalkerSnapshotError,
)
from .ir import (
    IRAtomView,
    IRBodyWalker,
)

__all__ = [
    "IRAtomView",
    "IRBodyWalker",
    "UnboundedStreamError",
    "WalkerError",
    "WalkerFrozenError",
    "WalkerLookupError",
    "WalkerParseError",
    "WalkerReferenceError",
    "WalkerSnapshotError",
]
