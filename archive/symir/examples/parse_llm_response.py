"""Parse OpenAI Responses API output into Rule IR (compact/verbose)."""

from __future__ import annotations

import json
from typing import Any

from symir.rules.constraint_schemas import build_pydantic_rule_model
from symir.ir.rule_schema import Rule, Cond, Expr
from symir.ir.expr_ir import Var, Const, Ref, expr_from_dict
from symir.rules.validator import RuleValidator


def _extract_json(resp) -> dict[str, Any]:
    """Extract JSON payload from Responses API result."""

    if getattr(resp, "output_text", None):
        return json.loads(resp.output_text)
    for item in getattr(resp, "output", []):
        for c in getattr(item, "content", []):
            if getattr(c, "type", None) == "output_text":
                return json.loads(c.text)
    raise ValueError("No JSON output found in response.")


def _term_from_value(value: dict[str, Any]):
    if value["kind"] == "var":
        return Var(name=value["name"])
    if value["kind"] == "const":
        return Const(value=value["value"])
    raise ValueError(f"Unknown term kind: {value.get('kind')}")


def _compact_args_to_ordered_terms(pred, args) -> list[Var | Const]:
    expected_names = [arg.arg_name or f"Arg{i + 1}" for i, arg in enumerate(pred.signature)]
    provided = {arg.name: _term_from_value(arg.value.model_dump()) for arg in args}
    if len(provided) == len(args) and all(name in provided for name in expected_names):
        return [provided[name] for name in expected_names]
    # Fallback for legacy payloads that rely on positional order only.
    return [_term_from_value(arg.value.model_dump()) for arg in args]


def resp_to_rule(
    resp,
    *,
    head,
    view,
    library=None,
    mode: str = "compact",
) -> Rule:
    """Parse a Responses API output into Rule IR.

    Args:
        resp: Responses API output object.
        head: Predicate schema (Fact/Rel) used as rule head.
        view: FactView for validation.
        library: Optional Library (for predicate/expr ops).
        mode: "compact" or "verbose" decoding.
    """

    payload = _extract_json(resp)
    model = build_pydantic_rule_model(view, library=library, mode=mode)
    validated = model.model_validate(payload)

    conditions: list[Cond] = []
    for body in validated.conditions:
        literals = []
        for lit in body.literals:
            if lit.kind == "ref":
                pred = view.schema.get(lit.schema)
                if mode == "compact":
                    terms = _compact_args_to_ordered_terms(pred, lit.args)
                else:
                    terms = [_term_from_value(term.model_dump()) for term in lit.terms]
                literals.append(
                    Ref(schema=pred, terms=terms, negated=lit.negated)
                )
            elif lit.kind == "expr":
                literals.append(Expr(expr=expr_from_dict(lit.expr.model_dump())))
            else:
                raise ValueError(f"Unknown literal kind: {lit.kind}")
        conditions.append(Cond(literals=literals, prob=body.prob))

    rule = Rule(predicate=head, conditions=conditions)
    RuleValidator(view, library=library).validate(rule)
    return rule
