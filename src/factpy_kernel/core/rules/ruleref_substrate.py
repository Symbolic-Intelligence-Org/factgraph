from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factpy_kernel.core.rules.ruleref_common import internal_rule_pred_id, resolve_exposed_rule_ref
from factpy_kernel.core.rules.where_ast import WhereASTError, parse_where_ir_to_ast
from factpy_kernel.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast
from factpy_kernel.core.rules.where_eval import WhereValidationError, evaluate_where


@dataclass(frozen=True)
class NativeWhereEvaluation:
    bindings: list[dict[str, Any]]
    rule_refs: tuple[str, ...] = ()


def evaluate_native_where(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    registry: Any | None = None,
) -> NativeWhereEvaluation:
    has_ruleref = _contains_ruleref_atom(where)
    if registry is None:
        if has_ruleref:
            raise WhereValidationError("RuleRef execution requires explicit RuleRegistry")
        return NativeWhereEvaluation(bindings=evaluate_where(view_facts, where))

    if has_ruleref:
        _validate_where_for_ruleref(where)
        memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
        stack: set[tuple[str, str]] = set()
        rewritten_where, overlay, direct_rule_refs = _rewrite_where_rule_refs(
            where,
            registry=registry,
            base_view_facts=view_facts,
            memo_rows=memo_rows,
            stack=stack,
        )
        resolved_view_facts = dict(view_facts)
        resolved_view_facts.update(overlay)
        bindings = evaluate_where(resolved_view_facts, rewritten_where)
        return NativeWhereEvaluation(bindings=bindings, rule_refs=tuple(sorted(set(direct_rule_refs))))

    return NativeWhereEvaluation(bindings=evaluate_where(view_facts, where))


def _validate_where_for_ruleref(where: list[Any]) -> None:
    try:
        ast = parse_where_ir_to_ast(where)
        validate_where_ast(
            ast,
            mode="python",
            capabilities={"allow_ruleref": True},
        )
    except (WhereASTError, WhereASTValidationError) as exc:
        adapted = WhereValidationError(str(exc))
        setattr(adapted, "path", getattr(exc, "path", None) or "$.where")
        raise adapted from exc


def _rewrite_where_rule_refs(
    where: list[Any],
    *,
    registry: Any,
    base_view_facts: dict[str, list[tuple[Any, ...]]],
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]],
    stack: set[tuple[str, str]],
) -> tuple[list[Any], dict[str, list[tuple[Any, ...]]], list[str]]:
    overlay: dict[str, list[tuple[Any, ...]]] = {}
    direct_rule_refs: list[str] = []

    def rewrite_atom(atom: Any) -> Any:
        if not isinstance(atom, tuple) or not atom:
            return atom
        if atom[0] != "ruleref":
            return atom
        if len(atom) != 4:
            raise WhereValidationError("ruleref atom must be ('ruleref', rule_id, version, [terms...])")
        _, rule_id, version, terms = atom
        if not isinstance(terms, list):
            raise WhereValidationError("ruleref atom terms must be list")
        ref_spec = resolve_exposed_rule_ref(
            registry,
            rule_id=rule_id,
            version=version,
            terms_len=len(terms),
            error_factory=WhereValidationError,
        )
        rows = _evaluate_registered_rule_rows(
            ref_spec,
            base_view_facts=base_view_facts,
            registry=registry,
            memo_rows=memo_rows,
            stack=stack,
        )
        pred_id = internal_rule_pred_id(ref_spec.rule_id, ref_spec.version)
        overlay[pred_id] = rows
        direct_rule_refs.append(ref_spec.rule_id)
        return ("pred", pred_id, terms)

    if all(isinstance(item, tuple) for item in where):
        return [rewrite_atom(atom) for atom in where], overlay, direct_rule_refs
    if all(isinstance(item, list) for item in where):
        out_branches: list[list[Any]] = []
        for branch in where:
            if not isinstance(branch, list):
                raise WhereValidationError("invalid where branch")
            out_branches.append([rewrite_atom(atom) for atom in branch])
        return out_branches, overlay, direct_rule_refs
    return where, overlay, direct_rule_refs


def _evaluate_registered_rule_rows(
    rule_spec: Any,
    *,
    base_view_facts: dict[str, list[tuple[Any, ...]]],
    registry: Any,
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]],
    stack: set[tuple[str, str]],
) -> list[tuple[Any, ...]]:
    key = (rule_spec.rule_id, rule_spec.version)
    if key in memo_rows:
        return memo_rows[key]
    if key in stack:
        raise WhereValidationError(f"RuleRef cycle detected at {rule_spec.rule_id}@{rule_spec.version}")

    stack.add(key)
    try:
        if _contains_ruleref_atom(rule_spec.where):
            _validate_where_for_ruleref(rule_spec.where)
            rewritten_where, overlay, _ = _rewrite_where_rule_refs(
                rule_spec.where,
                registry=registry,
                base_view_facts=base_view_facts,
                memo_rows=memo_rows,
                stack=stack,
            )
            resolved_view_facts = dict(base_view_facts)
            resolved_view_facts.update(overlay)
            bindings = evaluate_where(resolved_view_facts, rewritten_where)
        else:
            bindings = evaluate_where(base_view_facts, rule_spec.where)
        rows = _rows_from_bindings(bindings, rule_spec.select_vars)
        memo_rows[key] = rows
        return rows
    finally:
        stack.remove(key)


def _rows_from_bindings(bindings: list[dict[str, Any]], select_vars: list[str]) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for binding in bindings:
        row: list[Any] = []
        for var in select_vars:
            if var not in binding:
                raise WhereValidationError(f"select var is unbound: {var}")
            row.append(binding[var])
        rows.append(tuple(row))
    return sorted(set(rows), key=lambda item: tuple(str(cell) for cell in item))


def _contains_ruleref_atom(where: Any) -> bool:
    if isinstance(where, tuple):
        if where and where[0] == "ruleref":
            return True
        return any(_contains_ruleref_atom(item) for item in where[1:])
    if isinstance(where, list):
        return any(_contains_ruleref_atom(item) for item in where)
    return False
