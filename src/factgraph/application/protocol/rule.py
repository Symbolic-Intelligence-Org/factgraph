from __future__ import annotations

from dataclasses import dataclass
import json
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, Mapping, NoReturn

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import (
    AndExpr,
    AggregateAtom,
    Atom,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    Origin,
    OrExpr,
    PredAtom,
    RuleRefAtom,
    Term,
    Var,
    WhereExpr,
)

if TYPE_CHECKING:
    from .rule_expr import RuleJoinConstraint, _RuleExpr


class RuleValidationError(ValueError):
    """Raised when an application protocol Rule violates shape invariants."""


@dataclass(frozen=True)
class PortType:
    kind: Literal["entity_ref", "value"]
    entity_type: str | None = None


_ALLOWED_ATOM_TYPES = (PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom)
_DESC_PORT_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)")
_MALFORMED_PERCENT_RE = re.compile(r"%(?![A-Za-z_])")
_OCCURRENCE_ALIAS_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_PROJECTION_ID_PREFIX = "__factgraph_projection__"
_PROJECTION_ORIGIN = Origin(source="authoring", path="Rule.projection")
_PROJECTION_PLACEHOLDER_PRED_ID = "__factgraph_projection_placeholder"
_PROJECTION_VAR_PREFIX = "$__projection_"


@dataclass(frozen=True)
class Rule:
    """Application protocol Rule DTO storing core when-body AST atoms directly."""

    id: str
    when: tuple[Atom, ...]
    ports: Mapping[str, Var]
    version: str | None = None
    desc: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.id, field_name="id")
        if self.version is not None:
            _require_non_empty_str(self.version, field_name="version")
        if self.desc is not None:
            _require_non_empty_str(self.desc, field_name="desc")
        if not isinstance(self.when, tuple) or not self.when:
            raise RuleValidationError("when must be non-empty tuple[Atom, ...]")
        if not isinstance(self.ports, Mapping) or not self.ports:
            raise RuleValidationError("ports must be non-empty Mapping[str, Var]")

        outer_seen_vars: set[Var] = set()
        for idx, atom in enumerate(self.when):
            _validate_atom(atom, field_name=f"when[{idx}]", seen_vars=outer_seen_vars)
        seen_vars: set[Var] = set(outer_seen_vars)
        for idx, atom in enumerate(self.when):
            _collect_aggregate_term_vars_from_atom(
                atom,
                field_name=f"when[{idx}]",
                outer_seen_vars=outer_seen_vars,
                seen_vars=seen_vars,
            )

        frozen_ports: dict[str, Var] = {}
        for key, value in self.ports.items():
            _require_non_empty_str(key, field_name="ports.<key>")
            if not isinstance(value, Var):
                raise RuleValidationError(f"ports[{key!r}] must be core.rules.where_ast.Var")
            if value not in seen_vars:
                raise RuleValidationError(f"ports[{key!r}] Var must appear in where")
            frozen_ports[key] = value

        _validate_desc(self.desc, port_names=frozenset(frozen_ports))
        object.__setattr__(self, "ports", MappingProxyType(dict(frozen_ports)))
        object.__setattr__(self, "_port_types", MappingProxyType(_infer_port_types(frozen_ports, self.when)))

    @property
    def atom_ids(self) -> tuple[str, ...]:
        return tuple(f"{self.id}:atom_{idx}" for idx in range(len(self.when)))

    @property
    def port_types(self) -> Mapping[str, PortType]:
        return self._port_types

    @property
    def content_digest(self) -> str:
        payload = {
            "ports": [(name, _serialize_var(var)) for name, var in sorted(self.ports.items())],
            "when": [_serialize_atom(atom) for atom in self.when],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256_hex(canonical)

    def render_desc(self, bindings: Mapping[str, Any] | None = None) -> str:
        if self.desc is None:
            return ""
        values = {} if bindings is None else bindings
        if not isinstance(values, Mapping):
            raise RuleValidationError("bindings must be Mapping[str, Any] or None")

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in values:
                return str(values[name])
            return f"<{name}>"

        return _DESC_PORT_RE.sub(replace, self.desc)

    def as_(self, alias: str | None = None) -> RuleOccurrence:
        effective_alias = self.id if alias is None else alias
        return RuleOccurrence(rule=self, alias=_validate_occurrence_alias(effective_alias))

    @classmethod
    def projection(cls, *port_names: str) -> Rule:
        if not port_names:
            raise RuleValidationError("Rule.projection(...) requires at least one port name")
        seen: set[str] = set()
        for idx, name in enumerate(port_names):
            if not isinstance(name, str) or not name:
                raise RuleValidationError(f"Rule.projection(...) port_names[{idx}] must be non-empty string")
            if name in seen:
                raise RuleValidationError(f"Rule.projection(...) duplicate port name: {name!r}")
            seen.add(name)

        variables = tuple(Var(f"{_PROJECTION_VAR_PREFIX}{idx}", _PROJECTION_ORIGIN) for idx, _name in enumerate(port_names))
        return cls(
            id=_projection_rule_id(port_names),
            when=tuple(PredAtom(_PROJECTION_PLACEHOLDER_PRED_ID, [var], _PROJECTION_ORIGIN) for var in variables),
            ports={name: var for name, var in zip(port_names, variables, strict=True)},
        )

    def __and__(self, other: object) -> _RuleExpr:
        from .rule_expr import _combine

        return _combine("and", (self, other))

    def __or__(self, other: object) -> _RuleExpr:
        from .rule_expr import _combine

        return _combine("or", (self, other))

    def __bool__(self) -> NoReturn:
        from .rule_expr import ExplicitBoolError

        raise ExplicitBoolError("Rule values do not support Python truthiness; use & or | instead of and/or")


@dataclass(frozen=True)
class RulePortRef:
    occurrence_alias: str
    rule_id: str
    port_name: str
    var: Var
    port_type: PortType

    def __hash__(self) -> int:
        return hash((self.occurrence_alias, self.rule_id, self.port_name, self.var, self.port_type))

    def eq(self, other: RulePortRef) -> RuleJoinConstraint:
        from .rule_expr import RuleExprError, RuleJoinConstraint, _validate_not_same_occurrence

        if not isinstance(other, RulePortRef):
            raise RuleExprError("RulePortRef.eq(...) requires another RulePortRef")
        _validate_not_same_occurrence(self, other)
        return RuleJoinConstraint(left=self, right=other)


@dataclass(frozen=True)
class RuleOccurrence:
    rule: Rule
    alias: str

    def __post_init__(self) -> None:
        if not isinstance(self.rule, Rule):
            raise RuleValidationError("RuleOccurrence.rule must be application protocol Rule")
        object.__setattr__(self, "alias", _validate_occurrence_alias(self.alias))

    def port(self, name: str) -> RulePortRef:
        _require_non_empty_str(name, field_name="port name")
        if name not in self.rule.ports:
            raise RuleValidationError(f"port {name!r} is not declared on Rule {self.rule.id!r}")
        return RulePortRef(
            occurrence_alias=self.alias,
            rule_id=self.rule.id,
            port_name=name,
            var=self.rule.ports[name],
            port_type=self.rule.port_types[name],
        )

    def __and__(self, other: object) -> _RuleExpr:
        from .rule_expr import _combine

        return _combine("and", (self, other))

    def __or__(self, other: object) -> _RuleExpr:
        from .rule_expr import _combine

        return _combine("or", (self, other))

    def __getattr__(self, name: str) -> RulePortRef:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self.port(name)
        except RuleValidationError as exc:
            raise AttributeError(name) from exc

    def __hash__(self) -> int:
        return hash((self.rule.id, self.alias))


def _require_non_empty_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuleValidationError(f"{field_name} must be non-empty string")
    return value


def _validate_desc(desc: str | None, *, port_names: frozenset[str]) -> None:
    if desc is None:
        return
    if _MALFORMED_PERCENT_RE.search(desc):
        raise RuleValidationError("desc contains malformed percent port interpolation")
    for match in _DESC_PORT_RE.finditer(desc):
        name = match.group(1)
        if name not in port_names:
            raise RuleValidationError(f"desc references undeclared port: {name}")


def _validate_occurrence_alias(alias: Any) -> str:
    if not isinstance(alias, str) or not alias:
        raise RuleValidationError("occurrence alias must be non-empty string")
    if re.fullmatch(_OCCURRENCE_ALIAS_RE, alias) is None:
        raise RuleValidationError("occurrence alias must match [A-Za-z][A-Za-z0-9_]*")
    return alias


def _projection_rule_id(port_names: tuple[str, ...]) -> str:
    payload = json.dumps(list(port_names), separators=(",", ":")).encode("utf-8")
    return f"{_PROJECTION_ID_PREFIX}{sha256_hex(payload)[:16]}"


def _is_projection_rule(rule: Rule) -> bool:
    if not isinstance(rule, Rule):
        return False
    port_names = tuple(rule.ports)
    if not port_names or rule.id != _projection_rule_id(port_names):
        return False
    if len(rule.when) != len(port_names):
        return False
    expected_vars = tuple(Var(f"{_PROJECTION_VAR_PREFIX}{idx}", _PROJECTION_ORIGIN) for idx, _name in enumerate(port_names))
    if tuple(rule.ports.values()) != expected_vars:
        return False
    for atom, expected_var in zip(rule.when, expected_vars, strict=True):
        if not isinstance(atom, PredAtom):
            return False
        if atom.pred_id != _PROJECTION_PLACEHOLDER_PRED_ID:
            return False
        if atom.origin != _PROJECTION_ORIGIN:
            return False
        if tuple(atom.terms) != (expected_var,):
            return False
    return True


def _validate_atom(atom: Any, *, field_name: str, seen_vars: set[Var]) -> None:
    if isinstance(atom, RuleRefAtom):
        raise RuleValidationError(f"{field_name} must not be RuleRefAtom")
    if not isinstance(atom, _ALLOWED_ATOM_TYPES):
        raise RuleValidationError(f"{field_name} must be one of PredAtom/CmpAtom/InAtom/BuiltinAtom/NotAtom")

    if isinstance(atom, PredAtom):
        for idx, term in enumerate(atom.terms):
            _collect_term_vars(term, field_name=f"{field_name}.terms[{idx}]", seen_vars=seen_vars)
        return
    if isinstance(atom, CmpAtom):
        _collect_term_vars(atom.lhs, field_name=f"{field_name}.lhs", seen_vars=seen_vars)
        _collect_term_vars(atom.rhs, field_name=f"{field_name}.rhs", seen_vars=seen_vars)
        return
    if isinstance(atom, InAtom):
        seen_vars.add(atom.var)
        for idx, value in enumerate(atom.values):
            if not isinstance(value, Const):
                raise RuleValidationError(f"{field_name}.values[{idx}] must be Const")
        return
    if isinstance(atom, BuiltinAtom):
        for idx, term in enumerate(atom.args):
            _collect_term_vars(term, field_name=f"{field_name}.args[{idx}]", seen_vars=seen_vars)
        return
    if isinstance(atom, NotAtom):
        _validate_where_expr(atom.body, field_name=f"{field_name}.body", seen_vars=seen_vars)


def _validate_where_expr(expr: Any, *, field_name: str, seen_vars: set[Var]) -> None:
    if isinstance(expr, AndExpr):
        for idx, atom in enumerate(expr.atoms):
            _validate_atom(atom, field_name=f"{field_name}.atoms[{idx}]", seen_vars=seen_vars)
        return
    if isinstance(expr, OrExpr):
        for branch_idx, branch in enumerate(expr.branches):
            _validate_where_expr(branch, field_name=f"{field_name}.branches[{branch_idx}]", seen_vars=seen_vars)
        return
    raise RuleValidationError(f"{field_name} must be AndExpr or OrExpr")


def _collect_term_vars(term: Any, *, field_name: str, seen_vars: set[Var]) -> None:
    if isinstance(term, Var):
        seen_vars.add(term)
        return
    if isinstance(term, Const):
        return
    if isinstance(term, AggregateAtom):
        _validate_aggregate_term(term, field_name=field_name)
        return
    raise RuleValidationError(f"{field_name} must be Var or Const")


def _validate_aggregate_term(term: AggregateAtom, *, field_name: str) -> None:
    if term.kind not in {"count", "sum", "min", "max", "mean"}:
        raise RuleValidationError(f"{field_name}.kind must be one of count/sum/min/max/mean")
    if term.kind == "count":
        if term.target is not None:
            raise RuleValidationError(f"{field_name}.target must be None for count")
    elif term.target is None:
        raise RuleValidationError(f"{field_name}.target must not be None for {term.kind}")
    elif isinstance(term.target, AggregateAtom):
        _validate_aggregate_term(term.target, field_name=f"{field_name}.target")
    elif not isinstance(term.target, (Var, Const)):
        raise RuleValidationError(f"{field_name}.target must be Var, Const, or AggregateAtom")
    if not term.filter:
        raise RuleValidationError(f"{field_name}.filter must be non-empty")
    for idx, atom in enumerate(term.filter):
        if isinstance(atom, BuiltinAtom):
            raise RuleValidationError(f"{field_name}.filter[{idx}] must not be BuiltinAtom")
        if isinstance(atom, RuleRefAtom):
            raise RuleValidationError(f"{field_name}.filter[{idx}] must not be RuleRefAtom")
        if _atom_has_aggregate_term(atom):
            raise RuleValidationError(f"{field_name}.filter[{idx}] must not contain AggregateAtom")
        _validate_atom(
            atom,
            field_name=f"{field_name}.filter[{idx}]",
            seen_vars=set(),
        )


def _collect_aggregate_term_vars_from_atom(
    atom: Atom,
    *,
    field_name: str,
    outer_seen_vars: set[Var],
    seen_vars: set[Var],
) -> None:
    if isinstance(atom, CmpAtom):
        _collect_aggregate_term_vars(
            atom.lhs,
            field_name=f"{field_name}.lhs",
            outer_seen_vars=outer_seen_vars,
            seen_vars=seen_vars,
        )
        _collect_aggregate_term_vars(
            atom.rhs,
            field_name=f"{field_name}.rhs",
            outer_seen_vars=outer_seen_vars,
            seen_vars=seen_vars,
        )
        return
    if isinstance(atom, BuiltinAtom):
        for idx, term in enumerate(atom.args):
            _collect_aggregate_term_vars(
                term,
                field_name=f"{field_name}.args[{idx}]",
                outer_seen_vars=outer_seen_vars,
                seen_vars=seen_vars,
            )
        return
    if isinstance(atom, NotAtom):
        _collect_aggregate_term_vars_from_expr(
            atom.body,
            field_name=f"{field_name}.body",
            outer_seen_vars=outer_seen_vars,
            seen_vars=seen_vars,
        )


def _collect_aggregate_term_vars_from_expr(
    expr: WhereExpr,
    *,
    field_name: str,
    outer_seen_vars: set[Var],
    seen_vars: set[Var],
) -> None:
    if isinstance(expr, AndExpr):
        for idx, atom in enumerate(expr.atoms):
            _collect_aggregate_term_vars_from_atom(
                atom,
                field_name=f"{field_name}.atoms[{idx}]",
                outer_seen_vars=outer_seen_vars,
                seen_vars=seen_vars,
            )
        return
    if isinstance(expr, OrExpr):
        for branch_idx, branch in enumerate(expr.branches):
            _collect_aggregate_term_vars_from_expr(
                branch,
                field_name=f"{field_name}.branches[{branch_idx}]",
                outer_seen_vars=outer_seen_vars,
                seen_vars=seen_vars,
            )


def _collect_aggregate_term_vars(
    term: Any,
    *,
    field_name: str,
    outer_seen_vars: set[Var],
    seen_vars: set[Var],
) -> None:
    if not isinstance(term, AggregateAtom):
        return
    _validate_aggregate_term(term, field_name=field_name)
    target_vars: set[Var] = set()
    if term.target is not None:
        _collect_all_vars_in_term(term.target, seen_vars=target_vars)
    filter_vars: set[Var] = set()
    for atom in term.filter:
        _collect_all_vars_in_atom(atom, seen_vars=filter_vars)
    seen_vars |= target_vars
    seen_vars |= filter_vars & outer_seen_vars


def _collect_all_vars_in_term(term: Any, *, seen_vars: set[Var]) -> None:
    if isinstance(term, Var):
        seen_vars.add(term)
        return
    if isinstance(term, Const):
        return
    if isinstance(term, AggregateAtom):
        if term.target is not None:
            _collect_all_vars_in_term(term.target, seen_vars=seen_vars)
        for atom in term.filter:
            _collect_all_vars_in_atom(atom, seen_vars=seen_vars)


def _collect_all_vars_in_atom(atom: Atom, *, seen_vars: set[Var]) -> None:
    if isinstance(atom, PredAtom):
        for term in atom.terms:
            _collect_all_vars_in_term(term, seen_vars=seen_vars)
        return
    if isinstance(atom, CmpAtom):
        _collect_all_vars_in_term(atom.lhs, seen_vars=seen_vars)
        _collect_all_vars_in_term(atom.rhs, seen_vars=seen_vars)
        return
    if isinstance(atom, InAtom):
        _collect_all_vars_in_term(atom.var, seen_vars=seen_vars)
        for value in atom.values:
            _collect_all_vars_in_term(value, seen_vars=seen_vars)
        return
    if isinstance(atom, BuiltinAtom):
        for term in atom.args:
            _collect_all_vars_in_term(term, seen_vars=seen_vars)
        return
    if isinstance(atom, NotAtom):
        branches = atom.body.branches if isinstance(atom.body, OrExpr) else [atom.body]
        for branch in branches:
            for body_atom in branch.atoms:
                _collect_all_vars_in_atom(body_atom, seen_vars=seen_vars)


def _term_has_aggregate(term: Any) -> bool:
    return isinstance(term, AggregateAtom)


def _atom_has_aggregate_term(atom: Atom) -> bool:
    if isinstance(atom, PredAtom):
        return any(_term_has_aggregate(term) for term in atom.terms)
    if isinstance(atom, CmpAtom):
        return _term_has_aggregate(atom.lhs) or _term_has_aggregate(atom.rhs)
    if isinstance(atom, InAtom):
        return _term_has_aggregate(atom.var) or any(_term_has_aggregate(value) for value in atom.values)
    if isinstance(atom, BuiltinAtom):
        return True
    if isinstance(atom, NotAtom):
        branches = atom.body.branches if isinstance(atom.body, OrExpr) else [atom.body]
        return any(_atom_has_aggregate_term(body_atom) for branch in branches for body_atom in branch.atoms)
    return False


def _infer_port_types(ports: Mapping[str, Var], when: tuple[Atom, ...]) -> dict[str, PortType]:
    out: dict[str, PortType] = {}
    for name, var in ports.items():
        entity_type = _find_entity_ref_type(var, when)
        if entity_type is not None:
            out[name] = PortType(kind="entity_ref", entity_type=entity_type)
        else:
            out[name] = PortType(kind="value")
    return out


def _find_entity_ref_type(var: Var, atoms: tuple[Atom, ...]) -> str | None:
    for atom in atoms:
        found = _find_entity_ref_type_in_atom(var, atom)
        if found is not None:
            return found
    return None


def _find_entity_ref_type_in_atom(var: Var, atom: Atom) -> str | None:
    if isinstance(atom, PredAtom) and atom.pred_id.endswith(":exists"):
        if any(term == var for term in atom.terms):
            entity_type = atom.pred_id[: -len(":exists")]
            if entity_type:
                return entity_type
    if isinstance(atom, NotAtom):
        return _find_entity_ref_type_in_expr(var, atom.body)
    return None


def _find_entity_ref_type_in_expr(var: Var, expr: WhereExpr) -> str | None:
    if isinstance(expr, AndExpr):
        for atom in expr.atoms:
            found = _find_entity_ref_type_in_atom(var, atom)
            if found is not None:
                return found
    if isinstance(expr, OrExpr):
        for branch in expr.branches:
            found = _find_entity_ref_type_in_expr(var, branch)
            if found is not None:
                return found
    return None


def _serialize_atom(atom: Atom) -> dict[str, Any]:
    if isinstance(atom, PredAtom):
        return {"type": "PredAtom", "pred_id": atom.pred_id, "terms": [_serialize_term(term) for term in atom.terms]}
    if isinstance(atom, CmpAtom):
        return {"type": "CmpAtom", "op": atom.op, "lhs": _serialize_term(atom.lhs), "rhs": _serialize_term(atom.rhs)}
    if isinstance(atom, InAtom):
        return {"type": "InAtom", "var": _serialize_var(atom.var), "values": [_serialize_const(value) for value in atom.values]}
    if isinstance(atom, BuiltinAtom):
        return {"type": "BuiltinAtom", "op": atom.op, "args": [_serialize_term(term) for term in atom.args]}
    if isinstance(atom, NotAtom):
        return {"type": "NotAtom", "body": _serialize_where_expr(atom.body)}
    raise RuleValidationError(f"cannot serialize unsupported atom type: {type(atom).__name__}")


def _serialize_where_expr(expr: WhereExpr) -> dict[str, Any]:
    if isinstance(expr, AndExpr):
        return {"type": "AndExpr", "atoms": [_serialize_atom(atom) for atom in expr.atoms]}
    if isinstance(expr, OrExpr):
        return {"type": "OrExpr", "branches": [_serialize_where_expr(branch) for branch in expr.branches]}
    raise RuleValidationError(f"cannot serialize unsupported where expr type: {type(expr).__name__}")


def _serialize_term(term: Term) -> dict[str, Any]:
    if isinstance(term, Var):
        return _serialize_var(term)
    if isinstance(term, Const):
        return _serialize_const(term)
    if isinstance(term, AggregateAtom):
        return {
            "type": "AggregateAtom",
            "kind": term.kind,
            "target": None if term.target is None else _serialize_term(term.target),
            "filter": [_serialize_atom(atom) for atom in term.filter],
            "origin": _serialize_origin(term.origin),
        }
    raise RuleValidationError(f"cannot serialize unsupported term type: {type(term).__name__}")


def _serialize_var(var: Var) -> dict[str, Any]:
    return {"type": "Var", "name": var.name, "origin": _serialize_origin(var.origin)}


def _serialize_const(const: Const) -> dict[str, Any]:
    return {"type": "Const", "value": _serialize_value(const.value), "origin": _serialize_origin(const.origin)}


def _serialize_origin(origin: Any) -> dict[str, Any] | None:
    if origin is None:
        return None
    return {"source": getattr(origin, "source", None), "path": getattr(origin, "path", None)}


def _serialize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [_serialize_value(item) for item in value]}
    if isinstance(value, list):
        return {"type": "list", "items": [_serialize_value(item) for item in value]}
    if isinstance(value, dict):
        return {
            "type": "dict",
            "items": [
                [_serialize_value(key), _serialize_value(item)]
                for key, item in sorted(value.items(), key=lambda pair: repr(pair[0]))
            ],
        }
    return {"type": type(value).__qualname__, "repr": repr(value)}


__all__ = [
    "PortType",
    "Rule",
    "RuleOccurrence",
    "RulePortRef",
    "RuleValidationError",
]
