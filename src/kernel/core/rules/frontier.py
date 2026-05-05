from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from kernel.core.rules.ruleref_substrate import evaluate_native_where
from kernel.core.rules.ruleref_types import NativeRuleRefResolution

NativeWhereFrontierFailureKind = Literal["empty_input", "atom_filter_empty"]

_FRONTIER_FAILURE_KINDS = frozenset({"empty_input", "atom_filter_empty"})


@dataclass(frozen=True)
class NativeWhereFrontierRow:
    branch_index: int
    failed_atom_index: int
    atoms_satisfied: int
    frontier_count: int
    failure_kind: NativeWhereFrontierFailureKind

    def __post_init__(self) -> None:
        _validate_nonnegative_int("branch_index", self.branch_index)
        _validate_nonnegative_int("failed_atom_index", self.failed_atom_index)
        _validate_nonnegative_int("atoms_satisfied", self.atoms_satisfied)
        _validate_nonnegative_int("frontier_count", self.frontier_count)
        if self.atoms_satisfied != self.failed_atom_index:
            raise ValueError("atoms_satisfied must equal failed_atom_index")
        if self.failure_kind not in _FRONTIER_FAILURE_KINDS:
            raise ValueError("failure_kind must be one of: atom_filter_empty, empty_input")
        if self.failure_kind == "empty_input" and self.frontier_count != 0:
            raise ValueError("empty_input frontier rows must have frontier_count=0")
        if self.failure_kind == "atom_filter_empty" and self.frontier_count <= 0:
            raise ValueError("atom_filter_empty frontier rows must have frontier_count>0")


@dataclass(frozen=True)
class NativeWhereFrontierEvaluation:
    bindings: list[dict[str, Any]]
    rule_refs: tuple[str, ...] = ()
    rule_ref_resolutions: tuple[NativeRuleRefResolution, ...] = ()
    frontier_rows: tuple[NativeWhereFrontierRow, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.bindings, list):
            raise ValueError("bindings must be list")
        for binding in self.bindings:
            if not isinstance(binding, dict):
                raise ValueError("bindings must contain dict rows")
        if not isinstance(self.rule_refs, tuple) or any(
            not isinstance(rule_ref, str) or not rule_ref for rule_ref in self.rule_refs
        ):
            raise ValueError("rule_refs must be tuple[str, ...]")
        if not isinstance(self.rule_ref_resolutions, tuple) or any(
            not isinstance(row, NativeRuleRefResolution) for row in self.rule_ref_resolutions
        ):
            raise ValueError("rule_ref_resolutions must be tuple[NativeRuleRefResolution, ...]")
        if not isinstance(self.frontier_rows, tuple) or any(
            not isinstance(row, NativeWhereFrontierRow) for row in self.frontier_rows
        ):
            raise ValueError("frontier_rows must be tuple[NativeWhereFrontierRow, ...]")


def evaluate_native_where_frontier(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    registry: Any | None = None,
    witness_facts: dict[str, list[Any]] | None = None,
    remember_support_artifact: Any | None = None,
) -> NativeWhereFrontierEvaluation:
    evaluation = evaluate_native_where(
        view_facts,
        where,
        registry=registry,
        witness_facts=witness_facts,
        remember_support_artifact=remember_support_artifact,
    )
    return NativeWhereFrontierEvaluation(
        bindings=evaluation.bindings,
        rule_refs=evaluation.rule_refs,
        rule_ref_resolutions=evaluation.rule_ref_resolutions,
        frontier_rows=(),
    )


def _validate_nonnegative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative int")


__all__ = [
    "NativeWhereFrontierEvaluation",
    "NativeWhereFrontierFailureKind",
    "NativeWhereFrontierRow",
    "evaluate_native_where_frontier",
]
