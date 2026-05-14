"""Why-not Universe Diagnose protocol DTOs.

Why-not is a Sibling-with-Diagnose application capability: its runtime may call
Diagnose to fill red-row diagnostics, but this protocol owns its public row DTOs
and does not expose nested Diagnose result types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from factgraph.core.store._support import BindingItems, normalize_binding_items

from .common import (
    ErrorDTO,
    ProtocolShapeError,
    WarningDTO,
    _require_literal,
    _validate_tuple_items,
)
from .derivation import CompiledDerivationPlan

WhyNotStatus: TypeAlias = Literal["completed", "unsupported", "invalid_request"]
WhyNotEngine: TypeAlias = Literal["native", "souffle", "problog", "pyreason"]
WhyNotRowStatus: TypeAlias = Literal["failed", "unsupported"]
WhyNotFailureKind: TypeAlias = Literal["no_candidate", "atom_localized"]
WhyNotRowGranularity: TypeAlias = Literal["atom_localized", "coarse", "unavailable"]

_WHY_NOT_STATUSES = ("completed", "unsupported", "invalid_request")
_WHY_NOT_ENGINES = ("native", "souffle", "problog", "pyreason")
_WHY_NOT_ROW_STATUSES = ("failed", "unsupported")
_WHY_NOT_FAILURE_KINDS = ("no_candidate", "atom_localized")
_WHY_NOT_ROW_GRANULARITIES = ("atom_localized", "coarse", "unavailable")


def _validate_non_negative_int(value: Any, *, field_name: str) -> int:
    if value is None or isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolShapeError(f"{field_name} must be non-negative int")
    return value


def _validate_binding_items(value: Any, *, field_name: str) -> BindingItems:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be BindingItems tuple")

    seen: set[str] = set()
    for idx, item in enumerate(value):
        if not isinstance(item, tuple) or len(item) != 2:
            raise ProtocolShapeError(f"{field_name}[{idx}] must be tuple[str, Any]")
        key = item[0]
        if not isinstance(key, str) or not key:
            raise ProtocolShapeError(f"{field_name}[{idx}][0] must be non-empty string")
        if not key.startswith("$") or len(key) == 1:
            raise ProtocolShapeError(f"{field_name}[{idx}][0] must be $-prefixed variable")
        if key in seen:
            raise ProtocolShapeError(f"{field_name} must not contain duplicate variable names")
        seen.add(key)

    try:
        return normalize_binding_items(value)
    except ValueError as exc:
        raise ProtocolShapeError(f"{field_name} must be valid BindingItems") from exc


def _validate_binding_items_tuple(
    value: Any, *, field_name: str
) -> tuple[BindingItems, ...]:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[BindingItems, ...]")
    return tuple(
        _validate_binding_items(item, field_name=f"{field_name}[{idx}]")
        for idx, item in enumerate(value)
    )


def _validate_complete_head_universe(
    value: Any, *, field_name: str, head_var_names: tuple[str, ...]
) -> tuple[BindingItems, ...]:
    universe = _validate_binding_items_tuple(value, field_name=field_name)
    head_vars = tuple(
        name
        for name in head_var_names
        if isinstance(name, str) and name.startswith("$") and len(name) > 1
    )
    head_var_set = set(head_vars)
    if len(head_var_set) != len(head_vars):
        raise ProtocolShapeError("plan head variable names must be unique")

    seen_bindings: list[BindingItems] = []
    for idx, binding in enumerate(universe):
        binding_vars = {name for name, _ in binding}
        if binding_vars != head_var_set:
            raise ProtocolShapeError(
                f"{field_name}[{idx}] must contain exactly the plan head variables"
            )
        if _binding_in(binding, seen_bindings):
            raise ProtocolShapeError(f"{field_name} must not contain duplicate bindings")
        seen_bindings.append(binding)
    return universe


def _binding_in(binding: BindingItems, haystack: tuple[BindingItems, ...] | list[BindingItems]) -> bool:
    return any(existing == binding for existing in haystack)


def _validate_unique_bindings(
    value: tuple[BindingItems, ...], *, field_name: str
) -> tuple[BindingItems, ...]:
    seen: list[BindingItems] = []
    for binding in value:
        if _binding_in(binding, seen):
            raise ProtocolShapeError(f"{field_name} must not contain duplicate bindings")
        seen.append(binding)
    return value


def _validate_ordered_partition(
    *,
    requested_universe: tuple[BindingItems, ...],
    green: tuple[BindingItems, ...],
    red: tuple["WhyNotRedRow", ...],
) -> None:
    requested_universe = _validate_unique_bindings(
        requested_universe, field_name="requested_universe"
    )
    green = _validate_unique_bindings(green, field_name="green")
    red_bindings = tuple(row.binding for row in red)
    red_bindings = _validate_unique_bindings(red_bindings, field_name="red")

    if any(_binding_in(binding, red_bindings) for binding in green):
        raise ProtocolShapeError("completed WhyNotUniverseResult requires disjoint green/red")
    if any(not _binding_in(binding, requested_universe) for binding in green):
        raise ProtocolShapeError(
            "completed WhyNotUniverseResult requires green/red to cover requested_universe"
        )
    if any(not _binding_in(binding, requested_universe) for binding in red_bindings):
        raise ProtocolShapeError(
            "completed WhyNotUniverseResult requires green/red to cover requested_universe"
        )
    if any(
        not _binding_in(binding, green) and not _binding_in(binding, red_bindings)
        for binding in requested_universe
    ):
        raise ProtocolShapeError(
            "completed WhyNotUniverseResult requires green/red to cover requested_universe"
        )

    ordered_green = tuple(binding for binding in requested_universe if _binding_in(binding, green))
    ordered_red = tuple(
        binding for binding in requested_universe if _binding_in(binding, red_bindings)
    )
    if green != ordered_green:
        raise ProtocolShapeError(
            "completed WhyNotUniverseResult requires green order to follow requested_universe"
        )
    if red_bindings != ordered_red:
        raise ProtocolShapeError(
            "completed WhyNotUniverseResult requires red order to follow requested_universe"
        )


@dataclass(frozen=True)
class WhyNotAtomLocator:
    branch_index: int
    failed_atom_index: int
    attempted_binding: BindingItems

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.branch_index, field_name="branch_index")
        _validate_non_negative_int(self.failed_atom_index, field_name="failed_atom_index")
        object.__setattr__(
            self,
            "attempted_binding",
            _validate_binding_items(self.attempted_binding, field_name="attempted_binding"),
        )


@dataclass(frozen=True)
class WhyNotUniverseRequest:
    plan: CompiledDerivationPlan
    candidate_universe: tuple[BindingItems, ...]
    engine: WhyNotEngine

    def __post_init__(self) -> None:
        if not isinstance(self.plan, CompiledDerivationPlan):
            raise ProtocolShapeError("plan must be CompiledDerivationPlan")
        if len(self.plan.heads) != 1:
            raise ProtocolShapeError(
                "plan must contain exactly one head for WhyNotUniverseRequest"
            )
        object.__setattr__(
            self,
            "candidate_universe",
            _validate_complete_head_universe(
                self.candidate_universe,
                field_name="candidate_universe",
                head_var_names=self.plan.heads[0].head_var_names,
            ),
        )
        _require_literal(self.engine, field_name="engine", allowed=_WHY_NOT_ENGINES)


@dataclass(frozen=True)
class WhyNotRowDiagnostic:
    status: WhyNotRowStatus
    failure_kind: WhyNotFailureKind | None
    diagnostic_granularity: WhyNotRowGranularity
    atom_locator: WhyNotAtomLocator | None
    errors: tuple[ErrorDTO, ...] = field(default_factory=tuple)
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        status = _require_literal(
            self.status, field_name="status", allowed=_WHY_NOT_ROW_STATUSES
        )
        granularity = _require_literal(
            self.diagnostic_granularity,
            field_name="diagnostic_granularity",
            allowed=_WHY_NOT_ROW_GRANULARITIES,
        )
        if self.failure_kind is not None:
            _require_literal(
                self.failure_kind,
                field_name="failure_kind",
                allowed=_WHY_NOT_FAILURE_KINDS,
            )
        if self.atom_locator is not None and not isinstance(
            self.atom_locator, WhyNotAtomLocator
        ):
            raise ProtocolShapeError("atom_locator must be WhyNotAtomLocator or None")
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)

        if status == "unsupported":
            if self.failure_kind is not None:
                raise ProtocolShapeError(
                    "unsupported WhyNotRowDiagnostic requires failure_kind=None"
                )
            if granularity != "unavailable":
                raise ProtocolShapeError(
                    "unsupported WhyNotRowDiagnostic requires diagnostic_granularity='unavailable'"
                )
            if self.atom_locator is not None:
                raise ProtocolShapeError(
                    "unsupported WhyNotRowDiagnostic requires atom_locator=None"
                )
            if not self.errors:
                raise ProtocolShapeError("unsupported WhyNotRowDiagnostic requires errors")
            return

        if self.errors:
            raise ProtocolShapeError("failed WhyNotRowDiagnostic requires no errors")
        if self.failure_kind is None:
            raise ProtocolShapeError("failed WhyNotRowDiagnostic requires failure_kind")
        if self.failure_kind == "no_candidate":
            if granularity != "coarse":
                raise ProtocolShapeError(
                    "failed no_candidate WhyNotRowDiagnostic requires "
                    "diagnostic_granularity='coarse'"
                )
            if self.atom_locator is not None:
                raise ProtocolShapeError(
                    "failed no_candidate WhyNotRowDiagnostic requires atom_locator=None"
                )
            return

        if granularity != "atom_localized":
            raise ProtocolShapeError(
                "failed atom_localized WhyNotRowDiagnostic requires "
                "diagnostic_granularity='atom_localized'"
            )
        if not isinstance(self.atom_locator, WhyNotAtomLocator):
            raise ProtocolShapeError(
                "failed atom_localized WhyNotRowDiagnostic requires atom_locator"
            )


@dataclass(frozen=True)
class WhyNotRedRow:
    binding: BindingItems
    diagnostic: WhyNotRowDiagnostic

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "binding",
            _validate_binding_items(self.binding, field_name="binding"),
        )
        if not isinstance(self.diagnostic, WhyNotRowDiagnostic):
            raise ProtocolShapeError("diagnostic must be WhyNotRowDiagnostic")


@dataclass(frozen=True)
class WhyNotUniverseResult:
    status: WhyNotStatus
    requested_universe: tuple[BindingItems, ...]
    green: tuple[BindingItems, ...]
    red: tuple[WhyNotRedRow, ...]
    errors: tuple[ErrorDTO, ...] = field(default_factory=tuple)
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        status = _require_literal(self.status, field_name="status", allowed=_WHY_NOT_STATUSES)
        requested_universe = _validate_binding_items_tuple(
            self.requested_universe, field_name="requested_universe"
        )
        green = _validate_binding_items_tuple(self.green, field_name="green")
        red = _validate_tuple_items(self.red, field_name="red", item_type=WhyNotRedRow)
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)

        object.__setattr__(self, "requested_universe", requested_universe)
        object.__setattr__(self, "green", green)
        object.__setattr__(self, "red", red)

        if status == "completed":
            if self.errors:
                raise ProtocolShapeError("completed WhyNotUniverseResult requires no errors")
            _validate_ordered_partition(
                requested_universe=requested_universe,
                green=green,
                red=red,
            )
            return

        if self.green:
            raise ProtocolShapeError(f"{status} WhyNotUniverseResult requires green=()")
        if self.red:
            raise ProtocolShapeError(f"{status} WhyNotUniverseResult requires red=()")
        if not self.errors:
            raise ProtocolShapeError(f"{status} WhyNotUniverseResult requires errors")


__all__ = [
    "WhyNotAtomLocator",
    "WhyNotEngine",
    "WhyNotFailureKind",
    "WhyNotRedRow",
    "WhyNotRowDiagnostic",
    "WhyNotRowGranularity",
    "WhyNotRowStatus",
    "WhyNotStatus",
    "WhyNotUniverseRequest",
    "WhyNotUniverseResult",
]
