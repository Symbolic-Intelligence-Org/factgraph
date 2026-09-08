from __future__ import annotations

from dataclasses import dataclass


class SemanticAddressShapeError(ValueError):
    """A semantic occurrence-address value is malformed."""


@dataclass(frozen=True)
class SemanticPortAddress:
    """Canonical authored direct-port address; never a parsed dotted string."""

    occurrence_alias: str
    port_name: str

    def __post_init__(self) -> None:
        _require_text(self.occurrence_alias, "occurrence_alias")
        _require_text(self.port_name, "port_name")


def _require_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise SemanticAddressShapeError(f"{name} must be non-empty string")


__all__ = [
    "SemanticAddressShapeError",
    "SemanticPortAddress",
]
