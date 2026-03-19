from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from factpy_kernel.core.rules._trace import (
    RuleRunResult,
    RuleTraceArtifact,
    RuleTraceCaptureContext,
    RuleTraceInvocation,
    RuleTraceNonFactStep,
    RuleTracePredWitness,
    RuleTraceRuleRefLink,
)
from factpy_kernel.core.rules.ruleref_common import internal_rule_pred_id, resolve_exposed_rule_ref
from factpy_kernel.core.store._support import ProjectedFact, make_non_fact_step_key, make_pred_atom_key
from factpy_kernel.core.rules.where_eval import WhereValidationError, evaluate_where
from factpy_kernel.core.store.runtime import Store
from factpy_kernel.core.view.projector import project_view_facts, project_view_facts_with_witness


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
) -> list[tuple[Any, ...]]:
    if not isinstance(store, Store):
        raise RuleCompileError("store must be Store")
    if not isinstance(rule_spec, RuleSpec):
        raise RuleCompileError("rule_spec must be RuleSpec")
    if not isinstance(registry, RuleRegistry):
        raise RuleCompileError("registry must be RuleRegistry")
    base_view_facts = project_view_facts(store.ledger, store.schema_ir)
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
    stack: set[tuple[str, str]] = set()
    return _run_rule_core(
        rule_spec,
        registry,
        base_view_facts,
        None,
        memo_rows,
        stack,
    )


def run_rule_with_trace(
    store: Store,
    rule_spec: RuleSpec,
    registry: RuleRegistry,
) -> RuleRunResult:
    if not isinstance(store, Store):
        raise RuleCompileError("store must be Store")
    if not isinstance(rule_spec, RuleSpec):
        raise RuleCompileError("rule_spec must be RuleSpec")
    if not isinstance(registry, RuleRegistry):
        raise RuleCompileError("registry must be RuleRegistry")
    base_view_facts = project_view_facts(store.ledger, store.schema_ir)
    base_witness_facts = project_view_facts_with_witness(store.ledger, store.schema_ir)
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
    stack: set[tuple[str, str]] = set()
    trace_ctx = RuleTraceCaptureContext(rule_run_id=uuid4().hex)
    rows = _run_rule_core(
        rule_spec,
        registry,
        base_view_facts,
        base_witness_facts,
        memo_rows,
        stack,
        trace_ctx=trace_ctx,
    )
    artifact = RuleTraceArtifact(
        rule_run_id=trace_ctx.rule_run_id,
        root_rule_id=rule_spec.rule_id,
        root_version=rule_spec.version,
        select_vars=tuple(rule_spec.select_vars),
        invocations=tuple(trace_ctx.invocations),
        root_rows=tuple(rows),
    )
    store._remember_rule_trace_artifact(trace_ctx.rule_run_id, artifact)
    return RuleRunResult(rule_run_id=trace_ctx.rule_run_id, rows=rows)


def _run_rule_core(
    rule_spec: RuleSpec,
    registry: RuleRegistry,
    base_view_facts: dict[str, list[tuple[Any, ...]]],
    base_witness_facts: dict[str, list[ProjectedFact]] | None,
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]],
    stack: set[tuple[str, str]],
    *,
    trace_ctx: RuleTraceCaptureContext | None = None,
) -> list[tuple[Any, ...]]:
    return _evaluate_rule(
        rule_spec,
        registry,
        base_view_facts,
        base_witness_facts,
        memo_rows,
        stack,
        trace_ctx=trace_ctx,
        parent_invocation_id=None,
    )


def _evaluate_rule(
    rule_spec: RuleSpec,
    registry: RuleRegistry,
    base_view_facts: dict[str, list[tuple[Any, ...]]],
    base_witness_facts: dict[str, list[ProjectedFact]] | None,
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]],
    stack: set[tuple[str, str]],
    *,
    trace_ctx: RuleTraceCaptureContext | None = None,
    parent_invocation_id: str | None = None,
) -> list[tuple[Any, ...]]:
    key = (rule_spec.rule_id, rule_spec.version)
    if key in memo_rows:
        rows = memo_rows[key]
        if trace_ctx is not None:
            _append_rule_trace_memo_hit(
                trace_ctx,
                rule_spec=rule_spec,
                key=key,
                parent_invocation_id=parent_invocation_id,
                rows=rows,
            )
        return rows
    if key in stack:
        raise RuleCompileError(f"RuleRef cycle detected at {rule_spec.rule_id}@{rule_spec.version}")

    invocation_id = trace_ctx.next_invocation_id() if trace_ctx is not None else None
    stack.add(key)
    try:
        rewritten_where, ref_overlay, ruleref_atom_map = _rewrite_where_rule_refs(
            rule_spec.where,
            registry,
            base_view_facts,
            base_witness_facts,
            memo_rows,
            stack,
            trace_ctx=trace_ctx,
            parent_invocation_id=invocation_id,
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
        if trace_ctx is not None and invocation_id is not None:
            pred_witnesses, non_fact_steps = _build_rule_trace_witnesses(
                original_where=rule_spec.where,
                bindings=bindings,
                base_witness_facts=base_witness_facts,
            )
            ruleref_links = tuple(
                sorted(
                    [
                        RuleTraceRuleRefLink(
                            ruleref_atom_key=make_non_fact_step_key(branch_index, atom_index, "ruleref"),
                            child_invocation_id=child_invocation_id,
                        )
                        for (branch_index, atom_index), child_invocation_id in ruleref_atom_map.items()
                    ],
                    key=lambda link: link.ruleref_atom_key,
                )
            )
            invocation = RuleTraceInvocation(
                invocation_id=invocation_id,
                parent_invocation_id=parent_invocation_id,
                rule_id=rule_spec.rule_id,
                version=rule_spec.version,
                memo_hit=False,
                memo_source_invocation_id=None,
                original_where=_to_jsonable_where(rule_spec.where),
                rewritten_where=_to_jsonable_where(rewritten_where),
                bindings=tuple(_normalize_rule_binding(binding) for binding in bindings),
                output_rows=tuple(rows),
                pred_witnesses=pred_witnesses,
                non_fact_steps=non_fact_steps,
                ruleref_links=ruleref_links,
            )
            trace_ctx.append_invocation(invocation, primary_key=key)
        return rows
    finally:
        stack.remove(key)


def _rewrite_where_rule_refs(
    where: list[Any],
    registry: RuleRegistry,
    base_view_facts: dict[str, list[tuple[Any, ...]]],
    base_witness_facts: dict[str, list[ProjectedFact]] | None,
    memo_rows: dict[tuple[str, str], list[tuple[Any, ...]]],
    stack: set[tuple[str, str]],
    *,
    trace_ctx: RuleTraceCaptureContext | None = None,
    parent_invocation_id: str | None = None,
) -> tuple[list[Any], dict[str, list[tuple[Any, ...]]], dict[tuple[int, int], str]]:
    overlay: dict[str, list[tuple[Any, ...]]] = {}
    ruleref_atom_map: dict[tuple[int, int], str] = {}

    def rewrite_atom(atom: Any, *, branch_index: int, atom_index: int) -> Any:
        if not isinstance(atom, tuple) or not atom:
            return atom
        if atom[0] != "ruleref":
            return atom
        if len(atom) != 4:
            raise RuleCompileError("ruleref atom must be ('ruleref', rule_id, version, [terms...])")
        _, rule_id, version, terms = atom
        if not isinstance(terms, list) or not terms:
            raise RuleCompileError("ruleref terms must be non-empty list")
        ref_spec = resolve_exposed_rule_ref(
            registry,
            rule_id=rule_id,
            version=version,
            terms_len=len(terms),
            error_factory=RuleCompileError,
        )
        rows = _evaluate_rule(
            ref_spec,
            registry,
            base_view_facts,
            base_witness_facts,
            memo_rows,
            stack,
            trace_ctx=trace_ctx,
            parent_invocation_id=parent_invocation_id,
        )
        # Explicit implementation constraint: capture the child invocation immediately
        # after _evaluate_rule returns, while we still know this call-site triggered it.
        if trace_ctx is not None:
            ruleref_atom_map[(branch_index, atom_index)] = trace_ctx.invocations[-1].invocation_id
        pred_id = internal_rule_pred_id(rule_id, version)
        overlay[pred_id] = rows
        return ("pred", pred_id, terms)

    if all(isinstance(item, tuple) for item in where):
        rewritten: list[Any] = []
        for atom_index, atom in enumerate(where):
            rewritten.append(rewrite_atom(atom, branch_index=0, atom_index=atom_index))
        return rewritten, overlay, ruleref_atom_map
    if all(isinstance(item, list) for item in where):
        out_branches: list[list[Any]] = []
        for branch_index, branch in enumerate(where):
            if not isinstance(branch, list):
                raise RuleCompileError("invalid where branch")
            branch_out: list[Any] = []
            for atom_index, atom in enumerate(branch):
                branch_out.append(rewrite_atom(atom, branch_index=branch_index, atom_index=atom_index))
            out_branches.append(branch_out)
        return out_branches, overlay, ruleref_atom_map
    return where, overlay, ruleref_atom_map


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


def _append_rule_trace_memo_hit(
    trace_ctx: RuleTraceCaptureContext,
    *,
    rule_spec: RuleSpec,
    key: tuple[str, str],
    parent_invocation_id: str | None,
    rows: list[tuple[Any, ...]],
) -> None:
    source_invocation_id = trace_ctx.primary_invocation_by_rule_key.get(key)
    source_invocation = trace_ctx.invocation_by_id.get(source_invocation_id) if source_invocation_id is not None else None
    invocation = RuleTraceInvocation(
        invocation_id=trace_ctx.next_invocation_id(),
        parent_invocation_id=parent_invocation_id,
        rule_id=rule_spec.rule_id,
        version=rule_spec.version,
        memo_hit=True,
        memo_source_invocation_id=source_invocation_id,
        original_where=(
            source_invocation.original_where if source_invocation is not None else _to_jsonable_where(rule_spec.where)
        ),
        rewritten_where=(
            source_invocation.rewritten_where if source_invocation is not None else _to_jsonable_where(rule_spec.where)
        ),
        bindings=source_invocation.bindings if source_invocation is not None else (),
        output_rows=tuple(rows),
        pred_witnesses=source_invocation.pred_witnesses if source_invocation is not None else (),
        non_fact_steps=source_invocation.non_fact_steps if source_invocation is not None else (),
    )
    trace_ctx.append_invocation(invocation)


def _build_rule_trace_witnesses(
    *,
    original_where: list[Any],
    bindings: list[dict[str, Any]],
    base_witness_facts: dict[str, list[ProjectedFact]] | None,
) -> tuple[tuple[RuleTracePredWitness, ...], tuple[RuleTraceNonFactStep, ...]]:
    if base_witness_facts is None:
        return (), ()
    branches = _normalize_where_branches(original_where)
    pred_witnesses: list[RuleTracePredWitness] = []
    non_fact_steps: list[RuleTraceNonFactStep] = []
    for binding_index, binding in enumerate(bindings):
        for branch_index, branch in enumerate(branches):
            for atom_index, atom in enumerate(branch):
                if not isinstance(atom, tuple) or not atom:
                    continue
                tag = atom[0]
                if tag == "pred":
                    witness = _build_rule_trace_pred_witness(
                        atom=atom,
                        branch_index=branch_index,
                        atom_index=atom_index,
                        binding_index=binding_index,
                        binding=binding,
                        base_witness_facts=base_witness_facts,
                    )
                    if witness is not None:
                        pred_witnesses.append(witness)
                    continue
                if tag == "ruleref":
                    continue
                step = _build_rule_trace_non_fact_step(
                    atom=atom,
                    branch_index=branch_index,
                    atom_index=atom_index,
                    binding_index=binding_index,
                    binding=binding,
                )
                if step is not None:
                    non_fact_steps.append(step)
    return (
        tuple(sorted(pred_witnesses, key=lambda item: (item.binding_index, item.pred_atom_key))),
        tuple(sorted(non_fact_steps, key=lambda item: (item.binding_index, item.step_key))),
    )


def _build_rule_trace_pred_witness(
    *,
    atom: tuple[Any, ...],
    branch_index: int,
    atom_index: int,
    binding_index: int,
    binding: dict[str, Any],
    base_witness_facts: dict[str, list[ProjectedFact]],
) -> RuleTracePredWitness | None:
    if len(atom) != 3:
        return None
    _, pred_id, terms = atom
    if not isinstance(pred_id, str) or not pred_id:
        return None
    if not isinstance(terms, list):
        return None
    grounded_terms = [_resolve_binding_term(term, binding) for term in terms]
    matches: list[str] = []
    for projected in base_witness_facts.get(pred_id, []):
        if list(projected.fact_tuple) == grounded_terms:
            matches.append(projected.asrt_id)
    return RuleTracePredWitness(
        binding_index=binding_index,
        pred_atom_key=make_pred_atom_key(branch_index, atom_index, pred_id),
        asrt_ids=tuple(sorted(set(matches))),
    )


def _build_rule_trace_non_fact_step(
    *,
    atom: tuple[Any, ...],
    branch_index: int,
    atom_index: int,
    binding_index: int,
    binding: dict[str, Any],
) -> RuleTraceNonFactStep | None:
    if not atom:
        return None
    tag = atom[0]
    if not isinstance(tag, str) or tag in {"pred", "ruleref"}:
        return None
    status = "negated" if tag == "not" else "evaluated"
    return RuleTraceNonFactStep(
        binding_index=binding_index,
        step_key=make_non_fact_step_key(branch_index, atom_index, tag),
        kind=tag,
        status=status,
        details=tuple(
            sorted(
                [
                    ("atom", _to_jsonable_where(atom)),
                    ("binding", [[key, value] for key, value in _normalize_rule_binding(binding)]),
                ],
                key=lambda item: item[0],
            )
        ),
    )


def _normalize_where_branches(where: list[Any]) -> list[list[Any]]:
    if all(isinstance(item, tuple) for item in where):
        return [list(where)]
    if all(isinstance(item, list) for item in where):
        return [list(branch) for branch in where if isinstance(branch, list)]
    return [list(where)]


def _normalize_rule_binding(binding: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    items: list[tuple[str, Any]] = []
    for key, value in binding.items():
        if not isinstance(key, str) or not key.startswith("$"):
            raise RuleCompileError("binding keys must be '$'-prefixed variable names")
        items.append((key, value))
    return tuple(sorted(items, key=lambda item: item[0]))


def _resolve_binding_term(term: Any, binding: dict[str, Any]) -> Any:
    if isinstance(term, str) and term.startswith("$"):
        return binding.get(term)
    return term


def _to_jsonable_where(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_to_jsonable_where(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable_where(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable_where(item) for key, item in value.items()}
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    return value
