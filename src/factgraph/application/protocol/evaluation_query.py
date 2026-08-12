from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from .common import ErrorDTO
from .schema_runtime import EntityRef
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
class EvaluationQuery:
    policy_digest: str
    selections: tuple[EvaluationQuerySelection, ...]
    bindings: tuple[EvaluationQueryBinding, ...] = ()
    def __post_init__(self) -> None:
        if not _is_hex_digest(self.policy_digest):
            raise _shape("policy_digest must be a lowercase sha256 hex digest", "INVALID_QUERY_POLICY_DIGEST")
        if not isinstance(self.selections, tuple) or not self.selections or not all(
            isinstance(item, EvaluationQuerySelection) for item in self.selections
        ):
            raise _shape("selections must be a non-empty EvaluationQuerySelection tuple", "INVALID_QUERY_SELECTIONS")
        if not isinstance(self.bindings, tuple) or not all(isinstance(item, EvaluationQueryBinding) for item in self.bindings):
            raise _shape("bindings must be an EvaluationQueryBinding tuple", "INVALID_QUERY_BINDINGS")
        aliases, sources = (tuple(item.alias for item in self.selections),
                            tuple(item.address for item in self.selections))
        addresses = tuple(item.address for item in self.bindings)
        if len(set(aliases)) != len(aliases):
            raise _shape("selection aliases must be unique", "DUPLICATE_QUERY_SELECTION_ALIAS")
        if len(set(sources)) != len(sources):
            raise _shape("selection addresses must be unique", "DUPLICATE_QUERY_SELECTION_ADDRESS")
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
    "EvaluationQuerySelection", "EvaluationQueryValue",
]
