"""Rule schema definitions (predicate + conditions) and literals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union

from symir.errors import SchemaError
from symir.ir.fact_schema import PredicateSchema
from symir.ir.expr_ir import ExprIR, Var, Const, ExprTerm, Ref, expr_from_dict


@dataclass(frozen=True)
class Expr:
    expr: ExprIR

    def to_dict(self) -> dict[str, Any]:
        # Canonical payload uses direct ExprIR kinds (unify/call/if/not/ref).
        # "kind":"expr" wrapper is still accepted in from_dict for backward compatibility.
        return self.expr.to_dict()

Literal = Union[Ref, Expr]


def literal_from_dict(data: dict[str, Any]) -> Literal:
    kind = data.get("kind")
    if kind == "ref":
        ref = expr_from_dict(data)
        if not isinstance(ref, Ref):
            raise SchemaError("Ref literal parsing failed.")
        return ref
    if kind == "expr":
        expr_payload = data.get("expr")
        if not isinstance(expr_payload, dict):
            raise SchemaError("Expr literal requires dict payload in 'expr'.")
        return Expr(expr=expr_from_dict(expr_payload))
    # Backward-compatible payload: allow ExprIR kinds directly as body literals.
    try:
        expr = expr_from_dict(data)
    except SchemaError as exc:
        raise SchemaError(f"Unknown Literal kind: {kind}") from exc
    if isinstance(expr, Ref):
        return expr
    return Expr(expr=expr)


@dataclass(frozen=True)
class Cond:
    literals: list[Literal] = field(default_factory=list)
    prob: Optional[float] = None

    def __post_init__(self) -> None:
        normalized: list[Literal] = []
        for literal in self.literals:
            if isinstance(literal, Ref):
                normalized.append(literal)
                continue
            if isinstance(literal, Expr):
                normalized.append(literal)
                continue
            if isinstance(literal, ExprIR):
                if isinstance(literal, (Var, Const)):
                    raise SchemaError(
                        "Cond literals do not accept bare Var/Const. "
                        "Use Ref or expression nodes (Call/Unify/If/NotExpr)."
                    )
                normalized.append(Expr(expr=literal))
                continue
            raise SchemaError("Cond literals must be Ref, Expr, or ExprIR nodes.")
        object.__setattr__(self, "literals", normalized)
        if self.prob is not None:
            if not isinstance(self.prob, (int, float)):
                raise SchemaError("Cond prob must be a number if provided.")
            if not (0.0 <= float(self.prob) <= 1.0):
                raise SchemaError("Cond prob must be within [0.0, 1.0].")

    def to_dict(self) -> dict[str, Any]:
        return {
            "literals": [lit.to_dict() for lit in self.literals],
            "prob": self.prob,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Cond":
        if not isinstance(data, dict):
            raise SchemaError("Cond payload must be a dict.")
        items = data.get("literals", [])
        if not isinstance(items, list):
            raise SchemaError("Cond literals must be a list.")
        lits: list[Literal] = []
        for item in items:
            if not isinstance(item, dict):
                raise SchemaError("Cond literal entries must be dicts.")
            lits.append(literal_from_dict(item))
        return Cond(literals=lits, prob=data.get("prob"))


@dataclass(frozen=True)
class Rule:
    predicate: PredicateSchema
    conditions: list[Cond] = field(default_factory=list)
    render_configs: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.render_configs is not None and not isinstance(self.render_configs, dict):
            raise SchemaError("Rule render_configs must be a dict if provided.")

    @property
    def render_hints(self) -> dict[str, Any] | None:
        """Backward-compatible alias for older field naming."""
        return self.render_configs

    def to_dict(self) -> dict[str, Any]:
        data = self.predicate.to_dict()
        data["conditions"] = [cond.to_dict() for cond in self.conditions]
        if self.render_configs is not None:
            data["render_configs"] = self.render_configs
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Rule":
        render_configs = data.get("render_configs")
        legacy_render_hints = data.get("render_hints")
        if render_configs is None:
            render_configs = legacy_render_hints
        if render_configs is not None and not isinstance(render_configs, dict):
            raise SchemaError("Rule render_configs must be a dict if provided.")
        return Rule(
            predicate=PredicateSchema.from_dict(data),
            conditions=[Cond.from_dict(c) for c in data.get("conditions", [])],
            render_configs=render_configs,
        )


@dataclass(frozen=True)
class Query:
    """Query over a predicate (fact or rule-level)."""

    predicate_id: Optional[str] = None
    predicate: Optional[PredicateSchema] = None
    terms: list[ExprTerm] = field(default_factory=list)

    def __post_init__(self) -> None:
        if (self.predicate_id is None) == (self.predicate is None):
            raise SchemaError("Query requires exactly one of predicate_id or predicate.")
        if self.predicate is not None:
            if len(self.terms) != self.predicate.arity:
                raise SchemaError("Query terms length must match predicate arity.")
        for term in self.terms:
            if not isinstance(term, (Var, Const)):
                raise SchemaError("Query terms must be Var or Const.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicate_id": self.predicate_id,
            "predicate": self.predicate.to_dict() if self.predicate else None,
            "terms": [t.to_dict() for t in self.terms],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Query":
        predicate = data.get("predicate")
        return Query(
            predicate_id=data.get("predicate_id"),
            predicate=PredicateSchema.from_dict(predicate) if predicate else None,
            terms=[expr_from_dict(t) for t in data.get("terms", [])],
        )
