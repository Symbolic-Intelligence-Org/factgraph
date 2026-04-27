from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

from kernel.core.rules.backend_profile import BackendProfile
from kernel.core.rules.where_ast import (
    AndExpr,
    Atom,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    OrExpr,
    Origin,
    PredAtom,
    RuleRefAtom,
    Term,
    Var,
    WhereExpr,
)


class WhereASTValidationError(Exception):
    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


_CMP_OPS = {"eq", "ne", "gt", "ge", "lt", "le"}
_CMP_FILTER_OPS = {"gt", "ge", "lt", "le"}
_DEFAULT_BUILTINS = {"add", "sub", "neg", "addc", "mulc"}
_DEFAULT_MODES = {"python", "souffle"}
_RULEREF_POLICIES = {"allow", "require_resolved", "forbid"}
_NOT_BODY_POLICIES = {"allow", "require_correlated", "forbid_or", "forbid"}


@dataclass(frozen=True)
class _FlowState:
    bound: set[str]
    local_bound: set[str]
    free_used: set[str]
    bound_outside: set[str]


@dataclass(frozen=True)
class _StepEffect:
    requires: set[str]
    binds: set[str]
    references: set[str]


def validate_where_ast(
    expr: WhereExpr,
    *,
    mode: Literal["python", "souffle"] = "python",
    capabilities: dict[str, Any] | None = None,
    profile: BackendProfile | None = None,
    initial_bound_vars: set[str] | None = None,
) -> None:
    if mode not in _DEFAULT_MODES:
        raise WhereASTValidationError(f"unsupported validation mode: {mode}")
    resolved_initial_bound_vars = _normalize_initial_bound_vars(initial_bound_vars)
    resolved_caps = capabilities
    if resolved_caps is None and profile is not None:
        resolved_caps = profile.to_capabilities()
    caps = _capabilities_for_mode(mode, resolved_caps)
    _validate_expr_shape(expr, caps, in_not_body=False)
    _validate_expr_dataflow(expr, bound_outside=resolved_initial_bound_vars, caps=caps)


def _normalize_initial_bound_vars(initial_bound_vars: set[str] | None) -> set[str]:
    if initial_bound_vars is None:
        return set()
    if not isinstance(initial_bound_vars, set):
        raise WhereASTValidationError("initial_bound_vars must be set[str] when provided")
    out: set[str] = set()
    for value in initial_bound_vars:
        if not isinstance(value, str):
            raise WhereASTValidationError("initial_bound_vars must contain strings only")
        if not value.startswith("$") or len(value) < 2:
            raise WhereASTValidationError("initial_bound_vars entries must be '$' + identifier")
        out.add(value)
    return out


def _capabilities_for_mode(mode: str, overrides: dict[str, Any] | None) -> dict[str, Any]:
    caps: dict[str, Any] = {
        "mode": mode,
        "builtin_allow": set(_DEFAULT_BUILTINS),
        "cmp_allow": set(_CMP_OPS),
        "allow_ruleref": True,
        "allow_not_body_ruleref": False,
        "ruleref_policy": "allow",
        "not_body_policy": "allow",
    }
    if overrides:
        for key, value in overrides.items():
            caps[key] = value
    if "builtin_allow" in caps and not isinstance(caps["builtin_allow"], set):
        caps["builtin_allow"] = set(caps["builtin_allow"])
    if "cmp_allow" in caps and not isinstance(caps["cmp_allow"], set):
        caps["cmp_allow"] = set(caps["cmp_allow"])
    policy = caps.get("ruleref_policy", "allow")
    if policy not in _RULEREF_POLICIES:
        raise WhereASTValidationError(f"unsupported ruleref_policy: {policy}")
    not_body_policy = caps.get("not_body_policy", "allow")
    if not_body_policy not in _NOT_BODY_POLICIES:
        raise WhereASTValidationError(f"unsupported not_body_policy: {not_body_policy}")
    return caps


def _validate_expr_shape(expr: WhereExpr, caps: dict[str, Any], *, in_not_body: bool) -> None:
    if isinstance(expr, AndExpr):
        if not expr.atoms:
            raise _shape_error("AndExpr.atoms must be non-empty", origin=expr.origin)
        for atom in expr.atoms:
            _validate_atom_shape(atom, caps, in_not_body=in_not_body)
        return
    if isinstance(expr, OrExpr):
        if not expr.branches:
            raise _shape_error("OrExpr.branches must be non-empty", origin=expr.origin)
        for branch in expr.branches:
            if not isinstance(branch, AndExpr):
                raise _shape_error("OrExpr branches must be AndExpr", origin=expr.origin)
            _validate_expr_shape(branch, caps, in_not_body=in_not_body)
        return
    raise _shape_error(f"unsupported WhereExpr node: {type(expr).__name__}")


def _validate_atom_shape(atom: Atom, caps: dict[str, Any], *, in_not_body: bool) -> None:
    if isinstance(atom, PredAtom):
        if not isinstance(atom.pred_id, str) or not atom.pred_id:
            raise _shape_error("PredAtom.pred_id must be non-empty string", origin=atom.origin)
        if not atom.terms:
            raise _shape_error("PredAtom.terms must be non-empty", origin=atom.origin)
        for term in atom.terms:
            _validate_term_shape(term, origin=atom.origin)
        return

    if isinstance(atom, RuleRefAtom):
        ruleref_policy = caps.get("ruleref_policy", "allow")
        if caps.get("mode") == "souffle" and ruleref_policy in {"require_resolved", "forbid"}:
            raise _shape_error(
                f"RuleRefAtom is not allowed in this mode (ruleref_policy={ruleref_policy})",
                origin=atom.origin,
            )
        if in_not_body and not caps.get("allow_not_body_ruleref", False):
            raise _shape_error("RuleRefAtom is not allowed in not body", origin=atom.origin)
        if not caps.get("allow_ruleref", True):
            raise _shape_error("RuleRefAtom is not allowed in this mode", origin=atom.origin)
        if not isinstance(atom.rule_id, str) or not atom.rule_id:
            raise _shape_error("RuleRefAtom.rule_id must be non-empty string", origin=atom.origin)
        if atom.version is not None and (not isinstance(atom.version, str) or not atom.version):
            raise _shape_error("RuleRefAtom.version must be non-empty string or None", origin=atom.origin)
        if not atom.terms:
            raise _shape_error("RuleRefAtom.terms must be non-empty", origin=atom.origin)
        for term in atom.terms:
            _validate_term_shape(term, origin=atom.origin)
        return

    if isinstance(atom, CmpAtom):
        if atom.op not in caps["cmp_allow"]:
            raise _shape_error(f"CmpAtom op not allowed: {atom.op}", origin=atom.origin)
        _validate_term_shape(atom.lhs, origin=atom.origin)
        _validate_term_shape(atom.rhs, origin=atom.origin)
        return

    if isinstance(atom, InAtom):
        _validate_term_shape(atom.var, origin=atom.origin)
        if not isinstance(atom.var, Var):
            raise _shape_error("InAtom.var must be Var", origin=atom.origin)
        if not atom.values:
            raise _shape_error("InAtom.values must be non-empty", origin=atom.origin)
        for value in atom.values:
            if not isinstance(value, Const):
                raise _shape_error("InAtom.values must contain Const", origin=atom.origin)
        return

    if isinstance(atom, BuiltinAtom):
        if not isinstance(atom.op, str) or not atom.op:
            raise _shape_error("BuiltinAtom.op must be non-empty string", origin=atom.origin)
        if atom.op not in caps["builtin_allow"]:
            raise _shape_error(f"BuiltinAtom op not allowed: {atom.op}", origin=atom.origin)
        for arg in atom.args:
            _validate_term_shape(arg, origin=atom.origin)
        _validate_builtin_shape(atom)
        return

    if isinstance(atom, NotAtom):
        if atom.body is None:
            raise _shape_error("NotAtom.body must not be None", origin=atom.origin)
        not_body_policy = caps.get("not_body_policy", "allow")
        if caps.get("mode") == "souffle":
            if not_body_policy == "forbid":
                raise _shape_error(
                    f"NotAtom is not allowed in this mode (not_body_policy={not_body_policy})",
                    origin=atom.origin,
                )
            if not_body_policy == "forbid_or" and isinstance(atom.body, OrExpr):
                raise _shape_error(
                    f"NotAtom OR body is not allowed in this mode (not_body_policy={not_body_policy})",
                    origin=atom.origin,
                )
        _validate_expr_shape(atom.body, caps, in_not_body=True)
        _validate_not_body_subset(atom.body)
        return

    raise _shape_error(f"unsupported Atom node: {type(atom).__name__}")


def _validate_not_body_subset(expr: WhereExpr) -> None:
    allowed = (PredAtom, CmpAtom, InAtom, BuiltinAtom)
    branches = expr.branches if isinstance(expr, OrExpr) else [expr]
    for branch in branches:
        for atom in branch.atoms:
            if not isinstance(atom, allowed):
                raise _shape_error(
                    "not body supports Pred/Cmp/In/Builtin atoms only",
                    origin=getattr(atom, "origin", None),
                )


def _validate_builtin_shape(atom: BuiltinAtom) -> None:
    op = atom.op
    args = atom.args
    if op in {"add", "sub"}:
        if len(args) != 3:
            raise _shape_error(f"{op} expects 3 args: (z, x, y)", origin=atom.origin)
        if not isinstance(args[0], Var):
            raise _shape_error(f"{op} output z must be Var", origin=atom.origin)
        return
    if op == "neg":
        if len(args) != 2:
            raise _shape_error("neg expects 2 args: (z, x)", origin=atom.origin)
        if not isinstance(args[0], Var):
            raise _shape_error("neg output z must be Var", origin=atom.origin)
        return
    if op in {"addc", "mulc"}:
        if len(args) != 3:
            raise _shape_error(f"{op} expects 3 args: (z, x, c)", origin=atom.origin)
        if not isinstance(args[0], Var):
            raise _shape_error(f"{op} output z must be Var", origin=atom.origin)
        if not isinstance(args[2], Const):
            raise _shape_error(f"{op} constant operand c must be Const", origin=atom.origin)
        return
    # Forward-compatible op strings are allowed by AST shape; validator strict mode decides allow-list.
    raise _shape_error(f"unsupported builtin op in validator: {op}", origin=atom.origin)


def _validate_term_shape(term: Term, *, origin: Origin | None) -> None:
    if isinstance(term, Var):
        if not isinstance(term.name, str) or not term.name.startswith("$") or len(term.name) < 2:
            raise _shape_error("Var.name must be '$' + non-empty identifier token", origin=term.origin or origin)
        return
    if isinstance(term, Const):
        return
    raise _shape_error(f"unsupported term node in PR-2 validator: {type(term).__name__}", origin=origin)


def _validate_expr_dataflow(expr: WhereExpr, *, bound_outside: set[str], caps: dict[str, Any]) -> _FlowState:
    if isinstance(expr, AndExpr):
        return _validate_and_dataflow(expr, bound_outside=bound_outside, caps=caps)
    if isinstance(expr, OrExpr):
        if not expr.branches:
            raise _flow_error("OrExpr.branches must be non-empty", origin=expr.origin)
        union_free: set[str] = set()
        # PR-2 intentionally does not require branch exit-bound equality.
        for branch in expr.branches:
            branch_state = _validate_and_dataflow(branch, bound_outside=bound_outside, caps=caps)
            union_free |= branch_state.free_used
        return _FlowState(
            bound=set(bound_outside),
            local_bound=set(),
            free_used=union_free,
            bound_outside=set(bound_outside),
        )
    raise _flow_error(f"unsupported WhereExpr node: {type(expr).__name__}")


def _validate_and_dataflow(and_expr: AndExpr, *, bound_outside: set[str], caps: dict[str, Any]) -> _FlowState:
    bound = set(bound_outside)
    local_bound: set[str] = set()
    free_used: set[str] = set()
    for atom in and_expr.atoms:
        if isinstance(atom, NotAtom):
            _validate_not_dataflow(atom, bound_outside=bound, caps=caps)
            continue
        effect = _step_effect(atom, bound=bound)
        missing = effect.requires - bound
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise _flow_error(
                f"atom requires variables bound earlier in branch: {missing_list}",
                origin=getattr(atom, "origin", None),
            )
        free_used |= {var for var in effect.references if var in bound_outside and var not in local_bound}
        new_binds = effect.binds - bound
        bound |= effect.binds
        local_bound |= {var for var in new_binds if var not in bound_outside}
    return _FlowState(bound=bound, local_bound=local_bound, free_used=free_used, bound_outside=set(bound_outside))


def _validate_not_dataflow(not_atom: NotAtom, *, bound_outside: set[str], caps: dict[str, Any]) -> None:
    summary = _validate_expr_dataflow(not_atom.body, bound_outside=set(bound_outside), caps=caps)
    free_vars = summary.free_used
    if not free_vars:
        raise _flow_error(
            "not body must reference at least one outer bound variable",
            origin=not_atom.origin,
        )
    if not free_vars.issubset(bound_outside):
        # Defensive assertion: free vars are defined as outer references.
        extra = ", ".join(sorted(free_vars - bound_outside))
        raise _flow_error(f"not body free vars must be subset of outer bound vars: {extra}", origin=not_atom.origin)


def _step_effect(atom: Atom, *, bound: set[str]) -> _StepEffect:
    if isinstance(atom, PredAtom):
        vars_in_terms = _vars_in_terms(atom.terms)
        return _StepEffect(
            requires=set(),
            binds=set(vars_in_terms),
            references={v for v in vars_in_terms if v in bound},
        )

    if isinstance(atom, RuleRefAtom):
        # PR-2: only shape/capability validation for RuleRef. Binding semantics are deferred.
        return _StepEffect(requires=set(), binds=set(), references=set())

    if isinstance(atom, InAtom):
        req = {atom.var.name}
        return _StepEffect(requires=req, binds=set(), references=set(req))

    if isinstance(atom, BuiltinAtom):
        op = atom.op
        args = atom.args
        if op in {"add", "sub"}:
            z, x, y = args
            req = _vars_in_terms([x, y])
            return _StepEffect(requires=req, binds={_var_name(z)}, references=set(req))
        if op == "neg":
            z, x = args
            req = _vars_in_terms([x])
            return _StepEffect(requires=req, binds={_var_name(z)}, references=set(req))
        if op in {"addc", "mulc"}:
            z, x, _c = args
            req = _vars_in_terms([x])
            return _StepEffect(requires=req, binds={_var_name(z)}, references=set(req))
        return _StepEffect(requires=set(), binds=set(), references=set())

    if isinstance(atom, CmpAtom):
        if atom.op in _CMP_FILTER_OPS or atom.op == "ne":
            req = _term_requires(atom.lhs) | _term_requires(atom.rhs)
            return _StepEffect(requires=req, binds=set(), references=set(req))
        if atom.op != "eq":
            return _StepEffect(requires=set(), binds=set(), references=set())
        lhs_ready = _term_is_resolved(atom.lhs, bound)
        rhs_ready = _term_is_resolved(atom.rhs, bound)
        lhs_vars = _term_requires(atom.lhs)
        rhs_vars = _term_requires(atom.rhs)
        lhs_var = atom.lhs if isinstance(atom.lhs, Var) else None
        rhs_var = atom.rhs if isinstance(atom.rhs, Var) else None

        if lhs_ready and rhs_ready:
            req = lhs_vars | rhs_vars
            return _StepEffect(requires=req, binds=set(), references=set(req))
        if lhs_ready and isinstance(rhs_var, Var) and rhs_var.name not in bound:
            return _StepEffect(requires=lhs_vars, binds={rhs_var.name}, references=set(lhs_vars))
        if rhs_ready and isinstance(lhs_var, Var) and lhs_var.name not in bound:
            return _StepEffect(requires=rhs_vars, binds={lhs_var.name}, references=set(rhs_vars))
        raise _flow_error("eq requires at least one bound/constant side", origin=atom.origin)

    if isinstance(atom, NotAtom):
        return _StepEffect(requires=set(), binds=set(), references=set())

    raise _flow_error(f"unsupported atom node in dataflow: {type(atom).__name__}", origin=getattr(atom, "origin", None))


def _term_requires(term: Term) -> set[str]:
    if isinstance(term, Var):
        return {term.name}
    return set()


def _term_is_resolved(term: Term, bound: set[str]) -> bool:
    if isinstance(term, Const):
        return True
    if isinstance(term, Var):
        return term.name in bound
    return False


def _vars_in_terms(terms: Iterable[Term]) -> set[str]:
    return {term.name for term in terms if isinstance(term, Var)}


def _var_name(term: Term) -> str:
    if not isinstance(term, Var):
        raise _flow_error("builtin output position must be Var", origin=getattr(term, "origin", None))
    return term.name


def _shape_error(message: str, *, origin: Origin | None = None) -> WhereASTValidationError:
    return WhereASTValidationError(message, path=origin.path if origin else None)


def _flow_error(message: str, *, origin: Origin | None = None) -> WhereASTValidationError:
    return WhereASTValidationError(message, path=origin.path if origin else None)
