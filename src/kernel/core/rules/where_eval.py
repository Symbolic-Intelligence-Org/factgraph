from __future__ import annotations

import os
import re
from typing import Any

from kernel.core.rules.where_ast import WhereASTError, parse_where_ir_to_ast
from kernel.core.rules.where_ast_validate import (
    WhereASTValidationError,
    validate_where_ast,
)


class WhereValidationError(Exception):
    pass


_DEC_INT_RE = re.compile(r"^-?\d+$")
_ARITH_KINDS = {"add", "sub", "neg", "addc", "mulc"}


def evaluate_where(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    disabled_locators: frozenset[tuple[int, int]] = frozenset(),
) -> list[dict[str, Any]]:
    ast_gate_on = _where_ast_gate_enabled()
    if ast_gate_on:
        try:
            ast = parse_where_ir_to_ast(where)
            validate_where_ast(
                ast,
                mode="python",
                capabilities={"allow_ruleref": False},
            )
        except (WhereASTError, WhereASTValidationError) as exc:
            raise _adapt_where_ast_error(exc) from exc

    bodies = _normalize_where(where)
    if disabled_locators:
        bodies = _apply_disabled_locators(bodies, disabled_locators=disabled_locators)

    all_bindings: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()

    for body in bodies:
        body_bindings = _eval_body(view_facts, body, ast_gate_on=ast_gate_on)
        for binding in body_bindings:
            key = tuple(sorted(binding.items(), key=lambda item: item[0]))
            if key in seen:
                continue
            seen.add(key)
            all_bindings.append(binding)

    all_bindings.sort(key=lambda env: tuple((k, env[k]) for k in sorted(env.keys())))
    return all_bindings


def _where_ast_gate_enabled() -> bool:
    raw = os.environ.get("FACTPY_WHERE_AST_VALIDATE", "1")
    return raw not in {"0", "false", "False", "off", "OFF"}


def _adapt_where_ast_error(exc: Exception) -> WhereValidationError:
    adapted = WhereValidationError(str(exc))
    origin_path = getattr(exc, "path", None) or "$.where"
    setattr(adapted, "kind", "where_ast_validate")
    setattr(adapted, "path", origin_path)
    setattr(
        adapted,
        "details",
        {
            "ast_error_code": type(exc).__name__,
            "message": str(exc),
            "origin_source": None,
            "origin_path": getattr(exc, "path", None),
            "op": None,
            "tag": None,
        },
    )
    return adapted


def _normalize_where(where: Any) -> list[list[tuple[Any, ...]]]:
    if not isinstance(where, list) or not where:
        raise WhereValidationError("where must be non-empty list")

    if all(_is_atom(item) for item in where):
        body = [_validate_atom(item) for item in where]
        return [body]

    if all(isinstance(item, list) for item in where):
        bodies: list[list[tuple[Any, ...]]] = []
        for branch in where:
            if not branch:
                raise WhereValidationError("where OR branch must not be empty")
            if not all(_is_atom(atom) for atom in branch):
                raise WhereValidationError("where supports at most 2 list levels")
            bodies.append([_validate_atom(atom) for atom in branch])
        return bodies

    raise WhereValidationError("where must be one-level AND or two-level OR-of-AND")


def _apply_disabled_locators(
    bodies: list[list[tuple[Any, ...]]],
    *,
    disabled_locators: frozenset[tuple[int, int]],
) -> list[list[tuple[Any, ...]]]:
    _validate_disabled_locators(disabled_locators)
    branch_count = len(bodies)
    for branch_index, atom_index in disabled_locators:
        if branch_index >= branch_count:
            raise WhereValidationError("disabled locator branch_index out of range")
        if atom_index >= len(bodies[branch_index]):
            raise WhereValidationError("disabled locator atom_index out of range")
    return [
        [
            atom
            for atom_index, atom in enumerate(body)
            if (branch_index, atom_index) not in disabled_locators
        ]
        for branch_index, body in enumerate(bodies)
    ]


def _validate_disabled_locators(disabled_locators: object) -> None:
    if not isinstance(disabled_locators, frozenset):
        raise WhereValidationError("disabled_locators must be frozenset[tuple[int, int]]")
    for locator in disabled_locators:
        if not isinstance(locator, tuple) or len(locator) != 2:
            raise WhereValidationError("disabled_locators entries must be tuple[int, int]")
        branch_index, atom_index = locator
        if (
            isinstance(branch_index, bool)
            or not isinstance(branch_index, int)
            or branch_index < 0
            or isinstance(atom_index, bool)
            or not isinstance(atom_index, int)
            or atom_index < 0
        ):
            raise WhereValidationError("disabled_locators entries must be non-negative ints")


def _validate_atom(atom: Any) -> tuple[Any, ...]:
    if not _is_atom(atom):
        raise WhereValidationError("invalid atom structure")

    kind = atom[0]
    if kind == "pred":
        if len(atom) != 3:
            raise WhereValidationError("pred atom must be ('pred', pred_id, [terms...])")
        _, pred_id, terms = atom
        if not isinstance(terms, list):
            raise WhereValidationError("pred terms must be list")
        return atom

    if kind == "eq":
        if len(atom) != 3:
            raise WhereValidationError("eq atom must be ('eq', lhs, rhs)")
        return atom

    if kind == "in":
        if len(atom) != 3:
            raise WhereValidationError("in atom must be ('in', var, [values...])")
        _, var, values = atom
        if not _is_var(var):
            raise WhereValidationError("in atom first argument must be variable")
        if not isinstance(values, list):
            raise WhereValidationError("in atom values must be list")
        return atom

    if kind == "ne":
        if len(atom) != 3:
            raise WhereValidationError("ne atom must be ('ne', lhs, rhs)")
        return atom

    if kind in {"gt", "ge", "lt", "le"}:
        if len(atom) != 3:
            raise WhereValidationError(f"{kind} atom must be ('{kind}', lhs, rhs)")
        _, lhs, rhs = atom
        if not _is_var(lhs) and not _is_var(rhs):
            raise WhereValidationError(f"{kind} requires at least one variable side")
        return atom

    if kind in _ARITH_KINDS:
        return _validate_arith_atom(atom)

    if kind == "not":
        if len(atom) != 2:
            raise WhereValidationError("not atom must be ('not', [pred_atoms...])")
        _, not_body = atom
        if not isinstance(not_body, list):
            raise WhereValidationError("not atom must be ('not', [pred_atoms...])")
        return atom

    raise WhereValidationError(f"unsupported atom kind: {kind}")


def _eval_body(
    view_facts: dict[str, list[tuple[Any, ...]]],
    body: list[tuple[Any, ...]],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    planned_body = _plan_body_atoms(body, ast_gate_on=ast_gate_on)
    pred_lookup_cache: dict[str, dict[tuple[int, ...], dict[tuple[Any, ...], list[tuple[Any, ...]]]]] = {}
    envs: list[dict[str, Any]] = [{}]
    for atom in planned_body:
        kind = atom[0]
        if kind == "pred":
            envs = _eval_pred_atom(
                view_facts,
                envs,
                atom,
                pred_lookup_cache=pred_lookup_cache,
            )
        elif kind == "eq":
            envs = _eval_eq_atom(envs, atom, ast_gate_on=ast_gate_on)
        elif kind == "in":
            envs = _eval_in_atom(envs, atom, ast_gate_on=ast_gate_on)
        elif kind == "ne":
            envs = _eval_ne_atom(envs, atom, ast_gate_on=ast_gate_on)
        elif kind in {"gt", "ge", "lt", "le"}:
            envs = _eval_cmp_atom(envs, atom, ast_gate_on=ast_gate_on)
        elif kind in _ARITH_KINDS:
            envs = _eval_arith_atom(envs, atom, ast_gate_on=ast_gate_on)
        elif kind == "not":
            envs = _eval_not_atom(view_facts, envs, atom, ast_gate_on=ast_gate_on)
        else:
            raise WhereValidationError(f"unsupported atom kind: {kind}")
        if not envs:
            return []
    return envs


def _eval_pred_atom(
    view_facts: dict[str, list[tuple[Any, ...]]],
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    pred_lookup_cache: dict[str, dict[tuple[int, ...], dict[tuple[Any, ...], list[tuple[Any, ...]]]]],
) -> list[dict[str, Any]]:
    _, pred_id, terms = atom
    if pred_id not in view_facts:
        raise WhereValidationError(f"unknown predicate in where: {pred_id}")

    facts = view_facts[pred_id]
    expected_arity = len(terms)
    for fact in facts:
        if len(fact) != expected_arity:
            raise WhereValidationError(
                f"arity mismatch for predicate {pred_id}: expected {expected_arity}, got {len(fact)}"
            )
    out: list[dict[str, Any]] = []

    # NOTE: Current join optimization only guarantees that primary_key shared-variable
    # joins produced by attr_eq lowering use lookup paths in python evaluator.
    # Non-primary cross-coordinate equality is rejected at compile time upstream.
    for env in envs:
        candidates = _pred_candidates_for_env(
            facts=facts,
            terms=terms,
            env=env,
            cache_for_pred=pred_lookup_cache.setdefault(pred_id, {}),
        )
        for fact in candidates:
            next_env = dict(env)
            ok = True
            for term, value in zip(terms, fact):
                if _is_var(term):
                    bound = next_env.get(term)
                    if bound is None:
                        next_env[term] = value
                    elif bound != value:
                        ok = False
                        break
                else:
                    if term != value:
                        ok = False
                        break
            if ok:
                out.append(next_env)

    return out


def _eval_eq_atom(
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    _, lhs, rhs = atom
    out: list[dict[str, Any]] = []

    for env in envs:
        lhs_known, lhs_value = _resolve(env, lhs)
        rhs_known, rhs_value = _resolve(env, rhs)

        if lhs_known and rhs_known:
            if lhs_value == rhs_value:
                out.append(dict(env))
            continue

        if lhs_known and _is_var(rhs):
            next_env = dict(env)
            next_env[rhs] = lhs_value
            out.append(next_env)
            continue

        if rhs_known and _is_var(lhs):
            next_env = dict(env)
            next_env[lhs] = rhs_value
            out.append(next_env)
            continue

        if not ast_gate_on:
            raise WhereValidationError("eq requires at least one bound/constant side")

    return out


def _eval_in_atom(
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    _, var, values = atom
    allowed = set(values)

    out: list[dict[str, Any]] = []
    for env in envs:
        if var not in env:
            if not ast_gate_on:
                raise WhereValidationError(f"in variable must be bound before filter: {var}")
            continue
        if env[var] in allowed:
            out.append(dict(env))
    return out


def _eval_ne_atom(
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    _, lhs, rhs = atom
    out: list[dict[str, Any]] = []

    for env in envs:
        lhs_known, lhs_value = _resolve(env, lhs)
        rhs_known, rhs_value = _resolve(env, rhs)

        if not lhs_known and _is_var(lhs):
            if not ast_gate_on:
                raise WhereValidationError(f"ne variable must be bound before filter: {lhs}")
            continue
        if not rhs_known and _is_var(rhs):
            if not ast_gate_on:
                raise WhereValidationError(f"ne variable must be bound before filter: {rhs}")
            continue
        if not lhs_known or not rhs_known:
            if not ast_gate_on:
                raise WhereValidationError("ne requires both sides to be resolvable")
            continue

        if lhs_value != rhs_value:
            out.append(dict(env))

    return out


def _eval_cmp_atom(
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    kind, lhs, rhs = atom
    out: list[dict[str, Any]] = []

    for env in envs:
        lhs_known, lhs_value_raw = _resolve(env, lhs)
        rhs_known, rhs_value_raw = _resolve(env, rhs)

        if not lhs_known and _is_var(lhs):
            if not ast_gate_on:
                raise WhereValidationError(f"{kind} variable must be bound before filter: {lhs}")
            continue
        if not rhs_known and _is_var(rhs):
            if not ast_gate_on:
                raise WhereValidationError(f"{kind} variable must be bound before filter: {rhs}")
            continue
        if not lhs_known or not rhs_known:
            if not ast_gate_on:
                raise WhereValidationError(f"{kind} requires both sides to be resolvable")
            continue

        lhs_value = _coerce_cmp_int(lhs_value_raw, kind)
        rhs_value = _coerce_cmp_int(rhs_value_raw, kind)

        if _cmp_holds(kind, lhs_value, rhs_value):
            out.append(dict(env))

    return out


def _eval_not_atom(
    view_facts: dict[str, list[tuple[Any, ...]]],
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    _, not_body = atom
    not_branches = _normalize_not_body(not_body)
    vars_in_not_body = _vars_in_not_bodies(not_branches)

    out: list[dict[str, Any]] = []
    for env in envs:
        if not any(var in env for var in vars_in_not_body):
            if not ast_gate_on:
                raise WhereValidationError(
                    "not body must reference at least one outer bound variable"
                )
        correlated_vars = sorted(var for var in vars_in_not_body if var in env)
        if len(not_branches) > 1 and correlated_vars:
            for branch in not_branches:
                branch_vars = set(_vars_in_atoms(branch))
                missing = [var for var in correlated_vars if var not in branch_vars]
                if missing:
                    raise WhereValidationError(
                        "not OR branch must reference all correlated variables; missing: "
                        + ", ".join(missing)
                    )
        if not _exists_not_body(view_facts, env, not_branches, ast_gate_on=ast_gate_on):
            out.append(dict(env))
    return out


def _exists_not_body(
    view_facts: dict[str, list[tuple[Any, ...]]],
    env: dict[str, Any],
    bodies: list[list[tuple[Any, ...]]],
    *,
    ast_gate_on: bool,
) -> bool:
    for body in bodies:
        planned_body = _plan_body_atoms(body, ast_gate_on=ast_gate_on)
        pred_lookup_cache: dict[str, dict[tuple[int, ...], dict[tuple[Any, ...], list[tuple[Any, ...]]]]] = {}
        envs: list[dict[str, Any]] = [dict(env)]
        for atom in planned_body:
            kind = atom[0]
            if kind == "pred":
                envs = _eval_pred_atom(
                    view_facts,
                    envs,
                    atom,
                    pred_lookup_cache=pred_lookup_cache,
                )
            elif kind == "eq":
                envs = _eval_eq_atom(envs, atom, ast_gate_on=ast_gate_on)
            elif kind == "in":
                envs = _eval_in_atom(envs, atom, ast_gate_on=ast_gate_on)
            elif kind == "ne":
                envs = _eval_ne_atom(envs, atom, ast_gate_on=ast_gate_on)
            elif kind in {"gt", "ge", "lt", "le"}:
                envs = _eval_cmp_atom(envs, atom, ast_gate_on=ast_gate_on)
            elif kind in _ARITH_KINDS:
                envs = _eval_arith_atom(envs, atom, ast_gate_on=ast_gate_on)
            else:
                raise WhereValidationError(f"unsupported atom kind in not body: {kind}")
            if not envs:
                break
        if envs:
            return True
    return False


def _coerce_cmp_int(value: Any, kind: str) -> int:
    if isinstance(value, bool):
        raise WhereValidationError(f"{kind} supports only int/time (bool is not allowed)")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if not _DEC_INT_RE.fullmatch(value):
            raise WhereValidationError(f"{kind} supports only int/time decimal values")
        return int(value)
    raise WhereValidationError(f"{kind} supports only int/time values")


def _coerce_arith_int(value: Any, kind: str) -> int:
    if isinstance(value, bool):
        raise WhereValidationError(f"{kind} supports only integer operands (bool is not allowed)")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if not _DEC_INT_RE.fullmatch(value):
            raise WhereValidationError(f"{kind} supports only decimal integer operands")
        return int(value)
    raise WhereValidationError(f"{kind} supports only integer operands")


def _cmp_holds(kind: str, lhs: int, rhs: int) -> bool:
    if kind == "gt":
        return lhs > rhs
    if kind == "ge":
        return lhs >= rhs
    if kind == "lt":
        return lhs < rhs
    if kind == "le":
        return lhs <= rhs
    raise WhereValidationError(f"unsupported comparison kind: {kind}")


def _resolve(env: dict[str, Any], term: Any) -> tuple[bool, Any]:
    if _is_var(term):
        if term in env:
            return True, env[term]
        return False, None
    return True, term


def _validate_arith_atom(atom: tuple[Any, ...]) -> tuple[Any, ...]:
    kind = atom[0]
    if kind in {"add", "sub"}:
        if len(atom) != 4:
            raise WhereValidationError(f"{kind} atom must be ('{kind}', z, x, y)")
        _, z, x, y = atom
        if not _is_var(z):
            raise WhereValidationError(f"{kind} output must be variable")
        for side in (x, y):
            if not _is_var(side) and not _is_literal(side):
                raise WhereValidationError(f"{kind} inputs must be variables or literals")
        return atom
    if kind == "neg":
        if len(atom) != 3:
            raise WhereValidationError("neg atom must be ('neg', z, x)")
        _, z, x = atom
        if not _is_var(z):
            raise WhereValidationError("neg output must be variable")
        if not _is_var(x) and not _is_literal(x):
            raise WhereValidationError("neg input must be variable or literal")
        return atom
    if kind in {"addc", "mulc"}:
        if len(atom) != 4:
            raise WhereValidationError(f"{kind} atom must be ('{kind}', z, x, c)")
        _, z, x, c = atom
        if not _is_var(z):
            raise WhereValidationError(f"{kind} output must be variable")
        if not _is_var(x) and not _is_literal(x):
            raise WhereValidationError(f"{kind} x input must be variable or literal")
        if _is_var(c) or not _is_literal(c):
            raise WhereValidationError(f"{kind} constant operand must be literal")
        _coerce_arith_int(c, kind)
        return atom
    raise WhereValidationError(f"unsupported arithmetic atom kind: {kind}")


def _eval_arith_atom(
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    kind = atom[0]
    out: list[dict[str, Any]] = []
    for env in envs:
        if kind == "add":
            _, z, x, y = atom
            xv = _require_resolved_arith(env, x, kind, ast_gate_on=ast_gate_on)
            if xv is None:
                continue
            yv = _require_resolved_arith(env, y, kind, ast_gate_on=ast_gate_on)
            if yv is None:
                continue
            result = xv + yv
        elif kind == "sub":
            _, z, x, y = atom
            xv = _require_resolved_arith(env, x, kind, ast_gate_on=ast_gate_on)
            if xv is None:
                continue
            yv = _require_resolved_arith(env, y, kind, ast_gate_on=ast_gate_on)
            if yv is None:
                continue
            result = xv - yv
        elif kind == "neg":
            _, z, x = atom
            xv = _require_resolved_arith(env, x, kind, ast_gate_on=ast_gate_on)
            if xv is None:
                continue
            result = -xv
        elif kind == "addc":
            _, z, x, c = atom
            xv = _require_resolved_arith(env, x, kind, ast_gate_on=ast_gate_on)
            if xv is None:
                continue
            cv = _coerce_arith_int(c, kind)
            result = xv + cv
        elif kind == "mulc":
            _, z, x, c = atom
            xv = _require_resolved_arith(env, x, kind, ast_gate_on=ast_gate_on)
            if xv is None:
                continue
            cv = _coerce_arith_int(c, kind)
            result = xv * cv
        else:
            raise WhereValidationError(f"unsupported arithmetic atom kind: {kind}")

        next_env = _bind_or_check_result(env, z, result, kind)
        if next_env is not None:
            out.append(next_env)
    return out


def _require_resolved_arith(
    env: dict[str, Any],
    term: Any,
    kind: str,
    *,
    ast_gate_on: bool,
) -> int | None:
    known, value = _resolve(env, term)
    if not known:
        if ast_gate_on:
            return None
        if _is_var(term):
            raise WhereValidationError(f"{kind} input variable must be bound before use: {term}")
        raise WhereValidationError(f"{kind} input must be resolvable")
    return _coerce_arith_int(value, kind)


def _bind_or_check_result(env: dict[str, Any], z: str, result: int, kind: str) -> dict[str, Any] | None:
    if z in env:
        existing = _coerce_arith_int(env[z], kind)
        if existing != result:
            return None
        return dict(env)
    next_env = dict(env)
    next_env[z] = result
    return next_env


def _plan_body_atoms(
    body: list[tuple[Any, ...]],
    *,
    ast_gate_on: bool,
) -> list[tuple[Any, ...]]:
    if len(body) <= 1:
        return list(body)
    # Boundary for phase-3 execution optimization:
    # only enable atom reordering when system primary-key temporaries are present.
    # This keeps generic where evaluation semantics/order stable for non-pk bodies.
    if not _body_has_system_pk_signal(body):
        return list(body)
    remaining = list(body)
    planned: list[tuple[Any, ...]] = []
    bound_vars: set[str] = set()

    while remaining:
        selected_idx: int | None = None
        selected_score: tuple[int, int, int, int, int] | None = None
        for idx, atom in enumerate(remaining):
            if not _atom_ready_for_eval(atom, bound_vars=bound_vars, ast_gate_on=ast_gate_on):
                continue
            score = _atom_eval_score(atom, bound_vars=bound_vars)
            if selected_score is None or score > selected_score:
                selected_idx = idx
                selected_score = score
        if selected_idx is None:
            selected_idx = 0
        atom = remaining.pop(selected_idx)
        planned.append(atom)
        _update_bound_vars_for_plan(bound_vars, atom)
    return planned


def _atom_ready_for_eval(
    atom: tuple[Any, ...],
    *,
    bound_vars: set[str],
    ast_gate_on: bool,
) -> bool:
    kind = atom[0]
    if kind == "pred":
        return True
    if kind == "eq":
        _, lhs, rhs = atom
        return (not ast_gate_on) or _term_known_for_plan(lhs, bound_vars) or _term_known_for_plan(rhs, bound_vars)
    if kind == "in":
        _, var, _ = atom
        return (not ast_gate_on) or (var in bound_vars)
    if kind in {"ne", "gt", "ge", "lt", "le"}:
        _, lhs, rhs = atom
        return (not ast_gate_on) or (
            _term_known_for_plan(lhs, bound_vars) and _term_known_for_plan(rhs, bound_vars)
        )
    if kind in {"add", "sub"}:
        _, _, x, y = atom
        return (not ast_gate_on) or (
            _term_known_for_plan(x, bound_vars) and _term_known_for_plan(y, bound_vars)
        )
    if kind == "neg":
        _, _, x = atom
        return (not ast_gate_on) or _term_known_for_plan(x, bound_vars)
    if kind in {"addc", "mulc"}:
        _, _, x, _ = atom
        return (not ast_gate_on) or _term_known_for_plan(x, bound_vars)
    if kind == "not":
        _, not_body = atom
        vars_in_not_body = _vars_in_not_bodies(_normalize_not_body(not_body))
        return (not ast_gate_on) or any(var in bound_vars for var in vars_in_not_body)
    return True


def _atom_eval_score(
    atom: tuple[Any, ...],
    *,
    bound_vars: set[str],
) -> tuple[int, int, int, int, int]:
    kind = atom[0]
    if kind == "pred":
        _, pred_id, terms = atom
        known_terms = sum(1 for term in terms if _term_known_for_plan(term, bound_vars))
        bound_var_terms = sum(1 for term in terms if _is_var(term) and term in bound_vars)
        unbound_var_terms = sum(1 for term in terms if _is_var(term) and term not in bound_vars)
        is_exists = isinstance(pred_id, str) and pred_id.endswith(":exists")
        return (50, known_terms, bound_var_terms, -unbound_var_terms, 0 if not is_exists else -1)
    if kind == "eq":
        _, lhs, rhs = atom
        can_bind = 0
        if _is_var(lhs) and lhs not in bound_vars and _term_known_for_plan(rhs, bound_vars):
            can_bind += 1
        if _is_var(rhs) and rhs not in bound_vars and _term_known_for_plan(lhs, bound_vars):
            can_bind += 1
        known_terms = int(_term_known_for_plan(lhs, bound_vars)) + int(_term_known_for_plan(rhs, bound_vars))
        return (40, can_bind, known_terms, 0, 0)
    if kind in _ARITH_KINDS:
        output = atom[1] if len(atom) >= 2 else None
        can_bind_output = int(_is_var(output) and output not in bound_vars)
        known_inputs = sum(1 for term in atom[2:] if _term_known_for_plan(term, bound_vars))
        return (30, can_bind_output, known_inputs, 0, 0)
    if kind in {"in", "ne", "gt", "ge", "lt", "le"}:
        lhs = atom[1] if len(atom) >= 2 else None
        rhs = atom[2] if len(atom) >= 3 else None
        known_terms = int(_term_known_for_plan(lhs, bound_vars)) + int(_term_known_for_plan(rhs, bound_vars))
        return (20, known_terms, 0, 0, 0)
    if kind == "not":
        vars_in_not_body = _vars_in_not_bodies(_normalize_not_body(atom[1]))
        correlated = sum(1 for var in vars_in_not_body if var in bound_vars)
        return (10, correlated, 0, 0, 0)
    return (0, 0, 0, 0, 0)


def _update_bound_vars_for_plan(bound_vars: set[str], atom: tuple[Any, ...]) -> None:
    kind = atom[0]
    if kind == "pred":
        _, _, terms = atom
        for term in terms:
            if _is_var(term):
                bound_vars.add(term)
        return
    if kind == "eq":
        _, lhs, rhs = atom
        lhs_known = _term_known_for_plan(lhs, bound_vars)
        rhs_known = _term_known_for_plan(rhs, bound_vars)
        if _is_var(lhs) and rhs_known:
            bound_vars.add(lhs)
        if _is_var(rhs) and lhs_known:
            bound_vars.add(rhs)
        return
    if kind in {"add", "sub", "neg", "addc", "mulc"}:
        output = atom[1]
        if _is_var(output):
            bound_vars.add(output)


def _term_known_for_plan(term: Any, bound_vars: set[str]) -> bool:
    if _is_var(term):
        return term in bound_vars
    return True


def _body_has_system_pk_signal(body: list[tuple[Any, ...]]) -> bool:
    for atom in body:
        if not isinstance(atom, tuple) or len(atom) < 1:
            continue
        if atom[0] != "pred" or len(atom) != 3:
            continue
        terms = atom[2]
        if not isinstance(terms, list):
            continue
        for term in terms:
            if _is_system_pk_var(term):
                return True
    return False


def _is_system_pk_var(term: Any) -> bool:
    return isinstance(term, str) and term.startswith("$__pk_")


def _pred_candidates_for_env(
    *,
    facts: list[tuple[Any, ...]],
    terms: list[Any],
    env: dict[str, Any],
    cache_for_pred: dict[tuple[int, ...], dict[tuple[Any, ...], list[tuple[Any, ...]]]],
) -> list[tuple[Any, ...]]:
    positions: list[int] = []
    key_values: list[Any] = []
    for idx, term in enumerate(terms):
        if _is_var(term):
            if term not in env:
                continue
            positions.append(idx)
            key_values.append(env[term])
            continue
        positions.append(idx)
        key_values.append(term)

    if not positions:
        return facts

    key_positions = tuple(positions)
    index = cache_for_pred.get(key_positions)
    if index is None:
        index = {}
        for fact in facts:
            key = tuple(fact[pos] for pos in key_positions)
            index.setdefault(key, []).append(fact)
        cache_for_pred[key_positions] = index
    return index.get(tuple(key_values), [])


def _is_var(value: Any) -> bool:
    return isinstance(value, str) and len(value) > 1 and value.startswith("$")


def _is_literal(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, str) and not value.startswith("$"):
        return True
    return False


def _is_atom(value: Any) -> bool:
    return isinstance(value, tuple) and len(value) >= 1 and isinstance(value[0], str)


def _vars_in_atoms(body: list[tuple[Any, ...]]) -> list[str]:
    found: set[str] = set()
    for atom in body:
        kind = atom[0]
        if kind == "pred":
            _, _, terms = atom
            for term in terms:
                if _is_var(term):
                    found.add(term)
        elif kind == "eq":
            _, lhs, rhs = atom
            if _is_var(lhs):
                found.add(lhs)
            if _is_var(rhs):
                found.add(rhs)
        elif kind == "in":
            _, var, _ = atom
            if _is_var(var):
                found.add(var)
        elif kind in {"gt", "ge", "lt", "le", "ne"}:
            _, lhs, rhs = atom
            if _is_var(lhs):
                found.add(lhs)
            if _is_var(rhs):
                found.add(rhs)
        elif kind in _ARITH_KINDS:
            for term in atom[1:]:
                if _is_var(term):
                    found.add(term)
    return sorted(found)


def _vars_in_not_bodies(bodies: list[list[tuple[Any, ...]]]) -> list[str]:
    found: set[str] = set()
    for body in bodies:
        for var in _vars_in_atoms(body):
            found.add(var)
    return sorted(found)


def _normalize_not_body(not_body: Any) -> list[list[tuple[Any, ...]]]:
    if not isinstance(not_body, list) or not not_body:
        raise WhereValidationError("not body must be non-empty list")

    allowed_not_kinds = {"pred", "eq", "in", "gt", "ge", "lt", "le", "ne", *_ARITH_KINDS}

    def validate_not_atom(not_atom: Any) -> tuple[Any, ...]:
        if not _is_atom(not_atom):
            raise WhereValidationError("not body atoms must be valid atoms")
        not_kind = not_atom[0]
        if not_kind not in allowed_not_kinds:
            raise WhereValidationError("not body supports pred/eq/in/cmp/arithmetic atoms only")
        return _validate_atom(not_atom)

    if all(_is_atom(item) for item in not_body):
        body = [validate_not_atom(item) for item in not_body]
        return [body]

    if all(isinstance(item, list) for item in not_body):
        bodies: list[list[tuple[Any, ...]]] = []
        for branch in not_body:
            if not branch:
                raise WhereValidationError("not OR branch must not be empty")
            if not all(_is_atom(atom) for atom in branch):
                raise WhereValidationError("not body supports at most 2 list levels")
            bodies.append([validate_not_atom(atom) for atom in branch])
        return bodies

    raise WhereValidationError("not body must be AND list or OR-of-AND")
