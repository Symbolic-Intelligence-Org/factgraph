from __future__ import annotations

from typing import Any, Literal

from factgraph.core.rules.backend_profile import BackendProfile
from factgraph.core.rules.rule_ast import HeadAtom, ProgramAst, QueryRuleAst, RuleAst
from factgraph.core.rules.where_ast import (
    AndExpr,
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
from factgraph.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast


class RuleASTValidationError(Exception):
    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


def validate_rule_ast(
    rule_ast: RuleAst,
    *,
    mode: Literal["python", "souffle"] = "python",
    where_capabilities: dict[str, Any] | None = None,
    profile: BackendProfile | None = None,
) -> None:
    if not isinstance(rule_ast, RuleAst):
        raise RuleASTValidationError("rule_ast must be RuleAst", path="$.rule")
    _validate_rule_shape(rule_ast)
    _validate_head_shape(rule_ast.head)
    try:
        validate_where_ast(rule_ast.where, mode=mode, capabilities=where_capabilities, profile=profile)
    except WhereASTValidationError as exc:
        raise RuleASTValidationError(
            f"where validation failed: {exc}",
            path=_remap_where_path(exc.path),
        ) from exc


def validate_query_rule_ast(
    rule_ast: QueryRuleAst,
    *,
    mode: Literal["python", "souffle"] = "python",
    where_capabilities: dict[str, Any] | None = None,
    profile: BackendProfile | None = None,
) -> None:
    if not isinstance(rule_ast, QueryRuleAst):
        raise RuleASTValidationError("query rule_ast must be QueryRuleAst", path="$.query_rule")
    _validate_query_rule_shape(rule_ast)
    try:
        validate_where_ast(rule_ast.where, mode=mode, capabilities=where_capabilities, profile=profile)
    except WhereASTValidationError as exc:
        raise RuleASTValidationError(
            f"where validation failed: {exc}",
            path=_remap_where_path(exc.path, root="$.query_rule.where"),
        ) from exc
    _validate_query_select_vars_available(rule_ast)


def validate_program_ast(
    program_ast: ProgramAst,
    *,
    mode: Literal["python", "souffle"] = "python",
    where_capabilities: dict[str, Any] | None = None,
    profile: BackendProfile | None = None,
) -> None:
    if not isinstance(program_ast, ProgramAst):
        raise RuleASTValidationError("program_ast must be ProgramAst", path="$.program")
    if not isinstance(program_ast.rules, list):
        raise RuleASTValidationError("ProgramAst.rules must be list", path="$.program.rules")
    for idx, rule in enumerate(program_ast.rules):
        try:
            validate_rule_ast(rule, mode=mode, where_capabilities=where_capabilities, profile=profile)
        except RuleASTValidationError as exc:
            path = exc.path
            if path and path.startswith("$.rule"):
                path = path.replace("$.rule", f"$.program.rules[{idx}]", 1)
            raise RuleASTValidationError(str(exc), path=path or f"$.program.rules[{idx}]") from exc


def _validate_rule_shape(rule_ast: RuleAst) -> None:
    if not isinstance(rule_ast.rule_id, str) or not rule_ast.rule_id:
        raise RuleASTValidationError("rule_id must be non-empty string", path="$.rule.rule_id")
    if not isinstance(rule_ast.version, str) or not rule_ast.version:
        raise RuleASTValidationError("version must be non-empty string", path="$.rule.version")
    if not isinstance(rule_ast.head, HeadAtom):
        raise RuleASTValidationError("head must be HeadAtom", path="$.rule.head")
    if rule_ast.meta is not None and not isinstance(rule_ast.meta, dict):
        raise RuleASTValidationError("meta must be dict or None", path="$.rule.meta")


def _validate_query_rule_shape(rule_ast: QueryRuleAst) -> None:
    if not isinstance(rule_ast.rule_id, str) or not rule_ast.rule_id:
        raise RuleASTValidationError("rule_id must be non-empty string", path="$.query_rule.rule_id")
    if not isinstance(rule_ast.version, str) or not rule_ast.version:
        raise RuleASTValidationError("version must be non-empty string", path="$.query_rule.version")
    if not isinstance(rule_ast.select_vars, list) or not rule_ast.select_vars:
        raise RuleASTValidationError("select_vars must be non-empty list", path="$.query_rule.select_vars")
    for idx, value in enumerate(rule_ast.select_vars):
        if not isinstance(value, str) or not value:
            raise RuleASTValidationError(
                "select_vars items must be non-empty string",
                path=f"$.query_rule.select_vars[{idx}]",
            )
    if rule_ast.expose is not None and not isinstance(rule_ast.expose, bool):
        raise RuleASTValidationError("expose must be bool or None", path="$.query_rule.expose")
    if rule_ast.meta is not None and not isinstance(rule_ast.meta, dict):
        raise RuleASTValidationError("meta must be dict or None", path="$.query_rule.meta")


def _validate_query_select_vars_available(rule_ast: QueryRuleAst) -> None:
    guaranteed_bound = _query_guaranteed_bound(rule_ast.where, bound_in=set())
    missing = [var for var in rule_ast.select_vars if var not in guaranteed_bound]
    if missing:
        raise RuleASTValidationError(
            "select_vars must be guaranteed bound by where in every branch: " + ", ".join(missing),
            path="$.query_rule.select_vars",
        )


def _query_guaranteed_bound(expr: WhereExpr, *, bound_in: set[str]) -> set[str]:
    if isinstance(expr, AndExpr):
        return _query_guaranteed_bound_and(expr, bound_in=bound_in)
    if isinstance(expr, OrExpr):
        branch_bounds = [
            _query_guaranteed_bound_and(branch, bound_in=set(bound_in))
            for branch in expr.branches
        ]
        if not branch_bounds:
            return set(bound_in)
        out = set(branch_bounds[0])
        for bounds in branch_bounds[1:]:
            out &= bounds
        return out
    return set(bound_in)


def _query_guaranteed_bound_and(and_expr: AndExpr, *, bound_in: set[str]) -> set[str]:
    bound = set(bound_in)
    for atom in and_expr.atoms:
        if isinstance(atom, (PredAtom, RuleRefAtom)):
            bound |= _vars_in_terms(atom.terms)
            continue
        if isinstance(atom, InAtom):
            # Filter only; validate_where_ast already enforces pre-bound requirement.
            continue
        if isinstance(atom, NotAtom):
            # not never binds outward variables; inner locals are branch-local only.
            continue
        if isinstance(atom, BuiltinAtom):
            out_var = _builtin_output_var(atom)
            if out_var is not None:
                bound.add(out_var)
            continue
        if isinstance(atom, CmpAtom):
            _apply_cmp_eq_binder(atom, bound)
            continue
    return bound


def _apply_cmp_eq_binder(atom: CmpAtom, bound: set[str]) -> None:
    if atom.op != "eq":
        return
    lhs_ready = _term_is_resolved(atom.lhs, bound)
    rhs_ready = _term_is_resolved(atom.rhs, bound)
    if lhs_ready and isinstance(atom.rhs, Var) and atom.rhs.name not in bound:
        bound.add(atom.rhs.name)
        return
    if rhs_ready and isinstance(atom.lhs, Var) and atom.lhs.name not in bound:
        bound.add(atom.lhs.name)


def _builtin_output_var(atom: BuiltinAtom) -> str | None:
    if not atom.args:
        return None
    out_term = atom.args[0]
    if isinstance(out_term, Var):
        return out_term.name
    return None


def _vars_in_terms(terms: list[Term]) -> set[str]:
    return {term.name for term in terms if isinstance(term, Var)}


def _term_is_resolved(term: Term, bound: set[str]) -> bool:
    if isinstance(term, Const):
        return True
    if isinstance(term, Var):
        return term.name in bound
    return False


def _validate_head_shape(head: HeadAtom) -> None:
    if not isinstance(head.pred_id, str) or not head.pred_id:
        raise RuleASTValidationError("head pred_id must be non-empty string", path="$.rule.head[1]")
    if not isinstance(head.terms, list):
        raise RuleASTValidationError("head terms must be list", path="$.rule.head[2]")
    for idx, term in enumerate(head.terms):
        _validate_term_shape(term, path=f"$.rule.head[2][{idx}]")


def _validate_term_shape(term: Term, *, path: str) -> None:
    if isinstance(term, Var):
        if not isinstance(term.name, str) or not term.name.startswith("$") or len(term.name) < 2:
            raise RuleASTValidationError("Var.name must be '$' + non-empty identifier token", path=path)
        return
    if isinstance(term, Const):
        return
    raise RuleASTValidationError(f"unsupported term node: {type(term).__name__}", path=path)


def _remap_where_path(path: str | None, *, root: str = "$.rule.where") -> str:
    if not path:
        return root
    if path.startswith("$.where"):
        return path.replace("$.where", root, 1)
    origin = path if path.startswith(root) else root
    return origin
