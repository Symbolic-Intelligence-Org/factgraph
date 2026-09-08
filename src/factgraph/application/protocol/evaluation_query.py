from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from .common import ErrorDTO
from .schema_runtime import EntityRef, FieldPath
from .semantic_address import SemanticPortAddress

EvaluationQueryStage: TypeAlias = Literal[
    "query_construct", "query_admission", "query_compile", "query_compiler_invariant",
]
EvaluationQueryValue: TypeAlias = EntityRef | str | int | float | bool | bytes

class EvaluationQueryError(ValueError):
    """Typed EvaluationQuery construction or compilation failure."""
    def __init__(
        self, message: str, *, code: str, stage: EvaluationQueryStage,
        path: tuple[str, ...] = (), details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code, self.stage, self.path = code, stage, tuple(path)
        self.details = dict(details or {})
    def to_error_dto(self) -> ErrorDTO:
        return ErrorDTO(
            code=self.code, message=str(self), path=self.path,
            details={"stage": self.stage, **self.details},
        )

@dataclass(frozen=True)
class EvaluationQueryBinding:
    address: SemanticPortAddress
    value: EvaluationQueryValue
    def __post_init__(self) -> None:
        if not isinstance(self.address, SemanticPortAddress):
            raise _shape("binding address must be SemanticPortAddress", "INVALID_QUERY_BINDING")
        if not isinstance(self.value, (EntityRef, str, int, float, bool, bytes)):
            raise _shape("binding value has an unsupported protocol type", "INVALID_QUERY_BINDING")

@dataclass(frozen=True)
class EvaluationQuerySelection:
    alias: str
    address: SemanticPortAddress
    def __post_init__(self) -> None:
        _text(self.alias, "selection alias", "INVALID_QUERY_SELECTION")
        if not isinstance(self.address, SemanticPortAddress):
            raise _shape("selection address must be SemanticPortAddress", "INVALID_QUERY_SELECTION")


@dataclass(frozen=True)
class EvaluationQueryFieldNavigationV0:
    """One Query-owned identity-to-field projection source.

    This is intentionally distinct from ``PolicyFieldNavigation``.  The latter
    is authored business logic, whereas this DTO asks a Query compiler to add a
    read-only projection lookup after the Policy has already been compiled.
    Semantic endpoint/cardinality checks require the trusted runtime schema and
    therefore happen during compilation rather than construction.
    """

    base: SemanticPortAddress
    field: FieldPath

    def __post_init__(self) -> None:
        if not isinstance(self.base, SemanticPortAddress):
            raise _shape(
                "navigation base must be SemanticPortAddress",
                "INVALID_QUERY_NAVIGATION",
            )
        if not isinstance(self.field, FieldPath):
            raise _shape("navigation field must be FieldPath", "INVALID_QUERY_NAVIGATION")


@dataclass(frozen=True)
class EvaluationQueryNavigationSelectionV0:
    """Ordered Query projection sourced by one query-owned field lookup."""

    alias: str
    navigation: EvaluationQueryFieldNavigationV0

    def __post_init__(self) -> None:
        _text(self.alias, "selection alias", "INVALID_QUERY_SELECTION")
        if not isinstance(self.navigation, EvaluationQueryFieldNavigationV0):
            raise _shape(
                "navigation selection must contain EvaluationQueryFieldNavigationV0",
                "INVALID_QUERY_SELECTION",
            )


EvaluationQuerySelectionItem: TypeAlias = (
    EvaluationQuerySelection | EvaluationQueryNavigationSelectionV0
)

@dataclass(frozen=True)
class EvaluationQuery:
    policy_digest: str
    selections: tuple[EvaluationQuerySelectionItem, ...]
    bindings: tuple[EvaluationQueryBinding, ...] = ()
    def __post_init__(self) -> None:
        if not _is_hex_digest(self.policy_digest):
            raise _shape("policy_digest must be a lowercase sha256 hex digest", "INVALID_QUERY_POLICY_DIGEST")
        if not isinstance(self.selections, tuple) or not self.selections or not all(
            isinstance(item, (EvaluationQuerySelection, EvaluationQueryNavigationSelectionV0))
            for item in self.selections
        ):
            raise _shape(
                "selections must be a non-empty direct/navigation selection tuple",
                "INVALID_QUERY_SELECTIONS",
            )
        if not isinstance(self.bindings, tuple) or not all(isinstance(item, EvaluationQueryBinding) for item in self.bindings):
            raise _shape("bindings must be an EvaluationQueryBinding tuple", "INVALID_QUERY_BINDINGS")
        aliases = tuple(item.alias for item in self.selections)
        direct_sources = tuple(
            item.address for item in self.selections if isinstance(item, EvaluationQuerySelection)
        )
        navigation_sources = tuple(
            item.navigation
            for item in self.selections
            if isinstance(item, EvaluationQueryNavigationSelectionV0)
        )
        addresses = tuple(item.address for item in self.bindings)
        if len(set(aliases)) != len(aliases):
            raise _shape("selection aliases must be unique", "DUPLICATE_QUERY_SELECTION_ALIAS")
        if len(set(direct_sources)) != len(direct_sources):
            raise _shape("selection addresses must be unique", "DUPLICATE_QUERY_SELECTION_ADDRESS")
        if len(set(navigation_sources)) != len(navigation_sources):
            raise _shape("navigation selections must be unique", "DUPLICATE_QUERY_NAVIGATION")
        if len(set(addresses)) != len(addresses):
            raise _shape("binding addresses must be unique", "DUPLICATE_QUERY_BINDING_ADDRESS")
        object.__setattr__(self, "bindings", tuple(sorted(self.bindings, key=lambda item: _address_key(item.address))))

def _address_key(address: SemanticPortAddress) -> tuple[str, str]:
    return address.occurrence_alias, address.port_name
def _is_hex_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
def _text(value: object, name: str, code: str) -> None:
    if not isinstance(value, str) or not value:
        raise _shape(f"{name} must be a non-empty string", code)
def _shape(message: str, code: str) -> EvaluationQueryError:
    return EvaluationQueryError(message, code=code, stage="query_construct")

__all__ = [
    "EvaluationQuery", "EvaluationQueryBinding", "EvaluationQueryError",
    "EvaluationQueryFieldNavigationV0", "EvaluationQueryNavigationSelectionV0",
    "EvaluationQuerySelection", "EvaluationQuerySelectionItem", "EvaluationQueryValue",
]
