from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SDKDSLError


@dataclass(frozen=True)
class Branch:
    atoms: list[Any]

    def __post_init__(self) -> None:
        if not isinstance(self.atoms, list) or not self.atoms:
            raise SDKDSLError("Branch.atoms must be non-empty list", path="$.where[]")
        object.__setattr__(self, "atoms", list(self.atoms))
