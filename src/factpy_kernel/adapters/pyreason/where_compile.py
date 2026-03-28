"""WhereIR -> PyReason rule syntax compiler.

Compiles lowered WhereIR atoms (from ``sdk/dsl/expr.lower_where``) into
PyReason rule strings. This is the execution-surface compiler: it consumes
lowered tuples, not PredAtom/LogicVar SDK objects.

Per D3 (frozen), v0 only supports lowered predicate atoms:
    ("pred", pred_id, [term1, term2, ...])

Per D7 (frozen), v0 uses an attribute-existence model:
    - node predicates emit one entity term
    - relationship predicates emit two entity terms
    - value terms are ignored in generated syntax
"""
from __future__ import annotations

from typing import Any

from factpy_kernel.adapters.pyreason.rule_ext import _normalize_body_predicate_bounds

class PyReasonWhereCompileError(Exception):
    """Raised when WhereIR contains atoms unsupported by PyReason v0."""


def compile_where_ir_to_pyreason(
    target_pred_id: str,
    head_vars: list[Any],
    where: list[Any],
    *,
    schema_ir: dict[str, Any],
    engine_ext: Any | None = None,
) -> list[tuple[str, str]]:
    """Compile lowered WhereIR into ``(rule_string, rule_name)`` tuples."""
    if not isinstance(target_pred_id, str) or not target_pred_id:
        raise PyReasonWhereCompileError("target_pred_id must be non-empty string")
    if not isinstance(head_vars, list):
        raise PyReasonWhereCompileError("head_vars must be list")
    if not isinstance(schema_ir, dict):
        raise PyReasonWhereCompileError("schema_ir must be dict")

    branches = _extract_branches(where)
    relationship_preds = _relationship_pred_ids(schema_ir)
    delay = _resolve_delay(engine_ext)
    body_predicate_bounds = _resolve_body_predicate_bounds(engine_ext)

    rules: list[tuple[str, str]] = []
    base_name = f"derived_{_pred_short_name(target_pred_id)}"
    for branch_idx, branch_atoms in enumerate(branches):
        rule_name = base_name if len(branches) == 1 else f"{base_name}_b{branch_idx}"
        rule_str = _compile_single_branch(
            target_pred_id,
            head_vars,
            branch_atoms,
            relationship_preds=relationship_preds,
            delay=delay,
            body_predicate_bounds=body_predicate_bounds,
        )
        rules.append((rule_str, rule_name))
    return rules


def _compile_single_branch(
    target_pred_id: str,
    head_vars: list[Any],
    atoms: list[Any],
    *,
    relationship_preds: set[str],
    delay: int,
    body_predicate_bounds: dict[str, tuple[float, float]],
) -> str:
    if not atoms:
        raise PyReasonWhereCompileError("WHERE branch is empty")

    head_terms = _compile_terms(
        head_vars,
        pred_id=target_pred_id,
        relationship_preds=relationship_preds,
        position="head",
    )
    head_str = f"{_pred_short_name(target_pred_id)}({', '.join(head_terms)})"

    body_parts: list[str] = []
    for atom in atoms:
        pred_id, terms = _validate_pred_atom(atom)
        compiled_terms = _compile_terms(
            terms,
            pred_id=pred_id,
            relationship_preds=relationship_preds,
            position="body",
        )
        body_atom = f"{_pred_short_name(pred_id)}({', '.join(compiled_terms)})"
        bound = body_predicate_bounds.get(pred_id)
        if bound is not None:
            lo, hi = bound
            body_atom = f"{body_atom} : [{lo}, {hi}]"
        body_parts.append(body_atom)

    return f"{head_str} <-{delay} {', '.join(body_parts)}"


def _validate_pred_atom(atom: Any) -> tuple[str, list[Any]]:
    if not isinstance(atom, tuple) or not atom:
        raise PyReasonWhereCompileError(f"Invalid WhereIR atom shape: {atom!r}")
    kind = atom[0]
    if kind == "pred":
        if len(atom) != 3:
            raise PyReasonWhereCompileError(f"pred atom must have exactly 3 elements: {atom!r}")
        pred_id = atom[1]
        terms = atom[2]
        if not isinstance(pred_id, str) or not pred_id:
            raise PyReasonWhereCompileError(f"pred atom pred_id must be non-empty string: {atom!r}")
        if not isinstance(terms, list):
            raise PyReasonWhereCompileError(f"pred atom terms must be list: {atom!r}")
        for term in terms:
            _validate_term(term)
        return pred_id, terms
    if kind == "eq":
        raise PyReasonWhereCompileError("Equality comparisons (eq) are not supported in PyReason v0")
    if kind == "not":
        raise PyReasonWhereCompileError("Negation (not) is not supported in PyReason v0")
    if kind == "ruleref":
        raise PyReasonWhereCompileError("Rule references (ruleref) are not supported in PyReason v0")
    raise PyReasonWhereCompileError(
        f"WhereIR atom kind '{kind}' is not supported in PyReason v0"
    )


def _validate_atom(atom: Any) -> None:
    _validate_pred_atom(atom)


def _extract_branches(where: list[Any]) -> list[list[Any]]:
    if not isinstance(where, list) or not where:
        raise PyReasonWhereCompileError("WHERE clause is empty")
    if all(isinstance(item, list) for item in where):
        branches: list[list[Any]] = []
        for branch in where:
            if not branch:
                raise PyReasonWhereCompileError("WHERE OR branch must be non-empty")
            branches.append(list(branch))
        return branches
    return [list(where)]


def _compile_terms(
    terms: list[Any],
    *,
    pred_id: str,
    relationship_preds: set[str],
    position: str,
) -> list[str]:
    if pred_id in relationship_preds:
        if len(terms) < 2:
            raise PyReasonWhereCompileError(
                f"{position} relationship predicate requires at least two entity terms: {pred_id}"
            )
        return [_clean_term(terms[0]), _clean_term(terms[1])]
    if not terms:
        raise PyReasonWhereCompileError(
            f"{position} node predicate requires at least one entity term: {pred_id}"
        )
    return [_clean_term(terms[0])]


def _resolve_delay(engine_ext: Any | None) -> int:
    if engine_ext is None:
        return 0
    delay = getattr(engine_ext, "timestep_delay", 0)
    if isinstance(delay, bool) or not isinstance(delay, int) or delay < 0:
        raise PyReasonWhereCompileError("engine_ext.timestep_delay must be non-negative int")
    return delay


def _resolve_body_predicate_bounds(engine_ext: Any | None) -> dict[str, tuple[float, float]]:
    if engine_ext is None:
        return {}
    try:
        return _normalize_body_predicate_bounds(getattr(engine_ext, "body_predicate_bounds", {}))
    except ValueError as exc:
        raise PyReasonWhereCompileError(str(exc)) from exc


def _validate_term(term: Any) -> None:
    if isinstance(term, str):
        return
    if isinstance(term, (int, float)) and not isinstance(term, bool):
        return
    raise PyReasonWhereCompileError(
        f"Unsupported term type for PyReason v0: {type(term).__name__}"
    )


def _pred_short_name(pred_id: str) -> str:
    parts = pred_id.split(":", 1)
    return parts[1] if len(parts) > 1 else pred_id


def _clean_var(token: str) -> str:
    if isinstance(token, str) and token.startswith("$"):
        return token[1:]
    return str(token)


def _clean_term(term: Any) -> str:
    _validate_term(term)
    if isinstance(term, str):
        return _clean_var(term)
    return str(term)


def _relationship_pred_ids(schema_ir: dict[str, Any]) -> set[str]:
    predicates = schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        raise PyReasonWhereCompileError("schema_ir.predicates must be list")
    return {
        pred["pred_id"]
        for pred in predicates
        if isinstance(pred, dict)
        and isinstance(pred.get("pred_id"), str)
        and pred.get("relationship_type")
    }


__all__ = [
    "PyReasonWhereCompileError",
    "compile_where_ir_to_pyreason",
]
