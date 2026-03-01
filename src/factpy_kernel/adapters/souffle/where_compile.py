from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from factpy_kernel.adapters.souffle.pred_norm import normalize_pred_id
from factpy_kernel.core.rules.where_ast import WhereASTError, parse_where_ir_to_ast
from factpy_kernel.core.rules.where_ast_validate import (
    WhereASTValidationError,
    validate_where_ast,
)
from factpy_kernel.core.rules.where_eval import WhereValidationError

_ARITH_KINDS = {"add", "sub", "neg", "addc", "mulc"}


def compile_where_to_query_dl(
    *,
    schema_ir: dict,
    where: list[Any],
    query_rel: str,
    temporal_view: str = "active",
) -> str:
    ast_gate_on = _where_ast_gate_enabled()
    if not isinstance(schema_ir, dict):
        raise WhereValidationError("schema_ir must be dict")
    if not isinstance(query_rel, str) or not query_rel:
        raise WhereValidationError("query_rel must be non-empty string")
    if temporal_view not in {"active", "current"}:
        raise WhereValidationError("temporal_view must be 'active' or 'current'")
    if ast_gate_on:
        try:
            ast = parse_where_ir_to_ast(where)
            validate_where_ast(ast, mode="souffle")
        except (WhereASTError, WhereASTValidationError) as exc:
            raise _adapt_where_ast_error(exc) from exc

    pred_type_domains = _schema_pred_type_domains(schema_ir)
    pred_arities = {pred_id: len(arg_types) for pred_id, arg_types in pred_type_domains.items()}
    temporal_pred_ids = _temporal_pred_ids(schema_ir)
    bodies = _normalize_where_subset(where)
    variables = extract_where_variables(where)
    if not variables:
        raise WhereValidationError("where must contain at least one variable")

    var_symbols = {var: f"C{i}" for i, var in enumerate(variables)}
    head_vars = [var_symbols[var] for var in variables]
    query_decl_cols = [f"{var_symbols[var]}:symbol" for var in variables]

    in_rel_values: dict[str, tuple[str, ...]] = {}
    not_rel_defs: dict[str, tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = {}
    rule_lines: list[str] = []

    for body in bodies:
        bound_vars: set[str] = set()
        var_type_domains = _infer_var_type_domains(body, pred_type_domains)
        body_terms: list[str] = []
        for atom in body:
            body_terms.append(
                _compile_atom(
                    atom=atom,
                    pred_arities=pred_arities,
                    pred_type_domains=pred_type_domains,
                    var_symbols=var_symbols,
                    bound_vars=bound_vars,
                    var_type_domains=var_type_domains,
                    in_rel_values=in_rel_values,
                    query_variables=variables,
                    not_rel_defs=not_rel_defs,
                    temporal_view=temporal_view,
                    temporal_pred_ids=temporal_pred_ids,
                    ast_gate_on=ast_gate_on,
                )
            )
        missing_vars = [var for var in variables if var not in bound_vars]
        if missing_vars:
            raise WhereValidationError(
                "where branch must bind all query variables; missing: "
                + ", ".join(missing_vars)
            )
        rule_lines.append(f'{query_rel}({", ".join(head_vars)}) :- {", ".join(body_terms)}.')

    lines: list[str] = []
    for rel_name in sorted(in_rel_values):
        values = in_rel_values[rel_name]
        lines.append(f'.decl {rel_name}(V:symbol)')
        for text in values:
            lines.append(f'{rel_name}({_text_to_symbol(text)}).')
        lines.append("")

    for rel_name in sorted(not_rel_defs):
        key_vars, body_term_groups = not_rel_defs[rel_name]
        if key_vars:
            key_decl_cols = ", ".join(f"K{i}:symbol" for i in range(len(key_vars)))
            head_args = ", ".join(var_symbols[var] for var in key_vars)
            lines.append(f".decl {rel_name}({key_decl_cols})")
            for body_terms in body_term_groups:
                lines.append(f'{rel_name}({head_args}) :- {", ".join(body_terms)}.')
        else:
            lines.append(f".decl {rel_name}()")
            for body_terms in body_term_groups:
                lines.append(f'{rel_name}() :- {", ".join(body_terms)}.')
        lines.append("")

    lines.extend(
        [
            f'.decl {query_rel}({", ".join(query_decl_cols)})',
            f'.output {query_rel}',
            "",
            *rule_lines,
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


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


def _runtime_invariant_error(message: str, *, op: str | None = None) -> WhereValidationError:
    err = WhereValidationError(message)
    setattr(err, "kind", "where_compile_runtime")
    setattr(err, "path", "$.where")
    setattr(
        err,
        "details",
        {
            "message": message,
            "origin_source": "where_compile",
            "origin_path": "$.where",
            "op": op,
            "tag": "validator_miss",
        },
    )
    return err


def _raise_dataflow_or_runtime(*, ast_gate_on: bool, message: str, op: str) -> None:
    if ast_gate_on:
        raise _runtime_invariant_error(
            f"where compile invariant violated after AST validation: {message}",
            op=op,
        )
    raise WhereValidationError(message)


def extract_where_variables(where: list[Any]) -> list[str]:
    bodies = _normalize_where_subset(where)
    found: set[str] = set()
    for body in bodies:
        for atom in body:
            for var in _vars_in_atom(atom, include_not_body_vars=False):
                found.add(var)
    return sorted(found)


def query_rel_for_where(where: list[Any]) -> str:
    # Protocol behavior (hard contract):
    # 1) Internal query results must be addressed by outputs_map["__query__"].
    # 2) Query relation name is fixed to query__<sha256-prefix-8>.
    # 3) Any change here is an incompatible change and must bump protocol/version
    #    (e.g. where_v2 / export_v2 / policy_v2).
    digest = hashlib.sha256(canonical_where_json_bytes(where)).hexdigest()
    return f"query__{digest[:8]}"


def canonical_where_json_bytes(where: list[Any]) -> bytes:
    return json.dumps(
        where,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _compile_atom(
    *,
    atom: tuple[Any, ...],
    pred_arities: dict[str, int],
    pred_type_domains: dict[str, list[str]],
    var_symbols: dict[str, str],
    bound_vars: set[str],
    var_type_domains: dict[str, set[str]],
    in_rel_values: dict[str, tuple[str, ...]],
    query_variables: list[str],
    not_rel_defs: dict[str, tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]],
    temporal_view: str,
    temporal_pred_ids: set[str],
    ast_gate_on: bool,
) -> str:
    kind = atom[0]

    if kind == "pred":
        _, pred_id, terms = atom
        if pred_id not in pred_arities:
            raise WhereValidationError(f"unknown predicate in where: {pred_id}")
        if len(terms) != pred_arities[pred_id]:
            raise WhereValidationError(
                f"arity mismatch for predicate {pred_id}: expected {pred_arities[pred_id]}, got {len(terms)}"
            )

        args: list[str] = []
        for term in terms:
            if _is_var(term):
                args.append(var_symbols[term])
                bound_vars.add(term)
            else:
                args.append(_literal_to_symbol(term))
        rel_name = normalize_pred_id(pred_id)
        if temporal_view == "current" and pred_id in temporal_pred_ids:
            rel_name = f"{rel_name}__current"
        return f'{rel_name}({", ".join(args)})'

    if kind == "eq":
        _, lhs, rhs = atom
        lhs_is_var = _is_var(lhs)
        rhs_is_var = _is_var(rhs)

        if lhs_is_var and rhs_is_var:
            lhs_bound = lhs in bound_vars
            rhs_bound = rhs in bound_vars
            if not lhs_bound and not rhs_bound:
                _raise_dataflow_or_runtime(
                    ast_gate_on=ast_gate_on,
                    message="eq requires at least one bound/constant side",
                    op="eq",
                )
            if lhs_bound and not rhs_bound:
                bound_vars.add(rhs)
            if rhs_bound and not lhs_bound:
                bound_vars.add(lhs)
        elif lhs_is_var and not rhs_is_var:
            bound_vars.add(lhs)
        elif rhs_is_var and not lhs_is_var:
            bound_vars.add(rhs)
        else:
            raise WhereValidationError("eq requires at least one variable side")

        lhs_expr = var_symbols[lhs] if lhs_is_var else _literal_to_symbol(lhs)
        rhs_expr = var_symbols[rhs] if rhs_is_var else _literal_to_symbol(rhs)
        return f"{lhs_expr} = {rhs_expr}"

    if kind == "in":
        _, var, values = atom
        if var not in bound_vars:
            _raise_dataflow_or_runtime(
                ast_gate_on=ast_gate_on,
                message=f"in variable must be bound before filter: {var}",
                op="in",
            )

        canonical_values = _canonicalize_in_values(values)
        rel_name = _in_rel_name(canonical_values)
        existing = in_rel_values.get(rel_name)
        if existing is None:
            in_rel_values[rel_name] = canonical_values
        elif existing != canonical_values:
            raise WhereValidationError("in relation name collision detected")

        return f"{rel_name}({var_symbols[var]})"

    if kind in {"gt", "ge", "lt", "le"}:
        _, lhs, rhs = atom
        lhs_is_var = _is_var(lhs)
        rhs_is_var = _is_var(rhs)

        if lhs_is_var and lhs not in bound_vars:
            _raise_dataflow_or_runtime(
                ast_gate_on=ast_gate_on,
                message=f"{kind} variable must be bound before filter: {lhs}",
                op=kind,
            )
        if rhs_is_var and rhs not in bound_vars:
            _raise_dataflow_or_runtime(
                ast_gate_on=ast_gate_on,
                message=f"{kind} variable must be bound before filter: {rhs}",
                op=kind,
            )

        if lhs_is_var:
            _assert_cmp_var_allowed(lhs, var_type_domains, kind)
        if rhs_is_var:
            _assert_cmp_var_allowed(rhs, var_type_domains, kind)

        lhs_expr = _compile_cmp_side(lhs, var_symbols, kind)
        rhs_expr = _compile_cmp_side(rhs, var_symbols, kind)
        op = _cmp_operator(kind)
        return f"{lhs_expr} {op} {rhs_expr}"

    if kind in _ARITH_KINDS:
        return _compile_arith_atom(
            atom=atom,
            var_symbols=var_symbols,
            bound_vars=bound_vars,
            ast_gate_on=ast_gate_on,
        )

    if kind == "not":
        _, not_body = atom

        not_bodies = _normalize_not_body_subset(not_body)
        vars_in_not_body: set[str] = set()
        for branch in not_bodies:
            for not_atom in branch:
                vars_in_not_body.update(_vars_in_atom(not_atom, include_not_body_vars=True))
        if not any(var in bound_vars for var in vars_in_not_body):
            _raise_dataflow_or_runtime(
                ast_gate_on=ast_gate_on,
                message="not body must reference at least one outer bound variable",
                op="not",
            )

        key_vars = tuple(var for var in query_variables if var in vars_in_not_body)
        rel_name = _not_rel_name(not_body)
        body_term_groups: list[tuple[str, ...]] = []
        for branch in not_bodies:
            local_bound_vars = set(bound_vars)
            branch_terms: list[str] = []
            branch_vars: set[str] = set()
            for not_atom in branch:
                branch_vars.update(_vars_in_atom(not_atom, include_not_body_vars=True))
                branch_terms.append(
                    _compile_not_body_atom(
                        atom=not_atom,
                        pred_arities=pred_arities,
                        pred_type_domains=pred_type_domains,
                        var_symbols=var_symbols,
                        local_bound_vars=local_bound_vars,
                        var_type_domains=var_type_domains,
                        in_rel_values=in_rel_values,
                        temporal_view=temporal_view,
                        temporal_pred_ids=temporal_pred_ids,
                        ast_gate_on=ast_gate_on,
                    )
                )
            missing_key_vars = [var for var in key_vars if var not in branch_vars]
            if missing_key_vars:
                raise WhereValidationError(
                    "not OR branch must reference all correlated variables; missing: "
                    + ", ".join(missing_key_vars)
                )
            body_term_groups.append(tuple(branch_terms))
        rel_def = (key_vars, tuple(body_term_groups))

        existing = not_rel_defs.get(rel_name)
        if existing is None:
            not_rel_defs[rel_name] = rel_def
        elif existing != rel_def:
            raise WhereValidationError("not relation name collision detected")

        if key_vars:
            rel_args = ", ".join(var_symbols[var] for var in key_vars)
            return f"!{rel_name}({rel_args})"
        return f"!{rel_name}()"

    raise WhereValidationError(f"unsupported atom kind: {kind}")


def _schema_pred_type_domains(schema_ir: dict) -> dict[str, list[str]]:
    predicates = schema_ir.get("predicates")
    if not isinstance(predicates, list):
        raise WhereValidationError("schema_ir.predicates must be list")

    out: dict[str, list[str]] = {}
    for predicate in predicates:
        if not isinstance(predicate, dict):
            continue
        pred_id = predicate.get("pred_id")
        arg_specs = predicate.get("arg_specs")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if not isinstance(arg_specs, list):
            continue
        arg_types: list[str] = []
        for idx, arg_spec in enumerate(arg_specs):
            if not isinstance(arg_spec, dict):
                raise WhereValidationError(f"arg_specs[{idx}] must be object for {pred_id}")
            type_domain = arg_spec.get("type_domain")
            if not isinstance(type_domain, str) or not type_domain:
                raise WhereValidationError(
                    f"arg_specs[{idx}].type_domain must be non-empty string for {pred_id}"
                )
            arg_types.append(type_domain)
        out[pred_id] = arg_types
    return out


def _temporal_pred_ids(schema_ir: dict) -> set[str]:
    predicates = schema_ir.get("predicates")
    if not isinstance(predicates, list):
        raise WhereValidationError("schema_ir.predicates must be list")

    out: set[str] = set()
    for predicate in predicates:
        if not isinstance(predicate, dict):
            continue
        pred_id = predicate.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if predicate.get("cardinality") == "temporal":
            out.add(pred_id)
    return out


def _normalize_where_subset(where: Any) -> list[list[tuple[Any, ...]]]:
    if not isinstance(where, list) or not where:
        raise WhereValidationError("where must be non-empty list")

    if all(_is_atom(item) for item in where):
        body = [_validate_atom_subset(item) for item in where]
        return [body]

    if all(isinstance(item, list) for item in where):
        bodies: list[list[tuple[Any, ...]]] = []
        for branch in where:
            if not branch:
                raise WhereValidationError("where OR branch must not be empty")
            if not all(_is_atom(atom) for atom in branch):
                raise WhereValidationError("where supports at most 2 list levels")
            bodies.append([_validate_atom_subset(atom) for atom in branch])
        return bodies

    raise WhereValidationError("where must be one-level AND or two-level OR-of-AND")


def _validate_atom_subset(atom: Any) -> tuple[Any, ...]:
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
        _, lhs, rhs = atom
        lhs_is_var = _is_var(lhs)
        rhs_is_var = _is_var(rhs)
        if not lhs_is_var and not rhs_is_var:
            raise WhereValidationError("eq must be var=literal or var=var")
        return atom

    if kind == "in":
        if len(atom) != 3:
            raise WhereValidationError("in atom must be ('in', var, [values...])")
        _, var, values = atom
        if not _is_var(var):
            raise WhereValidationError("in atom first argument must be variable")
        if not isinstance(values, list):
            raise WhereValidationError("in values must be list")
        return atom

    if kind in {"gt", "ge", "lt", "le"}:
        if len(atom) != 3:
            raise WhereValidationError(f"{kind} atom must be ('{kind}', lhs, rhs)")
        _, lhs, rhs = atom
        if not _is_var(lhs) and not _is_var(rhs):
            raise WhereValidationError(f"{kind} requires at least one variable side")
        return atom

    if kind in _ARITH_KINDS:
        return _validate_arith_atom_subset(atom)

    if kind == "not":
        if len(atom) != 2:
            raise WhereValidationError("not atom must be ('not', [pred_atoms...])")
        _, not_body = atom
        if not isinstance(not_body, list):
            raise WhereValidationError("not atom must be ('not', [pred_atoms...])")
        return atom

    raise WhereValidationError(f"unsupported atom kind: {kind}")


def _validate_arith_atom_subset(atom: tuple[Any, ...]) -> tuple[Any, ...]:
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
        _literal_to_cmp_int_text(c, kind)
        return atom
    raise WhereValidationError(f"unsupported arithmetic atom kind: {kind}")


def _canonicalize_in_values(values: list[Any]) -> tuple[str, ...]:
    canonical = sorted({_literal_to_text(value) for value in values})
    if not canonical:
        raise WhereValidationError("in values must be non-empty")
    return tuple(canonical)


def _normalize_not_body_subset(not_body: Any) -> list[list[tuple[Any, ...]]]:
    if not isinstance(not_body, list) or not not_body:
        raise WhereValidationError("not body must be non-empty list")

    allowed_not_kinds = {"pred", "eq", "in", "gt", "ge", "lt", "le", *_ARITH_KINDS}

    def validate_not_atom(not_atom: Any) -> tuple[Any, ...]:
        if not _is_atom(not_atom):
            raise WhereValidationError("not body atoms must be valid atoms")
        not_kind = not_atom[0]
        if not_kind not in allowed_not_kinds:
            raise WhereValidationError("not body supports pred/eq/in/cmp/arithmetic atoms only")
        return _validate_atom_subset(not_atom)

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


def _in_rel_name(values: tuple[str, ...]) -> str:
    payload = json.dumps(list(values), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"__in_{digest[:12]}"


def _not_rel_name(not_body: list[tuple[Any, ...]]) -> str:
    payload = json.dumps(
        not_body,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"__not_{digest[:12]}"


def _literal_to_symbol(value: Any) -> str:
    return _text_to_symbol(_literal_to_text(value))


def _infer_var_type_domains(
    body: list[tuple[Any, ...]],
    pred_type_domains: dict[str, list[str]],
) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}

    def add_from_pred_atom(atom: tuple[Any, ...]) -> None:
        _, pred_id, terms = atom
        arg_types = pred_type_domains.get(pred_id)
        if arg_types is None:
            return
        for term, type_domain in zip(terms, arg_types):
            if _is_var(term):
                out.setdefault(term, set()).add(type_domain)

    for atom in body:
        if atom[0] == "pred":
            add_from_pred_atom(atom)
        elif atom[0] in _ARITH_KINDS:
            for term in atom[1:]:
                if _is_var(term):
                    out.setdefault(term, set()).add("int")
        elif atom[0] == "not":
            _, not_body = atom
            for branch in _normalize_not_body_subset(not_body):
                for not_atom in branch:
                    if not_atom[0] == "pred":
                        add_from_pred_atom(not_atom)
                    elif not_atom[0] in _ARITH_KINDS:
                        for term in not_atom[1:]:
                            if _is_var(term):
                                out.setdefault(term, set()).add("int")
    return out


def _assert_cmp_var_allowed(
    var: str,
    var_type_domains: dict[str, set[str]],
    kind: str,
) -> None:
    domains = var_type_domains.get(var)
    if not domains:
        raise WhereValidationError(f"{kind} variable type unknown: {var}")
    if any(domain not in {"int", "time"} for domain in domains):
        raise WhereValidationError(f"{kind} supports only int/time variables: {var}")


def _compile_cmp_side(term: Any, var_symbols: dict[str, str], kind: str) -> str:
    if _is_var(term):
        return f"to_number({_symbol_for_var(var_symbols, term)})"
    return _literal_to_cmp_int_text(term, kind)


def _literal_to_cmp_int_text(value: Any, kind: str) -> str:
    if isinstance(value, bool):
        raise WhereValidationError(f"{kind} supports only int/time literals")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        if not value or any(ch not in "0123456789-" for ch in value):
            raise WhereValidationError(f"{kind} literal must be decimal integer")
        if value.count("-") > 1 or ("-" in value and not value.startswith("-")):
            raise WhereValidationError(f"{kind} literal must be decimal integer")
        if value in {"-", ""}:
            raise WhereValidationError(f"{kind} literal must be decimal integer")
        return str(int(value))
    raise WhereValidationError(f"{kind} supports only int/time literals")


def _cmp_operator(kind: str) -> str:
    if kind == "gt":
        return ">"
    if kind == "ge":
        return ">="
    if kind == "lt":
        return "<"
    if kind == "le":
        return "<="
    raise WhereValidationError(f"unsupported comparison kind: {kind}")


def _compile_not_body_atom(
    *,
    atom: tuple[Any, ...],
    pred_arities: dict[str, int],
    pred_type_domains: dict[str, list[str]],
    var_symbols: dict[str, str],
    local_bound_vars: set[str],
    var_type_domains: dict[str, set[str]],
    in_rel_values: dict[str, tuple[str, ...]],
    temporal_view: str,
    temporal_pred_ids: set[str],
    ast_gate_on: bool,
) -> str:
    kind = atom[0]
    if kind == "pred":
        _, pred_id, terms = atom
        if pred_id not in pred_arities:
            raise WhereValidationError(f"unknown predicate in where: {pred_id}")
        if len(terms) != pred_arities[pred_id]:
            raise WhereValidationError(
                f"arity mismatch for predicate {pred_id}: expected {pred_arities[pred_id]}, got {len(terms)}"
            )

        args: list[str] = []
        for term in terms:
            if _is_var(term):
                local_bound_vars.add(term)
                args.append(_symbol_for_var(var_symbols, term))
            else:
                args.append(_literal_to_symbol(term))
        rel_name = normalize_pred_id(pred_id)
        if temporal_view == "current" and pred_id in temporal_pred_ids:
            rel_name = f"{rel_name}__current"
        return f'{rel_name}({", ".join(args)})'

    if kind == "eq":
        _, lhs, rhs = atom
        lhs_is_var = _is_var(lhs)
        rhs_is_var = _is_var(rhs)

        if lhs_is_var and rhs_is_var:
            lhs_bound = lhs in local_bound_vars
            rhs_bound = rhs in local_bound_vars
            if not lhs_bound and not rhs_bound:
                _raise_dataflow_or_runtime(
                    ast_gate_on=ast_gate_on,
                    message="eq requires at least one bound/constant side",
                    op="eq",
                )
            if lhs_bound and not rhs_bound:
                local_bound_vars.add(rhs)
            if rhs_bound and not lhs_bound:
                local_bound_vars.add(lhs)
        elif lhs_is_var and not rhs_is_var:
            local_bound_vars.add(lhs)
        elif rhs_is_var and not lhs_is_var:
            local_bound_vars.add(rhs)
        else:
            raise WhereValidationError("eq requires at least one variable side")

        lhs_expr = _symbol_for_var(var_symbols, lhs) if lhs_is_var else _literal_to_symbol(lhs)
        rhs_expr = _symbol_for_var(var_symbols, rhs) if rhs_is_var else _literal_to_symbol(rhs)
        return f"{lhs_expr} = {rhs_expr}"

    if kind == "in":
        _, var, values = atom
        if var not in local_bound_vars:
            _raise_dataflow_or_runtime(
                ast_gate_on=ast_gate_on,
                message=f"in variable must be bound before filter: {var}",
                op="in",
            )
        canonical_values = _canonicalize_in_values(values)
        rel_name = _in_rel_name(canonical_values)
        existing = in_rel_values.get(rel_name)
        if existing is None:
            in_rel_values[rel_name] = canonical_values
        elif existing != canonical_values:
            raise WhereValidationError("in relation name collision detected")
        return f"{rel_name}({_symbol_for_var(var_symbols, var)})"

    if kind in {"gt", "ge", "lt", "le"}:
        _, lhs, rhs = atom
        lhs_is_var = _is_var(lhs)
        rhs_is_var = _is_var(rhs)
        if lhs_is_var and lhs not in local_bound_vars:
            _raise_dataflow_or_runtime(
                ast_gate_on=ast_gate_on,
                message=f"{kind} variable must be bound before filter: {lhs}",
                op=kind,
            )
        if rhs_is_var and rhs not in local_bound_vars:
            _raise_dataflow_or_runtime(
                ast_gate_on=ast_gate_on,
                message=f"{kind} variable must be bound before filter: {rhs}",
                op=kind,
            )
        if lhs_is_var:
            _assert_cmp_var_allowed(lhs, var_type_domains, kind)
        if rhs_is_var:
            _assert_cmp_var_allowed(rhs, var_type_domains, kind)
        lhs_expr = _compile_cmp_side(lhs, var_symbols, kind)
        rhs_expr = _compile_cmp_side(rhs, var_symbols, kind)
        op = _cmp_operator(kind)
        return f"{lhs_expr} {op} {rhs_expr}"

    if kind in _ARITH_KINDS:
        return _compile_arith_atom(
            atom=atom,
            var_symbols=var_symbols,
            bound_vars=local_bound_vars,
            ast_gate_on=ast_gate_on,
        )

    raise WhereValidationError(f"unsupported atom kind in not body: {kind}")


def _compile_arith_atom(
    *,
    atom: tuple[Any, ...],
    var_symbols: dict[str, str],
    bound_vars: set[str],
    ast_gate_on: bool,
) -> str:
    kind = atom[0]

    def _require_bound(var: str) -> None:
        if var not in bound_vars:
            _raise_dataflow_or_runtime(
                ast_gate_on=ast_gate_on,
                message=f"{kind} input variable must be bound before use: {var}",
                op=kind,
            )

    def _arith_input(term: Any) -> str:
        if _is_var(term):
            _require_bound(term)
            return f"to_number({_symbol_for_var(var_symbols, term)})"
        return _literal_to_cmp_int_text(term, kind)

    if kind == "add":
        _, z, x, y = atom
        expr = f"({_arith_input(x)} + {_arith_input(y)})"
    elif kind == "sub":
        _, z, x, y = atom
        expr = f"({_arith_input(x)} - {_arith_input(y)})"
    elif kind == "neg":
        _, z, x = atom
        expr = f"(-{_arith_input(x)})"
    elif kind == "addc":
        _, z, x, c = atom
        expr = f"({_arith_input(x)} + {_literal_to_cmp_int_text(c, kind)})"
    elif kind == "mulc":
        _, z, x, c = atom
        expr = f"({_arith_input(x)} * {_literal_to_cmp_int_text(c, kind)})"
    else:
        raise WhereValidationError(f"unsupported arithmetic atom kind: {kind}")

    z_sym = _symbol_for_var(var_symbols, z)
    bound_vars.add(z)
    return f"{z_sym} = to_string({expr})"


def _literal_to_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    raise WhereValidationError("unsupported literal type")


def _text_to_symbol(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


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


def _vars_in_atom(atom: tuple[Any, ...], *, include_not_body_vars: bool) -> list[str]:
    kind = atom[0]
    found: set[str] = set()
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
    elif kind in _ARITH_KINDS:
        for term in atom[1:]:
            if _is_var(term):
                found.add(term)
    elif kind == "not":
        if include_not_body_vars:
            _, body = atom
            for not_atom in body:
                for var in _vars_in_atom(not_atom, include_not_body_vars=True):
                    found.add(var)
    return sorted(found)


def _symbol_for_var(var_symbols: dict[str, str], var: str) -> str:
    symbol = var_symbols.get(var)
    if symbol is not None:
        return symbol
    symbol = f"V{len(var_symbols)}"
    var_symbols[var] = symbol
    return symbol
