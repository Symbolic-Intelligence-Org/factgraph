"""Walker-layer error hierarchy.

Per blueprint §4.1 Round 2 (B-R2-2 lightweight variant):

- 5 B1/B2 subclasses with planned raise sites in later phases:
  WalkerLookupError, WalkerParseError, WalkerReferenceError,
  WalkerSnapshotError, WalkerFrozenError.
- 1 dormant subclass (UnboundedStreamError) reserved for future B3
  StreamWalker. Exported now to keep the finalized hierarchy coherent
  with bundle 40_ §4 / `#12` / `#14`; remains dormant until B3
  reactivation introduces walker/stream.py.

Parent `WalkerError(Exception)` because walker errors span lookup / parse
/ state / reference / frozen semantics — not all are value-validation.
Matches SDK convention (`SDKError(Exception)`).
"""

from __future__ import annotations


class WalkerError(Exception):
    """Base for all walker-layer errors."""


class WalkerLookupError(WalkerError):
    """Raised by find / require_key / require_position on miss in raise-mode."""


class WalkerParseError(WalkerError):
    """Raised by parse_atom_key on malformed atom key."""


class WalkerReferenceError(WalkerError):
    """Raised by SupportArtifactView.lookup_assertion on missing claim ref."""


class WalkerSnapshotError(WalkerError):
    """Raised when construction-time snapshot integrity is violated."""


class WalkerFrozenError(WalkerError):
    """Raised on attempt to mutate a frozen view."""


class UnboundedStreamError(WalkerError):
    """Reserved for future B3 StreamWalker construction without bound (`#14`).

    NOTE: B1/B2 has no raise site for this error. Exported now to keep the
    finalized hierarchy coherent with bundle 40_ §4 / `#12` / `#14`;
    remains dormant until B3 reactivation introduces walker/stream.py.
    """


__all__ = [
    "UnboundedStreamError",
    "WalkerError",
    "WalkerFrozenError",
    "WalkerLookupError",
    "WalkerParseError",
    "WalkerReferenceError",
    "WalkerSnapshotError",
]
