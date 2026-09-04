from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from factgraph.core.rules.ruleref_substrate import (
    _contains_ruleref_atom,
    _rewrite_where_rule_refs,
    _validate_where_for_ruleref,
)
from factgraph.core.rules.ruleref_types import NativeRuleRefResolution
from factgraph.core.rules.where_ast import WhereASTError, parse_where_ir_to_ast
from factgraph.core.rules.where_ast_validate import (
    WhereASTValidationError,
    validate_where_ast,
)
from factgraph.core.rules.where_eval import (
    _ARITH_KINDS,
    WhereValidationError,
    _adapt_where_ast_error,
    _eval_arith_atom,
    _eval_cmp_atom,
    _eval_eq_atom,
    _eval_in_atom,
    _eval_ne_atom,
    _eval_not_atom,
    _eval_pred_atom,
    _normalize_where,
    _plan_body_atoms,
    _where_ast_gate_enabled,
)

NativeWhereFrontierFailureKind = Literal["empty_input", "atom_filter_empty"]

_FRONTIER_FAILURE_KINDS = frozenset({"empty_input", "atom_filter_empty"})


@dataclass(frozen=True)
class NativeWhereFrontierRow:
    case_index: int
    failed_atom_index: int
    atoms_satisfied: int
    frontier_count: int
    failure_kind: NativeWhereFrontierFailureKind

    def __post_init__(self) -> None:
        _validate_nonnegative_int("case_index", self.case_index)
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
    memo_outputs: dict[tuple[str, str], Any] = {}
    stack: set[tuple[str, str]] = set()
    return _evaluate_native_where_frontier_internal(
        view_facts,
        where,
        registry=registry,
        witness_facts=witness_facts,
        remember_support_artifact=remember_support_artifact,
        memo_outputs=memo_outputs,
        stack=stack,
    )


def _evaluate_native_where_frontier_internal(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    registry: Any | None,
    witness_facts: dict[str, list[Any]] | None,
    remember_support_artifact: Any | None,
    memo_outputs: dict[tuple[str, str], Any],
    stack: set[tuple[str, str]],
) -> NativeWhereFrontierEvaluation:
    has_ruleref = _contains_ruleref_atom(where)
    if registry is None:
        if has_ruleref:
            raise WhereValidationError("RuleRef execution requires explicit RuleRegistry")
        bindings, frontier_rows = _evaluate_where_frontier(view_facts, where)
        return NativeWhereFrontierEvaluation(bindings=bindings, frontier_rows=frontier_rows)

    if has_ruleref:
        _validate_where_for_ruleref(where)
        rewritten_where, overlay, resolutions = _rewrite_where_rule_refs(
            where,
            registry=registry,
            base_view_facts=view_facts,
            witness_facts=witness_facts,
            remember_support_artifact=remember_support_artifact,
            memo_outputs=memo_outputs,
            stack=stack,
        )
        resolved_view_facts = dict(view_facts)
        resolved_view_facts.update(overlay)
        bindings, frontier_rows = _evaluate_where_frontier(resolved_view_facts, rewritten_where)
        return NativeWhereFrontierEvaluation(
            bindings=bindings,
            rule_refs=tuple(sorted({row.rule_ref_id for row in resolutions})),
            rule_ref_resolutions=tuple(sorted(resolutions, key=lambda row: row.ruleref_condition_key)),
            frontier_rows=frontier_rows,
        )

    bindings, frontier_rows = _evaluate_where_frontier(view_facts, where)
    return NativeWhereFrontierEvaluation(bindings=bindings, frontier_rows=frontier_rows)


def _evaluate_where_frontier(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
) -> tuple[list[dict[str, Any]], tuple[NativeWhereFrontierRow, ...]]:
    ast_gate_on = _where_ast_gate_enabled()
    if ast_gate_on:
        try:
            ast = parse_where_ir_to_ast(where)
            validate_where_ast(
                ast,
                mode="python",
                capabilities={"allow_ruleref": False},
            )
        except (WhereASTError, WhereASTValidationError) as exc:
            raise _adapt_where_ast_error(exc) from exc

    bodies = _normalize_where(where)

    all_bindings: list[dict[str, Any]] = []
    frontier_rows: list[NativeWhereFrontierRow] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()

    for case_index, body in enumerate(bodies):
        body_bindings, frontier_row = _eval_body_frontier(
            view_facts,
            body,
            case_index=case_index,
            ast_gate_on=ast_gate_on,
        )
        if frontier_row is not None:
            frontier_rows.append(frontier_row)
        for binding in body_bindings:
            key = tuple(sorted(binding.items(), key=lambda item: item[0]))
            if key in seen:
                continue
            seen.add(key)
            all_bindings.append(binding)

    all_bindings.sort(key=lambda env: tuple((key, env[key]) for key in sorted(env.keys())))
    return all_bindings, tuple(frontier_rows)


def _eval_body_frontier(
    view_facts: dict[str, list[tuple[Any, ...]]],
    body: list[tuple[Any, ...]],
    *,
    case_index: int,
    ast_gate_on: bool,
) -> tuple[list[dict[str, Any]], NativeWhereFrontierRow | None]:
    planned_body = _plan_body_atoms(body, ast_gate_on=ast_gate_on)
    pred_lookup_cache: dict[
        str,
        dict[tuple[int, ...], dict[tuple[Any, ...], list[tuple[Any, ...]]]],
    ] = {}
    envs: list[dict[str, Any]] = [{}]
    for condition_index, atom in enumerate(planned_body):
        frontier_count = len(envs)
        kind = atom[0]
        if kind == "pred":
            envs = _eval_pred_atom(
                view_facts,
                envs,
                atom,
                pred_lookup_cache=pred_lookup_cache,
            )
        elif kind == "eq":
            envs = _eval_eq_atom(view_facts, envs, atom, ast_gate_on=ast_gate_on)
        elif kind == "in":
            envs = _eval_in_atom(envs, atom, ast_gate_on=ast_gate_on)
        elif kind == "ne":
            envs = _eval_ne_atom(envs, atom, ast_gate_on=ast_gate_on)
        elif kind in {"gt", "ge", "lt", "le"}:
            envs = _eval_cmp_atom(envs, atom, ast_gate_on=ast_gate_on)
        elif kind in _ARITH_KINDS:
            envs = _eval_arith_atom(view_facts, envs, atom, ast_gate_on=ast_gate_on)
        elif kind == "not":
            envs = _eval_not_atom(view_facts, envs, atom, ast_gate_on=ast_gate_on)
        else:
            raise WhereValidationError(f"unsupported atom kind: {kind}")
        if not envs:
            failure_kind: NativeWhereFrontierFailureKind = (
                "empty_input" if frontier_count == 0 else "atom_filter_empty"
            )
            return [], NativeWhereFrontierRow(
                case_index=case_index,
                failed_atom_index=condition_index,
                atoms_satisfied=condition_index,
                frontier_count=frontier_count,
                failure_kind=failure_kind,
            )
    return envs, None


def _validate_nonnegative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative int")


__all__ = [
    "NativeWhereFrontierEvaluation",
    "NativeWhereFrontierFailureKind",
    "NativeWhereFrontierRow",
    "evaluate_native_where_frontier",
]
