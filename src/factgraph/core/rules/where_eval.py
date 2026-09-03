from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from factgraph.core.rules.where_ast import WhereASTError, parse_where_ir_to_ast
from factgraph.core.rules.where_ast_validate import (
    WhereASTValidationError,
    validate_where_ast,
)


class WhereValidationError(Exception):
    pass


@dataclass(frozen=True)
class WhereLiteralReplacement:
    case_index: int
    condition_index: int
    literal_path: tuple[str, int | None]
    old_literal: Any
    new_literal: Any


@dataclass(frozen=True)
class WhereAddedCondition:
    case_index: int
    atom: tuple[Any, ...]

    def __hash__(self) -> int:
        return hash((self.case_index, repr(self.atom)))


_DEC_INT_RE = re.compile(r"^-?\d+$")
_ARITH_KINDS = {"add", "sub", "neg", "addc", "mulc"}
_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}


class _AggregateNoValueSentinel:
    def __repr__(self) -> str:
        return "AggregateNoValue"


AggregateNoValue = _AggregateNoValueSentinel()


def evaluate_where(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    disabled_locators: frozenset[tuple[int, int]] = frozenset(),
    literal_replacements: frozenset[WhereLiteralReplacement] = frozenset(),
    added_conditions: frozenset[WhereAddedCondition] = frozenset(),
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
    if literal_replacements:
        bodies = _apply_literal_replacements(
            bodies,
            literal_replacements=literal_replacements,
        )
    if added_conditions:
        bodies = _apply_added_conditions(
            bodies,
            added_conditions=added_conditions,
        )
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
    adapted.kind = "where_ast_validate"
    adapted.path = origin_path
    adapted.details = {
        "ast_error_code": type(exc).__name__,
        "message": str(exc),
        "origin_source": None,
        "origin_path": getattr(exc, "path", None),
        "op": None,
        "tag": None,
    }
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
    for case_index, condition_index in disabled_locators:
        if case_index >= branch_count:
            raise WhereValidationError("disabled locator case_index out of range")
        if condition_index >= len(bodies[case_index]):
            raise WhereValidationError("disabled locator condition_index out of range")
    return [
        [
            atom
            for condition_index, atom in enumerate(body)
            if (case_index, condition_index) not in disabled_locators
        ]
        for case_index, body in enumerate(bodies)
    ]


def _apply_literal_replacements(
    bodies: list[list[tuple[Any, ...]]],
    *,
    literal_replacements: frozenset[WhereLiteralReplacement],
) -> list[list[tuple[Any, ...]]]:
    _validate_literal_replacements(literal_replacements)
    branch_count = len(bodies)
    replacement_by_target: dict[tuple[int, int, tuple[str, int | None]], WhereLiteralReplacement] = {}
    for replacement in literal_replacements:
        if replacement.case_index >= branch_count:
            raise WhereValidationError("literal replacement case_index out of range")
        if replacement.condition_index >= len(bodies[replacement.case_index]):
            raise WhereValidationError("literal replacement condition_index out of range")
        key = (
            replacement.case_index,
            replacement.condition_index,
            replacement.literal_path,
        )
        if key in replacement_by_target:
            raise WhereValidationError("duplicate literal replacement target")
        replacement_by_target[key] = replacement

    out: list[list[tuple[Any, ...]]] = []
    for case_index, body in enumerate(bodies):
        next_body: list[tuple[Any, ...]] = []
        for condition_index, atom in enumerate(body):
            replacements = [
                replacement
                for (r_branch, r_atom, _), replacement in replacement_by_target.items()
                if r_branch == case_index and r_atom == condition_index
            ]
            next_atom = atom
            for replacement in replacements:
                next_atom = _apply_literal_replacement_to_atom(next_atom, replacement)
            next_body.append(next_atom)
        out.append(next_body)
    return out


def _apply_added_conditions(
    bodies: list[list[tuple[Any, ...]]],
    *,
    added_conditions: frozenset[WhereAddedCondition],
) -> list[list[tuple[Any, ...]]]:
    _validate_added_conditions(added_conditions)
    branch_count = len(bodies)
    additions_by_branch: dict[int, list[tuple[Any, ...]]] = {}
    for condition in added_conditions:
        if condition.case_index >= branch_count:
            raise WhereValidationError("added condition case_index out of range")
        additions_by_branch.setdefault(condition.case_index, []).append(
            _validate_atom(condition.atom)
        )
    return [
        [
            *body,
            *sorted(additions_by_branch.get(case_index, ()), key=repr),
        ]
        for case_index, body in enumerate(bodies)
    ]


def _validate_disabled_locators(disabled_locators: object) -> None:
    if not isinstance(disabled_locators, frozenset):
        raise WhereValidationError("disabled_locators must be frozenset[tuple[int, int]]")
    for locator in disabled_locators:
        if not isinstance(locator, tuple) or len(locator) != 2:
            raise WhereValidationError("disabled_locators entries must be tuple[int, int]")
        case_index, condition_index = locator
        if (
            isinstance(case_index, bool)
            or not isinstance(case_index, int)
            or case_index < 0
            or isinstance(condition_index, bool)
            or not isinstance(condition_index, int)
            or condition_index < 0
        ):
            raise WhereValidationError("disabled_locators entries must be non-negative ints")


def _validate_literal_replacements(literal_replacements: object) -> None:
    if not isinstance(literal_replacements, frozenset):
        raise WhereValidationError(
            "literal_replacements must be frozenset[WhereLiteralReplacement]"
        )
    for replacement in literal_replacements:
        if not isinstance(replacement, WhereLiteralReplacement):
            raise WhereValidationError(
                "literal_replacements entries must be WhereLiteralReplacement"
            )
        if (
            isinstance(replacement.case_index, bool)
            or not isinstance(replacement.case_index, int)
            or replacement.case_index < 0
            or isinstance(replacement.condition_index, bool)
            or not isinstance(replacement.condition_index, int)
            or replacement.condition_index < 0
        ):
            raise WhereValidationError(
                "literal replacement coordinates must be non-negative ints"
            )
        if not _is_literal_path(replacement.literal_path):
            raise WhereValidationError("literal replacement path is invalid")
        if not _is_literal(replacement.old_literal):
            raise WhereValidationError("literal replacement old_literal must be literal")
        if not _is_literal(replacement.new_literal):
            raise WhereValidationError("literal replacement new_literal must be literal")


def _validate_added_conditions(added_conditions: object) -> None:
    if not isinstance(added_conditions, frozenset):
        raise WhereValidationError(
            "added_conditions must be frozenset[WhereAddedCondition]"
        )
    for condition in added_conditions:
        if not isinstance(condition, WhereAddedCondition):
            raise WhereValidationError(
                "added_conditions entries must be WhereAddedCondition"
            )
        if (
            isinstance(condition.case_index, bool)
            or not isinstance(condition.case_index, int)
            or condition.case_index < 0
        ):
            raise WhereValidationError(
                "added condition case_index must be non-negative int"
            )
        if not _is_atom(condition.atom):
            raise WhereValidationError("added condition atom must be atom tuple")


def _is_literal_path(value: object) -> bool:
    if not isinstance(value, tuple) or len(value) != 2:
        return False
    kind, index = value
    if kind in {"lhs", "rhs", "const_operand"}:
        return index is None
    if kind in {"pred_term", "in_value"}:
        return isinstance(index, int) and not isinstance(index, bool) and index >= 0
    return False


def _apply_literal_replacement_to_atom(
    atom: tuple[Any, ...],
    replacement: WhereLiteralReplacement,
) -> tuple[Any, ...]:
    kind, index = replacement.literal_path
    atom_kind = atom[0]
    if kind == "pred_term":
        if atom_kind != "pred":
            raise WhereValidationError("literal replacement path incompatible with atom kind")
        if index is None:
            raise WhereValidationError("pred_term literal replacement requires index")
        _, pred_id, terms = atom
        if index >= len(terms):
            raise WhereValidationError("literal replacement term index out of range")
        next_terms = list(terms)
        next_terms[index] = _replace_literal_leaf(next_terms[index], replacement)
        return ("pred", pred_id, next_terms)
    if kind in {"lhs", "rhs"}:
        if atom_kind not in {"eq", "ne", "gt", "ge", "lt", "le"}:
            raise WhereValidationError("literal replacement path incompatible with atom kind")
        side_index = 1 if kind == "lhs" else 2
        next_atom = list(atom)
        next_atom[side_index] = _replace_literal_leaf(next_atom[side_index], replacement)
        return tuple(next_atom)
    if kind == "in_value":
        if atom_kind != "in":
            raise WhereValidationError("literal replacement path incompatible with atom kind")
        if index is None:
            raise WhereValidationError("in_value literal replacement requires index")
        _, var, values = atom
        if index >= len(values):
            raise WhereValidationError("literal replacement in value index out of range")
        next_values = list(values)
        next_values[index] = _replace_literal_leaf(next_values[index], replacement)
        return ("in", var, next_values)
    if kind == "const_operand":
        if atom_kind not in {"addc", "mulc"}:
            raise WhereValidationError("literal replacement path incompatible with atom kind")
        next_atom = list(atom)
        next_atom[3] = _replace_literal_leaf(next_atom[3], replacement)
        return tuple(next_atom)
    raise WhereValidationError("literal replacement path is invalid")


def _replace_literal_leaf(value: Any, replacement: WhereLiteralReplacement) -> Any:
    if not _is_literal(value):
        raise WhereValidationError("literal replacement target leaf must be literal")
    if value != replacement.old_literal:
        raise WhereValidationError("literal replacement old_literal does not match target")
    if not _is_literal(replacement.new_literal):
        raise WhereValidationError("literal replacement new_literal must be literal")
    return replacement.new_literal


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
        if any(_is_aggregate_term(term) for term in terms):
            raise WhereValidationError("aggregate terms are not allowed in pred terms")
        return atom

    if kind == "eq":
        if len(atom) != 3:
            raise WhereValidationError("eq atom must be ('eq', lhs, rhs)")
        _, lhs, rhs = atom
        _validate_eval_term(lhs, allow_aggregate=True)
        _validate_eval_term(rhs, allow_aggregate=True)
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
        _, lhs, rhs = atom
        _validate_eval_term(lhs, allow_aggregate=True)
        _validate_eval_term(rhs, allow_aggregate=True)
        return atom

    if kind in {"gt", "ge", "lt", "le"}:
        if len(atom) != 3:
            raise WhereValidationError(f"{kind} atom must be ('{kind}', lhs, rhs)")
        _, lhs, rhs = atom
        _validate_eval_term(lhs, allow_aggregate=True)
        _validate_eval_term(rhs, allow_aggregate=True)
        if not _is_var(lhs) and not _is_var(rhs) and not _is_aggregate_term(lhs) and not _is_aggregate_term(rhs):
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
    initial_envs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    initial_bound_vars: set[str] = set()
    if initial_envs is not None:
        for env in initial_envs:
            initial_bound_vars.update(env)
    planned_body = _plan_body_atoms(
        body,
        ast_gate_on=ast_gate_on,
        initial_bound_vars=initial_bound_vars,
    )
    pred_lookup_cache: dict[str, dict[tuple[int, ...], dict[tuple[Any, ...], list[tuple[Any, ...]]]]] = {}
    envs: list[dict[str, Any]] = [{}] if initial_envs is None else [dict(env) for env in initial_envs]
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
            envs = _eval_eq_atom(view_facts, envs, atom, ast_gate_on=ast_gate_on)
        elif kind == "in":
            envs = _eval_in_atom(envs, atom, ast_gate_on=ast_gate_on)
        elif kind == "ne":
            envs = _eval_ne_atom(view_facts, envs, atom, ast_gate_on=ast_gate_on)
        elif kind in {"gt", "ge", "lt", "le"}:
            envs = _eval_cmp_atom(view_facts, envs, atom, ast_gate_on=ast_gate_on)
        elif kind in _ARITH_KINDS:
            envs = _eval_arith_atom(view_facts, envs, atom, ast_gate_on=ast_gate_on)
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

    # NOTE: Current join optimization guarantees that identity shared-variable
    # joins produced by attr_eq lowering use lookup paths in the Python evaluator.
    # Non-identity cross-coordinate equality is rejected at compile time upstream.
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
    view_facts: dict[str, list[tuple[Any, ...]]],
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    _, lhs, rhs = atom
    out: list[dict[str, Any]] = []

    for env in envs:
        lhs_known, lhs_value = _resolve_eval_term(env, lhs, view_facts, ast_gate_on=ast_gate_on)
        rhs_known, rhs_value = _resolve_eval_term(env, rhs, view_facts, ast_gate_on=ast_gate_on)

        if lhs_value is AggregateNoValue or rhs_value is AggregateNoValue:
            continue

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
    view_facts: dict[str, list[tuple[Any, ...]]],
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    _, lhs, rhs = atom
    out: list[dict[str, Any]] = []

    for env in envs:
        lhs_known, lhs_value = _resolve_eval_term(env, lhs, view_facts, ast_gate_on=ast_gate_on)
        rhs_known, rhs_value = _resolve_eval_term(env, rhs, view_facts, ast_gate_on=ast_gate_on)

        if lhs_value is AggregateNoValue or rhs_value is AggregateNoValue:
            continue

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
    view_facts: dict[str, list[tuple[Any, ...]]],
    envs: list[dict[str, Any]],
    atom: tuple[Any, ...],
    *,
    ast_gate_on: bool,
) -> list[dict[str, Any]]:
    kind, lhs, rhs = atom
    out: list[dict[str, Any]] = []

    for env in envs:
        lhs_known, lhs_value_raw = _resolve_eval_term(env, lhs, view_facts, ast_gate_on=ast_gate_on)
        rhs_known, rhs_value_raw = _resolve_eval_term(env, rhs, view_facts, ast_gate_on=ast_gate_on)

        if lhs_value_raw is AggregateNoValue or rhs_value_raw is AggregateNoValue:
            continue

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
        if not any(var in env for var in vars_in_not_body) and not ast_gate_on:
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
        envs = _eval_body(view_facts, body, ast_gate_on=ast_gate_on, initial_envs=[env])
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


def _resolve_eval_term(
    env: dict[str, Any],
    term: Any,
    view_facts: dict[str, list[tuple[Any, ...]]],
    *,
    ast_gate_on: bool,
) -> tuple[bool, Any]:
    if _is_aggregate_term(term):
        return True, _resolve_aggregate_term_for_env(
            env,
            term,
            view_facts,
            ast_gate_on=ast_gate_on,
        )
    return _resolve(env, term)


def _resolve_aggregate_term_for_env(
    env: dict[str, Any],
    aggregate_term: tuple[Any, ...],
    view_facts: dict[str, list[tuple[Any, ...]]],
    *,
    ast_gate_on: bool,
) -> Any:
    kind, target, filter_atoms = aggregate_term
    matched_envs = _eval_body(
        view_facts,
        filter_atoms,
        ast_gate_on=ast_gate_on,
        initial_envs=[env],
    )
    if kind == "count":
        return len(matched_envs)
    if not matched_envs:
        if kind == "sum":
            return 0
        return AggregateNoValue

    target_values: list[Any] = []
    for matched_env in matched_envs:
        known, value = _resolve_eval_term(matched_env, target, view_facts, ast_gate_on=ast_gate_on)
        if not known or value is AggregateNoValue:
            return AggregateNoValue
        target_values.append(value)

    if kind in {"sum", "mean"}:
        for value in target_values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return AggregateNoValue
    if kind == "sum":
        return sum(target_values)
    if kind == "mean":
        return sum(target_values) / len(target_values)
    if kind == "min":
        try:
            return min(target_values)
        except TypeError:
            return AggregateNoValue
    if kind == "max":
        try:
            return max(target_values)
        except TypeError:
            return AggregateNoValue
    raise WhereValidationError(f"unsupported aggregate kind: {kind}")


def _validate_arith_atom(atom: tuple[Any, ...]) -> tuple[Any, ...]:
    kind = atom[0]
    if kind in {"add", "sub"}:
        if len(atom) != 4:
            raise WhereValidationError(f"{kind} atom must be ('{kind}', z, x, y)")
        _, z, x, y = atom
        if not _is_var(z):
            raise WhereValidationError(f"{kind} output must be variable")
        for side in (x, y):
            _validate_eval_term(side, allow_aggregate=True)
            if not _is_var(side) and not _is_literal(side) and not _is_aggregate_term(side):
                raise WhereValidationError(f"{kind} inputs must be variables or literals")
        return atom
    if kind == "neg":
        if len(atom) != 3:
            raise WhereValidationError("neg atom must be ('neg', z, x)")
        _, z, x = atom
        if not _is_var(z):
            raise WhereValidationError("neg output must be variable")
        _validate_eval_term(x, allow_aggregate=True)
        if not _is_var(x) and not _is_literal(x) and not _is_aggregate_term(x):
            raise WhereValidationError("neg input must be variable or literal")
        return atom
    if kind in {"addc", "mulc"}:
        if len(atom) != 4:
            raise WhereValidationError(f"{kind} atom must be ('{kind}', z, x, c)")
        _, z, x, c = atom
        if not _is_var(z):
            raise WhereValidationError(f"{kind} output must be variable")
        _validate_eval_term(x, allow_aggregate=True)
        if not _is_var(x) and not _is_literal(x) and not _is_aggregate_term(x):
            raise WhereValidationError(f"{kind} x input must be variable or literal")
        if _is_var(c) or not _is_literal(c):
            raise WhereValidationError(f"{kind} constant operand must be literal")
        _coerce_arith_int(c, kind)
        return atom
    raise WhereValidationError(f"unsupported arithmetic atom kind: {kind}")


def _eval_arith_atom(
    view_facts: dict[str, list[tuple[Any, ...]]],
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
            xv = _require_resolved_arith(env, x, kind, view_facts, ast_gate_on=ast_gate_on)
            if xv is None:
                continue
            yv = _require_resolved_arith(env, y, kind, view_facts, ast_gate_on=ast_gate_on)
            if yv is None:
                continue
            result = xv + yv
        elif kind == "sub":
            _, z, x, y = atom
            xv = _require_resolved_arith(env, x, kind, view_facts, ast_gate_on=ast_gate_on)
            if xv is None:
                continue
            yv = _require_resolved_arith(env, y, kind, view_facts, ast_gate_on=ast_gate_on)
            if yv is None:
                continue
            result = xv - yv
        elif kind == "neg":
            _, z, x = atom
            xv = _require_resolved_arith(env, x, kind, view_facts, ast_gate_on=ast_gate_on)
            if xv is None:
                continue
            result = -xv
        elif kind == "addc":
            _, z, x, c = atom
            xv = _require_resolved_arith(env, x, kind, view_facts, ast_gate_on=ast_gate_on)
            if xv is None:
                continue
            cv = _coerce_arith_int(c, kind)
            result = xv + cv
        elif kind == "mulc":
            _, z, x, c = atom
            xv = _require_resolved_arith(env, x, kind, view_facts, ast_gate_on=ast_gate_on)
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
    view_facts: dict[str, list[tuple[Any, ...]]],
    *,
    ast_gate_on: bool,
) -> int | None:
    known, value = _resolve_eval_term(env, term, view_facts, ast_gate_on=ast_gate_on)
    if value is AggregateNoValue:
        return None
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
    initial_bound_vars: set[str] | None = None,
) -> list[tuple[Any, ...]]:
    if len(body) <= 1:
        return list(body)
    # Boundary for phase-3 execution optimization:
    # only enable atom reordering when system identity temporaries are present.
    # This keeps generic where evaluation semantics/order stable for non-identity bodies.
    if not _body_has_system_identity_signal(body):
        return list(body)
    remaining = list(body)
    planned: list[tuple[Any, ...]] = []
    bound_vars: set[str] = set() if initial_bound_vars is None else set(initial_bound_vars)

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
    if _is_aggregate_term(term):
        return True
    if _is_var(term):
        return term in bound_vars
    return True


def _body_has_system_identity_signal(body: list[tuple[Any, ...]]) -> bool:
    for atom in body:
        if not isinstance(atom, tuple) or len(atom) < 1:
            continue
        if atom[0] != "pred" or len(atom) != 3:
            continue
        terms = atom[2]
        if not isinstance(terms, list):
            continue
        for term in terms:
            if _is_system_identity_var(term):
                return True
    return False


def _is_system_identity_var(term: Any) -> bool:
    return isinstance(term, str) and term.startswith("$__identity_")


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
    return isinstance(value, str) and not value.startswith("$")


def _is_aggregate_term(value: Any) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 3
        and isinstance(value[0], str)
        and value[0] in _AGGREGATE_KINDS
    )


def _validate_eval_term(term: Any, *, allow_aggregate: bool) -> None:
    if _is_var(term) or _is_literal(term):
        return
    if _is_aggregate_term(term):
        if not allow_aggregate:
            raise WhereValidationError("aggregate terms are not allowed here")
        kind, target, filter_atoms = term
        if kind == "count":
            if target is not None:
                raise WhereValidationError("count aggregate target must be None")
        elif target is None:
            raise WhereValidationError(f"{kind} aggregate target must not be None")
        elif kind in {"sum", "mean"} and isinstance(target, bool):
            raise WhereValidationError(f"{kind} aggregate target must not be bool")
        elif kind in {"sum", "mean"} and _is_literal(target) and not isinstance(target, (int, float)):
            raise WhereValidationError(f"{kind} aggregate literal target must be numeric")
        if not isinstance(filter_atoms, list) or not filter_atoms:
            raise WhereValidationError("aggregate filter must be non-empty list")
        for filter_atom in filter_atoms:
            if _raw_atom_contains_aggregate(filter_atom):
                raise WhereValidationError("aggregate filter must not contain aggregate terms")
            validated = _validate_atom(filter_atom)
            if validated[0] not in {"pred", "eq", "ne", "gt", "ge", "lt", "le", "in", "not"}:
                raise WhereValidationError("aggregate filter supports scalar atoms only")
        return
    raise WhereValidationError("term must be variable, literal, or aggregate term")


def _is_atom(value: Any) -> bool:
    return isinstance(value, tuple) and len(value) >= 1 and isinstance(value[0], str)


def _raw_atom_contains_aggregate(atom: Any) -> bool:
    if not _is_atom(atom):
        return False
    kind = atom[0]
    if kind == "pred" and len(atom) == 3:
        return any(_raw_term_contains_aggregate(term) for term in atom[2])
    if kind in {"eq", "ne", "gt", "ge", "lt", "le"} and len(atom) == 3:
        return _raw_term_contains_aggregate(atom[1]) or _raw_term_contains_aggregate(atom[2])
    if kind == "in" and len(atom) == 3:
        return _raw_term_contains_aggregate(atom[1]) or any(
            _raw_term_contains_aggregate(value) for value in atom[2]
        )
    if kind in _ARITH_KINDS:
        return True
    if kind == "not" and len(atom) == 2:
        bodies = _normalize_not_body(atom[1])
        return any(_raw_atom_contains_aggregate(body_atom) for body in bodies for body_atom in body)
    return False


def _raw_term_contains_aggregate(term: Any) -> bool:
    return _is_aggregate_term(term)


def _vars_in_atoms(body: list[tuple[Any, ...]]) -> list[str]:
    found: set[str] = set()
    bound_vars: set[str] = set()
    for atom in body:
        kind = atom[0]
        if kind == "pred":
            _, _, terms = atom
            for term in terms:
                if _is_var(term):
                    found.add(term)
                    bound_vars.add(term)
        elif kind == "eq":
            _, lhs, rhs = atom
            for term in (lhs, rhs):
                term_vars = _visible_vars_in_term(term, bound_vars)
                found |= term_vars
            lhs_known = _term_known_for_plan(lhs, bound_vars)
            rhs_known = _term_known_for_plan(rhs, bound_vars)
            if _is_var(lhs) and rhs_known:
                bound_vars.add(lhs)
            if _is_var(rhs) and lhs_known:
                bound_vars.add(rhs)
        elif kind == "in":
            _, var, _ = atom
            if _is_var(var):
                found.add(var)
        elif kind in {"gt", "ge", "lt", "le", "ne"}:
            _, lhs, rhs = atom
            found |= _visible_vars_in_term(lhs, bound_vars)
            found |= _visible_vars_in_term(rhs, bound_vars)
        elif kind in _ARITH_KINDS:
            for term in atom[1:]:
                found |= _visible_vars_in_term(term, bound_vars)
            output = atom[1] if len(atom) > 1 else None
            if _is_var(output):
                bound_vars.add(output)
    return sorted(found)


def _visible_vars_in_term(term: Any, bound_vars: set[str]) -> set[str]:
    if _is_var(term):
        return {term}
    if _is_aggregate_term(term):
        kind, target, filter_atoms = term
        target_vars = _visible_vars_in_term(target, bound_vars) if target is not None else set()
        filter_vars = set(_vars_in_atoms(filter_atoms))
        return target_vars | (filter_vars & bound_vars)
    return set()


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
