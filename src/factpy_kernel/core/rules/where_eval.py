from __future__ import annotations

import re
from typing import Any


class WhereValidationError(Exception):
    pass


_DEC_INT_RE = re.compile(r"^-?\d+$")


def evaluate_where(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
) -> list[dict[str, Any]]:
    bodies = _normalize_where(where)

    all_bindings: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()

    for body in bodies:
        body_bindings = _eval_body(view_facts, body)
        for binding in body_bindings:
            key = tuple(sorted(binding.items(), key=lambda item: item[0]))
            if key in seen:
                continue
            seen.add(key)
            all_bindings.append(binding)

    all_bindings.sort(key=lambda env: tuple((k, env[k]) for k in sorted(env.keys())))
    return all_bindings


def _normalize_where(where: Any) -> list[list[tuple[Any, ...]]]:
    if not isinstance(where, list) or not where:
        raise WhereValidationError("where must be non-empty list")

    if all(_is_atom(item) for item in where):
        body = [_validate_atom(item) for item in where]
        if not body:
            raise WhereValidationError("where body must not be empty")
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


def _validate_atom(atom: Any) -> tuple[Any, ...]:
    if not _is_atom(atom):
        raise WhereValidationError("invalid atom structure")

    kind = atom[0]
    if kind == "pred":
        if len(atom) != 3:
            raise WhereValidationError("pred atom must be ('pred', pred_id, [terms...])")
        _, pred_id, terms = atom
        if not isinstance(pred_id, str) or not pred_id:
            raise WhereValidationError("pred_id must be non-empty string")
        if not isinstance(terms, list):
            raise WhereValidationError("pred terms must be list")
        for term in terms:
            if not _is_var(term) and not _is_literal(term):
                raise WhereValidationError("pred terms must be variables or literals")
        return atom

    if kind == "eq":
        if len(atom) != 3:
            raise WhereValidationError("eq atom must be ('eq', lhs, rhs)")
        _, lhs, rhs = atom
        for side in (lhs, rhs):
            if not _is_var(side) and not _is_literal(side):
                raise WhereValidationError("eq sides must be variables or literals")
        return atom

    if kind == "in":
        if len(atom) != 3:
            raise WhereValidationError("in atom must be ('in', var, [values...])")
        _, var, values = atom
        if not _is_var(var):
            raise WhereValidationError("in atom first argument must be variable")
        if not isinstance(values, list):
            raise WhereValidationError("in atom values must be list")
        for value in values:
            if not _is_literal(value):
                raise WhereValidationError("in values must be literals")
        return atom

    if kind in {"gt", "ge", "lt", "le"}:
        if len(atom) != 3:
            raise WhereValidationError(f"{kind} atom must be ('{kind}', lhs, rhs)")
        _, lhs, rhs = atom
        for side in (lhs, rhs):
            if not _is_var(side) and not _is_literal(side):
                raise WhereValidationError(f"{kind} sides must be variables or literals")
        if not _is_var(lhs) and not _is_var(rhs):
            raise WhereValidationError(f"{kind} requires at least one variable side")
        return atom

    if kind == "not":
        if len(atom) != 2:
            raise WhereValidationError("not atom must be ('not', [pred_atoms...])")
        _, not_body = atom
        _normalize_not_body(not_body)
        return atom

    raise WhereValidationError(f"unsupported atom kind: {kind}")


def _eval_body(
    view_facts: dict[str, list[tuple[Any, ...]]],
    body: list[tuple[Any, ...]],
) -> list[dict[str, Any]]:
    envs: list[dict[str, Any]] = [{}]
    for atom in body:
        kind = atom[0]
        if kind == "pred":
            envs = _eval_pred_atom(view_facts, envs, atom)
        elif kind == "eq":
            envs = _eval_eq_atom(envs, atom)
        elif kind == "in":
            envs = _eval_in_atom(envs, atom)
        elif kind in {"gt", "ge", "lt", "le"}:
            envs = _eval_cmp_atom(envs, atom)
        elif kind == "not":
            envs = _eval_not_atom(view_facts, envs, atom)
        else:
            raise WhereValidationError(f"unsupported atom kind: {kind}")
        if not envs:
            return []
    return envs


def _eval_pred_atom(
    view_facts: dict[str, list[tuple[Any, ...]]],
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
) -> list[dict[str, Any]]:
    _, pred_id, terms = atom
    if pred_id not in view_facts:
        raise WhereValidationError(f"unknown predicate in where: {pred_id}")

    facts = view_facts[pred_id]
    out: list[dict[str, Any]] = []

    for env in envs:
        for fact in facts:
            if len(fact) != len(terms):
                raise WhereValidationError(
                    f"arity mismatch for predicate {pred_id}: expected {len(terms)}, got {len(fact)}"
                )
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

        raise WhereValidationError("eq requires at least one bound/constant side")

    return out


def _eval_in_atom(
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
) -> list[dict[str, Any]]:
    _, var, values = atom
    allowed = set(values)

    out: list[dict[str, Any]] = []
    for env in envs:
        if var not in env:
            raise WhereValidationError(f"in variable must be bound before filter: {var}")
        if env[var] in allowed:
            out.append(dict(env))
    return out


def _eval_cmp_atom(
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
) -> list[dict[str, Any]]:
    kind, lhs, rhs = atom
    out: list[dict[str, Any]] = []

    for env in envs:
        lhs_known, lhs_value_raw = _resolve(env, lhs)
        rhs_known, rhs_value_raw = _resolve(env, rhs)

        if not lhs_known and _is_var(lhs):
            raise WhereValidationError(f"{kind} variable must be bound before filter: {lhs}")
        if not rhs_known and _is_var(rhs):
            raise WhereValidationError(f"{kind} variable must be bound before filter: {rhs}")
        if not lhs_known or not rhs_known:
            raise WhereValidationError(f"{kind} requires both sides to be resolvable")

        lhs_value = _coerce_cmp_int(lhs_value_raw, kind)
        rhs_value = _coerce_cmp_int(rhs_value_raw, kind)

        if _cmp_holds(kind, lhs_value, rhs_value):
            out.append(dict(env))

    return out


def _eval_not_atom(
    view_facts: dict[str, list[tuple[Any, ...]]],
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
) -> list[dict[str, Any]]:
    _, not_body = atom
    not_branches = _normalize_not_body(not_body)
    vars_in_not_body = _vars_in_not_bodies(not_branches)

    out: list[dict[str, Any]] = []
    for env in envs:
        if not any(var in env for var in vars_in_not_body):
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
        if not _exists_not_body(view_facts, env, not_branches):
            out.append(dict(env))
    return out


def _exists_not_body(
    view_facts: dict[str, list[tuple[Any, ...]]],
    env: dict[str, Any],
    bodies: list[list[tuple[Any, ...]]],
) -> bool:
    for body in bodies:
        envs: list[dict[str, Any]] = [dict(env)]
        for atom in body:
            kind = atom[0]
            if kind == "pred":
                envs = _eval_pred_atom(view_facts, envs, atom)
            elif kind == "eq":
                envs = _eval_eq_atom(envs, atom)
            elif kind == "in":
                envs = _eval_in_atom(envs, atom)
            elif kind in {"gt", "ge", "lt", "le"}:
                envs = _eval_cmp_atom(envs, atom)
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
        elif kind in {"gt", "ge", "lt", "le"}:
            _, lhs, rhs = atom
            if _is_var(lhs):
                found.add(lhs)
            if _is_var(rhs):
                found.add(rhs)
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

    allowed_not_kinds = {"pred", "eq", "in", "gt", "ge", "lt", "le"}

    def validate_not_atom(not_atom: Any) -> tuple[Any, ...]:
        if not _is_atom(not_atom):
            raise WhereValidationError("not body atoms must be valid atoms")
        not_kind = not_atom[0]
        if not_kind not in allowed_not_kinds:
            raise WhereValidationError("not body supports pred/eq/in/cmp atoms only")
        return _validate_atom(not_atom)

    if all(_is_atom(item) for item in not_body):
        body = [validate_not_atom(item) for item in not_body]
        if not body:
            raise WhereValidationError("not body must not be empty")
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
