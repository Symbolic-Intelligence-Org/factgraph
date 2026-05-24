from __future__ import annotations

from dataclasses import dataclass, field
import re
from types import MappingProxyType
from typing import Literal, Mapping

from factgraph.core.rules.where_ast import (
    AggregateAtom,
    Atom,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    PredAtom,
    Term,
    Var,
)

from .rule import Rule, RulePortRef
from .rule_expr import (
    RuleExprError,
    RuleJoinConstraint,
    _AndGroup,
    _OrGroup,
    _RuleExpr,
    _RuleOperand,
    _coerce_rule_expr_operand,
    _iter_rule_operands,
)

_DESC_PORT_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True)
class PortInspect:
    name: str
    kind: Literal["entity_ref", "value"]
    entity_type: str | None = None
    field: str | None = None
    value_type: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.name, field_name="PortInspect.name")
        if self.kind not in {"entity_ref", "value"}:
            raise RuleExprError("PortInspect.kind must be 'entity_ref' or 'value'")
        if self.kind == "entity_ref" and not self.entity_type:
            raise RuleExprError("PortInspect.entity_type is required for entity_ref ports")


@dataclass(frozen=True)
class AtomDescriptor:
    atom_id: str
    kind: str
    subject: str | None = None
    entity_type: str | None = None
    field: str | None = None
    op: str | None = None
    value: object = None
    summary: str = ""

    def __post_init__(self) -> None:
        _require_non_empty_str(self.atom_id, field_name="AtomDescriptor.atom_id")
        _require_non_empty_str(self.kind, field_name="AtomDescriptor.kind")
        if not isinstance(self.summary, str):
            raise RuleExprError("AtomDescriptor.summary must be string")


@dataclass(frozen=True)
class OccurrenceInspect:
    template_id: str
    alias: str
    desc_template: str | None
    ports: tuple[str, ...]
    atoms: tuple[AtomDescriptor, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.template_id, field_name="OccurrenceInspect.template_id")
        _require_non_empty_str(self.alias, field_name="OccurrenceInspect.alias")
        if self.desc_template is not None and not isinstance(self.desc_template, str):
            raise RuleExprError("OccurrenceInspect.desc_template must be string or None")
        if not isinstance(self.ports, tuple) or any(not isinstance(port, str) or not port for port in self.ports):
            raise RuleExprError("OccurrenceInspect.ports must be tuple of non-empty strings")
        if not isinstance(self.atoms, tuple) or any(not isinstance(atom, AtomDescriptor) for atom in self.atoms):
            raise RuleExprError("OccurrenceInspect.atoms must be tuple[AtomDescriptor, ...]")


@dataclass(frozen=True)
class RuleExprInspect:
    ast: tuple[object, ...]
    occurrences: tuple[OccurrenceInspect, ...]
    joins: tuple[RuleJoinConstraint, ...]
    unjoined_same_name_ports: tuple[dict[str, object], ...]
    _ports: tuple[PortInspect, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.ast, tuple):
            raise RuleExprError("RuleExprInspect.ast must be tuple")
        if not isinstance(self.occurrences, tuple) or any(
            not isinstance(occurrence, OccurrenceInspect) for occurrence in self.occurrences
        ):
            raise RuleExprError("RuleExprInspect.occurrences must be tuple[OccurrenceInspect, ...]")
        if not isinstance(self.joins, tuple) or any(not isinstance(join, RuleJoinConstraint) for join in self.joins):
            raise RuleExprError("RuleExprInspect.joins must be tuple[RuleJoinConstraint, ...]")
        if not isinstance(self.unjoined_same_name_ports, tuple):
            raise RuleExprError("RuleExprInspect.unjoined_same_name_ports must be tuple")
        for hint in self.unjoined_same_name_ports:
            if set(hint) != {"port_name", "occurrences"}:
                raise RuleExprError("unjoined_same_name_ports entries must have port_name and occurrences keys")
            if not isinstance(hint["port_name"], str):
                raise RuleExprError("unjoined_same_name_ports.port_name must be string")
            occurrences = hint["occurrences"]
            if not isinstance(occurrences, tuple) or any(not isinstance(alias, str) for alias in occurrences):
                raise RuleExprError("unjoined_same_name_ports.occurrences must be tuple[str, ...]")
        if not isinstance(self._ports, tuple) or any(not isinstance(port, PortInspect) for port in self._ports):
            raise RuleExprError("RuleExprInspect.ports must be tuple[PortInspect, ...]")

    @property
    def templates(self) -> tuple[str, ...]:
        seen: set[str] = set()
        out: list[str] = []
        for occurrence in self.occurrences:
            if occurrence.template_id not in seen:
                seen.add(occurrence.template_id)
                out.append(occurrence.template_id)
        return tuple(out)

    @property
    def port_visibility(self) -> Mapping[str, tuple[str, ...]]:
        return MappingProxyType({occurrence.alias: occurrence.ports for occurrence in self.occurrences})

    @property
    def ports(self) -> tuple[PortInspect, ...]:
        return self._ports

    def render(self, bindings: Mapping[str, object] | None = None) -> str:
        values = {} if bindings is None else bindings
        if not isinstance(values, Mapping):
            raise RuleExprError("RuleExprInspect.render bindings must be Mapping[str, object] or None")
        occurrence_lines = []
        for occurrence in self.occurrences:
            rendered_desc = _render_desc_template(occurrence.desc_template, occurrence.alias, values)
            label = f"{occurrence.alias}:{occurrence.template_id}"
            occurrence_lines.append(label if not rendered_desc else f"{label} {rendered_desc}")
        pieces = ["RuleExprInspect", _render_ast_compact(self.ast), "; ".join(occurrence_lines)]
        if self.joins:
            pieces.append("joins " + ", ".join(_render_join(join) for join in self.joins))
        return " | ".join(piece for piece in pieces if piece)

    def render_compact(self) -> str:
        return _render_ast_compact(self.ast)


def _inspect_application_rule(rule: Rule) -> RuleExprInspect:
    if not isinstance(rule, Rule):
        raise RuleExprError("inspect(application_rule) requires application protocol Rule")
    return _inspect_rule_expr(_coerce_rule_expr_operand(rule))


def _inspect_rule_expr(expr: _RuleExpr) -> RuleExprInspect:
    if not isinstance(expr, _RuleExpr):
        raise RuleExprError("inspect(rule_expr) requires RuleExpr value")
    occurrences = tuple(sorted(_inspect_occurrences(expr), key=lambda occurrence: (occurrence.alias, occurrence.template_id)))
    joins = _inspect_joins(expr)
    return RuleExprInspect(
        ast=_inspect_ast(expr),
        occurrences=occurrences,
        joins=joins,
        unjoined_same_name_ports=_inspect_unjoined_same_name_ports(expr),
        _ports=_inspect_ports(expr),
    )


def _inspect_ast(expr: _RuleExpr) -> tuple[object, ...]:
    if isinstance(expr, _RuleOperand):
        return ("rule", expr.alias, expr.rule.id)
    if isinstance(expr, _AndGroup):
        return (
            "and",
            tuple(_inspect_ast(child) for child in expr.children),
            tuple(_inspect_join_tuple(join) for join in _sort_joins(expr.joins)),
        )
    if isinstance(expr, _OrGroup):
        return ("or", tuple(_inspect_ast(child) for child in expr.children))
    raise RuleExprError(f"unsupported RuleExpr node: {type(expr).__name__}")


def _inspect_occurrences(expr: _RuleExpr) -> tuple[OccurrenceInspect, ...]:
    if isinstance(expr, _RuleOperand):
        return (_inspect_rule_operand(expr),)
    if isinstance(expr, (_AndGroup, _OrGroup)):
        out: list[OccurrenceInspect] = []
        for child in expr.children:
            out.extend(_inspect_occurrences(child))
        return tuple(out)
    return ()


def _inspect_rule_operand(operand: _RuleOperand) -> OccurrenceInspect:
    rule = operand.rule
    atom_ids = rule.atom_ids
    return OccurrenceInspect(
        template_id=rule.id,
        alias=operand.alias,
        desc_template=rule.desc,
        ports=tuple(sorted(rule.ports)),
        atoms=tuple(_derive_atom_descriptor(atom, atom_ids[idx]) for idx, atom in enumerate(rule.where)),
    )


def _inspect_ports(expr: _RuleExpr) -> tuple[PortInspect, ...]:
    descriptors: dict[tuple[object, ...], PortInspect] = {}
    for operand in _iter_rule_operands(expr):
        for name in sorted(operand.rule.ports):
            port_type = operand.rule.port_types[name]
            descriptor = PortInspect(
                name=name,
                kind=port_type.kind,
                entity_type=port_type.entity_type,
                field=None,
                value_type=None if port_type.kind == "entity_ref" else "unknown",
            )
            descriptors.setdefault(
                (descriptor.name, descriptor.kind, descriptor.entity_type, descriptor.field, descriptor.value_type),
                descriptor,
            )
    return tuple(descriptors[key] for key in sorted(descriptors, key=repr))


def _inspect_joins(expr: _RuleExpr) -> tuple[RuleJoinConstraint, ...]:
    joins: list[RuleJoinConstraint] = []
    if isinstance(expr, _AndGroup):
        joins.extend(expr.joins)
        for child in expr.children:
            joins.extend(_inspect_joins(child))
    elif isinstance(expr, _OrGroup):
        for child in expr.children:
            joins.extend(_inspect_joins(child))
    return _sort_joins(tuple(joins))


def _inspect_unjoined_same_name_ports(expr: _RuleExpr) -> tuple[dict[str, object], ...]:
    hints: dict[tuple[str, tuple[str, ...]], dict[str, object]] = {}
    for group in _iter_and_groups(expr):
        direct_operands = tuple(child for child in group.children if isinstance(child, _RuleOperand))
        by_name: dict[str, list[_RuleOperand]] = {}
        for operand in direct_operands:
            for name in operand.rule.ports:
                by_name.setdefault(name, []).append(operand)
        for name, operands in sorted(by_name.items()):
            if len(operands) < 2:
                continue
            aliases = tuple(sorted(operand.alias for operand in operands))
            if not _port_name_fully_joined(name, aliases, group.joins):
                hints.setdefault((name, aliases), {"port_name": name, "occurrences": aliases})
    return tuple(hints[key] for key in sorted(hints, key=repr))


def _iter_and_groups(expr: _RuleExpr) -> tuple[_AndGroup, ...]:
    if isinstance(expr, _AndGroup):
        groups = [expr]
        for child in expr.children:
            groups.extend(_iter_and_groups(child))
        return tuple(groups)
    if isinstance(expr, _OrGroup):
        groups: list[_AndGroup] = []
        for child in expr.children:
            groups.extend(_iter_and_groups(child))
        return tuple(groups)
    return ()


def _port_name_fully_joined(name: str, aliases: tuple[str, ...], joins: tuple[RuleJoinConstraint, ...]) -> bool:
    expected = {(left, right) for idx, left in enumerate(aliases) for right in aliases[idx + 1 :]}
    actual: set[tuple[str, str]] = set()
    for join in joins:
        if join.left.port_name != name or join.right.port_name != name:
            continue
        pair = tuple(sorted((join.left.occurrence_alias, join.right.occurrence_alias)))
        actual.add((pair[0], pair[1]))
    return expected <= actual


def _derive_atom_descriptor(atom: Atom, atom_id: str) -> AtomDescriptor:
    if isinstance(atom, PredAtom):
        if atom.pred_id.endswith(":exists") and atom.terms:
            entity_type = atom.pred_id.removesuffix(":exists")
            return _atom_descriptor(
                atom_id,
                "entity_existence",
                subject=_term_summary(atom.terms[0]),
                entity_type=entity_type,
                summary=f"{entity_type}({_term_summary(atom.terms[0])})",
            )
        if ":" in atom.pred_id and atom.terms:
            entity_type, _, field = atom.pred_id.partition(":")
            return _atom_descriptor(
                atom_id,
                "field_predicate",
                subject=_term_summary(atom.terms[0]),
                entity_type=entity_type,
                field=field,
                value=_term_summary(atom.terms[-1]) if len(atom.terms) > 1 else None,
                summary=_pred_summary(atom),
            )
        return _atom_descriptor(atom_id, "pred", summary=_pred_summary(atom))
    if isinstance(atom, CmpAtom):
        return _atom_descriptor(
            atom_id,
            "cmp",
            subject=_term_summary(atom.lhs),
            op=atom.op,
            value=_term_summary(atom.rhs),
            summary=f"{_term_summary(atom.lhs)} {atom.op} {_term_summary(atom.rhs)}",
        )
    if isinstance(atom, InAtom):
        values = tuple(_term_summary(value) for value in atom.values)
        return _atom_descriptor(
            atom_id,
            "in",
            subject=_term_summary(atom.var),
            op="in",
            value=values,
            summary=f"{_term_summary(atom.var)} in {values!r}",
        )
    if isinstance(atom, BuiltinAtom):
        args = tuple(_term_summary(arg) for arg in atom.args)
        return _atom_descriptor(atom_id, "builtin", op=atom.op, value=args, summary=f"{atom.op}{args!r}")
    if isinstance(atom, NotAtom):
        return _atom_descriptor(atom_id, "not", summary="not(...)")
    raise RuleExprError(f"unsupported atom type for inspect: {type(atom).__name__}")


def _atom_descriptor(
    atom_id: str,
    kind: str,
    *,
    subject: str | None = None,
    entity_type: str | None = None,
    field: str | None = None,
    op: str | None = None,
    value: object = None,
    summary: str = "",
) -> AtomDescriptor:
    return AtomDescriptor(
        atom_id=atom_id,
        kind=kind,
        subject=subject,
        entity_type=entity_type,
        field=field,
        op=op,
        value=value,
        summary=summary,
    )


def _pred_summary(atom: PredAtom) -> str:
    args = ", ".join(_term_summary(term) for term in atom.terms)
    return f"{atom.pred_id}({args})"


def _term_summary(term: Term) -> str:
    if isinstance(term, Var):
        return term.name
    if isinstance(term, Const):
        return repr(term.value)
    if isinstance(term, AggregateAtom):
        return f"{term.kind}(...)"
    return repr(term)


def _render_desc_template(
    desc_template: str | None,
    alias: str,
    bindings: Mapping[str, object],
) -> str:
    if desc_template is None:
        return ""

    def replace(match: re.Match[str]) -> str:
        port_name = match.group(1)
        qualified = f"{alias}.{port_name}"
        if qualified in bindings:
            return str(bindings[qualified])
        if port_name in bindings:
            return str(bindings[port_name])
        return f"<{port_name}>"

    return _DESC_PORT_RE.sub(replace, desc_template)


def _render_ast_compact(ast: tuple[object, ...]) -> str:
    tag = ast[0]
    if tag == "rule":
        _tag, alias, rule_id = ast
        return str(alias) if alias == rule_id else f"{alias}:{rule_id}"
    if tag == "and":
        _tag, children, joins = ast
        child_text = " & ".join(_render_ast_compact(child) for child in children)
        if joins:
            return f"({child_text}).join({len(joins)})"
        return f"({child_text})"
    if tag == "or":
        _tag, children = ast
        return "(" + " | ".join(_render_ast_compact(child) for child in children) + ")"
    return repr(ast)


def _render_join(join: RuleJoinConstraint) -> str:
    return f"{join.left.occurrence_alias}.{join.left.port_name} = {join.right.occurrence_alias}.{join.right.port_name}"


def _inspect_join_tuple(join: RuleJoinConstraint) -> tuple[object, ...]:
    return (
        join.op,
        _inspect_join_endpoint(join.left),
        _inspect_join_endpoint(join.right),
    )


def _inspect_join_endpoint(ref: RulePortRef) -> tuple[str, str, str]:
    return (ref.occurrence_alias, ref.rule_id, ref.port_name)


def _sort_joins(joins: tuple[RuleJoinConstraint, ...]) -> tuple[RuleJoinConstraint, ...]:
    return tuple(sorted(joins, key=lambda join: repr(_inspect_join_tuple(join))))


def _require_non_empty_str(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuleExprError(f"{field_name} must be non-empty string")
    return value


__all__ = [
    "AtomDescriptor",
    "OccurrenceInspect",
    "PortInspect",
    "RuleExprInspect",
]
