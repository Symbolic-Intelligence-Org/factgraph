from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from factgraph.adapters.souffle.pred_norm import normalize_pred_id
from factgraph.adapters.souffle.souffle_view_gen import witness_rel_name
from factgraph.core.rules.ruleref_common import internal_rule_pred_id, resolve_exposed_rule_ref
from factgraph.core.rules.where_ast import (
    _AGGREGATE_KINDS,
    WhereASTError,
    parse_where_ir_to_ast,
)
from factgraph.core.rules.where_ast_validate import (
    WhereASTValidationError,
    validate_where_ast,
)
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store._support import make_pred_condition_key

_ARITH_KINDS = {"add", "sub", "neg", "addc", "mulc"}
# Souffle's interpreter aborts (SIGABRT, "Requested arity not yet supported")
# on any relation whose arity exceeds 22 — verified on Souffle 2.5 (23+ all
# crash). `_raise_if_relation_arity_too_large` pre-flight-checks against this so
# an over-wide witness relation fails with a named WhereValidationError before
# Souffle is invoked, instead of an opaque rc=134 crash.
SOUFFLE_MAX_SUPPORTED_ARITY = 22
# T2.3c: min/max/mean require `count : {same_body} > 0` guard prefix per
# blueprint §2.5 v2 lock to honor C101 AggregateNoValue via branch-not-firing.
# count/sum empty=0 is a legal C101 value and needs no guard.
_AGGREGATE_GUARD_KINDS = {"min", "max", "mean"}
_AGGREGATE_FILTER_ATOM_KINDS = {"pred", "eq", "ne", "in", "gt", "ge", "lt", "le", "not"}


@dataclass(frozen=True)
class PredWitnessColumnSpec:
    pred_condition_key: str
    pred_id: str
    case_index: int
    condition_index: int


@dataclass(frozen=True)
class QueryWitnessLayout:
    query_variables: tuple[str, ...]
    pred_witness_columns: tuple[PredWitnessColumnSpec, ...]


@dataclass(frozen=True)
class BranchWitnessRelationSpec:
    relation_name: str
    case_index: int
    layout: QueryWitnessLayout


@dataclass(frozen=True)
class PerBranchWitnessProgram:
    text: str
    query_rel: str
    query_variables: tuple[str, ...]
    branch_relations: tuple[BranchWitnessRelationSpec, ...]


@dataclass(frozen=True)
class _RuleRefRelationSpec:
    rel_name: str
    select_vars: tuple[str, ...]
    where: list[Any]


def compile_where_to_query_dl(
    *,
    schema_ir: dict,
    where: list[Any],
    query_rel: str,
    query_variables: list[str] | tuple[str, ...] | None = None,
    include_pred_witness_columns: bool = False,
    registry: Any | None = None,
) -> str:
    ast_gate_on = _where_ast_gate_enabled()
    if not isinstance(schema_ir, dict):
        raise WhereValidationError("schema_ir must be dict")
    if not isinstance(query_rel, str) or not query_rel:
        raise WhereValidationError("query_rel must be non-empty string")
    if ast_gate_on:
        try:
            ast = parse_where_ir_to_ast(where)
            validate_where_ast(ast, mode="souffle")
        except (WhereASTError, WhereASTValidationError) as exc:
            raise _adapt_where_ast_error(exc) from exc

    pred_type_domains = _schema_pred_type_domains(schema_ir)
    expanded = _expand_ruleref_relations_for_query_export(
        where=where,
        registry=registry,
        pred_type_domains=pred_type_domains,
    )
    pred_arities = {pred_id: len(arg_types) for pred_id, arg_types in pred_type_domains.items()}
    in_rel_values: dict[str, tuple[str, ...]] = {}
    not_rel_defs: dict[str, tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = {}
    relation_blocks: list[list[str]] = []
    for rel_name in sorted(expanded.relation_specs):
        spec = expanded.relation_specs[rel_name]
        relation_blocks.append(
            _compile_relation_to_dl_block(
                relation_name=normalize_pred_id(rel_name),
                where=spec.where,
                relation_variables=list(spec.select_vars),
                pred_arities=pred_arities,
                pred_type_domains=pred_type_domains,
                in_rel_values=in_rel_values,
                not_rel_defs=not_rel_defs,
                ast_gate_on=ast_gate_on,
                include_pred_witness_columns=False,
                emit_output=False,
                not_rel_namespace=rel_name,
            )
        )

    if query_variables is None:
        relation_variables = extract_where_variables(expanded.rewritten_where)
    else:
        relation_variables = _normalize_query_variables(query_variables)
    relation_blocks.append(
        _compile_relation_to_dl_block(
            relation_name=query_rel,
            where=expanded.rewritten_where,
            relation_variables=relation_variables,
            pred_arities=pred_arities,
            pred_type_domains=pred_type_domains,
            in_rel_values=in_rel_values,
            not_rel_defs=not_rel_defs,
            ast_gate_on=ast_gate_on,
            include_pred_witness_columns=include_pred_witness_columns,
            emit_output=True,
            not_rel_namespace=None,
        )
    )

    lines: list[str] = []
    for rel_name in sorted(in_rel_values):
        values = in_rel_values[rel_name]
        lines.append(f'.decl {rel_name}(V:symbol)')
        for text in values:
            lines.append(f'{rel_name}({_text_to_symbol(text)}).')
        lines.append("")

    for rel_name in sorted(not_rel_defs):
        key_args, body_term_groups = not_rel_defs[rel_name]
        if key_args:
            key_decl_cols = ", ".join(f"K{i}:symbol" for i in range(len(key_args)))
            head_args = ", ".join(key_args)
            lines.append(f".decl {rel_name}({key_decl_cols})")
            for body_terms in body_term_groups:
                lines.append(f'{rel_name}({head_args}) :- {", ".join(body_terms)}.')
        else:
            lines.append(f".decl {rel_name}()")
            for body_terms in body_term_groups:
                lines.append(f'{rel_name}() :- {", ".join(body_terms)}.')
        lines.append("")

    for block in relation_blocks:
        lines.extend(block)
    return "\n".join(lines).rstrip() + "\n"


def compile_where_to_per_branch_witness_dl(
    *,
    schema_ir: dict,
    where: list[Any],
    query_rel: str,
    query_variables: list[str] | tuple[str, ...],
    registry: Any | None = None,
) -> PerBranchWitnessProgram:
    ast_gate_on = _where_ast_gate_enabled()
    if not isinstance(schema_ir, dict):
        raise WhereValidationError("schema_ir must be dict")
    if not isinstance(query_rel, str) or not query_rel:
        raise WhereValidationError("query_rel must be non-empty string")
    if ast_gate_on:
        try:
            ast = parse_where_ir_to_ast(where)
            validate_where_ast(ast, mode="souffle")
        except (WhereASTError, WhereASTValidationError) as exc:
            raise _adapt_where_ast_error(exc) from exc

    pred_type_domains = _schema_pred_type_domains(schema_ir)
    expanded = _expand_ruleref_relations_for_query_export(
        where=where,
        registry=registry,
        pred_type_domains=pred_type_domains,
    )
    pred_arities = {pred_id: len(arg_types) for pred_id, arg_types in pred_type_domains.items()}
    relation_variables = _normalize_query_variables(query_variables)
    bodies = _normalize_where_subset(expanded.rewritten_where)
    _raise_if_relation_arity_too_large(
        relation_name=query_rel,
        case_index=None,
        query_variables=relation_variables,
        pred_witness_columns=(),
    )

    in_rel_values: dict[str, tuple[str, ...]] = {}
    not_rel_defs: dict[str, tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = {}
    relation_blocks: list[list[str]] = []
    for rel_name in sorted(expanded.relation_specs):
        spec = expanded.relation_specs[rel_name]
        relation_blocks.append(
            _compile_relation_to_dl_block(
                relation_name=normalize_pred_id(rel_name),
                where=spec.where,
                relation_variables=list(spec.select_vars),
                pred_arities=pred_arities,
                pred_type_domains=pred_type_domains,
                in_rel_values=in_rel_values,
                not_rel_defs=not_rel_defs,
                ast_gate_on=ast_gate_on,
                include_pred_witness_columns=False,
                emit_output=False,
                not_rel_namespace=rel_name,
            )
        )

    relation_blocks.append(
        _compile_relation_to_dl_block(
            relation_name=query_rel,
            where=expanded.rewritten_where,
            relation_variables=relation_variables,
            pred_arities=pred_arities,
            pred_type_domains=pred_type_domains,
            in_rel_values=in_rel_values,
            not_rel_defs=not_rel_defs,
            ast_gate_on=ast_gate_on,
            include_pred_witness_columns=False,
            emit_output=True,
            not_rel_namespace=None,
        )
    )

    branch_relations: list[BranchWitnessRelationSpec] = []
    for case_index, body in enumerate(bodies):
        branch_rel = f"{query_rel}__b{case_index}_w"
        branch_where = list(body)
        layout = build_query_witness_layout(
            branch_where,
            query_variables=relation_variables,
            case_index_base=case_index,
        )
        if not layout.pred_witness_columns:
            continue
        _raise_if_relation_arity_too_large(
            relation_name=branch_rel,
            case_index=case_index,
            query_variables=relation_variables,
            pred_witness_columns=layout.pred_witness_columns,
        )
        relation_blocks.append(
            _compile_relation_to_dl_block(
                relation_name=branch_rel,
                where=branch_where,
                relation_variables=relation_variables,
                pred_arities=pred_arities,
                pred_type_domains=pred_type_domains,
                in_rel_values=in_rel_values,
                not_rel_defs=not_rel_defs,
                ast_gate_on=ast_gate_on,
                include_pred_witness_columns=True,
                emit_output=True,
                not_rel_namespace=f"{query_rel}__b{case_index}",
                case_index_base=case_index,
            )
        )
        branch_relations.append(
            BranchWitnessRelationSpec(
                relation_name=branch_rel,
                case_index=case_index,
                layout=layout,
            )
        )

    lines: list[str] = []
    for rel_name in sorted(in_rel_values):
        values = in_rel_values[rel_name]
        lines.append(f'.decl {rel_name}(V:symbol)')
        for text in values:
            lines.append(f'{rel_name}({_text_to_symbol(text)}).')
        lines.append("")

    for rel_name in sorted(not_rel_defs):
        key_args, body_term_groups = not_rel_defs[rel_name]
        if key_args:
            key_decl_cols = ", ".join(f"K{i}:symbol" for i in range(len(key_args)))
            head_args = ", ".join(key_args)
            lines.append(f".decl {rel_name}({key_decl_cols})")
            for body_terms in body_term_groups:
                lines.append(f'{rel_name}({head_args}) :- {", ".join(body_terms)}.')
        else:
            lines.append(f".decl {rel_name}()")
            for body_terms in body_term_groups:
                lines.append(f'{rel_name}() :- {", ".join(body_terms)}.')
        lines.append("")

    for block in relation_blocks:
        lines.extend(block)
    return PerBranchWitnessProgram(
        text="\n".join(lines).rstrip() + "\n",
        query_rel=query_rel,
        query_variables=tuple(relation_variables),
        branch_relations=tuple(branch_relations),
    )


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


def _runtime_invariant_error(message: str, *, op: str | None = None) -> WhereValidationError:
    err = WhereValidationError(message)
    err.kind = "where_compile_runtime"
    err.path = "$.where"
    err.details = {
        "message": message,
        "origin_source": "where_compile",
        "origin_path": "$.where",
        "op": op,
        "tag": "validator_miss",
    }
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


def _normalize_query_variables(query_variables: list[str] | tuple[str, ...]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in query_variables:
        if not isinstance(item, str) or not item.startswith("$"):
            raise WhereValidationError("query variables must be variable tokens")
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    if not out:
        raise WhereValidationError("query variables must be non-empty")
    return out


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


def build_query_witness_layout(
    where: list[Any],
    *,
    query_variables: list[str] | tuple[str, ...] | None = None,
    case_index_base: int = 0,
) -> QueryWitnessLayout:
    variables = (
        tuple(extract_where_variables(where))
        if query_variables is None
        else tuple(_normalize_query_variables(query_variables))
    )
    bodies = _normalize_where_subset(where)
    pred_witness_columns: list[PredWitnessColumnSpec] = []
    for local_case_index, body in enumerate(bodies):
        case_index = case_index_base + local_case_index
        for condition_index, atom in enumerate(body):
            if atom[0] != "pred":
                continue
            _, pred_id, _terms = atom
            pred_witness_columns.append(
                PredWitnessColumnSpec(
                    pred_condition_key=make_pred_condition_key(case_index, condition_index, pred_id),
                    pred_id=pred_id,
                    case_index=case_index,
                    condition_index=condition_index,
                )
            )
    return QueryWitnessLayout(
        query_variables=variables,
        pred_witness_columns=tuple(pred_witness_columns),
    )


def _raise_if_relation_arity_too_large(
    *,
    relation_name: str,
    case_index: int | None,
    query_variables: list[str],
    pred_witness_columns: tuple[PredWitnessColumnSpec, ...],
) -> None:
    arity = len(query_variables) + len(pred_witness_columns)
    if arity <= SOUFFLE_MAX_SUPPORTED_ARITY:
        return
    contributors = ", ".join(
        f"{spec.pred_condition_key}:{spec.pred_id}" for spec in pred_witness_columns
    )
    branch_text = "result relation" if case_index is None else f"branch c{case_index}"
    raise WhereValidationError(
        "souffle witness relation arity exceeds supported limit: "
        f"{relation_name} ({branch_text}) arity={arity}, "
        f"query_columns={len(query_variables)}, "
        f"witness_predicates={len(pred_witness_columns)}, "
        f"limit={SOUFFLE_MAX_SUPPORTED_ARITY}; "
        f"contributors=[{contributors}]"
    )


def _compile_relation_to_dl_block(
    *,
    relation_name: str,
    where: list[Any],
    relation_variables: list[str],
    pred_arities: dict[str, int],
    pred_type_domains: dict[str, list[str]],
    in_rel_values: dict[str, tuple[str, ...]],
    not_rel_defs: dict[str, tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]],
    ast_gate_on: bool,
    include_pred_witness_columns: bool,
    emit_output: bool,
    not_rel_namespace: str | None,
    case_index_base: int = 0,
) -> list[str]:
    bodies = _normalize_where_subset(where)
    if include_pred_witness_columns:
        witness_layout = build_query_witness_layout(
            where,
            query_variables=relation_variables,
            case_index_base=case_index_base,
        )
        head_relation_variables = list(witness_layout.query_variables)
        all_variables = list(witness_layout.query_variables)
        for var in extract_where_variables(where):
            if var not in all_variables:
                all_variables.append(var)
    else:
        witness_layout = None
        head_relation_variables = list(relation_variables)
        all_variables = extract_where_variables(where)
    if not all_variables:
        raise WhereValidationError("where must contain at least one variable")

    ordered_variables = list(head_relation_variables)
    for var in all_variables:
        if var not in head_relation_variables:
            ordered_variables.append(var)
    var_symbols = {var: f"C{i}" for i, var in enumerate(ordered_variables)}
    head_vars = [var_symbols[var] for var in head_relation_variables]
    relation_decl_cols = [f"{var_symbols[var]}:symbol" for var in head_relation_variables]
    pred_witness_symbols: dict[tuple[int, int], str] = {}
    if witness_layout is not None:
        for index, spec in enumerate(witness_layout.pred_witness_columns):
            witness_symbol = f"W{index}"
            pred_witness_symbols[(spec.case_index, spec.condition_index)] = witness_symbol
            head_vars.append(witness_symbol)
            relation_decl_cols.append(f"{witness_symbol}:symbol")

    rule_lines: list[str] = []
    for local_case_index, body in enumerate(bodies):
        case_index = case_index_base + local_case_index
        bound_vars: set[str] = set()
        var_type_domains = _infer_var_type_domains(body, pred_type_domains)
        body_terms: list[str] = []
        seen_pred_occurrences: set[tuple[int, int]] = set()
        for condition_index, atom in enumerate(body):
            body_terms.append(
                _compile_atom(
                    atom=atom,
                    pred_arities=pred_arities,
                    pred_type_domains=pred_type_domains,
                    var_symbols=var_symbols,
                    bound_vars=bound_vars,
                    var_type_domains=var_type_domains,
                    in_rel_values=in_rel_values,
                    query_variables=head_relation_variables,
                    not_rel_defs=not_rel_defs,
                    ast_gate_on=ast_gate_on,
                    case_index=case_index,
                    condition_index=condition_index,
                    pred_witness_symbols=pred_witness_symbols,
                    not_rel_namespace=not_rel_namespace,
                )
            )
            if atom[0] == "pred" and witness_layout is not None:
                seen_pred_occurrences.add((case_index, condition_index))
        if witness_layout is not None:
            for spec in witness_layout.pred_witness_columns:
                occurrence = (spec.case_index, spec.condition_index)
                if occurrence in seen_pred_occurrences:
                    continue
                body_terms.append(f'{pred_witness_symbols[occurrence]} = ""')
        missing_vars = [var for var in head_relation_variables if var not in bound_vars]
        if missing_vars:
            raise WhereValidationError(
                "where branch must bind all query variables; missing: "
                + ", ".join(missing_vars)
            )
        rule_lines.append(f'{relation_name}({", ".join(head_vars)}) :- {", ".join(body_terms)}.')

    lines = [f'.decl {relation_name}({", ".join(relation_decl_cols)})']
    if emit_output:
        lines.append(f".output {relation_name}")
    lines.append("")
    lines.extend(rule_lines)
    return lines


def _expand_ruleref_relations_for_query_export(
    *,
    where: list[Any],
    registry: Any | None,
    pred_type_domains: dict[str, list[str]],
) -> _ExpandedRuleRefQuery:
    relation_specs: dict[str, _RuleRefRelationSpec] = {}
    pending_rule_specs: dict[tuple[str, str], tuple[str, tuple[str, ...], list[Any]]] = {}

    def rewrite_where_expr(expr: list[Any]) -> list[Any]:
        if all(isinstance(item, tuple) for item in expr):
            return [rewrite_atom(atom) for atom in expr]
        if all(isinstance(item, list) for item in expr):
            return [rewrite_where_expr(branch) for branch in expr]
        raise WhereValidationError("where must be one-level AND or two-level OR-of-AND")

    def rewrite_atom(atom: tuple[Any, ...]) -> tuple[Any, ...]:
        if atom[0] != "ruleref":
            return atom
        if registry is None:
            # Slice 7C / Q6-A (c.1): the filesystem-registry gate was replaced
            # with a caller-provided in-memory resolver satisfying the
            # `registry.resolve(rule_id, version)` protocol in
            # `core/rules/ruleref_common.py`. The core helper is unchanged
            # (N-3 preservation); only the wording of this gate changes.
            raise WhereValidationError(
                "query export with ruleref requires an in-memory rule resolver "
                "implementing registry.resolve(rule_id, version)"
            )
        if len(atom) != 4:
            raise WhereValidationError("ruleref atom must be ('ruleref', rule_id, version, [terms...])")
        _, rule_id, version, terms = atom
        if not isinstance(terms, list):
            raise WhereValidationError("ruleref atom terms must be list")
        ref_spec = resolve_exposed_rule_ref(
            registry,
            rule_id=rule_id,
            version=version,
            terms_len=len(terms),
            error_factory=WhereValidationError,
        )
        key = (ref_spec.rule_id, ref_spec.version)
        rel_name = internal_rule_pred_id(ref_spec.rule_id, ref_spec.version)
        if key not in pending_rule_specs:
            pending_rule_specs[key] = (rel_name, tuple(ref_spec.select_vars), [])
            pred_type_domains.setdefault(rel_name, ["symbol"] * len(ref_spec.select_vars))
            rewritten_child = rewrite_where_expr(ref_spec.where)
            pending_rule_specs[key] = (rel_name, tuple(ref_spec.select_vars), rewritten_child)
            pred_type_domains[rel_name] = _infer_rule_output_domains(
                where=rewritten_child,
                select_vars=list(ref_spec.select_vars),
                pred_type_domains=pred_type_domains,
            )
            relation_specs[rel_name] = _RuleRefRelationSpec(
                rel_name=rel_name,
                select_vars=tuple(ref_spec.select_vars),
                where=rewritten_child,
            )
        return ("pred", rel_name, terms)

    rewritten_where = rewrite_where_expr(where)
    return _ExpandedRuleRefQuery(
        rewritten_where=rewritten_where,
        relation_specs=relation_specs,
    )


@dataclass(frozen=True)
class _ExpandedRuleRefQuery:
    rewritten_where: list[Any]
    relation_specs: dict[str, _RuleRefRelationSpec]


def _infer_rule_output_domains(
    *,
    where: list[Any],
    select_vars: list[str],
    pred_type_domains: dict[str, list[str]],
) -> list[str]:
    bodies = _normalize_where_subset(where)
    body_domains = [_infer_var_type_domains(body, pred_type_domains) for body in bodies]
    out: list[str] = []
    for select_var in select_vars:
        domains: set[str] = set()
        for item in body_domains:
            domains.update(item.get(select_var, set()))
        out.append(_collapse_domains_for_internal_relation(domains))
    return out


def _collapse_domains_for_internal_relation(domains: set[str]) -> str:
    if not domains:
        return "symbol"
    if domains <= {"int"}:
        return "int"
    if domains <= {"time"}:
        return "time"
    if domains <= {"int", "time"}:
        return "time" if "time" in domains else "int"
    if len(domains) == 1:
        return next(iter(domains))
    return "symbol"


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
    ast_gate_on: bool,
    case_index: int,
    condition_index: int,
    pred_witness_symbols: dict[tuple[int, int], str],
    not_rel_namespace: str | None,
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
        occurrence = (case_index, condition_index)
        witness_symbol = pred_witness_symbols.get(occurrence)
        rel_name = normalize_pred_id(pred_id)
        if witness_symbol is not None:
            rel_name = witness_rel_name(rel_name)
            args.append(witness_symbol)
        return f'{rel_name}({", ".join(args)})'

    if kind == "eq":
        _, lhs, rhs = atom
        lhs_is_var = _is_var(lhs)
        rhs_is_var = _is_var(rhs)
        lhs_is_agg = _is_aggregate(lhs)
        rhs_is_agg = _is_aggregate(rhs)

        # T2.3c eq dispatch with aggregate operand per blueprint §5.3.5 v3
        # wrapper table. Guard for min/max/mean composed as peer body clause
        # (NOT inside to_string wrap).
        if lhs_is_agg or rhs_is_agg:
            agg_ctx = {
                "var_symbols": var_symbols,
                "outer_bound_vars": bound_vars,
                "pred_arities": pred_arities,
                "pred_type_domains": pred_type_domains,
                "var_type_domains": var_type_domains,
                "in_rel_values": in_rel_values,
                "not_rel_defs": not_rel_defs,
                "not_rel_namespace": not_rel_namespace,
                "ast_gate_on": ast_gate_on,
            }
            # Case 1: eq with two aggregates → numeric filter, both sides bare.
            # Both guards (if min/max/mean) prepend as peer clauses.
            if lhs_is_agg and rhs_is_agg:
                lhs_guard, lhs_value = _compile_aggregate_parts(aggregate=lhs, **agg_ctx)
                rhs_guard, rhs_value = _compile_aggregate_parts(aggregate=rhs, **agg_ctx)
                parts: list[str] = []
                if lhs_guard is not None:
                    parts.append(lhs_guard)
                if rhs_guard is not None:
                    parts.append(rhs_guard)
                parts.append(f"{lhs_value} = {rhs_value}")
                return ", ".join(parts)
            # Identify aggregate side and other side.
            agg = lhs if lhs_is_agg else rhs
            other = rhs if lhs_is_agg else lhs
            other_is_var = rhs_is_var if lhs_is_agg else lhs_is_var
            agg_guard, agg_value = _compile_aggregate_parts(aggregate=agg, **agg_ctx)
            # Case 2: eq binding to unbound var → `<guard>?, v_X = to_string(<value>)`.
            if other_is_var and other not in bound_vars:
                bound_vars.add(other)
                return _compose_aggregate_eq_binding(
                    other_var_token=other,
                    var_symbols=var_symbols,
                    guard_clause=agg_guard,
                    value_expr=agg_value,
                )
            # Case 3: eq filter with bound var → `<guard>?, <value> = to_number(v_X)`.
            # T2.3c P1 v7: aggregate is numeric; bound-var side MUST also be
            # numeric (int/time domain). Reject entity/string bound vars
            # because `to_number(symbol)` of non-numeric content yields
            # undefined Souffle DL behavior. Mirrors gt/ge/lt/le precedent.
            if other_is_var and other in bound_vars:
                _assert_cmp_var_allowed(other, var_type_domains, "eq")
                other_cmp_expr = f"to_number({var_symbols[other]})"
                return _compose_aggregate_numeric_cmp(
                    guard_clause=agg_guard,
                    value_expr=agg_value,
                    op="=",
                    other_expr=other_cmp_expr,
                    aggregate_on_left=True,
                )
            # Case 4: eq filter with literal → `<guard>?, <value> = <literal>`.
            return _compose_aggregate_numeric_cmp(
                guard_clause=agg_guard,
                value_expr=agg_value,
                op="=",
                other_expr=_literal_to_cmp_int_text(other, "eq"),
                aggregate_on_left=True,
            )

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

    if kind == "ne":
        # T2.3c: aggregate-aware ne. Falls through to _compile_ne_filter for
        # var/literal-only; otherwise dispatch via _compile_aggregate_parts
        # to get guard + value separately.
        _, lhs, rhs = atom
        lhs_is_agg = _is_aggregate(lhs)
        rhs_is_agg = _is_aggregate(rhs)
        if lhs_is_agg or rhs_is_agg:
            agg_ctx = {
                "var_symbols": var_symbols,
                "outer_bound_vars": bound_vars,
                "pred_arities": pred_arities,
                "pred_type_domains": pred_type_domains,
                "var_type_domains": var_type_domains,
                "in_rel_values": in_rel_values,
                "not_rel_defs": not_rel_defs,
                "not_rel_namespace": not_rel_namespace,
                "ast_gate_on": ast_gate_on,
            }
            # Two-aggregate ne
            if lhs_is_agg and rhs_is_agg:
                lhs_guard, lhs_value = _compile_aggregate_parts(aggregate=lhs, **agg_ctx)
                rhs_guard, rhs_value = _compile_aggregate_parts(aggregate=rhs, **agg_ctx)
                parts: list[str] = []
                if lhs_guard is not None:
                    parts.append(lhs_guard)
                if rhs_guard is not None:
                    parts.append(rhs_guard)
                parts.append(f"{lhs_value} != {rhs_value}")
                return ", ".join(parts)
            agg = lhs if lhs_is_agg else rhs
            other = rhs if lhs_is_agg else lhs
            agg_guard, agg_value = _compile_aggregate_parts(aggregate=agg, **agg_ctx)
            if _is_var(other):
                if other not in bound_vars:
                    _raise_dataflow_or_runtime(
                        ast_gate_on=ast_gate_on,
                        message=f"ne variable must be bound before filter: {other}",
                        op="ne",
                    )
                # T2.3c P1 v7: aggregate is numeric; bound-var side MUST
                # also be numeric (int/time domain) — mirrors gt/ge/lt/le
                # precedent. Without this, `to_number(symbol)` of a
                # non-numeric bound var produces undefined Souffle DL.
                _assert_cmp_var_allowed(other, var_type_domains, "ne")
                other_expr = f"to_number({var_symbols[other]})"
            else:
                other_expr = _literal_to_cmp_int_text(other, "ne")
            return _compose_aggregate_numeric_cmp(
                guard_clause=agg_guard,
                value_expr=agg_value,
                op="!=",
                other_expr=other_expr,
                aggregate_on_left=lhs_is_agg,
            )
        return _compile_ne_filter(
            atom=atom,
            var_symbols=var_symbols,
            bound_vars=bound_vars,
            ast_gate_on=ast_gate_on,
        )

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
        lhs_is_agg = _is_aggregate(lhs)
        rhs_is_agg = _is_aggregate(rhs)

        # T2.3c: aggregate operand bypasses bound check for the aggregate
        # side (aggregate is always numeric per Souffle aggregator output;
        # aggregate-local vars stay private). Var/literal side follows
        # normal cmp side rules.
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

        op = _cmp_operator(kind)

        if lhs_is_agg or rhs_is_agg:
            agg_ctx = {
                "var_symbols": var_symbols,
                "outer_bound_vars": bound_vars,
                "pred_arities": pred_arities,
                "pred_type_domains": pred_type_domains,
                "var_type_domains": var_type_domains,
                "in_rel_values": in_rel_values,
                "not_rel_defs": not_rel_defs,
                "not_rel_namespace": not_rel_namespace,
                "ast_gate_on": ast_gate_on,
            }
            # Two-aggregate cmp
            if lhs_is_agg and rhs_is_agg:
                lhs_guard, lhs_value = _compile_aggregate_parts(aggregate=lhs, **agg_ctx)
                rhs_guard, rhs_value = _compile_aggregate_parts(aggregate=rhs, **agg_ctx)
                parts: list[str] = []
                if lhs_guard is not None:
                    parts.append(lhs_guard)
                if rhs_guard is not None:
                    parts.append(rhs_guard)
                parts.append(f"{lhs_value} {op} {rhs_value}")
                return ", ".join(parts)
            agg = lhs if lhs_is_agg else rhs
            other = rhs if lhs_is_agg else lhs
            agg_guard, agg_value = _compile_aggregate_parts(aggregate=agg, **agg_ctx)
            other_expr = _compile_cmp_side(other, var_symbols, kind)
            return _compose_aggregate_numeric_cmp(
                guard_clause=agg_guard,
                value_expr=agg_value,
                op=op,
                other_expr=other_expr,
                aggregate_on_left=lhs_is_agg,
            )

        lhs_expr = _compile_cmp_side(lhs, var_symbols, kind)
        rhs_expr = _compile_cmp_side(rhs, var_symbols, kind)
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
        key_args = tuple(var_symbols[var] for var in key_vars)
        rel_name = _not_rel_name(not_body, namespace=not_rel_namespace)
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
        rel_def = (key_args, tuple(body_term_groups))

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
        # T2.3c P2 v7: cmp operands cannot be raw atoms (atoms live at the
        # where-level, not inside operands). Any tuple operand is therefore
        # treated as aggregate-shaped for validation; unknown kinds get
        # rejected with "unsupported aggregate kind" per blueprint §5.7.5
        # Layer 1 structural contract.
        if isinstance(lhs, tuple):
            _validate_aggregate_atom_shape(lhs)
        if isinstance(rhs, tuple):
            _validate_aggregate_atom_shape(rhs)
        lhs_is_agg = _is_aggregate(lhs)
        rhs_is_agg = _is_aggregate(rhs)
        if not lhs_is_var and not rhs_is_var and not lhs_is_agg and not rhs_is_agg:
            raise WhereValidationError("eq must be var=literal or var=var or aggregate=...")
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

    if kind in {"ne", "gt", "ge", "lt", "le"}:
        if len(atom) != 3:
            raise WhereValidationError(f"{kind} atom must be ('{kind}', lhs, rhs)")
        _, lhs, rhs = atom
        # T2.3c P2 v7: same rationale as eq branch — any tuple cmp operand
        # is aggregate-shaped; unknown kind rejected here regardless of gate.
        if isinstance(lhs, tuple):
            _validate_aggregate_atom_shape(lhs)
        if isinstance(rhs, tuple):
            _validate_aggregate_atom_shape(rhs)
        lhs_is_agg = _is_aggregate(lhs)
        rhs_is_agg = _is_aggregate(rhs)
        if not _is_var(lhs) and not _is_var(rhs) and not lhs_is_agg and not rhs_is_agg:
            raise WhereValidationError(f"{kind} requires at least one variable or aggregate side")
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


def _validate_aggregate_atom_shape(aggregate: tuple[Any, ...]) -> None:
    """Layer 1 structural validation per blueprint §5.7.5.

    Mandatory regardless of FACTPY_WHERE_AST_VALIDATE gate state because
    the compile path itself cannot proceed on malformed aggregate shapes
    or non-C100 filter atom kinds (e.g., _ARITH_KINDS in aggregate filter
    would emit var-binding clauses Souffle aggregate body slots cannot
    accept).
    """
    if not isinstance(aggregate, tuple) or len(aggregate) != 3:
        raise WhereValidationError(
            "aggregate atom must be (kind, target_var, [filter_atoms])"
        )
    kind, target_var, filter_atoms = aggregate
    if kind not in _AGGREGATE_KINDS:
        raise WhereValidationError(f"unsupported aggregate kind: {kind}")
    if kind == "count":
        if target_var is not None:
            raise WhereValidationError("count aggregate target_var must be None")
    else:
        if not isinstance(target_var, str) or not target_var.startswith("$") or len(target_var) < 2:
            raise WhereValidationError(
                f"numeric aggregate target_var must be $-prefixed variable, got {target_var!r}"
            )
    if not isinstance(filter_atoms, list):
        raise WhereValidationError("aggregate filter must be list")
    for filter_atom in filter_atoms:
        if _is_aggregate(filter_atom):
            raise WhereValidationError("aggregate not allowed inside aggregate filter")
        if not isinstance(filter_atom, tuple) or not filter_atom or not isinstance(filter_atom[0], str):
            raise WhereValidationError("aggregate filter atom must be non-empty tuple with string kind")
        atom_kind = filter_atom[0]
        if atom_kind not in _AGGREGATE_FILTER_ATOM_KINDS:
            raise WhereValidationError(
                f"{atom_kind} not allowed inside aggregate filter (C100)"
            )
        # Recurse shape validation for sub-atoms via _validate_atom_subset
        # (which handles pred / eq / ne / in / gt / ge / lt / le / not shapes).
        _validate_atom_subset(filter_atom)


def _canonicalize_in_values(values: list[Any]) -> tuple[str, ...]:
    canonical = sorted({_literal_to_text(value) for value in values})
    if not canonical:
        raise WhereValidationError("in values must be non-empty")
    return tuple(canonical)


def _normalize_not_body_subset(not_body: Any) -> list[list[tuple[Any, ...]]]:
    if not isinstance(not_body, list) or not not_body:
        raise WhereValidationError("not body must be non-empty list")

    allowed_not_kinds = {"pred", "eq", "ne", "in", "gt", "ge", "lt", "le", *_ARITH_KINDS}

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


def _not_rel_name(not_body: list[tuple[Any, ...]], *, namespace: str | None = None) -> str:
    payload = json.dumps(
        [namespace, not_body],
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

    def walk_atom(atom: tuple[Any, ...]) -> None:
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
                    walk_atom(not_atom)
        elif atom[0] in {"eq", "ne", "gt", "ge", "lt", "le"}:
            # T2.3c §2.6b P2 v3: descend into aggregate operands so filter-
            # internal numeric cmp (e.g., gt($_agg1, 5)) sees the type domain
            # contributed by aggregate-filter pred atoms.
            for side in (atom[1], atom[2]):
                if _is_aggregate(side):
                    walk_aggregate(side)
            # When eq binds a var to an aggregate value (v_X = to_string(<agg>)),
            # the var carries a numeric value as symbol; mark int type domain
            # so subsequent gt/ge/lt/le on that var passes _assert_cmp_var_allowed.
            if atom[0] == "eq":
                lhs, rhs = atom[1], atom[2]
                if _is_aggregate(lhs) and _is_var(rhs):
                    out.setdefault(rhs, set()).add("int")
                elif _is_aggregate(rhs) and _is_var(lhs):
                    out.setdefault(lhs, set()).add("int")

    def walk_aggregate(aggregate: tuple[Any, ...]) -> None:
        _, target_var, filter_atoms = aggregate
        # Aggregate target_var is numeric per C102 (sum/min/max/mean require
        # numeric target; count has target_var=None).
        if (
            isinstance(target_var, str)
            and target_var.startswith("$")
            and len(target_var) >= 2
        ):
            out.setdefault(target_var, set()).add("int")
        for filter_atom in filter_atoms:
            walk_atom(filter_atom)

    for atom in body:
        walk_atom(atom)
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


def _compile_ne_filter(
    *,
    atom: tuple[Any, ...],
    var_symbols: dict[str, str],
    bound_vars: set[str],
    ast_gate_on: bool,
) -> str:
    _, lhs, rhs = atom
    lhs_is_var = _is_var(lhs)
    rhs_is_var = _is_var(rhs)
    if not lhs_is_var and not rhs_is_var:
        raise WhereValidationError("ne requires at least one variable side")
    if lhs_is_var and lhs not in bound_vars:
        _raise_dataflow_or_runtime(
            ast_gate_on=ast_gate_on,
            message=f"ne variable must be bound before filter: {lhs}",
            op="ne",
        )
    if rhs_is_var and rhs not in bound_vars:
        _raise_dataflow_or_runtime(
            ast_gate_on=ast_gate_on,
            message=f"ne variable must be bound before filter: {rhs}",
            op="ne",
        )
    lhs_expr = _symbol_for_var(var_symbols, lhs) if lhs_is_var else _literal_to_symbol(lhs)
    rhs_expr = _symbol_for_var(var_symbols, rhs) if rhs_is_var else _literal_to_symbol(rhs)
    return f"{lhs_expr} != {rhs_expr}"


def _compile_cmp_side(term: Any, var_symbols: dict[str, str], kind: str) -> str:
    """Compile one side of numeric cmp (gt/ge/lt/le) for var/literal only.

    Aggregate operand is NOT handled here — _compile_atom cmp branches
    dispatch aggregate via _compile_aggregate_parts directly so they can
    properly compose the guard clause for min/max/mean (which must appear
    as a peer body clause, not inside any cast wrap).
    """
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

    if kind == "ne":
        return _compile_ne_filter(
            atom=atom,
            var_symbols=var_symbols,
            bound_vars=local_bound_vars,
            ast_gate_on=ast_gate_on,
        )

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


def _compile_aggregate_parts(
    *,
    aggregate: tuple[Any, ...],
    var_symbols: dict[str, str],
    outer_bound_vars: set[str],
    pred_arities: dict[str, int],
    pred_type_domains: dict[str, list[str]],
    var_type_domains: dict[str, set[str]],
    in_rel_values: dict[str, tuple[str, ...]],
    not_rel_defs: dict[str, tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]],
    not_rel_namespace: str | None,
    ast_gate_on: bool,
) -> tuple[str | None, str]:
    """Compile aggregate tuple to (guard_clause_or_None, value_expr).

    Returns:
        guard_clause: For min/max/mean, returns `count : {same_body} > 0`
            so caller can prepend as peer body atom (NOT inside to_string
            wrap). For count/sum returns None (empty=0 is legal C101 value).
        value_expr: Bare numeric aggregate expression (e.g., `count : {body}`
            or `sum to_number(v_X) : {body}`). Caller decides to_string /
            to_number wrapping per blueprint §5.3.5 wrapper table.

    The guard MUST be emitted as a peer body atom (separate from value),
    NOT wrapped inside to_string with the value, because `to_string(...)`
    is a per-expression conversion and the guard is a per-clause filter.
    """
    kind, target_var, filter_atoms = aggregate
    # Aggregate scope per C104: local copy of bound_vars; filter-introduced
    # vars stay private to the aggregate body and do NOT leak back to outer.
    local_bound_vars = set(outer_bound_vars)
    body_terms: list[str] = []
    for filter_atom in filter_atoms:
        body_terms.append(
            _compile_filter_atom_within_aggregate(
                atom=filter_atom,
                var_symbols=var_symbols,
                local_bound_vars=local_bound_vars,
                pred_arities=pred_arities,
                pred_type_domains=pred_type_domains,
                var_type_domains=var_type_domains,
                in_rel_values=in_rel_values,
                not_rel_defs=not_rel_defs,
                not_rel_namespace=not_rel_namespace,
                ast_gate_on=ast_gate_on,
            )
        )
    body = ", ".join(body_terms)

    # Value clause per kind (bare numeric aggregate expression).
    if kind == "count":
        value_expr = f"count : {{ {body} }}"
    else:
        target_sym = _symbol_for_var(var_symbols, target_var)
        target_expr = f"to_number({target_sym})"
        value_expr = f"{kind} {target_expr} : {{ {body} }}"

    # min/max/mean: emit `count : {same_body} > 0` guard as peer clause
    # per blueprint §2.5 v2 lock. count/sum have no guard.
    guard_clause: str | None = None
    if kind in _AGGREGATE_GUARD_KINDS:
        guard_clause = f"count : {{ {body} }} > 0"

    return guard_clause, value_expr


def _compose_aggregate_eq_binding(
    *,
    other_var_token: str,
    var_symbols: dict[str, str],
    guard_clause: str | None,
    value_expr: str,
) -> str:
    """Compose eq-binding-to-unbound-var DL: `<guard>?, v_X = to_string(<value>)`.

    Guard appears as peer body clause BEFORE the binding; the binding wraps
    only the value expression in to_string for symbol-domain consistency.
    """
    binding = f"{var_symbols[other_var_token]} = to_string({value_expr})"
    if guard_clause is None:
        return binding
    return f"{guard_clause}, {binding}"


def _compose_aggregate_numeric_cmp(
    *,
    guard_clause: str | None,
    value_expr: str,
    op: str,
    other_expr: str,
    aggregate_on_left: bool,
) -> str:
    """Compose numeric cmp DL: `<guard>?, <value_or_other> <op> <value_or_other>`.

    Guard appears as peer body clause; cmp expression uses bare numeric.
    """
    if aggregate_on_left:
        cmp = f"{value_expr} {op} {other_expr}"
    else:
        cmp = f"{other_expr} {op} {value_expr}"
    if guard_clause is None:
        return cmp
    return f"{guard_clause}, {cmp}"


def _compile_filter_atom_within_aggregate(
    *,
    atom: tuple[Any, ...],
    var_symbols: dict[str, str],
    local_bound_vars: set[str],
    pred_arities: dict[str, int],
    pred_type_domains: dict[str, list[str]],
    var_type_domains: dict[str, set[str]],
    in_rel_values: dict[str, tuple[str, ...]],
    not_rel_defs: dict[str, tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]],
    not_rel_namespace: str | None,
    ast_gate_on: bool,
) -> str:
    """Compile a single filter atom inside aggregate body.

    Differences from _compile_atom:
    - No witness symbols emitted (aggregate body has no rule-level witness)
    - Operates on local_bound_vars (scope isolation per blueprint §2.4)
    - C100 filter atom kinds enforced upstream by _validate_aggregate_atom_shape
    - `not` body uses synthetic not-relation extraction pattern (same as outer)
    """
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

    if kind == "ne":
        return _compile_ne_filter(
            atom=atom,
            var_symbols=var_symbols,
            bound_vars=local_bound_vars,
            ast_gate_on=ast_gate_on,
        )

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

    if kind == "not":
        # Synthetic not-relation extraction pattern (mirror outer _compile_atom not branch).
        # Aggregate-internal not body shares not_rel_defs with outer relation block,
        # but uses a distinct namespace to avoid collision (aggregate body has its own
        # scope, so even an identically-structured not body is semantically different).
        _, not_body = atom
        not_bodies = _normalize_not_body_subset(not_body)
        vars_in_not_body: set[str] = set()
        for branch in not_bodies:
            for not_atom in branch:
                if _is_aggregate(not_atom):
                    raise WhereValidationError(
                        "aggregate not allowed inside not body in aggregate filter"
                    )
                vars_in_not_body.update(_vars_in_atom(not_atom, include_not_body_vars=True))
        if not any(var in local_bound_vars for var in vars_in_not_body):
            _raise_dataflow_or_runtime(
                ast_gate_on=ast_gate_on,
                message="not body must reference at least one bound variable",
                op="not",
            )

        # Key vars: aggregate-local vars referenced inside not body that are also
        # bound in the aggregate's local scope at this point.
        key_vars = tuple(sorted(var for var in vars_in_not_body if var in local_bound_vars))
        key_args = tuple(var_symbols[var] for var in key_vars)
        # Namespace: distinguish aggregate-internal not bodies from outer-where ones.
        agg_namespace = f"agg:{not_rel_namespace or ''}"
        rel_name = _not_rel_name(not_body, namespace=agg_namespace)
        body_term_groups: list[tuple[str, ...]] = []
        for branch in not_bodies:
            branch_local_bound_vars = set(local_bound_vars)
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
                        local_bound_vars=branch_local_bound_vars,
                        var_type_domains=var_type_domains,
                        in_rel_values=in_rel_values,
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
        rel_def = (key_args, tuple(body_term_groups))

        existing = not_rel_defs.get(rel_name)
        if existing is None:
            not_rel_defs[rel_name] = rel_def
        elif existing != rel_def:
            raise WhereValidationError("not relation name collision detected")

        if key_vars:
            rel_args = ", ".join(var_symbols[var] for var in key_vars)
            return f"!{rel_name}({rel_args})"
        return f"!{rel_name}()"

    raise WhereValidationError(f"{kind} not allowed inside aggregate filter (C100)")


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


def _is_aggregate(value: Any) -> bool:
    """Identify aggregate-tuple operand inside cmp atoms.

    Aggregate IR shape per T2.3a substrate + T2.3b SDK lowering:
    `(kind, target_var, filter_atoms)` where kind ∈ _AGGREGATE_KINDS.
    """
    return (
        isinstance(value, tuple)
        and len(value) >= 1
        and isinstance(value[0], str)
        and value[0] in _AGGREGATE_KINDS
    )


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
        # T2.3c: aggregate operand contributes ZERO outer vars per blueprint
        # §5.5 + §2.6. Correlated outer vars are bound by their original
        # outer-scope atom independently; aggregate-local vars stay private
        # per C104. _is_aggregate(side) intentionally produces no .add()
        # below — explicit pass to surface the design choice.
    elif kind == "in":
        _, var, _ = atom
        if _is_var(var):
            found.add(var)
    elif kind in {"ne", "gt", "ge", "lt", "le"}:
        _, lhs, rhs = atom
        if _is_var(lhs):
            found.add(lhs)
        if _is_var(rhs):
            found.add(rhs)
        # T2.3c: aggregate operand contributes ZERO outer vars (same rationale
        # as eq branch above).
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
