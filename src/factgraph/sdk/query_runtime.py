from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from factgraph.application.protocol import (
    EntitySnapshotDTO,
    ErrorDTO,
    FieldPath,
    QueryReturnContract,
    QueryReturnSlot,
    QueryRuntimeRequest,
)
from factgraph.application.query_runtime import execute_query
from factgraph.core.rules.rule_ast import lower_query_rule_ast_to_ir
from factgraph.core.rules.where_eval import WhereValidationError

from .dsl import ReturnContractEntry
from .error_codes import QUERY_INVALID_ROW_FORMAT, QUERY_MISSING_REF, QUERY_TYPE_MISMATCH
from .errors import SDKStoreError
from .facade import AssertionView, EntitySnapshot, _dto_to_sdk_snapshot
from .query_lower import QueryPlan

if TYPE_CHECKING:
    from .store import SDKStore


@dataclass(frozen=True)
class _EntityFieldSpec:
    field_name: str
    pred_id: str
    cardinality: str


def execute_query_plan(sdk: SDKStore, plan: QueryPlan, *, registry: Any | None = None) -> list[Any]:
    where_ir = lower_query_rule_ast_to_ir(plan.rule_ast)["where"]
    request = QueryRuntimeRequest(
        entity_type=_primary_entity_type(plan.return_contract),
        where_ir=where_ir,
        return_contract=QueryReturnContract(
            slots=tuple(_build_app_slot(entry) for entry in plan.return_contract),
        ),
        on_missing=plan.on_missing,
        on_type_mismatch=plan.on_type_mismatch,
        query_id=plan.query_id,
    )
    try:
        response = execute_query(
            request,
            store=sdk._store,
            index=sdk._application_schema_index,
            registry=registry,
        )
    except WhereValidationError as exc:
        path = getattr(exc, "path", None) or "$.query_rule.where"
        raise SDKStoreError(f"query where evaluation failed: {exc}", path=path) from exc

    if response.errors:
        raise _sdk_error_from_app_dto(response.errors[0], plan.query_id)

    rows = [
        _map_app_row_to_sdk_row(row, plan.return_contract, sdk)
        for row in response.rows
    ]
    rows = _dedup_rows(rows)
    if plan.return_mode == "dict":
        return rows
    if plan.return_mode == "instance":
        return _rows_to_instances(rows, plan.return_contract)
    raise SDKStoreError(
        f"unsupported Query return_mode: {plan.return_mode!r}",
        code=QUERY_INVALID_ROW_FORMAT,
        path="$.query.return_mode",
    )


def _build_app_slot(entry: ReturnContractEntry) -> QueryReturnSlot:
    if entry.entity_type is not None:
        return QueryReturnSlot(
            alias=entry.alias,
            kind="entity",
            var=entry.var,
            entity_type=entry.entity_type,
        )
    return QueryReturnSlot(
        alias=entry.alias,
        kind="scalar",
        var=entry.var,
        field_path=_parse_field_path(entry.field_path),
    )


def _parse_field_path(field_path: str | None) -> FieldPath:
    if not isinstance(field_path, str) or not field_path:
        raise SDKStoreError("Query scalar return slot requires field_path", path="$.query.return_contract")
    entity_type, sep, field_name = field_path.rpartition(".")
    if not sep or not entity_type or not field_name:
        raise SDKStoreError(
            "Query field_path must be '<Entity>.<field>'",
            path="$.query.return_contract",
        )
    return FieldPath(entity_type=entity_type, field_name=field_name)


def _primary_entity_type(return_contract: tuple[ReturnContractEntry, ...]) -> str:
    for entry in return_contract:
        if entry.entity_type is not None:
            return entry.entity_type
    return "Query"


def _sdk_error_from_app_dto(error: ErrorDTO, query_id: str) -> SDKStoreError:
    digest = query_id.split(":", 1)[1] if ":" in query_id else query_id
    code = {
        "QUERY_TYPE_MISMATCH": QUERY_TYPE_MISMATCH,
        "QUERY_MISSING_BINDING": QUERY_MISSING_REF,
        "QUERY_UNSUPPORTED_SLOT": QUERY_INVALID_ROW_FORMAT,
    }.get(error.code, error.code)
    return SDKStoreError(
        f"query@{digest}: {error.message}",
        code=code,
        path=_sdk_path_from_app_path(error.path),
    )


def _sdk_path_from_app_path(path: tuple[str, ...]) -> str:
    if not path:
        return "$.query"
    if len(path) >= 3 and path[:2] == ("return_contract", "slots"):
        return f"$.query.return_contract.{path[2]}"
    return "$.query." + ".".join(path)


def _map_app_row_to_sdk_row(
    row: dict[str, Any],
    return_contract: tuple[ReturnContractEntry, ...],
    sdk: SDKStore,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for entry in return_contract:
        value = row.get(entry.alias)
        if entry.entity_type is None:
            out[entry.alias] = value
            continue
        if value is None:
            out[entry.alias] = None
            continue
        if not isinstance(value, EntitySnapshotDTO):
            raise SDKStoreError(
                f"query result slot {entry.alias!r} expected EntitySnapshotDTO",
                code=QUERY_TYPE_MISMATCH,
                path=f"$.run.result.{entry.alias}",
            )
        entity_cls = _entity_cls_for_type(sdk, entry.entity_type)
        snapshot = _dto_to_sdk_snapshot(
            value,
            sdk=sdk,
            entity_cls=entity_cls,
        )
        out[entry.alias] = _ensure_query_field_assertions(
            snapshot,
            sdk=sdk,
            entity_type=entry.entity_type,
        )
    return out


def _ensure_query_field_assertions(
    snapshot: EntitySnapshot,
    *,
    sdk: SDKStore,
    entity_type: str,
) -> EntitySnapshot:
    field_map = object.__getattribute__(snapshot.assertions, "_field_map")
    if field_map:
        return snapshot
    _, field_specs = _entity_field_specs_for_type(sdk, entity_type)
    field_assertions = {
        spec.field_name: AssertionView(
            entity_type=entity_type,
            field_name=spec.field_name,
            cardinality=spec.cardinality,
            active_records=(),
            history_records=(),
        )
        for spec in field_specs
    }
    field_values = object.__getattribute__(snapshot, "_field_values")
    return EntitySnapshot(
        ref=snapshot.ref,
        entity_type=snapshot.entity_type,
        field_values=field_values,
        field_assertions=field_assertions,
        identity_values=None,
        identity_available=False,
    )


def _dedup_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for row in rows:
        key = _row_dedup_key(row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _rows_to_instances(
    rows: list[dict[str, Any]],
    return_contract: tuple[ReturnContractEntry, ...],
) -> list[Any]:
    if len(return_contract) != 1:
        raise SDKStoreError(
            "Query return_mode='instance' requires exactly one Entity(var) item in head",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.query.return_contract",
        )
    entry = return_contract[0]
    if entry.entity_type is None or entry.field_path is not None:
        raise SDKStoreError(
            "Query return_mode='instance' requires head=[Entity(var)]",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.query.return_contract[0]",
        )
    alias = entry.alias
    out: list[Any] = []
    for idx, row in enumerate(rows):
        if alias not in row:
            raise SDKStoreError(
                f"query row missing required alias: {alias}",
                path=f"$.run.result[{idx}]",
            )
        out.append(row[alias])
    return out


def _row_dedup_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple((key, _to_hashable(value)) for key, value in row.items())


def _to_hashable(value: Any) -> Any:
    if isinstance(value, EntitySnapshot):
        return ("entity_snapshot", value.entity_type, value.ref)
    if isinstance(value, tuple):
        return tuple(_to_hashable(item) for item in value)
    if isinstance(value, list):
        return tuple(_to_hashable(item) for item in value)
    if isinstance(value, dict):
        return tuple((str(key), _to_hashable(item)) for key, item in sorted(value.items(), key=lambda kv: str(kv[0])))
    try:
        hash(value)
        return value
    except TypeError:
        return ("repr", repr(value))


def _entity_cls_for_type(sdk: SDKStore, entity_type: str) -> type:
    for entity_cls, spec in sdk._entity_spec_by_class.items():
        if spec.get("entity_type") == entity_type:
            return entity_cls
    raise SDKStoreError(
        f"unknown entity type in Query contract: {entity_type}",
        path="$.query.return_contract",
    )


def _entity_field_specs_for_type(sdk: SDKStore, entity_type: str) -> tuple[str | None, list[_EntityFieldSpec]]:
    predicates = sdk.schema_ir.get("predicates")
    if not isinstance(predicates, list):
        raise SDKStoreError("schema_ir.predicates must be list", path="$.store.schema_ir.predicates")

    exists_pred_id: str | None = None
    field_specs: dict[str, _EntityFieldSpec] = {}
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        if pred.get("owner_type") != entity_type:
            continue
        pred_id = pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if pred.get("is_entity_exists") is True:
            exists_pred_id = pred_id
            continue
        field_name = pred.get("py_field_name")
        if not isinstance(field_name, str) or not field_name:
            continue
        field_specs[field_name] = _EntityFieldSpec(
            field_name=field_name,
            pred_id=pred_id,
            cardinality=str(pred.get("cardinality", "single")),
        )

    ordered = [field_specs[name] for name in sorted(field_specs)]
    return exists_pred_id, ordered
