from __future__ import annotations

from dataclasses import dataclass
import json
import re
from types import MappingProxyType
from typing import Any, Literal, Mapping

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import (
    AndExpr,
    Atom,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    OrExpr,
    PredAtom,
    RuleRefAtom,
    Term,
    Var,
    WhereExpr,
)


class RuleValidationError(ValueError):
    """Raised when an application protocol Rule violates shape invariants."""


@dataclass(frozen=True)
class PortType:
    kind: Literal["entity_ref", "value"]
    entity_type: str | None = None


_ALLOWED_ATOM_TYPES = (PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom)
_DESC_PORT_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)")
_MALFORMED_PERCENT_RE = re.compile(r"%(?![A-Za-z_])")


@dataclass(frozen=True)
class Rule:
    """Application protocol Rule DTO storing core where AST atoms directly."""

    id: str
    where: tuple[Atom, ...]
    ports: Mapping[str, Var]
    version: str | None = None
    desc: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.id, field_name="id")
        if self.version is not None:
            _require_non_empty_str(self.version, field_name="version")
        if self.desc is not None:
            _require_non_empty_str(self.desc, field_name="desc")
        if not isinstance(self.where, tuple) or not self.where:
            raise RuleValidationError("where must be non-empty tuple[Atom, ...]")
        if not isinstance(self.ports, Mapping) or not self.ports:
            raise RuleValidationError("ports must be non-empty Mapping[str, Var]")

        seen_vars: set[Var] = set()
        for idx, atom in enumerate(self.where):
            _validate_atom(atom, field_name=f"where[{idx}]", seen_vars=seen_vars)

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
        object.__setattr__(self, "_port_types", MappingProxyType(_infer_port_types(frozen_ports, self.where)))

    @property
    def atom_ids(self) -> tuple[str, ...]:
        return tuple(f"{self.id}:atom_{idx}" for idx in range(len(self.where)))

    @property
    def port_types(self) -> Mapping[str, PortType]:
        return self._port_types

    @property
    def content_digest(self) -> str:
        payload = {
            "ports": [(name, _serialize_var(var)) for name, var in sorted(self.ports.items())],
            "where": [_serialize_atom(atom) for atom in self.where],
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
    raise RuleValidationError(f"{field_name} must be Var or Const")


def _infer_port_types(ports: Mapping[str, Var], where: tuple[Atom, ...]) -> dict[str, PortType]:
    out: dict[str, PortType] = {}
    for name, var in ports.items():
        entity_type = _find_entity_ref_type(var, where)
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
    "RuleValidationError",
]
