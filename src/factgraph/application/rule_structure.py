from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from factgraph.application.explain.structure_keys import (
    alias_for_atom,
    atom_id_for_condition,
    is_head_atom,
    join_id_for_materialization,
)
from factgraph.application.protocol.rule_expr import RuleExprError, RuleJoinConstraint
from factgraph.application.protocol.rule_expr import _RuleExpr, _iter_rule_operands
from factgraph.application.protocol.rule_expr_inspect import (
    ConditionDescriptor,
    OccurrenceInspect,
    _inspect_closed_head,
    _inspect_rule_expr,
)
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprEvaluationTrace,
    RuleExprLoweringBranch,
    RuleExprLoweringPlan,
    RuleExprOccurrenceBinding,
    _materialize_adapter_derivation_plan,
)
from factgraph.application.protocol.rule_structure import (
    Aggregate,
    Builtin,
    Compare,
    Const,
    Fact,
    FreeVar,
    HeadClosure,
    RuleStructure,
    StructureAtom,
    StructureAtomForm,
    StructureBranch,
    StructureHeadLink,
    StructureJoin,
    StructureOccurrence,
    StructurePort,
    StructurePortRef,
    StructureTerm,
)

_AGGREGATE_KINDS = frozenset({"count", "sum", "min", "max", "mean"})


def assemble_static_structure(
    plan: RuleExprLoweringPlan,
    schema_index: object | None = None,
    *,
    rule_expr: _RuleExpr | None = None,
) -> RuleStructure:
    if not isinstance(plan, RuleExprLoweringPlan):
        raise RuleExprError("plan must be RuleExprLoweringPlan")
    if rule_expr is not None and not isinstance(rule_expr, _RuleExpr):
        raise RuleExprError("rule_expr must be RuleExpr or None")

    compiled, traces = _materialize_adapter_derivation_plan(plan, engine="native")
    materialized_branches = _normalize_compiled_body(compiled.body_ir)
    if len(materialized_branches) != len(plan.branches) or len(traces) != len(plan.branches):
        raise RuleExprError("materialized RuleExpr branch count does not match lowering plan")

    occurrence_by_alias = {occurrence.alias: occurrence for occurrence in plan.occurrence_map}
    var_port_names = _var_port_names(plan)
    inspected = _inspect_rule_expr(rule_expr) if rule_expr is not None else None
    repr_by_alias = _repr_templates_by_alias(rule_expr)
    branches = tuple(
        _structure_branch(
            plan,
            lowered_branch,
            trace,
            atoms,
            occurrence_by_alias=occurrence_by_alias,
            var_port_names=var_port_names,
            repr_by_alias=repr_by_alias,
            schema_index=schema_index,
        )
        for lowered_branch, trace, atoms in zip(plan.branches, traces, materialized_branches, strict=True)
    )
    closed = _inspect_closed_head(plan.head, schema_index=schema_index) if schema_index is not None else None
    return RuleStructure(
        structure_id=repr(plan.canonical_key),
        source_kind=plan.source_kind,
        head_rule_id=plan.head_binding.head_rule_id,
        head_binding_kind=plan.head_binding.kind,
        ast=() if inspected is None else inspected.ast,
        branches=branches,
        ports=_flat_ports(plan) if inspected is None else _floor_ports(inspected.ports),
        unjoined_same_name_ports=_unjoined_same_name_ports(plan)
        if inspected is None
        else inspected.unjoined_same_name_ports,
        head_closure=None if closed is None else HeadClosure(closed.is_closed, closed.unbound_ports),
        metadata={"canonical_key": plan.canonical_key},
        _floor_occurrences=() if inspected is None else _floor_occurrences(inspected.occurrences),
        _floor_joins=() if inspected is None else inspected.joins,
    )


def _structure_branch(
    plan: RuleExprLoweringPlan,
    lowered_branch: RuleExprLoweringBranch,
    trace: RuleExprEvaluationTrace,
    atoms: list[tuple[Any, ...]],
    *,
    occurrence_by_alias: Mapping[str, RuleExprOccurrenceBinding],
    var_port_names: Mapping[str, str],
    repr_by_alias: Mapping[str, str | None],
    schema_index: object | None,
) -> StructureBranch:
    join_indexes = {join.materialized_condition_index for join in trace.join_materializations}
    head_link_indexes = {link.materialized_condition_index for link in trace.head_port_link_materializations}
    body_atoms: dict[str, list[StructureAtom]] = {alias: [] for alias in lowered_branch.occurrence_aliases}
    head_atoms: list[StructureAtom] = []
    fallback_alias = lowered_branch.occurrence_aliases[0] if lowered_branch.occurrence_aliases else ""

    for index, atom in enumerate(atoms):
        if index in join_indexes or index in head_link_indexes:
            continue
        structure_atom = _structure_atom(
            atom,
            atom_id=atom_id_for_condition(trace.branch_id, index),
            var_port_names=var_port_names,
            schema_index=schema_index,
        )
        if is_head_atom(atom, lowered_branch.occurrence_aliases):
            head_atoms.append(structure_atom)
            continue
        alias = alias_for_atom(atom, lowered_branch.occurrence_aliases) or fallback_alias
        body_atoms.setdefault(alias, []).append(structure_atom)

    head_occurrence = StructureOccurrence(
        occurrence_alias=plan.head.id,
        rule_id=plan.head.id,
        role="head",
        repr_text=plan.head.repr,
        port_names=tuple(sorted(plan.head.ports)),
        ports=_ports_for_rule(plan.head.port_types),
        atoms=tuple(head_atoms),
    )
    body_occurrences = tuple(
        _body_occurrence(
            alias,
            occurrence_by_alias.get(alias),
            tuple(body_atoms.get(alias, ())),
            repr_text=repr_by_alias.get(alias),
        )
        for alias in lowered_branch.occurrence_aliases
    )
    joins = tuple(_structure_join(join, occurrence_by_alias) for join in trace.join_materializations)
    head_links = tuple(
        StructureHeadLink(
            head_port_name=link.head_port_name,
            source_occurrence_alias=link.source_occurrence_alias,
            source_port_name=link.source_port_name,
        )
        for link in trace.head_port_link_materializations
    )
    return StructureBranch(
        branch_id=lowered_branch.branch_id,
        path=lowered_branch.path,
        occurrences=(head_occurrence, *body_occurrences),
        joins=joins,
        head_links=head_links,
    )


def _body_occurrence(
    alias: str,
    occurrence: RuleExprOccurrenceBinding | None,
    atoms: tuple[StructureAtom, ...],
    *,
    repr_text: str | None,
) -> StructureOccurrence:
    if occurrence is None:
        return StructureOccurrence(
            occurrence_alias=alias,
            rule_id=alias,
            role="body",
            repr_text=repr_text,
            atoms=atoms,
        )
    return StructureOccurrence(
        occurrence_alias=alias,
        rule_id=occurrence.rule_id,
        role="body",
        repr_text=repr_text,
        port_names=tuple(sorted(binding.port_name for binding in occurrence.port_bindings)),
        ports=_ports_for_bindings(occurrence),
        atoms=atoms,
    )


def _structure_join(
    join: Any,
    occurrence_by_alias: Mapping[str, RuleExprOccurrenceBinding],
) -> StructureJoin:
    left_occurrence = occurrence_by_alias.get(join.left_occurrence_alias)
    right_occurrence = occurrence_by_alias.get(join.right_occurrence_alias)
    return StructureJoin(
        left=StructurePortRef(
            occurrence_alias=join.left_occurrence_alias,
            port_name=join.left_port_name,
            rule_id=None if left_occurrence is None else left_occurrence.rule_id,
        ),
        right=StructurePortRef(
            occurrence_alias=join.right_occurrence_alias,
            port_name=join.right_port_name,
            rule_id=None if right_occurrence is None else right_occurrence.rule_id,
        ),
        join_id=join_id_for_materialization(join),
        op="eq",
    )


def _structure_atom(
    atom: tuple[Any, ...],
    *,
    atom_id: str,
    var_port_names: Mapping[str, str],
    schema_index: object | None,
) -> StructureAtom:
    kind = str(atom[0])
    form = _atom_form(atom, var_port_names)
    descriptor = _atom_descriptor(atom, atom_id=atom_id)
    return StructureAtom(
        atom_id=atom_id,
        kind=descriptor["kind"],
        form=form,
        repr_text=_atom_repr_text(form, schema_index=schema_index),
        subject=descriptor.get("subject"),
        entity_type=descriptor.get("entity_type"),
        field=descriptor.get("field"),
        op=descriptor.get("op"),
        value=descriptor.get("value"),
        negated=kind == "not",
        summary=str(descriptor.get("summary", "")),
    )


def _atom_form(atom: tuple[Any, ...], var_port_names: Mapping[str, str]) -> StructureAtomForm | None:
    kind = str(atom[0])
    if kind == "pred" and len(atom) == 3:
        return Fact(predicate=str(atom[1]), terms=tuple(_term_form(term, var_port_names) for term in _sequence(atom[2])))
    if kind in {"eq", "ne", "gt", "ge", "lt", "le"} and len(atom) == 3:
        return Compare(
            op=kind,
            left=_term_form(atom[1], var_port_names),
            right=_term_form(atom[2], var_port_names),
        )
    if kind == "in" and len(atom) == 3:
        return Builtin(
            kind="in",
            operands=(_term_form(atom[1], var_port_names), *tuple(_term_form(term, var_port_names) for term in _sequence(atom[2]))),
        )
    if kind == "not":
        return Builtin(kind="not", operands=())
    return Builtin(kind=kind, operands=tuple(_term_form(term, var_port_names) for term in atom[1:]))


def _term_form(term: Any, var_port_names: Mapping[str, str]) -> StructureTerm:
    aggregate = _aggregate_form(term, var_port_names)
    if aggregate is not None:
        return aggregate
    if isinstance(term, str) and term.startswith("$"):
        return FreeVar(name=term, port_name=var_port_names.get(term))
    return Const(term)


def _aggregate_form(value: Any, var_port_names: Mapping[str, str]) -> Aggregate | None:
    if not _is_aggregate_tuple(value):
        return None
    kind = str(value[0])
    target = value[1]
    filter_atoms = value[2]
    head_terms = () if target is None else (_term_form(target, var_port_names),)
    return Aggregate(
        kind=kind,
        body_terms=_aggregate_body_terms(filter_atoms, var_port_names),
        head_terms=head_terms,
    )


def _is_aggregate_tuple(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 3
        and isinstance(value[0], str)
        and value[0] in _AGGREGATE_KINDS
        and isinstance(value[2], list)
    )


def _aggregate_body_terms(filter_atoms: object, var_port_names: Mapping[str, str]) -> tuple[StructureTerm, ...]:
    if not isinstance(filter_atoms, list):
        return ()
    terms: list[StructureTerm] = []
    seen: set[str] = set()
    for atom in filter_atoms:
        if not isinstance(atom, tuple) or len(atom) < 3:
            continue
        raw_terms = atom[2]
        if not isinstance(raw_terms, Sequence) or isinstance(raw_terms, (str, bytes)):
            continue
        for raw_term in raw_terms:
            term = _term_form(raw_term, var_port_names)
            key = repr(term)
            if key in seen:
                continue
            seen.add(key)
            terms.append(term)
    return tuple(terms)


def _atom_descriptor(atom: tuple[Any, ...], *, atom_id: str) -> dict[str, object]:
    kind = str(atom[0])
    if kind == "pred" and len(atom) == 3:
        pred_id = str(atom[1])
        terms = tuple(_sequence(atom[2]))
        if pred_id.endswith(":exists") and terms:
            entity_type = pred_id.removesuffix(":exists")
            subject = _term_summary(terms[0])
            return {
                "atom_id": atom_id,
                "kind": "entity_existence",
                "subject": subject,
                "entity_type": entity_type,
                "summary": f"{entity_type}({subject})",
            }
        if ":" in pred_id and terms:
            entity_type, _sep, field = pred_id.partition(":")
            return {
                "atom_id": atom_id,
                "kind": "field_predicate",
                "subject": _term_summary(terms[0]),
                "entity_type": entity_type,
                "field": field,
                "value": _term_summary(terms[-1]) if len(terms) > 1 else None,
                "summary": _pred_summary(pred_id, terms),
            }
        return {"atom_id": atom_id, "kind": "pred", "summary": _pred_summary(pred_id, terms)}
    if kind in {"eq", "ne", "gt", "ge", "lt", "le"} and len(atom) == 3:
        return {
            "atom_id": atom_id,
            "kind": "cmp",
            "subject": _term_summary(atom[1]),
            "op": kind,
            "value": _term_summary(atom[2]),
            "summary": f"{_term_summary(atom[1])} {kind} {_term_summary(atom[2])}",
        }
    if kind == "in" and len(atom) == 3:
        values = tuple(_term_summary(value) for value in _sequence(atom[2]))
        return {
            "atom_id": atom_id,
            "kind": "in",
            "subject": _term_summary(atom[1]),
            "op": "in",
            "value": values,
            "summary": f"{_term_summary(atom[1])} in {values!r}",
        }
    if kind == "not":
        return {"atom_id": atom_id, "kind": "not", "summary": "not(...)"}
    args = tuple(_term_summary(arg) for arg in atom[1:])
    return {"atom_id": atom_id, "kind": "builtin", "op": kind, "value": args, "summary": f"{kind}{args!r}"}


def _term_summary(term: Any) -> str:
    if _is_aggregate_tuple(term):
        return _aggregate_tuple_summary(term)
    if isinstance(term, str) and term.startswith("$"):
        return term
    return repr(term)


def _aggregate_tuple_summary(value: tuple[Any, ...]) -> str:
    kind = str(value[0])
    if kind == "count":
        return "count(...)"
    target = value[1] if len(value) > 1 else None
    if target is None:
        return f"{kind}(...)"
    return f"{kind}({_term_summary(target)})"


def _pred_summary(pred_id: str, terms: tuple[Any, ...]) -> str:
    return f"{pred_id}({', '.join(_term_summary(term) for term in terms)})"


def _atom_repr_text(form: StructureAtomForm | None, *, schema_index: object | None) -> str | None:
    if isinstance(form, Fact):
        info = _predicate_info(schema_index, form.predicate)
        if info is not None and getattr(info, "repr", None) is not None:
            placeholder_values = {
                "%CLS": str(getattr(info, "owner_type", "")),
                "%FLD": _term_repr_text(form.terms[1]) if len(form.terms) > 1 else "",
                "%ENT": _static_entity_repr_for_fact(form, info),
            }
            rendered = str(getattr(info, "repr"))
            for token, value in placeholder_values.items():
                rendered = rendered.replace(token, value)
            return rendered
        return _fact_fallback_repr(form, predicate_info=info)
    if isinstance(form, Compare):
        labels = {
            "eq": "equals",
            "ne": "does not equal",
            "gt": ">",
            "ge": ">=",
            "lt": "<",
            "le": "<=",
        }
        return f"{_term_repr_text(form.left)} {labels.get(form.op, form.op)} {_term_repr_text(form.right)}"
    if isinstance(form, Builtin):
        if form.kind == "in" and form.operands:
            subject, *values = form.operands
            return f"{_term_repr_text(subject)} is in ({', '.join(_term_repr_text(value) for value in values)})"
        if form.kind == "not":
            return "not(...)"
        return f"{form.kind}({', '.join(_term_repr_text(term) for term in form.operands)})"
    if isinstance(form, Aggregate):
        return _aggregate_repr_text(form)
    return None


def _term_repr_text(term: StructureTerm) -> str:
    if isinstance(term, FreeVar):
        return f"%{term.port_name}" if term.port_name else term.name
    if isinstance(term, Const):
        return str(term.value)
    if isinstance(term, Aggregate):
        return _aggregate_repr_text(term)
    return type(term).__name__


def _aggregate_repr_text(form: Aggregate) -> str:
    if form.kind == "count":
        return "count(...)"
    terms = form.head_terms or form.body_terms
    if terms:
        return f"{form.kind}({', '.join(_term_repr_text(term) for term in terms)})"
    return f"{form.kind}(...)"


def _predicate_info(schema_index: object | None, predicate: str) -> object | None:
    if schema_index is None:
        return None
    predicates = getattr(schema_index, "predicates_by_id", None)
    if not isinstance(predicates, Mapping):
        return None
    return predicates.get(predicate)


def _fact_fallback_repr(form: Fact, *, predicate_info: object | None) -> str:
    if predicate_info is not None and getattr(predicate_info, "is_entity_exists", False):
        return f"{_static_entity_repr_for_fact(form, predicate_info)} exists"
    field_name = getattr(predicate_info, "py_field_name", None) if predicate_info is not None else None
    owner_type = getattr(predicate_info, "owner_type", None) if predicate_info is not None else None
    if isinstance(field_name, str) and field_name and isinstance(owner_type, str) and len(form.terms) > 1:
        entity = _static_entity_repr_for_fact(form, predicate_info)
        return f"{entity} has {field_name} {_term_repr_text(form.terms[1])}"
    return f"{form.predicate}({', '.join(_term_repr_text(term) for term in form.terms)})"


def _static_entity_repr_for_fact(form: Fact, predicate_info: object) -> str:
    subject = form.terms[0] if form.terms else None
    owner_type = getattr(predicate_info, "owner_type", None)
    if isinstance(owner_type, str) and owner_type and isinstance(subject, FreeVar):
        return f"{owner_type} {_term_repr_text(subject)}"
    if isinstance(subject, StructureTerm):
        return _term_repr_text(subject)
    return ""


def _sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(value)
    return (value,)


def _ports_for_rule(port_types: Mapping[str, Any]) -> Mapping[str, StructurePort]:
    return {
        name: StructurePort(name=name, kind=port_type.kind, entity_type=port_type.entity_type)
        for name, port_type in sorted(port_types.items())
    }


def _ports_for_bindings(occurrence: RuleExprOccurrenceBinding) -> Mapping[str, StructurePort]:
    return {
        binding.port_name: StructurePort(
            name=binding.port_name,
            kind=binding.port_type.kind,
            entity_type=binding.port_type.entity_type,
        )
        for binding in sorted(occurrence.port_bindings, key=lambda binding: binding.port_name)
    }


def _flat_ports(plan: RuleExprLoweringPlan) -> tuple[StructurePort, ...]:
    ports: dict[tuple[object, ...], StructurePort] = {}
    for port in _ports_for_rule(plan.head.port_types).values():
        ports.setdefault((port.name, port.kind, port.entity_type), port)
    for occurrence in plan.occurrence_map:
        for port in _ports_for_bindings(occurrence).values():
            ports.setdefault((port.name, port.kind, port.entity_type), port)
    return tuple(ports[key] for key in sorted(ports, key=repr))


def _floor_ports(ports: tuple[Any, ...]) -> tuple[StructurePort, ...]:
    return tuple(
        StructurePort(name=port.name, kind=port.kind, entity_type=port.entity_type)
        for port in ports
    )


def _floor_occurrences(occurrences: tuple[OccurrenceInspect, ...]) -> tuple[StructureOccurrence, ...]:
    return tuple(
        StructureOccurrence(
            occurrence_alias=occurrence.alias,
            rule_id=occurrence.template_id,
            role="body",
            repr_text=occurrence.repr_template,
            port_names=occurrence.ports,
            atoms=tuple(_floor_atom(atom) for atom in occurrence.atoms),
        )
        for occurrence in occurrences
    )


def _floor_atom(atom: ConditionDescriptor) -> StructureAtom:
    return StructureAtom(
        atom_id=atom.atom_id,
        kind=atom.kind,
        subject=atom.subject,
        entity_type=atom.entity_type,
        field=atom.field,
        op=atom.op,
        value=atom.value,
        repr_text=atom.summary or type(atom).__name__,
        summary=atom.summary,
    )


def _repr_templates_by_alias(rule_expr: _RuleExpr | None) -> dict[str, str | None]:
    if rule_expr is None:
        return {}
    return {
        operand.alias: operand.rule.repr
        for operand in _iter_rule_operands(rule_expr)
    }


def _var_port_names(plan: RuleExprLoweringPlan) -> dict[str, str]:
    out: dict[str, str] = {}
    for port_name, var in plan.head.ports.items():
        out[var.name] = port_name
        source = var.name[1:] if var.name.startswith("$") else var.name
        out[f"$__head__{source}"] = port_name
    for occurrence in plan.occurrence_map:
        for binding in occurrence.port_bindings:
            out[binding.alias_local_execution_var.name] = binding.port_name
            out[binding.source_var.name] = binding.port_name
    return out


def _unjoined_same_name_ports(plan: RuleExprLoweringPlan) -> tuple[Mapping[str, object], ...]:
    hints: dict[tuple[str, tuple[str, ...]], Mapping[str, object]] = {}
    occurrence_by_alias = {occurrence.alias: occurrence for occurrence in plan.occurrence_map}
    for branch in plan.branches:
        by_name: dict[str, list[str]] = {}
        for alias in branch.occurrence_aliases:
            occurrence = occurrence_by_alias.get(alias)
            if occurrence is None:
                continue
            for binding in occurrence.port_bindings:
                by_name.setdefault(binding.port_name, []).append(alias)
        for port_name, aliases in sorted(by_name.items()):
            unique_aliases = tuple(sorted(dict.fromkeys(aliases)))
            if len(unique_aliases) < 2:
                continue
            if _same_port_name_fully_joined(port_name, unique_aliases, branch.pending_joins):
                continue
            hints.setdefault(
                (port_name, unique_aliases),
                {"port_name": port_name, "occurrences": unique_aliases},
            )
    return tuple(hints[key] for key in sorted(hints, key=repr))


def _same_port_name_fully_joined(
    port_name: str,
    aliases: tuple[str, ...],
    joins: tuple[RuleJoinConstraint, ...],
) -> bool:
    expected = {(left, right) for idx, left in enumerate(aliases) for right in aliases[idx + 1 :]}
    actual: set[tuple[str, str]] = set()
    for join in joins:
        if join.left.port_name != port_name or join.right.port_name != port_name:
            continue
        pair = tuple(sorted((join.left.occurrence_alias, join.right.occurrence_alias)))
        actual.add((pair[0], pair[1]))
    return expected <= actual


def _normalize_compiled_body(body_ir: object) -> list[list[tuple[Any, ...]]]:
    if not isinstance(body_ir, list) or not body_ir:
        raise RuleExprError("compiled body_ir must be non-empty list")
    if all(_is_atom_tuple(item) for item in body_ir):
        return [list(body_ir)]  # type: ignore[list-item]
    if all(isinstance(item, list) for item in body_ir):
        return [list(branch) for branch in body_ir]  # type: ignore[list-item]
    raise RuleExprError("compiled body_ir must be one-level AND or two-level OR")


def _is_atom_tuple(value: object) -> bool:
    return isinstance(value, tuple) and bool(value) and isinstance(value[0], str)


__all__ = ["assemble_static_structure"]
