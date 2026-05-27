from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from factgraph.application.protocol.rule import PortType, Rule
from factgraph.application.protocol.rule_expr import _RuleExpr
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprDeclaredPort,
    _declared_port_state_for_rule_expr_plan,
    _lower_rule_expr,
    _materialize_branch,
)
from factgraph.application.schema_runtime import entity_type_from_ref
from factgraph.core.rules.where_ast import (
    AggregateAtom,
    AndExpr,
    Atom,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    PredAtom,
    RuleRefAtom,
    Term,
    Var,
    lower_ast_to_where_ir,
    parse_where_ir_to_ast,
)
from factgraph.core.rules.where_eval import evaluate_where
from factgraph.core.view.projector import project_view_facts

from .errors import SDKStoreError
from .facade import EntitySnapshot, _build_snapshot
from .schema import Entity, Field


_MATCH_OR_UNSUPPORTED = "fg.read.match(...) currently supports Rule and AND RuleExpr only"
_MATCH_VIEW_UNSUPPORTED = (
    "method-level view= is not supported by fg.read.match(); use FactGraph.attach(db, view=view) instead"
)


@dataclass(frozen=True)
class _DeclaredMatchPort:
    name: str
    port_type: PortType
    var: Var


@dataclass(frozen=True)
class _MatchPlan:
    body_ir: list[Any]
    projection_port: _DeclaredMatchPort
    ports_by_name: Mapping[str, _DeclaredMatchPort]


def sdk_match(
    sdk: Any,
    entity_cls: type[Entity],
    template: Rule | _RuleExpr,
    *,
    limit: int | None = None,
    **port_constraints: Any,
) -> tuple[EntitySnapshot, ...]:
    if "view" in port_constraints:
        raise SDKStoreError(_MATCH_VIEW_UNSUPPORTED, path="$.read.match.view")
    if not isinstance(entity_cls, type) or not issubclass(entity_cls, Entity):
        raise SDKStoreError("fg.read.match(...) first argument must be an Entity subclass")
    if entity_cls not in sdk._entity_spec_by_class:
        raise SDKStoreError(f"Entity class {entity_cls.__name__!r} is not registered with this FactGraph")
    if limit is not None:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise SDKStoreError("fg.read.match(..., limit=...) must be a non-negative integer or None")
    if not isinstance(template, Rule | _RuleExpr):
        raise SDKStoreError(
            "fg.read.match(...) template must be application Rule or AND RuleExpr; "
            f"got {type(template).__name__}"
        )

    plan = _build_match_plan(sdk, entity_cls, template)
    effective_ir = _apply_port_constraints(
        sdk,
        entity_cls,
        plan,
        port_constraints,
    )
    _validate_connectivity(
        effective_ir,
        projected_var=plan.projection_port.var.name,
        constrained_vars={plan.ports_by_name[name].var.name for name in port_constraints},
    )

    view_facts = project_view_facts(sdk.ledger, sdk.schema_ir)
    rows = evaluate_where(view_facts, effective_ir)
    out: list[EntitySnapshot] = []
    seen_refs: set[str] = set()
    for row in rows:
        e_ref = row.get(plan.projection_port.var.name)
        if not isinstance(e_ref, str) or not e_ref:
            continue
        if entity_type_from_ref(e_ref) != entity_cls.__name__:
            continue
        if e_ref in seen_refs:
            continue
        seen_refs.add(e_ref)
        out.append(_build_snapshot(sdk, entity_cls, e_ref=e_ref, known_identity_values=None))
        if limit is not None and len(out) >= limit:
            break
    return tuple(out)


def _build_match_plan(sdk: Any, entity_cls: type[Entity], template: Rule | _RuleExpr) -> _MatchPlan:
    if isinstance(template, Rule):
        declared = tuple(
            _DeclaredMatchPort(name=name, port_type=template.port_types[name], var=var)
            for name, var in template.ports.items()
        )
        body_ir = lower_ast_to_where_ir(AndExpr(list(template.where)))
        return _plan_from_declared_ports(entity_cls, declared, body_ir)

    probe_plan = _lower_rule_expr(template, head=Rule.projection("__fg_match_probe"))
    if len(probe_plan.branches) != 1:
        raise SDKStoreError(_MATCH_OR_UNSUPPORTED)
    declared_ports, _partial_ports = _declared_port_state_for_rule_expr_plan(probe_plan)
    head = Rule.projection(*(port.name for port in declared_ports))
    plan = _lower_rule_expr(template, head=head)
    if len(plan.branches) != 1:
        raise SDKStoreError(_MATCH_OR_UNSUPPORTED)
    body_ir, _joins, _head_links = _materialize_branch(plan.branches[0], plan)
    declared = tuple(_declared_match_port_from_rule_expr(head, port) for port in declared_ports)
    return _plan_from_declared_ports(entity_cls, declared, body_ir)


def _declared_match_port_from_rule_expr(head: Rule, declared: RuleExprDeclaredPort) -> _DeclaredMatchPort:
    return _DeclaredMatchPort(
        name=declared.name,
        port_type=declared.port_type,
        var=head.ports[declared.name],
    )


def _plan_from_declared_ports(
    entity_cls: type[Entity],
    declared: tuple[_DeclaredMatchPort, ...],
    body_ir: list[Any],
) -> _MatchPlan:
    ports_by_name = {port.name: port for port in declared}
    matches = [
        port
        for port in declared
        if port.port_type.kind == "entity_ref" and port.port_type.entity_type == entity_cls.__name__
    ]
    if not matches:
        available = ", ".join(sorted(ports_by_name)) or "<none>"
        raise SDKStoreError(
            f"fg.read.match({entity_cls.__name__}, ...) requires exactly one entity_ref port "
            f"for {entity_cls.__name__!r}; available ports: {available}"
        )
    if len(matches) > 1:
        names = ", ".join(sorted(port.name for port in matches))
        raise SDKStoreError(
            f"fg.read.match({entity_cls.__name__}, ...) is ambiguous: multiple {entity_cls.__name__!r} "
            f"entity_ref ports are declared ({names})"
        )
    return _MatchPlan(body_ir=list(body_ir), projection_port=matches[0], ports_by_name=ports_by_name)


def _apply_port_constraints(
    sdk: Any,
    entity_cls: type[Entity],
    plan: _MatchPlan,
    constraints: Mapping[str, Any],
) -> list[Any]:
    if not constraints:
        return list(plan.body_ir)
    atoms: list[Atom] = []
    for name, value in constraints.items():
        port = plan.ports_by_name.get(name)
        if port is None:
            available = ", ".join(sorted(plan.ports_by_name))
            raise SDKStoreError(f"unknown match port {name!r}; valid ports: {available}")
        if isinstance(value, Field):
            atoms.extend(_field_constraint_atoms(sdk, entity_cls, plan.projection_port, port, value))
        else:
            atoms.append(CmpAtom(op="eq", lhs=port.var, rhs=Const(_normalize_constraint_value(port, value))))
    return [*plan.body_ir, *lower_ast_to_where_ir(AndExpr(atoms))]


def _field_constraint_atoms(
    sdk: Any,
    entity_cls: type[Entity],
    projection_port: _DeclaredMatchPort,
    port: _DeclaredMatchPort,
    descriptor: Field,
) -> tuple[Atom, ...]:
    if descriptor.sdk_owner_cls is not entity_cls:
        raise SDKStoreError(
            "cross-entity Field constraints are not supported by fg.read.match(...); "
            "use RuleExpr.join_by_ports(...) to connect entities"
        )
    schema_pred = sdk._field_pred_by_descriptor.get(descriptor)
    if not isinstance(schema_pred, dict):
        raise SDKStoreError(f"field {descriptor.sdk_attr_name!r} is not registered with this FactGraph")
    pred_id = schema_pred.get("pred_id")
    if not isinstance(pred_id, str) or not pred_id:
        raise SDKStoreError(f"field {descriptor.sdk_attr_name!r} is missing schema predicate metadata")
    field_var = Var(f"$__match_field_{descriptor.sdk_attr_name}_{port.name}")
    return (
        PredAtom(pred_id=pred_id, terms=[_projected_entity_var(projection_port), field_var]),
        CmpAtom(op="eq", lhs=port.var, rhs=field_var),
    )


def _projected_entity_var(port: _DeclaredMatchPort) -> Var:
    if port.port_type.kind != "entity_ref":
        # This only happens if the projected entity port resolution invariant
        # is broken internally.
        raise SDKStoreError("match projection port must be entity_ref")
    return port.var


def _normalize_constraint_value(port: _DeclaredMatchPort, value: Any) -> Any:
    if port.port_type.kind != "entity_ref":
        return value
    if isinstance(value, EntitySnapshot):
        value = value.ref
    if not isinstance(value, str) or not value.startswith("idref_v1:"):
        raise SDKStoreError(f"match port {port.name!r} expects an idref_v1 token or EntitySnapshot")
    actual_entity_type = entity_type_from_ref(value)
    if port.port_type.entity_type is not None and actual_entity_type != port.port_type.entity_type:
        raise SDKStoreError(
            f"match port {port.name!r} expects entity_ref:{port.port_type.entity_type}; "
            f"got entity_ref:{actual_entity_type}"
        )
    return value


def _validate_connectivity(body_ir: list[Any], *, projected_var: str, constrained_vars: set[str]) -> None:
    required = {projected_var, *constrained_vars}
    if len(required) <= 1:
        return
    expr = parse_where_ir_to_ast(body_ir)
    atoms = expr.atoms if isinstance(expr, AndExpr) else [atom for branch in expr.branches for atom in branch.atoms]
    parent: dict[str, str] = {name: name for atom in atoms for name in _vars_in_atom(atom)}

    def find(name: str) -> str:
        parent.setdefault(name, name)
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for atom in atoms:
        names = sorted(_vars_in_atom(atom))
        if len(names) < 2:
            continue
        head = names[0]
        for name in names[1:]:
            union(head, name)

    projected_root = find(projected_var)
    disconnected = sorted(name for name in constrained_vars if find(name) != projected_root)
    if disconnected:
        names = ", ".join(disconnected)
        raise SDKStoreError(
            "disconnected match pattern would create a silent cross product; "
            f"ports not connected to the projected entity: {names}"
        )


def _vars_in_atom(atom: Atom) -> set[str]:
    if isinstance(atom, PredAtom | RuleRefAtom):
        return {name for term in atom.terms for name in _vars_in_term(term)}
    if isinstance(atom, CmpAtom):
        return {*_vars_in_term(atom.lhs), *_vars_in_term(atom.rhs)}
    if isinstance(atom, InAtom):
        return _vars_in_term(atom.var) | {name for value in atom.values for name in _vars_in_term(value)}
    if isinstance(atom, BuiltinAtom):
        return {name for term in atom.args for name in _vars_in_term(term)}
    if isinstance(atom, NotAtom):
        if isinstance(atom.body, AndExpr):
            return {name for inner in atom.body.atoms for name in _vars_in_atom(inner)}
        return {name for branch in atom.body.branches for inner in branch.atoms for name in _vars_in_atom(inner)}
    return set()


def _vars_in_term(term: Term) -> set[str]:
    if isinstance(term, Var):
        return {term.name}
    if isinstance(term, Const):
        return set()
    if isinstance(term, AggregateAtom):
        names = set() if term.target is None else _vars_in_term(term.target)
        for atom in term.filter:
            names.update(_vars_in_atom(atom))
        return names
    return set()
