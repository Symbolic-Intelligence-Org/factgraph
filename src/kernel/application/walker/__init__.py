"""Application-layer walker mechanism (Tier 2 advanced importable).

See docs/blueprints/active/2026-05-07_walker-mechanism.md for design.

- B1 (mandatory): IR walker + frozen tuple wrapper protocol.
- B2 (mandatory): evidence cross-reference + per-DTO wrapper views.
- B3 (future-only, NOT B1/B2 acceptance): audit / store stream walker —
  reserved. `UnboundedStreamError` is exported as a dormant placeholder
  per blueprint §4.1 Round 2 to keep the WalkerError hierarchy coherent
  with bundle `#12` / `#14`; B1/B2 has no raise site for it.

Walker instances are single-thread objects; share frozen source DTOs between
threads, not walker instances.
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
from .keys import (
    AtomKeyView,
    parse_atom_key,
)
from .views import (
    AssertionView,
    FrozenTupleView,
    SupportArtifactView,
    frozen_collection,
)

__all__ = [
    "AssertionView",
    "AtomKeyView",
    "FrozenTupleView",
    "IRAtomView",
    "IRBodyWalker",
    "SupportArtifactView",
    "UnboundedStreamError",
    "WalkerError",
    "WalkerFrozenError",
    "WalkerLookupError",
    "WalkerParseError",
    "WalkerReferenceError",
    "WalkerSnapshotError",
    "frozen_collection",
    "parse_atom_key",
]
