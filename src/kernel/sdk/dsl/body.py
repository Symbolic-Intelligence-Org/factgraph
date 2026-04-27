from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SDKDSLError


@dataclass(frozen=True)
class Body:
    atoms: list[Any]
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.atoms, list) or not self.atoms:
            raise SDKDSLError("Body.atoms must be non-empty list", path="$.where[]")
        object.__setattr__(self, "atoms", list(self.atoms))

        if self.confidence is None:
            return
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise SDKDSLError("Body.confidence must be float in (0,1]", path="$.where[].confidence")

        normalized = float(self.confidence)
        if normalized <= 0.0 or normalized > 1.0:
            raise SDKDSLError("Body.confidence must be within (0,1]", path="$.where[].confidence")
        object.__setattr__(self, "confidence", normalized)
