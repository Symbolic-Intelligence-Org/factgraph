from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from kernel.core.rules.rule_ast import QueryRuleAst, RuleASTError, parse_query_rule_ir_to_ast

from .dsl import Query, ReturnContractEntry
from .error_codes import QUERY_INVALID_ROW_FORMAT
from .errors import SDKStoreError


@dataclass(frozen=True)
class QueryPlan:
    query_id: str
    rule_ast: QueryRuleAst
    return_contract: tuple[ReturnContractEntry, ...]
    return_mode: str
    on_missing: str
    on_type_mismatch: str


def lower_query(
    query: Query,
    *,
    schema_ir: dict[str, Any],
    schema_digest: str,
    return_mode: str = "dict",
) -> QueryPlan:
    if not isinstance(query, Query):
        raise SDKStoreError("query must be Query", path="$.run.obj")
    if return_mode not in {"dict", "instance"}:
        raise SDKStoreError(
            "Query return_mode must be 'dict' or 'instance'",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.query.return_mode",
        )
    if not isinstance(schema_ir, dict):
        raise SDKStoreError("schema_ir must be dict", path="$.store.schema_ir")
    if not isinstance(schema_digest, str) or not schema_digest:
        raise SDKStoreError("schema_digest must be non-empty string", path="$.store.schema_digest")

    return_contract = tuple(query.return_contract)
    _validate_field_projection_contract(return_contract, schema_ir=schema_ir)
    if return_mode == "instance":
        _validate_instance_return_contract(return_contract)
    where_ir = query.where_ir

    query_id = _build_query_id(
        return_contract=return_contract,
        where_ir=where_ir,
        return_mode=return_mode,
        on_missing=query.on_missing,
        on_type_mismatch=query.on_type_mismatch,
        schema_digest=schema_digest,
    )
    rule_ir = {
        "rule_id": query_id,
        "version": "runtime",
        "select_vars": [entry.var for entry in return_contract],
        "where": where_ir,
    }
    try:
        rule_ast = parse_query_rule_ir_to_ast(rule_ir)
    except RuleASTError as exc:
        raise SDKStoreError(
            f"failed to lower Query into QueryRuleAst: {exc}",
            path=exc.path or "$.query_rule",
        ) from exc

    return QueryPlan(
        query_id=query_id,
        rule_ast=rule_ast,
        return_contract=return_contract,
        return_mode=return_mode,
        on_missing=query.on_missing,
        on_type_mismatch=query.on_type_mismatch,
    )


def _build_query_id(
    *,
    return_contract: tuple[ReturnContractEntry, ...],
    where_ir: list[Any],
    return_mode: str,
    on_missing: str,
    on_type_mismatch: str,
    schema_digest: str,
) -> str:
    canonical_payload = {
        "head_ir": _serialize_return_contract(return_contract),
        "where_ir": _to_jsonable(where_ir),
        "return_mode": return_mode,
        "on_missing": on_missing,
        "on_type_mismatch": on_type_mismatch,
        "schema_digest": schema_digest,
    }
    payload_bytes = _canonical_json_bytes(canonical_payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()[:16]
    return f"__query__:{digest}"


def _serialize_return_contract(return_contract: tuple[ReturnContractEntry, ...]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in return_contract:
        out.append(
            {
                "var": entry.var,
                "alias": entry.alias,
                "entity_type": entry.entity_type,
                "field_path": entry.field_path,
            }
        )
    return out


def _validate_field_projection_contract(
    return_contract: tuple[ReturnContractEntry, ...],
    *,
    schema_ir: dict[str, Any],
) -> None:
    pred_by_field = _index_predicates_by_owner_field(schema_ir)
    for idx, entry in enumerate(return_contract):
        if entry.field_path is None:
            continue
        entity_type, field_name = _split_field_path(entry.field_path, path=f"$.head[{idx}]")
        pred = pred_by_field.get((entity_type, field_name))
        if pred is None:
            raise SDKStoreError(
                f"Query field head does not match schema field: {entry.field_path}",
                path=f"$.head[{idx}]",
            )
        cardinality = pred.get("cardinality")
        if cardinality != "single":
            raise SDKStoreError(
                "Query field head only supports single fields",
                path=f"$.head[{idx}]",
            )


def _validate_instance_return_contract(
    return_contract: tuple[ReturnContractEntry, ...],
) -> None:
    if len(return_contract) != 1:
        raise SDKStoreError(
            "Query return_mode='instance' requires exactly one Entity(var) item in head",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.head",
        )
    entry = return_contract[0]
    if entry.entity_type is None or entry.field_path is not None:
        raise SDKStoreError(
            "Query return_mode='instance' requires head=[Entity(var)]",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.head[0]",
        )


def _index_predicates_by_owner_field(schema_ir: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    predicates = schema_ir.get("predicates")
    if not isinstance(predicates, list):
        raise SDKStoreError("schema_ir.predicates must be list", path="$.store.schema_ir.predicates")
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        owner_type = pred.get("owner_type")
        py_field_name = pred.get("py_field_name")
        if not isinstance(owner_type, str) or not owner_type:
            continue
        if not isinstance(py_field_name, str) or not py_field_name:
            continue
        out[(owner_type, py_field_name)] = pred
    return out


def _split_field_path(field_path: str, *, path: str) -> tuple[str, str]:
    if not isinstance(field_path, str):
        raise SDKStoreError("Query field_path must be string", path=path)
    parts = field_path.split(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise SDKStoreError("Query field_path must be '<Entity>.<field>'", path=path)
    return parts[0], parts[1]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(_to_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    return value
