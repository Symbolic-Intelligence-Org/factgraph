from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from factgraph.application.protocol import Rule as ApplicationRule
from factgraph.core.rules.where_ast import (
    AndExpr,
    Atom,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    OrExpr,
    PredAtom as CorePredAtom,
    RuleRefAtom as CoreRuleRefAtom,
    Var,
    WhereASTError,
    WhereExpr,
    parse_where_ir_to_ast,
)

from .branch import Branch
from .errors import SDKDSLError
from .expr import (
    AttrRef,
    CompareExpr,
    NotExpr,
    PredAtom as DSLPredAtom,
    RuleRefAtom as DSLRuleRefAtom,
    lower_where,
)


class DSLToApplicationRuleError(SDKDSLError):
    """Raised when SDK DSL input cannot be lowered into an application Rule."""


def build_application_rule(
    *,
    id: str,
    where: list[Any],
    ports: Mapping[str, Any],
    version: str | None = None,
    desc: str | None = None,
) -> ApplicationRule:
    """Build an application-layer Rule from SDK DSL where atoms and ports."""

    _reject_or_shape(where)
    _reject_legacy_where(where, path="where")
    try:
        where_ir = lower_where(where)
        where_expr = _canonicalize_vars(parse_where_ir_to_ast(where_ir))
    except (SDKDSLError, WhereASTError) as exc:
        raise DSLToApplicationRuleError(str(exc)) from exc

    if not isinstance(where_expr, AndExpr):
        raise DSLToApplicationRuleError("application Rule bridge accepts AND-only where bodies")

    vars_by_name = _collect_vars_by_name(where_expr)
    converted_ports = _convert_ports(ports, vars_by_name=vars_by_name)
    return ApplicationRule(
        id=id,
        version=version,
        desc=desc,
        where=tuple(where_expr.atoms),
        ports=converted_ports,
    )


def _reject_or_shape(where: Any) -> None:
    if not isinstance(where, list) or not where:
        raise DSLToApplicationRuleError("where must be a non-empty list")
    if any(isinstance(item, Branch) for item in where):
        raise DSLToApplicationRuleError("application Rule bridge accepts AND-only where bodies; Branch is not allowed")
    if all(isinstance(item, list) for item in where):
        raise DSLToApplicationRuleError("application Rule bridge accepts AND-only where bodies; OR branches are not allowed")


def _reject_legacy_where(items: Sequence[Any], *, path: str) -> None:
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if isinstance(item, Branch):
            raise DSLToApplicationRuleError(f"{item_path}: Branch is not allowed in new Rule path")
        if isinstance(item, list):
            raise DSLToApplicationRuleError(f"{item_path}: OR branch list is not allowed in new Rule path")
        _reject_legacy_atom(item, path=item_path)


def _reject_legacy_atom(atom: Any, *, path: str) -> None:
    if isinstance(atom, DSLPredAtom):
        raise DSLToApplicationRuleError(
            f"{path}: Pred(...) raw atom is not allowed in new Rule path; use Entity(var).field syntax"
        )
    if isinstance(atom, DSLRuleRefAtom):
        raise DSLToApplicationRuleError(
            f"{path}: RuleRef atom is not allowed in new Rule path; compose Rules through ports"
        )
    if isinstance(atom, AttrRef):
        raise DSLToApplicationRuleError(
            f"{path}: bare AttrRef is not allowed in new Rule path; use Entity(var).field == value"
        )
    if isinstance(atom, CompareExpr):
        _reject_legacy_compare(atom, path=path)
        return
    if isinstance(atom, NotExpr):
        _reject_legacy_where(atom.body, path=f"{path}.body")


def _reject_legacy_compare(expr: CompareExpr, *, path: str) -> None:
    for side_name, value in (("left", expr.left), ("right", expr.right)):
        if isinstance(value, AttrRef) and value.entity_type is None:
            raise DSLToApplicationRuleError(
                f"{path}.{side_name}: legacy AttrRef is not allowed in new Rule path; "
                "use Entity(var).field == value"
            )


def _convert_ports(ports: Mapping[str, Any], *, vars_by_name: Mapping[str, Var]) -> dict[str, Var]:
    if not isinstance(ports, Mapping) or not ports:
        raise DSLToApplicationRuleError("ports must be non-empty Mapping[str, LogicVar]")
    converted: dict[str, Var] = {}
    for name, value in ports.items():
        if not isinstance(name, str) or not name:
            raise DSLToApplicationRuleError("ports keys must be non-empty strings")
        token = getattr(value, "token", None)
        label = getattr(value, "label", None)
        if token is None or not isinstance(token, str):
            raise DSLToApplicationRuleError(f"ports[{name!r}] must be SDK LogicVar")
        if label is None:
            raise DSLToApplicationRuleError(
                f"ports[{name!r}] cannot use anonymous LogicVar from Entity(...) Ellipsis"
            )
        try:
            converted[name] = vars_by_name[token]
        except KeyError as exc:
            raise DSLToApplicationRuleError(f"ports[{name!r}] LogicVar must appear in where") from exc
    return converted


def _collect_vars_by_name(expr: WhereExpr) -> dict[str, Var]:
    out: dict[str, Var] = {}
    if isinstance(expr, AndExpr):
        for atom in expr.atoms:
            _collect_vars_from_atom(atom, out)
        return out
    if isinstance(expr, OrExpr):
        for branch in expr.branches:
            for atom in branch.atoms:
                _collect_vars_from_atom(atom, out)
        return out
    return out


def _collect_vars_from_atom(atom: Atom, out: dict[str, Var]) -> None:
    if isinstance(atom, CorePredAtom):
        for term in atom.terms:
            _collect_vars_from_term(term, out)
        return
    if isinstance(atom, CoreRuleRefAtom):
        for term in atom.terms:
            _collect_vars_from_term(term, out)
        return
    if isinstance(atom, CmpAtom):
        _collect_vars_from_term(atom.lhs, out)
        _collect_vars_from_term(atom.rhs, out)
        return
    if isinstance(atom, InAtom):
        out.setdefault(atom.var.name, atom.var)
        return
    if isinstance(atom, BuiltinAtom):
        for term in atom.args:
            _collect_vars_from_term(term, out)
        return
    if isinstance(atom, NotAtom):
        for nested in _collect_vars_by_name(atom.body).values():
            out.setdefault(nested.name, nested)


def _collect_vars_from_term(term: Any, out: dict[str, Var]) -> None:
    if isinstance(term, Var):
        out.setdefault(term.name, term)
    elif isinstance(term, Const):
        return


def _canonicalize_vars(expr: WhereExpr) -> WhereExpr:
    vars_by_name: dict[str, Var] = {}
    return _canonicalize_expr(expr, vars_by_name)


def _canonicalize_expr(expr: WhereExpr, vars_by_name: dict[str, Var]) -> WhereExpr:
    if isinstance(expr, AndExpr):
        return AndExpr(
            atoms=[_canonicalize_atom(atom, vars_by_name) for atom in expr.atoms],
            origin=expr.origin,
        )
    if isinstance(expr, OrExpr):
        return OrExpr(
            branches=[
                _canonicalize_expr(branch, vars_by_name) for branch in expr.branches
            ],
            origin=expr.origin,
        )
    return expr


def _canonicalize_atom(atom: Atom, vars_by_name: dict[str, Var]) -> Atom:
    if isinstance(atom, CorePredAtom):
        return CorePredAtom(
            pred_id=atom.pred_id,
            terms=[_canonicalize_term(term, vars_by_name) for term in atom.terms],
            origin=atom.origin,
        )
    if isinstance(atom, CoreRuleRefAtom):
        return CoreRuleRefAtom(
            rule_id=atom.rule_id,
            version=atom.version,
            terms=[_canonicalize_term(term, vars_by_name) for term in atom.terms],
            origin=atom.origin,
        )
    if isinstance(atom, CmpAtom):
        return CmpAtom(
            op=atom.op,
            lhs=_canonicalize_term(atom.lhs, vars_by_name),
            rhs=_canonicalize_term(atom.rhs, vars_by_name),
            origin=atom.origin,
        )
    if isinstance(atom, InAtom):
        return InAtom(
            var=_canonicalize_term(atom.var, vars_by_name),
            values=list(atom.values),
            origin=atom.origin,
        )
    if isinstance(atom, BuiltinAtom):
        return BuiltinAtom(
            op=atom.op,
            args=[_canonicalize_term(term, vars_by_name) for term in atom.args],
            origin=atom.origin,
        )
    if isinstance(atom, NotAtom):
        return NotAtom(
            body=_canonicalize_expr(atom.body, vars_by_name),
            origin=atom.origin,
        )
    return atom


def _canonicalize_term(term: Any, vars_by_name: dict[str, Var]) -> Any:
    if isinstance(term, Var):
        existing = vars_by_name.setdefault(term.name, term)
        return existing
    return term
