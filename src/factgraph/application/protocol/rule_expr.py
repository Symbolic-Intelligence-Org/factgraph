from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations, product
from typing import Iterable, Literal, NoReturn

from factgraph._sdk_errors import SDKDSLError

from .rule import Rule, RuleOccurrence, RulePortRef, RuleValidationError


class RuleExprError(SDKDSLError):
    """Raised when RuleExpr authoring input violates the T3 expression contract."""


class ExplicitBoolError(RuleExprError):
    """Raised when Rule or RuleExpr values are used in Python boolean contexts."""


@dataclass(frozen=True, eq=False)
class RuleJoinConstraint:
    """Explicit equality join between ports of two Rule occurrences."""

    left: RulePortRef
    right: RulePortRef
    op: Literal["eq"] = "eq"

    def __post_init__(self) -> None:
        if not isinstance(self.left, RulePortRef):
            raise RuleExprError("RuleJoinConstraint.left must be RulePortRef")
        if not isinstance(self.right, RulePortRef):
            raise RuleExprError("RuleJoinConstraint.right must be RulePortRef")
        if self.op != "eq":
            raise RuleExprError("RuleJoinConstraint.op must be 'eq'")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RuleJoinConstraint):
            return NotImplemented
        return _canonical_join_constraint(self) == _canonical_join_constraint(other)

    def __hash__(self) -> int:
        return hash(_canonical_join_constraint(self))


class RuleExpr:
    """Public namespace for RuleExpr factories and the nominal RuleExpr surface."""

    @staticmethod
    def all(*operands: object) -> _RuleExpr:
        """Compose Rule occurrences with explicit logical conjunction.

        Args:
            *operands: Rules, occurrences, RuleExpr groups, or join constraints.

        Returns:
            A canonical conjunction expression.
        """
        return _combine("and", operands)

    @staticmethod
    def any(*operands: object) -> _RuleExpr:
        """Compose Rule occurrences with explicit logical disjunction.

        Args:
            *operands: Rules, occurrences, or compatible RuleExpr groups.

        Returns:
            A canonical disjunction expression.
        """
        return _combine("or", operands)

    def __and__(self, other: object) -> _RuleExpr:
        return _combine("and", (self, other))

    def __rand__(self, other: object) -> _RuleExpr:
        return _combine("and", (other, self))

    def __or__(self, other: object) -> _RuleExpr:
        return _combine("or", (self, other))

    def __ror__(self, other: object) -> _RuleExpr:
        return _combine("or", (other, self))

    def __bool__(self) -> NoReturn:
        raise ExplicitBoolError("RuleExpr values do not support Python truthiness; use & or | instead of and/or")


CanonicalExpr = tuple[object, ...]


@dataclass(frozen=True, eq=False)
class _RuleExpr(RuleExpr):
    def _canonical(self) -> CanonicalExpr:
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _RuleExpr):
            return NotImplemented
        return self._canonical() == other._canonical()

    def __hash__(self) -> int:
        return hash(self._canonical())


@dataclass(frozen=True, eq=False)
class _RuleOperand(_RuleExpr):
    rule: Rule
    alias: str
    explicit_alias: bool
    authored_alias: str | None = None

    def _canonical(self) -> CanonicalExpr:
        return ("rule", _rule_identity(self.rule), self.alias)


@dataclass(frozen=True, eq=False)
class _AndGroup(_RuleExpr):
    children: tuple[_RuleExpr, ...]
    joins: tuple[RuleJoinConstraint, ...] = ()

    def _canonical(self) -> CanonicalExpr:
        return ("and", _canonical_children(self.children), _canonical_joins(self.joins))

    def join(self, *constraints: RuleJoinConstraint) -> _AndGroup:
        if not constraints:
            raise RuleExprError("RuleExpr.join requires at least one join constraint")
        _validate_join_constraint_shapes(constraints)
        merged = _normalize_join_constraints((*self.joins, *constraints))
        _validate_join_reach(self, merged)
        return _AndGroup(self.children, merged)

    def join_by_ports(self, *explicit_names: str) -> _AndGroup:
        constraints = _expand_join_by_ports(self, explicit_names)
        _validate_join_constraint_shapes(constraints)
        merged = _normalize_join_constraints((*self.joins, *constraints))
        _validate_join_reach(self, merged)
        return _AndGroup(self.children, merged)


@dataclass(frozen=True, eq=False)
class _OrGroup(_RuleExpr):
    children: tuple[_RuleExpr, ...]

    def _canonical(self) -> CanonicalExpr:
        return ("or", _canonical_children(self.children))

    def join(self, *constraints: RuleJoinConstraint) -> NoReturn:
        raise RuleExprError("RuleExpr joins must be attached to AND groups; distribute joins into OR branches")

    def join_by_ports(self, *explicit_names: str) -> NoReturn:
        raise RuleExprError(
            "RuleExpr join_by_ports must be attached to AND groups; distribute joins into OR branches"
        )


def _coerce_rule_expr_operand(value: object) -> _RuleExpr:
    if isinstance(value, _RuleExpr):
        return value
    if isinstance(value, RuleOccurrence):
        return _RuleOperand(rule=value.rule, alias=value.alias, explicit_alias=True)
    if isinstance(value, Rule):
        try:
            occurrence = value.as_()
        except RuleValidationError as exc:
            raise RuleExprError(
                "bare Rule id cannot be used as a RuleExpr alias; use .as_(...) with an identifier alias"
            ) from exc
        return _RuleOperand(rule=occurrence.rule, alias=occurrence.alias, explicit_alias=False)
    if _is_legacy_sdk_rule(value):
        raise RuleExprError(
            "legacy SDK Rule cannot be used in RuleExpr; use build_application_rule(...) "
            "or import Rule"
        )
    raise RuleExprError("RuleExpr operands must be Rule or RuleExpr values")


def _combine(kind: Literal["and", "or"], operands: tuple[object, ...]) -> _RuleExpr:
    if not operands:
        raise RuleExprError("RuleExpr.all/any require at least one operand")

    children: list[_RuleExpr] = []
    joins: list[RuleJoinConstraint] = []
    for operand in operands:
        expr = _coerce_rule_expr_operand(operand)
        if kind == "and" and isinstance(expr, _AndGroup):
            children.extend(expr.children)
            joins.extend(expr.joins)
        elif kind == "or" and isinstance(expr, _OrGroup):
            children.extend(expr.children)
        else:
            children.append(expr)

    if kind == "and":
        merged_joins = _normalize_join_constraints(joins)
        expr: _RuleExpr = _AndGroup(tuple(children), merged_joins)
    else:
        expr = _OrGroup(tuple(children))
    _validate_expression_scope(expr)
    if isinstance(expr, _AndGroup) and expr.joins:
        _validate_join_reach(expr, expr.joins)
    return expr


def _validate_expression_scope(expr: _RuleExpr) -> None:
    operands = tuple(_iter_rule_operands(expr))
    aliases: dict[str, int] = defaultdict(int)
    by_identity: dict[tuple[str, str], list[_RuleOperand]] = defaultdict(list)

    for operand in operands:
        aliases[operand.alias] += 1
        by_identity[_rule_identity(operand.rule)].append(operand)

    issues: list[str] = [
        f"duplicate alias {alias!r}" for alias, count in sorted(aliases.items()) if count > 1
    ]
    for (rule_id, _content_digest), matches in sorted(by_identity.items(), key=lambda item: item[0]):
        if len(matches) > 1 and any(not match.explicit_alias for match in matches):
            issues.append(f"rule {rule_id!r} appears multiple times without explicit aliases")

    if issues:
        raise RuleExprError("RuleExpr occurrence validation failed: " + "; ".join(issues))


def _iter_rule_operands(expr: _RuleExpr) -> tuple[_RuleOperand, ...]:
    if isinstance(expr, _RuleOperand):
        return (expr,)
    if isinstance(expr, (_AndGroup, _OrGroup)):
        operands: list[_RuleOperand] = []
        for child in expr.children:
            operands.extend(_iter_rule_operands(child))
        return tuple(operands)
    return ()


def _canonical_children(children: tuple[_RuleExpr, ...]) -> tuple[CanonicalExpr, ...]:
    return tuple(sorted((child._canonical() for child in children), key=repr))


def _canonical_join_constraint(constraint: RuleJoinConstraint) -> tuple[object, ...]:
    left = _canonical_join_endpoint(constraint.left)
    right = _canonical_join_endpoint(constraint.right)
    endpoint_a, endpoint_b = sorted((left, right), key=repr)
    return (constraint.op, endpoint_a, endpoint_b)


def _canonical_join_endpoint(ref: RulePortRef) -> tuple[object, ...]:
    return (ref.occurrence_alias, ref.rule_id, ref.port_name, ref.var, ref.port_type)


def _canonical_joins(joins: tuple[RuleJoinConstraint, ...]) -> tuple[tuple[object, ...], ...]:
    return tuple(sorted((_canonical_join_constraint(join) for join in joins), key=repr))


def _normalize_join_constraints(constraints: Iterable[RuleJoinConstraint]) -> tuple[RuleJoinConstraint, ...]:
    unique: dict[tuple[object, ...], RuleJoinConstraint] = {}
    for constraint in constraints:
        unique.setdefault(_canonical_join_constraint(constraint), constraint)
    return tuple(unique[key] for key in sorted(unique, key=repr))


def _validate_join_by_port_names(explicit_names: tuple[str, ...]) -> None:
    if not explicit_names:
        raise RuleExprError("RuleExpr.join_by_ports requires at least one explicit port name")

    counts: dict[str, int] = defaultdict(int)
    issues: list[str] = []
    for name in explicit_names:
        if not isinstance(name, str) or not name:
            raise RuleExprError("RuleExpr.join_by_ports port names must be non-empty strings")
        counts[name] += 1

    issues.extend(f"duplicate requested port name {name!r}" for name, count in sorted(counts.items()) if count > 1)
    if issues:
        raise RuleExprError("RuleExpr.join_by_ports validation failed: " + "; ".join(issues))


def _expand_join_by_ports(group: _AndGroup, explicit_names: tuple[str, ...]) -> tuple[RuleJoinConstraint, ...]:
    _validate_join_by_port_names(explicit_names)
    issues: list[str] = []
    constraints: list[RuleJoinConstraint] = []

    for name in explicit_names:
        child_ref_branches = tuple(_port_ref_branches_for_name(child, name) for child in group.children)
        participating = tuple(
            branches for branches in child_ref_branches if branches and all(branch for branch in branches)
        )
        any_refs = any(branch for branches in child_ref_branches for branch in branches)
        if not any_refs:
            issues.append(f"port {name!r} is not present on any direct AND occurrence")
        elif len(participating) < 2:
            issues.append(f"port {name!r} is present on fewer than two direct AND occurrences")
        else:
            constraints.extend(_join_constraints_for_port_ref_branches(participating))

    if issues:
        raise RuleExprError("RuleExpr.join_by_ports validation failed: " + "; ".join(sorted(issues)))
    return tuple(constraints)


def _join_constraints_for_port_ref_branches(
    participating: tuple[tuple[tuple[RulePortRef, ...], ...], ...],
) -> tuple[RuleJoinConstraint, ...]:
    constraints: list[RuleJoinConstraint] = []
    for branch_product in product(*participating):
        for left_refs, right_refs in combinations(branch_product, 2):
            constraints.extend(left.eq(right) for left in left_refs for right in right_refs)
    return tuple(_normalize_join_constraints(constraints))


def _port_ref_branches_for_name(expr: _RuleExpr, name: str) -> tuple[tuple[RulePortRef, ...], ...]:
    if isinstance(expr, _RuleOperand):
        if name in expr.rule.ports:
            return ((expr.rule.as_(expr.alias).port(name),),)
        return ((),)
    if isinstance(expr, _AndGroup):
        child_branches = tuple(_port_ref_branches_for_name(child, name) for child in expr.children)
        branches: list[tuple[RulePortRef, ...]] = []
        for branch_product in product(*child_branches):
            refs: list[RulePortRef] = []
            for branch in branch_product:
                refs.extend(branch)
            branches.append(tuple(refs))
        return tuple(branches)
    if isinstance(expr, _OrGroup):
        branches: list[tuple[RulePortRef, ...]] = []
        for child in expr.children:
            branches.extend(_port_ref_branches_for_name(child, name))
        return tuple(branches)
    return ((),)


def _validate_join_constraint_shapes(constraints: tuple[RuleJoinConstraint, ...]) -> None:
    for constraint in constraints:
        if not isinstance(constraint, RuleJoinConstraint):
            raise RuleExprError("RuleExpr.join accepts only RuleJoinConstraint values")
        _validate_not_same_occurrence(constraint.left, constraint.right)


def _validate_not_same_occurrence(left: RulePortRef, right: RulePortRef) -> None:
    if left.occurrence_alias == right.occurrence_alias and left.rule_id == right.rule_id:
        raise RuleExprError("join constraints must connect distinct Rule occurrences; put self constraints in Rule.when")


def _validate_join_reach(group: _AndGroup, constraints: tuple[RuleJoinConstraint, ...]) -> None:
    reachable = _reachable_operands(group)
    for constraint in constraints:
        _validate_not_same_occurrence(constraint.left, constraint.right)
        for endpoint in (constraint.left, constraint.right):
            key = (endpoint.occurrence_alias, endpoint.rule_id)
            operand = reachable.get(key)
            if operand is None:
                raise RuleExprError(
                    f"join endpoint {endpoint.occurrence_alias!r}.{endpoint.port_name} is not reachable "
                    "from the direct AND spine"
                )
            _validate_endpoint_matches_operand(endpoint, operand)


def _reachable_operands(group: _AndGroup) -> dict[tuple[str, str], _RuleOperand]:
    reachable: dict[tuple[str, str], _RuleOperand] = {}
    for child in group.children:
        for operand in _iter_rule_operands(child):
            reachable[(operand.alias, operand.rule.id)] = operand
    return reachable


def _validate_endpoint_matches_operand(endpoint: RulePortRef, operand: _RuleOperand) -> None:
    if endpoint.port_name not in operand.rule.ports:
        raise RuleExprError(
            f"join endpoint {endpoint.occurrence_alias!r}.{endpoint.port_name} is not a declared port"
        )
    if endpoint.var != operand.rule.ports[endpoint.port_name]:
        raise RuleExprError(
            f"join endpoint {endpoint.occurrence_alias!r}.{endpoint.port_name} Var does not match the Rule port"
        )
    if endpoint.port_type != operand.rule.port_types[endpoint.port_name]:
        raise RuleExprError(
            f"join endpoint {endpoint.occurrence_alias!r}.{endpoint.port_name} port type does not match the Rule port"
        )


def _rule_identity(rule: object) -> tuple[str, str]:
    return (str(getattr(rule, "id")), str(getattr(rule, "content_digest")))


def _is_legacy_sdk_rule(value: object) -> bool:
    cls = value.__class__
    return cls.__name__ == "Rule" and cls.__module__ == "factgraph.sdk.dsl.rule"


__all__ = [
    "ExplicitBoolError",
    "RuleJoinConstraint",
    "RuleExpr",
    "RuleExprError",
]
