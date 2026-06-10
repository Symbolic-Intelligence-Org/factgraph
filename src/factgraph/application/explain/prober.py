from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from factgraph.core.protocol.tup_v1 import ENTITY_REF_PREFIX

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
    last_non_empty_envs = anchor_envs
    atom_results: list[tuple[int, tuple[Any, ...], EvidenceAtom, tuple[ProbeEnv, ...]]] = []
    failed_upstream = False
    join_indexes = {join.materialized_condition_index for join in trace.join_materializations}
    head_link_indexes = {link.materialized_condition_index for link in trace.head_port_link_materializations}

    for idx, atom in enumerate(atoms):
        before_envs = envs
        if idx in join_indexes or idx in head_link_indexes:
            evidence_atom, envs = _probe_atom(
                atom,
                before_envs,
                verdict_envs=last_non_empty_envs,
                view_facts=view_facts,
                atom_id=f"{trace.branch_id}:materialized:{idx}",
                failed_upstream=failed_upstream,
                schema_index=schema_index,
            )
            if envs:
                last_non_empty_envs = envs
            if isinstance(evidence_atom.verdict, Fails):
                failed_upstream = True
            atom_results.append((idx, atom, evidence_atom, envs))
            continue

        evidence_atom, envs = _probe_atom(
            atom,
            before_envs,
            verdict_envs=last_non_empty_envs,
            view_facts=view_facts,
            atom_id=f"{trace.branch_id}:atom:{idx}",
            failed_upstream=failed_upstream,
            schema_index=schema_index,
        )
        if envs:
            last_non_empty_envs = envs
        if isinstance(evidence_atom.verdict, Fails):
            failed_upstream = True
        atom_results.append((idx, atom, evidence_atom, envs))

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
) -> tuple[EvidenceAtom, tuple[ProbeEnv, ...]]:
    runnable_envs: list[ProbeEnv] = []
    blocked_by: str | None = None
    verdict_only = failed_upstream and not envs
    candidate_envs = envs
    if verdict_only:
        for env in verdict_envs:
            missing = _missing_variables(atom, env.bindings)
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
    form = _atom_form(atom, deduped or tuple(runnable_envs) or envs or verdict_envs)
    repr_text = _bake_repr_text(form, schema_index, view_facts=view_facts)
    if verdict_only:
        if deduped:
            return EvidenceAtom(form=form, verdict=Holds(), atom_id=atom_id, repr_text=repr_text), candidate_envs
        if blocked_by is not None and not runnable_envs:
            return EvidenceAtom(
                form=form,
                verdict=NotReached(blocked_by=blocked_by),
                atom_id=atom_id,
                repr_text=repr_text,
            ), candidate_envs
        return EvidenceAtom(form=form, verdict=Fails(), atom_id=atom_id, repr_text=repr_text), candidate_envs
    if deduped:
        return EvidenceAtom(form=form, verdict=Holds(), atom_id=atom_id, repr_text=repr_text), deduped
    if blocked_by is not None:
        return EvidenceAtom(
            form=form,
            verdict=NotReached(blocked_by=blocked_by),
            atom_id=atom_id,
            repr_text=repr_text,
        ), ()
    return EvidenceAtom(form=form, verdict=Fails(), atom_id=atom_id, repr_text=repr_text), ()


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
        return _repr_compare(form)
    return _repr_builtin(form)


def _repr_fact(
    form: Fact,
    schema_index: object | None,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    info = _predicate_info(schema_index, form.predicate)
    if info is None or info.repr is None:
        return _fact_fallback_repr(form)

    out = info.repr.replace("%CLS", info.owner_type)
    if "%FLD" in out:
        out = out.replace("%FLD", _term_display(form.terms[1]) if len(form.terms) > 1 else "")
    if "%ENT" in out:
        out = out.replace("%ENT", _entity_repr_for_fact(schema_index, info.owner_type, form, view_facts=view_facts))
    return out


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
            return _term_display(subject)
    if schema_index is not None and isinstance(value, Mapping):
        identity = value.get("identity")
        ref_entity_type = value.get("entity_type", entity_type)
        if isinstance(ref_entity_type, str) and isinstance(identity, Mapping):
            try:
                return schema_runtime.render_entity_repr(schema_index, ref_entity_type, identity)
            except Exception:
                return _term_display(subject)
    if schema_index is not None and isinstance(value, str) and value.startswith(ENTITY_REF_PREFIX):
        try:
            identity = _recover_identity_from_predicates(value, entity_type, view_facts=view_facts, index=schema_index)
            return schema_runtime.render_entity_repr(schema_index, entity_type, identity)
        except Exception:
            return _term_display(subject)
    return _term_display(subject)


def _fact_fallback_repr(form: Fact) -> str:
    return f"{form.predicate}({', '.join(_term_display(term) for term in form.terms)})"


def _repr_compare(form: Compare) -> str:
    left = _term_display(form.left)
    right = _term_display(form.right)
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


def _repr_builtin(form: Builtin) -> str:
    terms = tuple(_term_display(term) for term in form.operands)
    if form.kind == "in" and terms:
        return f"{terms[0]} is in ({', '.join(terms[1:])})"
    if form.kind == "not" and terms:
        return f"not {terms[0]}"
    return f"{form.kind}({', '.join(terms)})"


def _term_display(term: BoundVar | Const | None) -> str:
    value = _term_value(term)
    if isinstance(value, EntityRef):
        return value.encoded_ref or f"{value.entity_type}({', '.join(str(v) for v in value.identity.values())})"
    if value is None and isinstance(term, BoundVar):
        return term.name
    return str(value)


def _term_value(term: BoundVar | Const | None) -> Any:
    if isinstance(term, BoundVar):
        return term.value
    if isinstance(term, Const):
        return term.value
    return None


def _atom_can_bind(atom: tuple[Any, ...]) -> bool:
    return bool(atom) and atom[0] == "pred"


def _missing_variables(atom: tuple[Any, ...], env: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(var for var in _vars_in_atom_tuple(atom) if var not in env)


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
