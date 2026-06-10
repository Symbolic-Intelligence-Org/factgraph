from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any

from factgraph.application.diagnose_runtime import _extend_env_with_atom
from factgraph.application.entity_view import _recover_identity_from_predicates
from factgraph.application import schema_runtime
from factgraph.application.protocol.schema_runtime import EntityRef
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprEvaluationTrace,
    RuleExprJoinMaterialization,
    RuleExprLoweringBranch,
    RuleExprLoweringPlan,
    RuleExprOccurrenceBinding,
    _materialize_native_derivation_plan,
)
from factgraph.application.protocol.certainty import BOOLEAN_CERTAINTY
from factgraph.core.protocol.tup_v1 import ENTITY_REF_PREFIX, display_float64_value
from factgraph.core.rules.where_ast import _AGGREGATE_KINDS, _parse_term, AggregateAtom
from factgraph.core.rules.where_ast_validate import _aggregate_filter_bound_vars

from .evidence_tree import (
    BoundVar,
    Builtin,
    Compare,
    Const,
    EvidenceAtom,
    EvidenceJoin,
    EvidenceProbeResult,
    EvidenceRule,
    EvidenceTree,
    Fact,
    Fails,
    Holds,
    NotReached,
    PortRef,
    TreeStatus,
)

_REPR_PLACEHOLDER_RE = re.compile(r"%[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class ProbeEnv:
    bindings: Mapping[str, Any]

    @classmethod
    def from_bindings(cls, bindings: Mapping[str, Any] | None = None) -> ProbeEnv:
        return cls(dict(bindings or {}))


def probe_native(
    plan: RuleExprLoweringPlan,
    bindings: Mapping[str, Any] | None,
    view_facts: Mapping[str, Sequence[tuple[Any, ...]]],
    schema_index: object | None = None,
) -> EvidenceProbeResult:
    if not isinstance(plan, RuleExprLoweringPlan):
        raise TypeError("plan must be RuleExprLoweringPlan")
    compiled, traces = _materialize_native_derivation_plan(plan)
    branches = _normalize_compiled_body(compiled.body_ir)
    paths: list[EvidenceTree] = []
    for branch, trace, lowered_branch in zip(branches, traces, plan.branches, strict=True):
        paths.append(
            _probe_branch(
                plan,
                lowered_branch,
                trace,
                branch,
                view_facts={key: list(value) for key, value in view_facts.items()},
                initial_bindings=dict(bindings or {}),
                schema_index=schema_index,
            )
        )
    return EvidenceProbeResult(paths=tuple(paths), certainty=BOOLEAN_CERTAINTY)


def _probe_branch(
    plan: RuleExprLoweringPlan,
    lowered_branch: RuleExprLoweringBranch,
    trace: RuleExprEvaluationTrace,
    atoms: list[tuple[Any, ...]],
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    initial_bindings: dict[str, Any],
    schema_index: object | None,
) -> EvidenceTree:
    anchor_envs = (ProbeEnv.from_bindings(initial_bindings),)
    envs = anchor_envs
    verdict_envs = anchor_envs
    atom_results: list[tuple[int, tuple[Any, ...], EvidenceAtom, tuple[ProbeEnv, ...]]] = []
    failed_upstream = False
    join_indexes = {join.materialized_condition_index for join in trace.join_materializations}
    head_link_indexes = {link.materialized_condition_index for link in trace.head_port_link_materializations}

    for idx, atom in enumerate(atoms):
        before_envs = envs
        if idx in join_indexes or idx in head_link_indexes:
            evidence_atom, envs, verdict_envs = _probe_atom(
                atom,
                before_envs,
                verdict_envs=verdict_envs,
                view_facts=view_facts,
                atom_id=f"{trace.branch_id}:materialized:{idx}",
                failed_upstream=failed_upstream,
                schema_index=schema_index,
            )
            if isinstance(evidence_atom.verdict, Fails):
                failed_upstream = True
            atom_results.append((idx, atom, evidence_atom, envs))
            continue

        evidence_atom, envs, verdict_envs = _probe_atom(
            atom,
            before_envs,
            verdict_envs=verdict_envs,
            view_facts=view_facts,
            atom_id=f"{trace.branch_id}:atom:{idx}",
            failed_upstream=failed_upstream,
            schema_index=schema_index,
        )
        if isinstance(evidence_atom.verdict, Fails):
            failed_upstream = True
        atom_results.append((idx, atom, evidence_atom, envs))

    atom_results = _rebake_atom_results_from_terminal(
        atom_results,
        terminal_envs=envs,
        view_facts=view_facts,
        schema_index=schema_index,
    )
    body_rules = _body_rules_for_branch(plan, lowered_branch, trace, atom_results, terminal_envs=envs)
    joins = _joins_for_trace(trace, atom_results)
    status = _tree_status((*body_rules,)) if body_rules else "fails"
    head_rule = _head_rule_for_plan(plan, status=status, terminal_envs=envs, initial_bindings=initial_bindings)
    return EvidenceTree(
        tree_id=trace.branch_id,
        status=status,
        rules=(head_rule, *body_rules),
        joins=joins,
        certainty=BOOLEAN_CERTAINTY,
        metadata={"branch_id": trace.branch_id, "runtime_case_index": trace.runtime_case_index},
    )


def _probe_atom(
    atom: tuple[Any, ...],
    envs: tuple[ProbeEnv, ...],
    *,
    verdict_envs: tuple[ProbeEnv, ...],
    view_facts: dict[str, list[tuple[Any, ...]]],
    atom_id: str,
    failed_upstream: bool,
    schema_index: object | None,
) -> tuple[EvidenceAtom, tuple[ProbeEnv, ...], tuple[ProbeEnv, ...]]:
    runnable_envs: list[ProbeEnv] = []
    blocked_by: str | None = None
    verdict_only = failed_upstream and not envs
    candidate_envs = envs
    if verdict_only:
        for env in verdict_envs:
            missing = _missing_verdict_dependencies(atom, env.bindings)
            if missing:
                blocked_by = blocked_by or missing[0]
                continue
            runnable_envs.append(env)
    elif _atom_can_bind(atom):
        runnable_envs = list(envs)
    elif not failed_upstream:
        for env in envs:
            missing = _missing_variables(atom, env.bindings)
            if missing:
                blocked_by = missing[0]
                continue
            runnable_envs.append(env)
    elif envs:
        runnable_envs = list(envs)

    next_envs: list[ProbeEnv] = []
    for env in runnable_envs:
        for next_env in _extend_env_with_atom(view_facts, dict(env.bindings), atom):
            next_envs.append(ProbeEnv.from_bindings(next_env))
    deduped = _dedupe_envs(next_envs)
    form_envs = deduped or tuple(runnable_envs) or envs or verdict_envs
    form = _atom_form(atom, form_envs)
    negated = _is_not_atom(atom)
    repr_text = (
        _repr_not_atom(atom, form_envs, schema_index, view_facts=view_facts)
        if negated
        else _bake_repr_text(form, schema_index, view_facts=view_facts)
    )
    if verdict_only:
        if deduped:
            return (
                EvidenceAtom(form=form, verdict=Holds(), atom_id=atom_id, repr_text=repr_text, negated=negated),
                candidate_envs,
                deduped,
            )
        if blocked_by is not None and not runnable_envs:
            return (
                EvidenceAtom(
                    form=form,
                    verdict=NotReached(blocked_by=blocked_by),
                    atom_id=atom_id,
                    repr_text=repr_text,
                    negated=negated,
                ),
                candidate_envs,
                verdict_envs,
            )
        return (
            EvidenceAtom(form=form, verdict=Fails(), atom_id=atom_id, repr_text=repr_text, negated=negated),
            candidate_envs,
            tuple(runnable_envs) or verdict_envs,
        )
    if deduped:
        return EvidenceAtom(form=form, verdict=Holds(), atom_id=atom_id, repr_text=repr_text, negated=negated), deduped, deduped
    if blocked_by is not None:
        return (
            EvidenceAtom(
                form=form,
                verdict=NotReached(blocked_by=blocked_by),
                atom_id=atom_id,
                repr_text=repr_text,
                negated=negated,
            ),
            (),
            envs or verdict_envs,
        )
    return EvidenceAtom(form=form, verdict=Fails(), atom_id=atom_id, repr_text=repr_text, negated=negated), (), envs or verdict_envs


def _body_rules_for_branch(
    plan: RuleExprLoweringPlan,
    lowered_branch: RuleExprLoweringBranch,
    trace: RuleExprEvaluationTrace,
    atom_results: list[tuple[int, tuple[Any, ...], EvidenceAtom, tuple[ProbeEnv, ...]]],
    *,
    terminal_envs: tuple[ProbeEnv, ...],
) -> tuple[EvidenceRule, ...]:
    occurrence_by_alias = {occ.alias: occ for occ in plan.occurrence_map}
    join_indexes = {join.materialized_condition_index for join in trace.join_materializations}
    head_link_indexes = {link.materialized_condition_index for link in trace.head_port_link_materializations}
    grouped: dict[str, list[EvidenceAtom]] = {alias: [] for alias in lowered_branch.occurrence_aliases}
    fallback_alias = lowered_branch.occurrence_aliases[0] if lowered_branch.occurrence_aliases else ""
    for idx, atom, evidence_atom, _envs in atom_results:
        if idx in join_indexes or idx in head_link_indexes:
            continue
        alias = _alias_for_atom(atom, lowered_branch.occurrence_aliases) or fallback_alias
        grouped.setdefault(alias, []).append(evidence_atom)

    return tuple(
        EvidenceRule(
            occurrence_alias=alias,
            rule_id=occurrence_by_alias[alias].rule_id if alias in occurrence_by_alias else alias,
            role="body",
            status=_atom_status(tuple(atoms)),
            ports=_ports_for_occurrence(occurrence_by_alias.get(alias), terminal_envs),
            atoms=tuple(atoms),
        )
        for alias, atoms in grouped.items()
    )


def _atom_var_names(atom: tuple[Any, ...]) -> set[str]:
    out: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, str) and value.startswith("$"):
            out.add(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(atom)
    return out


def _rebake_atom_results_from_terminal(
    atom_results: list[tuple[int, tuple[Any, ...], EvidenceAtom, tuple[ProbeEnv, ...]]],
    *,
    terminal_envs: tuple[ProbeEnv, ...],
    view_facts: dict[str, list[tuple[Any, ...]]],
    schema_index: object | None,
) -> list[tuple[int, tuple[Any, ...], EvidenceAtom, tuple[ProbeEnv, ...]]]:
    if not terminal_envs:
        return atom_results
    terminal_bindings = terminal_envs[0].bindings
    rebaked: list[tuple[int, tuple[Any, ...], EvidenceAtom, tuple[ProbeEnv, ...]]] = []
    for idx, atom, evidence_atom, envs_after in atom_results:
        if not evidence_atom.negated:
            names = _atom_var_names(atom)
            if names and all(terminal_bindings.get(name) is not None for name in names):
                original_bindings = envs_after[0].bindings if envs_after else {}
                if all(original_bindings.get(name) == terminal_bindings.get(name) for name in names):
                    rebaked.append((idx, atom, evidence_atom, envs_after))
                    continue
                form = _atom_form(atom, terminal_envs)
                repr_text = _bake_repr_text(form, schema_index, view_facts=view_facts)
                evidence_atom = EvidenceAtom(
                    form=form,
                    verdict=evidence_atom.verdict,
                    atom_id=evidence_atom.atom_id,
                    repr_text=repr_text,
                    negated=evidence_atom.negated,
                    timestep=evidence_atom.timestep,
                )
        rebaked.append((idx, atom, evidence_atom, envs_after))
    return rebaked


def _head_rule_for_plan(
    plan: RuleExprLoweringPlan,
    *,
    status: TreeStatus,
    terminal_envs: tuple[ProbeEnv, ...],
    initial_bindings: Mapping[str, Any],
) -> EvidenceRule:
    env = dict(terminal_envs[0].bindings) if terminal_envs else dict(initial_bindings)
    ports = {
        port_name: env.get(var.name)
        for port_name, var in plan.head.ports.items()
    }
    return EvidenceRule(
        occurrence_alias=plan.head.id,
        rule_id=plan.head.id,
        role="head",
        status=status,
        ports=ports,
        atoms=(),
    )


def _joins_for_trace(
    trace: RuleExprEvaluationTrace,
    atom_results: list[tuple[int, tuple[Any, ...], EvidenceAtom, tuple[ProbeEnv, ...]]],
) -> tuple[EvidenceJoin, ...]:
    atom_by_index = {idx: evidence_atom for idx, _atom, evidence_atom, _envs in atom_results}
    joins: list[EvidenceJoin] = []
    for join in trace.join_materializations:
        evidence_atom = atom_by_index.get(join.materialized_condition_index)
        status: TreeStatus = "not_reached"
        if evidence_atom is not None:
            status = _verdict_status(evidence_atom.verdict)
        joins.append(
            EvidenceJoin(
                left=PortRef(join.left_occurrence_alias, join.left_port_name),
                right=PortRef(join.right_occurrence_alias, join.right_port_name),
                status=status,
                join_id=_join_id(join),
            )
        )
    return tuple(joins)


def _ports_for_occurrence(
    occurrence: RuleExprOccurrenceBinding | None,
    envs: tuple[ProbeEnv, ...],
) -> Mapping[str, Any]:
    if occurrence is None:
        return {}
    env = envs[0].bindings if envs else {}
    return {
        binding.port_name: env.get(binding.alias_local_execution_var.name)
        for binding in occurrence.port_bindings
    }


def _atom_form(atom: tuple[Any, ...], envs: tuple[ProbeEnv, ...]) -> Fact | Compare | Builtin:
    env = envs[0].bindings if envs else {}
    kind = atom[0]
    if kind == "pred":
        return Fact(predicate=str(atom[1]), terms=tuple(_term_form(term, env) for term in atom[2]))
    if kind in {"eq", "ne", "gt", "ge", "lt", "le"}:
        return Compare(op=str(kind), left=_term_form(atom[1], env), right=_term_form(atom[2], env))
    if kind == "not":
        return Builtin(kind="not", operands=())
    operands: tuple[BoundVar | Const, ...]
    if kind in {"in"}:
        operands = (_term_form(atom[1], env), *tuple(_term_form(term, env) for term in atom[2]))
    else:
        operands = tuple(_term_form(term, env) for term in atom[1:])
    return Builtin(kind=str(kind), operands=operands)


def _term_form(term: Any, env: Mapping[str, Any]) -> BoundVar | Const:
    if isinstance(term, str) and term.startswith("$"):
        return BoundVar(name=term, value=env.get(term), bound_by=None)
    return Const(term)


def _bake_repr_text(
    form: Fact | Compare | Builtin,
    schema_index: object | None,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    if isinstance(form, Fact):
        return _repr_fact(form, schema_index, view_facts=view_facts)
    if isinstance(form, Compare):
        return _repr_compare(form, schema_index, view_facts=view_facts)
    return _repr_builtin(form, schema_index, view_facts=view_facts)


def _repr_not_atom(
    atom: tuple[Any, ...],
    envs: tuple[ProbeEnv, ...],
    schema_index: object | None,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    branches = _not_body_branches(atom)
    if not branches:
        return "!<not>"
    branch_texts = tuple(
        _repr_not_branch(branch, envs, schema_index, view_facts=view_facts)
        for branch in branches
    )
    if len(branch_texts) == 1:
        text = branch_texts[0]
        return f"!{text}" if not text.startswith("(") else f"!{text}"
    return "!(" + " || ".join(branch_texts) + ")"


def _repr_not_branch(
    branch: tuple[tuple[Any, ...], ...],
    envs: tuple[ProbeEnv, ...],
    schema_index: object | None,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    atom_texts = tuple(
        _repr_inner_not_atom(inner_atom, envs, schema_index, view_facts=view_facts)
        for inner_atom in branch
    )
    if not atom_texts:
        return "<empty>"
    if len(atom_texts) == 1:
        return atom_texts[0]
    return "(" + " && ".join(atom_texts) + ")"


def _repr_inner_not_atom(
    atom: tuple[Any, ...],
    envs: tuple[ProbeEnv, ...],
    schema_index: object | None,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    if _is_not_atom(atom):
        return _repr_not_atom(atom, envs, schema_index, view_facts=view_facts)
    form = _atom_form(atom, envs)
    return _bake_repr_text(form, schema_index, view_facts=view_facts)


def _not_body_branches(atom: tuple[Any, ...]) -> tuple[tuple[tuple[Any, ...], ...], ...]:
    if not _is_not_atom(atom):
        return ()
    not_body = atom[1]
    if not isinstance(not_body, list) or not not_body:
        return ()
    if all(_is_atom_tuple(item) for item in not_body):
        return (tuple(not_body),)  # type: ignore[return-value]
    if all(isinstance(item, list) for item in not_body):
        branches: list[tuple[tuple[Any, ...], ...]] = []
        for branch in not_body:
            if not branch or not all(_is_atom_tuple(inner) for inner in branch):
                return ()
            branches.append(tuple(branch))  # type: ignore[arg-type]
        return tuple(branches)
    return ()


def _repr_fact(
    form: Fact,
    schema_index: object | None,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    info = _predicate_info(schema_index, form.predicate)
    if info is None or info.repr is None:
        return _fact_fallback_repr(form, schema_index, view_facts=view_facts, predicate_info=info)

    placeholder_values = {
        "%CLS": info.owner_type,
        "%FLD": _render_term_value(
            form.terms[1],
            schema_index=schema_index,
            view_facts=view_facts,
            decode_float64=info.value_type_domain == "float64",
        )
        if len(form.terms) > 1
        else "",
        "%ENT": _entity_repr_for_fact(schema_index, info.owner_type, form, view_facts=view_facts),
    }

    def replace_placeholder(match: re.Match[str]) -> str:
        token = match.group(0)
        return placeholder_values.get(token, token)

    return _REPR_PLACEHOLDER_RE.sub(replace_placeholder, info.repr)


def _predicate_info(schema_index: object | None, predicate: str) -> object | None:
    if schema_index is None:
        return None
    predicates = getattr(schema_index, "predicates_by_id", None)
    if not isinstance(predicates, Mapping):
        return None
    return predicates.get(predicate)


def _entity_repr_for_fact(
    schema_index: object | None,
    entity_type: str,
    form: Fact,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    subject = form.terms[0] if form.terms else None
    value = _term_value(subject)
    if schema_index is not None and isinstance(value, EntityRef):
        try:
            return schema_runtime.render_entity_repr(schema_index, value.entity_type, value.identity)
        except Exception:
            return _render_term_value(subject, schema_index=schema_index, view_facts=view_facts)
    if schema_index is not None and isinstance(value, Mapping):
        identity = value.get("identity")
        ref_entity_type = value.get("entity_type", entity_type)
        if isinstance(ref_entity_type, str) and isinstance(identity, Mapping):
            try:
                return schema_runtime.render_entity_repr(schema_index, ref_entity_type, identity)
            except Exception:
                return _render_term_value(subject, schema_index=schema_index, view_facts=view_facts)
    if schema_index is not None and isinstance(value, str) and value.startswith(ENTITY_REF_PREFIX):
        try:
            identity = _recover_identity_from_predicates(value, entity_type, view_facts=view_facts, index=schema_index)
            return schema_runtime.render_entity_repr(schema_index, entity_type, identity)
        except Exception:
            return _render_term_value(subject, schema_index=schema_index, view_facts=view_facts)
    return _render_term_value(subject, schema_index=schema_index, view_facts=view_facts)


def _fact_fallback_repr(
    form: Fact,
    schema_index: object | None,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    predicate_info: object | None,
) -> str:
    terms = tuple(
        _render_term_value(
            term,
            schema_index=schema_index,
            view_facts=view_facts,
            decode_float64=idx > 0 and getattr(predicate_info, "value_type_domain", None) == "float64",
        )
        for idx, term in enumerate(form.terms)
    )
    return f"{form.predicate}({', '.join(terms)})"


def _repr_compare(
    form: Compare,
    schema_index: object | None,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    left = _render_term_value(form.left, schema_index=schema_index, view_facts=view_facts, decode_float64=True)
    right = _render_term_value(form.right, schema_index=schema_index, view_facts=view_facts, decode_float64=True)
    labels = {
        "eq": "equals",
        "ne": "does not equal",
        "gt": ">",
        "ge": ">=",
        "lt": "<",
        "le": "<=",
    }
    op = labels.get(form.op, form.op)
    return f"{left} {op} {right}"


def _repr_builtin(
    form: Builtin,
    schema_index: object | None,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    terms = tuple(
        _render_term_value(term, schema_index=schema_index, view_facts=view_facts, decode_float64=True)
        for term in form.operands
    )
    if form.kind == "in" and terms:
        return f"{terms[0]} is in ({', '.join(terms[1:])})"
    if form.kind == "not" and terms:
        return f"not {terms[0]}"
    return f"{form.kind}({', '.join(terms)})"


def _render_term_value(
    term: BoundVar | Const | None,
    *,
    schema_index: object | None,
    view_facts: dict[str, list[tuple[Any, ...]]],
    decode_float64: bool = False,
) -> str:
    value = _term_value(term)
    if _is_aggregate_term(value):
        return _render_aggregate_term(value)
    if isinstance(value, EntityRef):
        fallback = value.encoded_ref or f"{value.entity_type}({', '.join(str(v) for v in value.identity.values())})"
        try:
            return schema_runtime.render_entity_repr(schema_index, value.entity_type, value.identity) if schema_index is not None else fallback
        except Exception:
            return fallback
    if schema_index is not None and isinstance(value, Mapping):
        identity = value.get("identity")
        ref_entity_type = value.get("entity_type")
        if isinstance(ref_entity_type, str) and isinstance(identity, Mapping):
            try:
                return schema_runtime.render_entity_repr(schema_index, ref_entity_type, identity)
            except Exception:
                pass
    if schema_index is not None and isinstance(value, str) and value.startswith(ENTITY_REF_PREFIX):
        entity_type = _entity_type_from_ref(value)
        if entity_type is not None:
            try:
                identity = _recover_identity_from_predicates(value, entity_type, view_facts=view_facts, index=schema_index)
                return schema_runtime.render_entity_repr(schema_index, entity_type, identity)
            except Exception:
                pass
    if decode_float64 and isinstance(value, str):
        try:
            return display_float64_value(value)
        except Exception:
            pass
    if value is None and isinstance(term, BoundVar):
        return "<unbound>"
    return str(value)


def _render_aggregate_term(value: tuple[Any, ...]) -> str:
    kind = str(value[0])
    target = value[1] if len(value) > 1 else None
    if kind == "count":
        return "count"
    label = _aggregate_target_label(target, value[2] if len(value) > 2 else ())
    return f"{kind} of {label}"


def _aggregate_target_label(target: Any, filter_atoms: Any) -> str:
    target_vars = set(_vars_in_atom_tuple(target))
    if target_vars and isinstance(filter_atoms, list):
        for atom in filter_atoms:
            if not _is_atom_tuple(atom) or atom[0] != "pred" or len(atom) < 3:
                continue
            pred_id = atom[1]
            terms = atom[2]
            if not isinstance(terms, Sequence) or isinstance(terms, (str, bytes)):
                continue
            if target_vars & set(_vars_in_atom_tuple(terms)):
                if isinstance(pred_id, str) and ":" in pred_id:
                    return pred_id.rsplit(":", 1)[1]
    if target_vars:
        return _clean_var_label(sorted(target_vars)[0])
    return "value"


def _clean_var_label(var_name: str) -> str:
    label = var_name[1:] if var_name.startswith("$") else var_name
    if "__" in label:
        label = label.rsplit("__", 1)[1]
    if label.startswith("_agg"):
        label = label[4:]
    if label.startswith("agg"):
        label = label[3:]
    return label or "value"


def _entity_type_from_ref(value: str) -> str | None:
    parts = value.split(":", 2)
    if len(parts) != 3 or parts[0] != ENTITY_REF_PREFIX[:-1] or not parts[1]:
        return None
    return parts[1]


def _term_value(term: BoundVar | Const | None) -> Any:
    if isinstance(term, BoundVar):
        return term.value
    if isinstance(term, Const):
        return term.value
    return None


def _atom_can_bind(atom: tuple[Any, ...]) -> bool:
    return bool(atom) and atom[0] == "pred"


def _is_not_atom(atom: tuple[Any, ...]) -> bool:
    return bool(atom) and atom[0] == "not" and len(atom) == 2


def _missing_variables(atom: tuple[Any, ...], env: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(var for var in _vars_for_missing_check(atom, env) if var not in env)


def _missing_verdict_dependencies(atom: tuple[Any, ...], env: Mapping[str, Any]) -> tuple[str, ...]:
    if _atom_can_bind(atom):
        terms = atom[2] if len(atom) > 2 else ()
        if not isinstance(terms, Sequence) or isinstance(terms, (str, bytes)) or not terms:
            return _missing_variables(atom, env)
        return tuple(var for var in _vars_for_missing_check(terms[0], env) if var not in env)
    return _missing_variables(atom, env)


def _vars_for_missing_check(atom: Any, env: Mapping[str, Any]) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(atom, str) and atom.startswith("$"):
        return (atom,)
    if _is_aggregate_term(atom):
        found.extend(_aggregate_required_outer_vars(atom, env))
    elif isinstance(atom, (list, tuple)):
        for item in atom:
            found.extend(_vars_for_missing_check(item, env))
    return tuple(dict.fromkeys(found))


def _is_aggregate_term(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 3
        and isinstance(value[0], str)
        and value[0] in _AGGREGATE_KINDS
        and isinstance(value[2], list)
    )


def _aggregate_required_outer_vars(aggregate_term: tuple[Any, ...], env: Mapping[str, Any]) -> tuple[str, ...]:
    _kind, target, filter_atoms = aggregate_term
    all_vars = set(_vars_in_atom_tuple(target))
    all_vars |= set(_vars_in_atom_tuple(filter_atoms))
    local_vars = _aggregate_local_vars(aggregate_term, env)
    return tuple(var for var in _vars_in_atom_tuple((target, filter_atoms)) if var in all_vars - local_vars)


def _aggregate_local_vars(aggregate_term: tuple[Any, ...], env: Mapping[str, Any]) -> set[str]:
    _kind, target, filter_atoms = aggregate_term
    target_vars = set(_vars_in_atom_tuple(target))
    local = set(target_vars)
    if not isinstance(filter_atoms, list):
        return local

    canonically_bound = _canonical_aggregate_filter_bound_vars(aggregate_term, env)
    pred_atoms = [atom for atom in filter_atoms if _is_atom_tuple(atom) and atom[0] == "pred" and len(atom) >= 3]

    changed = True
    while changed:
        changed = False
        for atom in pred_atoms:
            terms = atom[2]
            if not isinstance(terms, Sequence) or isinstance(terms, (str, bytes)) or not terms:
                continue
            subject_vars = set(_vars_in_atom_tuple(terms[0]))
            for var in subject_vars:
                if var not in local:
                    local.add(var)
                    changed = True
            for term in terms[1:]:
                for var in _vars_in_atom_tuple(term):
                    if (
                        var in target_vars
                        or (_is_lowered_aggregate_local_var(var) and var in canonically_bound)
                    ) and var not in local:
                        local.add(var)
                        changed = True
    return local


def _canonical_aggregate_filter_bound_vars(aggregate_term: tuple[Any, ...], env: Mapping[str, Any]) -> set[str]:
    try:
        parsed = _parse_term(aggregate_term, path="$.aggregate")
    except Exception:
        return set()
    if not isinstance(parsed, AggregateAtom):
        return set()
    try:
        return set(_aggregate_filter_bound_vars(parsed, set(env))) - set(env)
    except Exception:
        return set()


def _is_lowered_aggregate_local_var(var_name: str) -> bool:
    return var_name.startswith("$agg") or var_name.startswith("$_agg") or "__" in var_name


def _vars_in_atom_tuple(atom: Any) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(atom, str) and atom.startswith("$"):
        return (atom,)
    if isinstance(atom, (list, tuple)):
        for item in atom:
            found.extend(_vars_in_atom_tuple(item))
    return tuple(dict.fromkeys(found))


def _alias_for_atom(atom: tuple[Any, ...], aliases: tuple[str, ...]) -> str | None:
    variables = _vars_in_atom_tuple(atom)
    for alias in aliases:
        prefix = f"${alias}__"
        if any(var.startswith(prefix) for var in variables):
            return alias
    return None


def _normalize_compiled_body(body_ir: object) -> list[list[tuple[Any, ...]]]:
    if not isinstance(body_ir, list) or not body_ir:
        raise TypeError("compiled body_ir must be non-empty list")
    if all(_is_atom_tuple(item) for item in body_ir):
        return [list(body_ir)]  # type: ignore[list-item]
    if all(isinstance(item, list) for item in body_ir):
        return [list(branch) for branch in body_ir]  # type: ignore[list-item]
    raise TypeError("compiled body_ir must be one-level AND or two-level OR")


def _is_atom_tuple(value: object) -> bool:
    return isinstance(value, tuple) and bool(value) and isinstance(value[0], str)


def _dedupe_envs(envs: list[ProbeEnv]) -> tuple[ProbeEnv, ...]:
    deduped: dict[tuple[tuple[str, str], ...], ProbeEnv] = {}
    for env in envs:
        deduped.setdefault(_env_sort_key(env.bindings), env)
    return tuple(deduped[key] for key in sorted(deduped))


def _env_sort_key(env: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple((key, repr(value)) for key, value in sorted(env.items()))


def _verdict_status(verdict: object) -> TreeStatus:
    if isinstance(verdict, Holds):
        return "holds"
    if isinstance(verdict, NotReached):
        return "not_reached"
    return "fails"


def _atom_status(atoms: tuple[EvidenceAtom, ...]) -> TreeStatus:
    if not atoms:
        return "not_reached"
    statuses = tuple(_verdict_status(atom.verdict) for atom in atoms)
    if all(status == "holds" for status in statuses):
        return "holds"
    if all(status == "not_reached" for status in statuses):
        return "not_reached"
    if any(status == "fails" for status in statuses):
        return "fails"
    return "not_reached"


def _tree_status(rules: tuple[EvidenceRule, ...]) -> TreeStatus:
    statuses = tuple(rule.status for rule in rules)
    if statuses and all(status == "holds" for status in statuses):
        return "holds"
    if statuses and all(status == "not_reached" for status in statuses):
        return "not_reached"
    if any(status == "fails" for status in statuses):
        return "fails"
    return "not_reached"


def _join_id(join: RuleExprJoinMaterialization) -> str:
    return (
        f"{join.branch_id}:{join.left_occurrence_alias}.{join.left_port_name}"
        f"={join.right_occurrence_alias}.{join.right_port_name}"
    )


__all__ = ["ProbeEnv", "probe_native"]
