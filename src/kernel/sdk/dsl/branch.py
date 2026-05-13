from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
import re
from typing import Any

from .errors import SDKDSLError

_BRANCH_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Branch:
    """Named alternative body inside a rule or inference.

    A rule with multiple branches expresses alternative pathways: each branch
    is a conjunction of atoms, and the branch list acts like OR over those
    conjunctions. Supplying `id=` gives inspection and semantics APIs a stable
    branch name.
    """

    atoms: list[Any]
    _: KW_ONLY
    id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.atoms, list) or not self.atoms:
            raise SDKDSLError("Branch.atoms must be non-empty list", path="$.where[]")
        if self.id is not None:
            if not isinstance(self.id, str) or not self.id:
                raise SDKDSLError("Branch.id must be non-empty string when provided", path="$.where[].id")
            if not _BRANCH_ID_RE.fullmatch(self.id):
                raise SDKDSLError(
                    "Branch.id must match ^[A-Za-z_][A-Za-z0-9_]*$",
                    path="$.where[].id",
                )
        object.__setattr__(self, "atoms", list(self.atoms))
