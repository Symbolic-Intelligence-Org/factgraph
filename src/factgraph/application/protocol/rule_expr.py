from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NoReturn

from factgraph._sdk_errors import SDKDSLError


class RuleExprError(SDKDSLError):
    """Raised when RuleExpr authoring input violates the T3 expression contract."""


class ExplicitBoolError(RuleExprError):
    """Raised when Rule or RuleExpr values are used in Python boolean contexts."""


class RuleExpr:
    """Public namespace for RuleExpr factories and the nominal RuleExpr surface."""

    @staticmethod
    def all(*operands: object) -> _RuleExpr:
        return _combine("and", operands)

    @staticmethod
    def any(*operands: object) -> _RuleExpr:
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
    rule: object

    def _canonical(self) -> CanonicalExpr:
        return ("rule", _rule_identity(self.rule))


@dataclass(frozen=True, eq=False)
class _AndGroup(_RuleExpr):
    children: tuple[_RuleExpr, ...]

    def _canonical(self) -> CanonicalExpr:
        return ("and", _canonical_children(self.children))


@dataclass(frozen=True, eq=False)
class _OrGroup(_RuleExpr):
    children: tuple[_RuleExpr, ...]

    def _canonical(self) -> CanonicalExpr:
        return ("or", _canonical_children(self.children))


def _coerce_rule_expr_operand(value: object) -> _RuleExpr:
    from .rule import Rule

    if isinstance(value, _RuleExpr):
        return value
    if isinstance(value, Rule):
        return _RuleOperand(value)
    if _is_legacy_sdk_rule(value):
        raise RuleExprError(
            "legacy SDK Rule cannot be used in RuleExpr; use build_application_rule(...) "
            "or import ApplicationRule"
        )
    raise RuleExprError("RuleExpr operands must be application protocol Rule or RuleExpr values")


def _combine(kind: Literal["and", "or"], operands: tuple[object, ...]) -> _RuleExpr:
    if not operands:
        raise RuleExprError("RuleExpr.all/any require at least one operand")

    children: list[_RuleExpr] = []
    for operand in operands:
        expr = _coerce_rule_expr_operand(operand)
        if kind == "and" and isinstance(expr, _AndGroup):
            children.extend(expr.children)
        elif kind == "or" and isinstance(expr, _OrGroup):
            children.extend(expr.children)
        else:
            children.append(expr)

    if kind == "and":
        return _AndGroup(tuple(children))
    return _OrGroup(tuple(children))


def _canonical_children(children: tuple[_RuleExpr, ...]) -> tuple[CanonicalExpr, ...]:
    return tuple(sorted((child._canonical() for child in children), key=repr))


def _rule_identity(rule: object) -> tuple[str, str]:
    return (str(getattr(rule, "id")), str(getattr(rule, "content_digest")))


def _is_legacy_sdk_rule(value: object) -> bool:
    cls = value.__class__
    return cls.__name__ == "Rule" and cls.__module__ == "factgraph.sdk.dsl.rule"


__all__ = [
    "ExplicitBoolError",
    "RuleExpr",
    "RuleExprError",
]
