from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from factpy_kernel.core.rules.rule_ast import lower_query_rule_ast_to_ir
from factpy_kernel.core.rules.where_eval import WhereValidationError, evaluate_where
from factpy_kernel.core.view.projector import project_view_facts

from .dsl import ReturnContractEntry
from .error_codes import QUERY_MISSING_REF, QUERY_TYPE_MISMATCH
from .errors import SDKStoreError
from .facade import DimensionedValue, EntitySnapshot, FieldAssertions
from .query_lower import QueryPlan

if TYPE_CHECKING:
    from .store import SDKStore


@dataclass(frozen=True)
class _EntityFieldSpec:
    field_name: str
    pred_id: str
    cardinality: str
    dims_names: tuple[str, ...]


def execute_query_plan(sdk: "SDKStore", plan: QueryPlan) -> list[dict[str, Any]]:
    view_facts = project_view_facts(sdk.ledger, sdk.schema_ir, temporal_view=plan.temporal_view)
    where_ir = lower_query_rule_ast_to_ir(plan.rule_ast)["where"]
    try:
        bindings = evaluate_where(view_facts, where_ir)
    except WhereValidationError as exc:
        path = getattr(exc, "path", None) or "$.query_rule.where"
        raise SDKStoreError(f"query where evaluation failed: {exc}", path=path) from exc

    buckets = _extract_refs(bindings, plan.return_contract)
    hydrate_map = _batch_hydrate(
        sdk,
        buckets,
        temporal_view=plan.temporal_view,
        view_facts=view_facts,
    )
    return _apply_contract(
        bindings,
        hydrate_map,
        plan.return_contract,
        on_missing=plan.on_missing,
        on_type_mismatch=plan.on_type_mismatch,
        query_id=plan.query_id,
    )


def _extract_refs(
    bindings: list[dict[str, Any]],
    return_contract: tuple[ReturnContractEntry, ...],
) -> dict[str, set[str]]:
    buckets: dict[str, set[str]] = {}
    for binding in bindings:
        for entry in return_contract:
            if entry.entity_type is None:
                continue
            raw = binding.get(entry.var)
            if _is_valid_entity_ref_for_type(raw, entry.entity_type):
                buckets.setdefault(entry.entity_type, set()).add(raw)
    return buckets


def _batch_hydrate(
    sdk: "SDKStore",
    buckets: dict[str, set[str]],
    *,
    temporal_view: str,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> dict[tuple[str, str], EntitySnapshot | None]:
    del temporal_view
    out: dict[tuple[str, str], EntitySnapshot | None] = {}
    entity_cls_by_type = _entity_class_by_type(sdk)

    for entity_type, refs in buckets.items():
        if entity_cls_by_type.get(entity_type) is None:
            raise SDKStoreError(
                f"unknown entity type in Query contract: {entity_type}",
                path="$.query.return_contract",
            )
        if not refs:
            continue

        exists_pred_id, field_specs = _entity_field_specs_for_type(sdk, entity_type)
        ref_set = set(refs)
        visible_refs: set[str] = set()

        if exists_pred_id is not None:
            for row in view_facts.get(exists_pred_id, []):
                if not row:
                    continue
                e_ref = row[0]
                if isinstance(e_ref, str) and e_ref in ref_set:
                    visible_refs.add(e_ref)

        rows_by_field_ref: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
        for spec in field_specs:
            for row in view_facts.get(spec.pred_id, []):
                if not row:
                    continue
                e_ref = row[0]
                if not isinstance(e_ref, str) or e_ref not in ref_set:
                    continue
                visible_refs.add(e_ref)
                rows_by_field_ref.setdefault((spec.field_name, e_ref), []).append(row)

        for e_ref in sorted(ref_set):
            key = (entity_type, e_ref)
            if e_ref not in visible_refs:
                out[key] = None
                continue

            field_values: dict[str, Any] = {}
            field_assertions: dict[str, FieldAssertions] = {}
            for spec in field_specs:
                rows = rows_by_field_ref.get((spec.field_name, e_ref), [])
                rows_sorted = sorted(rows, key=lambda row: tuple(str(cell) for cell in row))
                field_values[spec.field_name] = _current_value_from_rows(
                    rows_sorted,
                    cardinality=spec.cardinality,
                    dims_names=list(spec.dims_names),
                )
                field_assertions[spec.field_name] = FieldAssertions(
                    field_name=spec.field_name,
                    cardinality=spec.cardinality,
                    has_dims=bool(spec.dims_names),
                    chosen_record=None,
                    active_records=tuple(),
                    history_records=tuple(),
                )

            out[key] = EntitySnapshot(
                ref=e_ref,
                entity_type=entity_type,
                field_values=field_values,
                field_assertions=field_assertions,
                identity_values={},
                identity_available=False,
            )

    return out


def _apply_contract(
    bindings: list[dict[str, Any]],
    hydrate_map: dict[tuple[str, str], EntitySnapshot | None],
    return_contract: tuple[ReturnContractEntry, ...],
    *,
    on_missing: str,
    on_type_mismatch: str,
    query_id: str,
) -> list[dict[str, Any]]:
    digest = query_id.split(":", 1)[1] if ":" in query_id else query_id
    out: list[dict[str, Any]] = []

    for row_idx, binding in enumerate(bindings):
        rendered: dict[str, Any] = {}
        skip_row = False

        for entry in return_contract:
            if entry.entity_type is None:
                rendered[entry.alias] = binding.get(entry.var)
                continue

            value = binding.get(entry.var)
            path = f"$.run.result[{row_idx}].{entry.alias}"
            classification = _classify_entity_binding(value, expected_entity_type=entry.entity_type)
            if classification != "ok":
                action = _resolve_policy_action(on_type_mismatch, policy_name="on_type_mismatch")
                if action == "skip":
                    skip_row = True
                    break
                if action == "null":
                    rendered[entry.alias] = None
                    continue
                raise SDKStoreError(
                    f"query@{digest} type mismatch for '{entry.alias}': expected entity_ref<{entry.entity_type}>",
                    code=QUERY_TYPE_MISMATCH,
                    path=path,
                )

            assert isinstance(value, str)
            snapshot = hydrate_map.get((entry.entity_type, value))
            if snapshot is None:
                action = _resolve_policy_action(on_missing, policy_name="on_missing")
                if action == "skip":
                    skip_row = True
                    break
                if action == "null":
                    rendered[entry.alias] = None
                    continue
                raise SDKStoreError(
                    f"query@{digest} missing entity for '{entry.alias}': {value}",
                    code=QUERY_MISSING_REF,
                    path=path,
                )

            rendered[entry.alias] = snapshot

        if skip_row:
            continue
        out.append(rendered)

    return _dedup_rows(out)


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


def _row_dedup_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple((key, _to_hashable(value)) for key, value in row.items())


def _to_hashable(value: Any) -> Any:
    if isinstance(value, EntitySnapshot):
        return ("entity_snapshot", value.entity_type, value.ref)
    if isinstance(value, DimensionedValue):
        return (
            "dimensioned",
            _to_hashable(value.value),
            tuple((key, _to_hashable(dim_value)) for key, dim_value in sorted(value.dims.items())),
        )
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


def _resolve_policy_action(value: str, *, policy_name: str) -> str:
    if value not in {"error", "skip", "null"}:
        raise SDKStoreError(
            f"Query {policy_name} must be one of: error|skip|null",
            path=f"$.query.{policy_name}",
        )
    return value


def _classify_entity_binding(value: Any, *, expected_entity_type: str) -> str:
    if not isinstance(value, str):
        return "type_mismatch"
    ref_entity_type = _entity_type_from_ref(value)
    if ref_entity_type is None:
        return "type_mismatch"
    if ref_entity_type != expected_entity_type:
        return "type_mismatch"
    return "ok"


def _is_valid_entity_ref_for_type(value: Any, expected_entity_type: str) -> bool:
    return _classify_entity_binding(value, expected_entity_type=expected_entity_type) == "ok"


def _entity_type_from_ref(value: str) -> str | None:
    if not value.startswith("idref_v1:"):
        return None
    parts = value.split(":", 2)
    if len(parts) != 3:
        return None
    _, entity_type, digest = parts
    if not entity_type or not digest:
        return None
    return entity_type


def _entity_class_by_type(sdk: "SDKStore") -> dict[str, type]:
    out: dict[str, type] = {}
    for entity_cls, spec in sdk._entity_spec_by_class.items():
        entity_type = spec.get("entity_type")
        if isinstance(entity_type, str) and entity_type:
            out[entity_type] = entity_cls
    return out


def _entity_field_specs_for_type(sdk: "SDKStore", entity_type: str) -> tuple[str | None, list[_EntityFieldSpec]]:
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
        dims = pred.get("dims")
        if not isinstance(dims, list):
            dims = []
        dims_names = tuple(dim for dim in dims if isinstance(dim, str))
        field_specs[field_name] = _EntityFieldSpec(
            field_name=field_name,
            pred_id=pred_id,
            cardinality=str(pred.get("cardinality", "functional")),
            dims_names=dims_names,
        )

    ordered = [field_specs[name] for name in sorted(field_specs)]
    return exists_pred_id, ordered


def _current_value_from_rows(rows: list[tuple[Any, ...]], *, cardinality: str, dims_names: list[str]) -> Any:
    if not dims_names:
        if cardinality == "functional":
            if not rows:
                return None
            return rows[0][-1]
        return tuple(row[-1] for row in rows)

    return tuple(
        DimensionedValue(
            value=row[-1],
            dims={name: row[idx + 1] for idx, name in enumerate(dims_names)},
        )
        for row in rows
    )
