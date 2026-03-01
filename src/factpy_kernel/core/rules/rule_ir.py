from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factpy_kernel.core.rules.where_eval import WhereValidationError, evaluate_where
from factpy_kernel.core.store.runtime import Store
from factpy_kernel.core.view.projector import project_view_facts


class RuleCompileError(Exception):
    pass


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    version: str
    select_vars: list[str]
    where: list[Any]
    expose: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id:
            raise RuleCompileError("rule_id must be non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise RuleCompileError("version must be non-empty string")
        if not isinstance(self.select_vars, list) or not self.select_vars:
            raise RuleCompileError("select_vars must be non-empty list")
        for var in self.select_vars:
            if not isinstance(var, str) or not var.startswith("$"):
                raise RuleCompileError("select_vars must be variable names prefixed with '$'")
        if not isinstance(self.where, list) or not self.where:
            raise RuleCompileError("where must be non-empty list")


class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[tuple[str, str], RuleSpec] = {}

    def register(self, rule_spec: RuleSpec) -> None:
        if not isinstance(rule_spec, RuleSpec):
            raise RuleCompileError("rule_spec must be RuleSpec")
        key = (rule_spec.rule_id, rule_spec.version)
        if key in self._rules:
            raise RuleCompileError(f"duplicate rule registration: {rule_spec.rule_id}@{rule_spec.version}")
        self._rules[key] = rule_spec

    def resolve(self, rule_id: str, version: str) -> RuleSpec:
        key = (rule_id, version)
        if key not in self._rules:
            raise RuleCompileError(f"unknown RuleRef: {rule_id}@{version}")
        return self._rules[key]


def run_rule(
    store: Store,
    rule_spec: RuleSpec,
    registry: RuleRegistry,
    *,
    temporal_view: str = "active",
) -> list[tuple[Any, ...]]:
    if not isinstance(store, Store):
        raise RuleCompileError("store must be Store")
    if not isinstance(rule_spec, RuleSpec):
        raise RuleCompileError("rule_spec must be RuleSpec")
    if not isinstance(registry, RuleRegistry):
        raise RuleCompileError("registry must be RuleRegistry")
    if temporal_view not in {"active", "current"}:
        raise RuleCompileError("temporal_view must be 'active' or 'current'")

    base_view_facts = project_view_facts(store.ledger, store.schema_ir, temporal_view=temporal_view)
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
    stack: set[tuple[str, str]] = set()
    return _evaluate_rule(
        rule_spec,
        registry,
        base_view_facts,
        memo_rows,
        stack,
    )


def internal_rule_pred_id(rule_id: str, version: str) -> str:
    safe_rule = _sanitize(rule_id)
    safe_ver = _sanitize(version)
    return f"__rule_ref__{safe_rule}__{safe_ver}"


def _sanitize(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch.isalnum():
            out.append(ch.lower())
        else:
            out.append("_")
    return "".join(out)


def _evaluate_rule(
    rule_spec: RuleSpec,
    registry: RuleRegistry,
    base_view_facts: dict[str, list[tuple[Any, ...]]],
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]],
    stack: set[tuple[str, str]],
) -> list[tuple[Any, ...]]:
    key = (rule_spec.rule_id, rule_spec.version)
    if key in memo_rows:
        return memo_rows[key]
    if key in stack:
        raise RuleCompileError(f"RuleRef cycle detected at {rule_spec.rule_id}@{rule_spec.version}")

    stack.add(key)
    try:
        rewritten_where, ref_overlay = _rewrite_where_rule_refs(
            rule_spec.where,
            registry,
            base_view_facts,
            memo_rows,
            stack,
        )
        view_facts = dict(base_view_facts)
        for (dep_rule_id, dep_version), dep_rows in memo_rows.items():
            dep_spec = registry.resolve(dep_rule_id, dep_version)
            if dep_spec.expose:
                view_facts[internal_rule_pred_id(dep_rule_id, dep_version)] = dep_rows
        for pred_id, rows in ref_overlay.items():
            view_facts[pred_id] = rows

        try:
            bindings = evaluate_where(view_facts, rewritten_where)
        except WhereValidationError as exc:
            raise RuleCompileError(str(exc)) from exc

        rows = _rows_from_bindings(bindings, rule_spec.select_vars)
        if rule_spec.expose:
            memo_rows[key] = rows
        return rows
    finally:
        stack.remove(key)


def _rewrite_where_rule_refs(
    where: list[Any],
    registry: RuleRegistry,
    base_view_facts: dict[str, list[tuple[Any, ...]]],
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]],
    stack: set[tuple[str, str]],
) -> tuple[list[Any], dict[str, list[tuple[Any, ...]]]]:
    overlay: dict[str, list[tuple[Any, ...]]] = {}

    def rewrite_atom(atom: Any) -> Any:
        if not isinstance(atom, tuple) or not atom:
            return atom
        if atom[0] != "ruleref":
            return atom
        if len(atom) != 4:
            raise RuleCompileError("ruleref atom must be ('ruleref', rule_id, version, [terms...])")
        _, rule_id, version, terms = atom
        if not isinstance(rule_id, str) or not rule_id:
            raise RuleCompileError("ruleref rule_id must be non-empty string")
        if not isinstance(version, str) or not version:
            raise RuleCompileError("ruleref version must be non-empty string")
        if not isinstance(terms, list) or not terms:
            raise RuleCompileError("ruleref terms must be non-empty list")

        ref_spec = registry.resolve(rule_id, version)
        if not ref_spec.expose:
            raise RuleCompileError(f"RuleRef target must be expose=True: {rule_id}@{version}")
        if len(terms) != len(ref_spec.select_vars):
            raise RuleCompileError(
                f"RuleRef arity mismatch for {rule_id}@{version}: expected {len(ref_spec.select_vars)}, got {len(terms)}"
            )
        rows = _evaluate_rule(ref_spec, registry, base_view_facts, memo_rows, stack)
        pred_id = internal_rule_pred_id(rule_id, version)
        overlay[pred_id] = rows
        return ("pred", pred_id, terms)

    if all(isinstance(item, tuple) for item in where):
        return [rewrite_atom(item) for item in where], overlay
    if all(isinstance(item, list) for item in where):
        out_branches: list[list[Any]] = []
        for branch in where:
            if not isinstance(branch, list):
                raise RuleCompileError("invalid where branch")
            out_branches.append([rewrite_atom(atom) for atom in branch])
        return out_branches, overlay
    return where, overlay


def _rows_from_bindings(bindings: list[dict[str, Any]], select_vars: list[str]) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for binding in bindings:
        row: list[Any] = []
        for var in select_vars:
            if var not in binding:
                raise RuleCompileError(f"select var is unbound: {var}")
            row.append(binding[var])
        rows.append(tuple(row))

    dedup = sorted(set(rows), key=lambda row: tuple(str(cell) for cell in row))
    return dedup
