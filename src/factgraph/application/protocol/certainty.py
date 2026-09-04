from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from factgraph.application.protocol.common import ProtocolShapeError

CertaintyKind = Literal["boolean", "probabilistic", "possibilistic"]
_CERTAINTY_KINDS = frozenset({"boolean", "probabilistic", "possibilistic"})


@dataclass(frozen=True)
class Certainty:
    lo: float
    hi: float
    kind: CertaintyKind = "boolean"

    def __post_init__(self) -> None:
        if self.kind not in _CERTAINTY_KINDS:
            raise ProtocolShapeError("Certainty.kind must be boolean, probabilistic, or possibilistic")
        lo = _require_probability_bound(self.lo, field_name="Certainty.lo")
        hi = _require_probability_bound(self.hi, field_name="Certainty.hi")
        if lo > hi:
            raise ProtocolShapeError("Certainty.lo must be <= Certainty.hi")
        object.__setattr__(self, "lo", lo)
        object.__setattr__(self, "hi", hi)


def _require_probability_bound(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolShapeError(f"{field_name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ProtocolShapeError(f"{field_name} must be finite")
    if normalized < 0.0 or normalized > 1.0:
        raise ProtocolShapeError(f"{field_name} must be between 0.0 and 1.0")
    return normalized


BOOLEAN_CERTAINTY = Certainty(1.0, 1.0, "boolean")


__all__ = ["BOOLEAN_CERTAINTY", "Certainty", "CertaintyKind"]
