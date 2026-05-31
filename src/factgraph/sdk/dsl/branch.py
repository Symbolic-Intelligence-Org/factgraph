from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
import re
from typing import Any

from .errors import SDKDSLError

_CASE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Case:
    """Named alternative body inside an inference.

    An inference with multiple cases expresses alternative pathways: each case
    is a conjunction of atoms, and the case list acts like OR over those
    conjunctions. Supplying `id=` gives inspection and semantics APIs a stable
    case name.
    """

    atoms: list[Any]
    _: KW_ONLY
    id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.atoms, list) or not self.atoms:
            raise SDKDSLError("Case.atoms must be non-empty list", path="$.when[]")
        if self.id is not None:
            if not isinstance(self.id, str) or not self.id:
                raise SDKDSLError("Case.id must be non-empty string when provided", path="$.when[].id")
            if not _CASE_ID_RE.fullmatch(self.id):
                raise SDKDSLError(
                    "Case.id must match ^[A-Za-z_][A-Za-z0-9_]*$",
                    path="$.when[].id",
                )
        object.__setattr__(self, "atoms", list(self.atoms))
