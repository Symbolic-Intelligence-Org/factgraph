"""Validation utilities for rules."""

from __future__ import annotations

from symir.errors import ValidationError
from symir.ir.fact_schema import FactView
from symir.ir.rule_schema import Rule, Expr
from symir.ir.expr_ir import Var, Const, Ref, Call, Unify, If, NotExpr, ExprIR
from symir.rules.library import Library


class RuleValidator:
    """Validate rules against schema/view constraints."""

    def __init__(self, view: FactView, library: Library | None = None) -> None:
        self.view = view
        self.library = library
        self._allowed_predicate_ids = set(view.schema_ids)
        if library is not None:
            self._allowed_predicate_ids.update(library.predicate_ids().keys())

    def validate(self, rule: Rule) -> None:
        self._validate_conditions(rule)

    def _validate_conditions(self, rule: Rule) -> None:
        head_id = rule.predicate.schema_id
        for body_index, body in enumerate(rule.conditions):
            for lit_index, literal in enumerate(body.literals):
                if isinstance(literal, Ref):
                    self._validate_ref(literal, head_id, body_index, lit_index)
                elif isinstance(literal, Expr):
                    self._validate_expr(literal.expr, head_id, body_index, lit_index)
                else:  # pragma: no cover - safeguard
                    raise ValidationError("Unknown literal type.")

    def _validate_ref(
        self,
        ref: Ref,
        head_id: str,
        body_index: int,
        lit_index: int,
    ) -> None:
        pred_id = ref.schema
        if pred_id not in self._allowed_predicate_ids:
            raise ValidationError(f"Ref predicate not in allowed references: {pred_id}")
        if pred_id == head_id:
            raise ValidationError(
                f"Direct recursion detected: head {head_id} refers to itself in body {body_index}"
            )
        predicate = self.view.schema.get(pred_id)
        if len(ref.terms) != predicate.arity:
            raise ValidationError(
                f"Ref arity mismatch: expected {predicate.arity}, got {len(ref.terms)}"
            )
        for term, arg in zip(ref.terms, predicate.signature):
            if not isinstance(term, (Var, Const)):
                raise ValidationError(
                    f"Ref term must be Var/Const at body {body_index} literal {lit_index}"
                )
            if isinstance(term, Const):
                self._validate_const_type(term, arg.datatype, body_index, lit_index)

    def _validate_const_type(
        self,
        const: Const,
        datatype: str | None,
        body_index: int,
        lit_index: int,
    ) -> None:
        if datatype is None:
            return
        dtype = datatype.strip().lower()
        value = const.value
        if dtype == "string":
            if not isinstance(value, str):
                raise ValidationError(
                    f"Const type mismatch at body {body_index} literal {lit_index}: expected string."
                )
            return
        if dtype == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValidationError(
                    f"Const type mismatch at body {body_index} literal {lit_index}: expected int."
                )
            return
        if dtype == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValidationError(
                    f"Const type mismatch at body {body_index} literal {lit_index}: expected float."
                )
            return
        if dtype == "bool":
            if not isinstance(value, bool):
                raise ValidationError(
                    f"Const type mismatch at body {body_index} literal {lit_index}: expected bool."
                )
            return

    def _validate_expr(
        self,
        expr: ExprIR,
        head_id: str,
        body_index: int,
        lit_index: int,
    ) -> None:
        if isinstance(expr, Ref):
            self._validate_ref(expr, head_id, body_index, lit_index)
            return
        if isinstance(expr, Unify):
            self._validate_expr(expr.lhs, head_id, body_index, lit_index)
            self._validate_expr(expr.rhs, head_id, body_index, lit_index)
            return
        if isinstance(expr, Call):
            for arg in expr.args:
                self._validate_expr(arg, head_id, body_index, lit_index)
            return
        if isinstance(expr, If):
            self._validate_expr(expr.cond, head_id, body_index, lit_index)
            self._validate_expr(expr.then, head_id, body_index, lit_index)
            self._validate_expr(expr.else_, head_id, body_index, lit_index)
            return
        if isinstance(expr, NotExpr):
            self._validate_expr(expr.expr, head_id, body_index, lit_index)
            return
        if isinstance(expr, (Var, Const)):
            return
        raise ValidationError("Unknown expression type.")
