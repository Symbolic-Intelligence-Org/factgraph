from __future__ import annotations

from typing import Any, Iterable

from factpy.core.policy.active import is_active
from factpy.core.store import Store
from factpy.core.store.ledger import Claim, Ledger
from factpy.core.view.projector import project_view_facts

from .protocol import (
    AssertionRecordDTO,
    EntityReadRequest,
    EntityReadResponse,
    EntityRef,
    EntitySnapshotDTO,
    ErrorDTO,
    FieldAssertionsDTO,
    FieldFilterValue,
    FieldPath,
    FieldValue,
    FieldValueDTO,
    WarningDTO,
)
from .schema_runtime import (
    FieldTypeInfo,
    SchemaIndex,
    SchemaResolutionError,
    entity_info,
    entity_type_from_ref,
    field_predicate,
    field_value_type,
    materialize_identity,
    resolve_selector,
)


class EntityViewError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        path: tuple[str, ...] = (),
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = tuple(path)
        self.details = dict(details or {})

    def to_error_dto(self) -> ErrorDTO:
        return ErrorDTO(
            code=self.code,
            message=str(self),
            path=self.path,
            details=self.details,
        )

    def to_warning_dto(self) -> WarningDTO:
        return WarningDTO(
            code=self.code,
            message=str(self),
            path=self.path,
            details=self.details,
        )


def hydrate_entity(
    e_ref: str,
    *,
    store: Store,
    index: SchemaIndex,
    include_assertions: bool = False,
    include_history: bool = False,
) -> EntitySnapshotDTO:
    view_facts = project_view_facts(store.ledger, store.schema_ir)
    return _hydrate_entity_snapshot(
        e_ref,
        store=store,
        index=index,
        view_facts=view_facts,
        ref_cache={},
        include_assertions=include_assertions,
        include_history=include_history,
    )


def hydrate_entities(
    e_refs: Iterable[str],
    *,
    store: Store,
    index: SchemaIndex,
    include_assertions: bool = False,
    include_history: bool = False,
) -> list[EntitySnapshotDTO]:
    view_facts = project_view_facts(store.ledger, store.schema_ir)
    ref_cache: dict[str, EntityRef] = {}
    return [
        _hydrate_entity_snapshot(
            e_ref,
            store=store,
            index=index,
            view_facts=view_facts,
            ref_cache=ref_cache,
            include_assertions=include_assertions,
            include_history=include_history,
        )
        for e_ref in e_refs
    ]


def execute_read_request(
    request: EntityReadRequest,
    *,
    store: Store,
    index: SchemaIndex,
) -> EntityReadResponse:
    temporal_error = _unsupported_temporal_error(request)
    if temporal_error is not None:
        return EntityReadResponse(
            mode=request.mode,
            entity_type=request.entity_type,
            errors=(temporal_error,),
        )

    try:
        _validate_filter_paths(request, index=index)
    except (SchemaResolutionError, EntityViewError) as exc:
        return EntityReadResponse(
            mode=request.mode,
            entity_type=request.entity_type,
            errors=(_to_error_dto(exc),),
        )

    view_facts = project_view_facts(store.ledger, store.schema_ir)
    ref_cache: dict[str, EntityRef] = {}

    if request.mode == "get":
        assert request.selector is not None
        try:
            selector_ref = resolve_selector(request.selector, index=index)
            snapshot = _hydrate_entity_snapshot(
                selector_ref.encoded_ref or e_ref_from_entity_ref(selector_ref, index=index),
                store=store,
                index=index,
                view_facts=view_facts,
                ref_cache=ref_cache,
                known_ref=selector_ref,
                include_assertions=request.effective_include_assertions,
                include_history=request.include_history,
            )
            if not _snapshot_matches_filters(snapshot, request.field_filters):
                raise EntityViewError(
                    f"no entity matches selector for {request.entity_type}",
                    code="ENTITY_NOT_FOUND",
                    path=("selector",),
                    details={"entity_type": request.entity_type},
                )
            return EntityReadResponse(
                mode="get",
                entity_type=request.entity_type,
                items=(snapshot,),
            )
        except (SchemaResolutionError, EntityViewError) as exc:
            return EntityReadResponse(
                mode="get",
                entity_type=request.entity_type,
                errors=(_to_error_dto(exc),),
            )

    warnings: list[WarningDTO] = []
    items: list[EntitySnapshotDTO] = []
    for e_ref in sorted(_enumerate_entity_refs(request.entity_type, view_facts=view_facts, index=index)):
        try:
            snapshot = _hydrate_entity_snapshot(
                e_ref,
                store=store,
                index=index,
                view_facts=view_facts,
                ref_cache=ref_cache,
                include_assertions=request.effective_include_assertions,
                include_history=request.include_history,
            )
        except (SchemaResolutionError, EntityViewError) as exc:
            warning = _to_warning_dto(exc, e_ref=e_ref)
            warnings.append(warning)
            continue
        if not _snapshot_matches_filters(snapshot, request.field_filters):
            continue
        items.append(snapshot)
        if request.limit is not None and len(items) >= request.limit:
            break

    return EntityReadResponse(
        mode="find",
        entity_type=request.entity_type,
        items=tuple(items),
        warnings=tuple(warnings),
    )


def e_ref_from_entity_ref(ref: EntityRef, *, index: SchemaIndex) -> str:
    from .schema_runtime import encode_entity_ref

    return encode_entity_ref(ref, index=index)


def _hydrate_entity_snapshot(
    e_ref: str,
    *,
    store: Store,
    index: SchemaIndex,
    view_facts: dict[str, list[tuple[Any, ...]]],
    ref_cache: dict[str, EntityRef],
    known_ref: EntityRef | None = None,
    include_assertions: bool = False,
    include_history: bool = False,
) -> EntitySnapshotDTO:
    entity_type = entity_type_from_ref(e_ref)
    if entity_type is None:
        raise EntityViewError(
            f"invalid entity_ref token: {e_ref!r}",
            code="INVALID_ENTITY_REF",
            path=("ref",),
            details={"e_ref": e_ref},
        )
    entity_info(index, entity_type)
    if not _entity_visible(entity_type, e_ref, view_facts=view_facts, index=index):
        raise EntityViewError(
            f"entity not found in current view: {entity_type}",
            code="ENTITY_NOT_FOUND",
            path=("ref",),
            details={"entity_type": entity_type, "e_ref": e_ref},
        )

    ref = known_ref or _recover_entity_ref(e_ref, view_facts=view_facts, index=index, ref_cache=ref_cache)
    ref_cache[e_ref] = ref

    fields: dict[str, FieldValueDTO] = {}
    assertions: dict[str, FieldAssertionsDTO] = {}
    for field_name in _ordered_non_identity_fields(entity_type, index=index):
        field_type = field_value_type(index, entity_type, field_name)
        pred_info = field_predicate(index, entity_type, field_name)
        rows = [row for row in view_facts.get(pred_info.pred_id, []) if row and row[0] == e_ref]
        fields[field_name] = FieldValueDTO(
            field=FieldPath(entity_type=entity_type, field_name=field_name),
            value_kind=field_type.value_kind,
            cardinality=field_type.cardinality,
            value=_rows_to_field_value(rows, field_type=field_type, view_facts=view_facts, index=index, ref_cache=ref_cache),
        )
        if include_assertions:
            assertions[field_name] = _build_field_assertions(
                e_ref,
                entity_type=entity_type,
                field_name=field_name,
                field_type=field_type,
                ledger=store.ledger,
                index=index,
                view_facts=view_facts,
                ref_cache=ref_cache,
                include_history=include_history,
            )

    return EntitySnapshotDTO(
        ref=ref,
        fields=fields,
        assertions=assertions,
        identity_available=True,
    )


def _recover_entity_ref(
    e_ref: str,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
    ref_cache: dict[str, EntityRef],
) -> EntityRef:
    cached = ref_cache.get(e_ref)
    if cached is not None:
        return cached
    entity_type = entity_type_from_ref(e_ref)
    if entity_type is None:
        raise EntityViewError(
            f"invalid entity_ref token: {e_ref!r}",
            code="INVALID_ENTITY_REF",
            path=("ref",),
            details={"e_ref": e_ref},
        )
    raw_identity = _recover_identity_from_predicates(
        e_ref,
        entity_type=entity_type,
        view_facts=view_facts,
        index=index,
    )
    ref = EntityRef(entity_type=entity_type, identity=raw_identity, encoded_ref=e_ref)
    ref_cache[e_ref] = ref
    return ref


def _recover_identity_from_predicates(
    e_ref: str,
    entity_type: str,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
) -> dict[str, Any]:
    info = entity_info(index, entity_type)
    identity_values: dict[str, Any] = {}
    for field in info.identity_fields:
        pred_info = info.identity_predicates.get(field.name)
        if pred_info is None:
            raise EntityViewError(
                f"schema is missing identity predicate for {entity_type}.{field.name}",
                code="IDENTITY_PREDICATE_NOT_FOUND",
                path=("ref", "identity", field.name),
                details={"entity_type": entity_type, "field_name": field.name},
            )
        matched = [row for row in view_facts.get(pred_info.pred_id, []) if row and row[0] == e_ref]
        if not matched:
            raise EntityViewError(
                f"identity value is not visible for {entity_type}.{field.name}",
                code="IDENTITY_NOT_AVAILABLE",
                path=("ref", "identity", field.name),
                details={"entity_type": entity_type, "field_name": field.name, "e_ref": e_ref},
            )
        identity_values[field.name] = matched[0][-1]
    return materialize_identity(
        entity_type,
        identity_values,
        index=index,
        allow_identity_defaults=False,
    )


def _rows_to_field_value(
    rows: list[tuple[Any, ...]],
    *,
    field_type: FieldTypeInfo,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
    ref_cache: dict[str, EntityRef],
) -> FieldValue | tuple[FieldValue, ...] | None:
    if field_type.cardinality == "single":
        if not rows:
            return None
        return _hydrate_value(rows[0][-1], field_type=field_type, view_facts=view_facts, index=index, ref_cache=ref_cache)
    return tuple(
        _hydrate_value(row[-1], field_type=field_type, view_facts=view_facts, index=index, ref_cache=ref_cache)
        for row in rows
    )


def _hydrate_value(
    raw_value: Any,
    *,
    field_type: FieldTypeInfo,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
    ref_cache: dict[str, EntityRef],
) -> FieldValue:
    if field_type.value_kind == "entity_ref":
        if not isinstance(raw_value, str):
            raise EntityViewError(
                "entity_ref field value must be encoded ref string",
                code="INVALID_FIELD_VALUE",
                path=("value",),
                details={"expected_kind": "entity_ref"},
            )
        return _recover_entity_ref(raw_value, view_facts=view_facts, index=index, ref_cache=ref_cache)
    return raw_value


def _build_field_assertions(
    e_ref: str,
    *,
    entity_type: str,
    field_name: str,
    field_type: FieldTypeInfo,
    ledger: Ledger,
    index: SchemaIndex,
    view_facts: dict[str, list[tuple[Any, ...]]],
    ref_cache: dict[str, EntityRef],
    include_history: bool,
) -> FieldAssertionsDTO:
    pred_info = field_predicate(index, entity_type, field_name)
    claims = sorted(
        ledger.find_claims(pred_id=pred_info.pred_id, e_ref=e_ref),
        key=lambda claim: _claim_sort_key(ledger, claim),
    )
    history_records = tuple(
        _assertion_record_from_claim(
            claim,
            ledger=ledger,
            field_type=field_type,
            view_facts=view_facts,
            index=index,
            ref_cache=ref_cache,
        )
        for claim in claims
    )
    active_records = tuple(record for record in history_records if record.active)
    return FieldAssertionsDTO(
        field=FieldPath(entity_type=entity_type, field_name=field_name),
        active=active_records,
        history=history_records if include_history else (),
    )


def _assertion_record_from_claim(
    claim: Claim,
    *,
    ledger: Ledger,
    field_type: FieldTypeInfo,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
    ref_cache: dict[str, EntityRef],
) -> AssertionRecordDTO:
    raw_value = claim.rest_terms[-1][1] if claim.rest_terms else None
    value = None
    if raw_value is not None:
        value = _hydrate_value(raw_value, field_type=field_type, view_facts=view_facts, index=index, ref_cache=ref_cache)
    meta = {row.key: row.value for row in ledger.find_meta(asrt_id=claim.asrt_id)}
    return AssertionRecordDTO(
        assertion_id=claim.asrt_id,
        value=value,
        active=is_active(ledger, claim.asrt_id),
        meta=meta,
    )


def _claim_sort_key(ledger: Ledger, claim: Claim) -> tuple[int, bytes]:
    rows = ledger.find_meta(asrt_id=claim.asrt_id, key="ingested_at")
    ingested = -1
    if rows:
        row = rows[-1]
        if row.kind == "time" and isinstance(row.value, int) and not isinstance(row.value, bool):
            ingested = row.value
    return (ingested, claim.asrt_id.encode("utf-8"))


def _entity_visible(
    entity_type: str,
    e_ref: str,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
) -> bool:
    info = entity_info(index, entity_type)
    for row in view_facts.get(info.exists_predicate_id, []):
        if row and row[0] == e_ref:
            return True
    for pred_key, pred_info in index.field_predicates.items():
        if pred_key[0] != entity_type:
            continue
        for row in view_facts.get(pred_info.pred_id, []):
            if row and row[0] == e_ref:
                return True
    return False


def _enumerate_entity_refs(
    entity_type: str,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
) -> set[str]:
    info = entity_info(index, entity_type)
    refs: set[str] = set()
    for row in view_facts.get(info.exists_predicate_id, []):
        if row and isinstance(row[0], str):
            refs.add(row[0])
    for pred_key, pred_info in index.field_predicates.items():
        if pred_key[0] != entity_type:
            continue
        for row in view_facts.get(pred_info.pred_id, []):
            if row and isinstance(row[0], str):
                refs.add(row[0])
    return refs


def _ordered_non_identity_fields(entity_type: str, *, index: SchemaIndex) -> list[str]:
    names = [
        field_name
        for (owner_type, field_name), pred_info in index.field_predicates.items()
        if owner_type == entity_type and not pred_info.is_identity_field
    ]
    return sorted(names)


def _snapshot_matches_filters(
    snapshot: EntitySnapshotDTO,
    filters: dict[str, FieldFilterValue],
) -> bool:
    for field_name, expected in filters.items():
        dto = snapshot.fields.get(field_name)
        if dto is None:
            return False
        actual = dto.value
        expected_values = expected if isinstance(expected, tuple) else (expected,)
        if dto.cardinality == "single":
            if actual not in expected_values:
                return False
            continue
        if not isinstance(actual, tuple):
            return False
        if not any(candidate in actual for candidate in expected_values):
            return False
    return True


def _validate_filter_paths(request: EntityReadRequest, *, index: SchemaIndex) -> None:
    for field_name in request.field_filters:
        pred_info = field_predicate(index, request.entity_type, field_name)
        if pred_info.is_identity_field:
            raise EntityViewError(
                f"field_filters does not support identity field {request.entity_type}.{field_name}",
                code="IDENTITY_FILTER_NOT_SUPPORTED",
                path=("field_filters", field_name),
                details={"entity_type": request.entity_type, "field_name": field_name},
            )


def _unsupported_temporal_error(request: EntityReadRequest) -> ErrorDTO | None:
    if request.at_time_ns is not None:
        return ErrorDTO(
            code="TEMPORAL_READ_NOT_IMPLEMENTED",
            message="entity_read.at_time_ns is not implemented yet",
            path=("at_time_ns",),
        )
    if request.version is not None:
        return ErrorDTO(
            code="VERSIONED_READ_NOT_IMPLEMENTED",
            message="entity_read.version is not implemented yet",
            path=("version",),
        )
    return None


def _to_error_dto(exc: SchemaResolutionError | EntityViewError) -> ErrorDTO:
    if isinstance(exc, SchemaResolutionError):
        return exc.to_error_dto()
    return exc.to_error_dto()


def _to_warning_dto(exc: SchemaResolutionError | EntityViewError, *, e_ref: str) -> WarningDTO:
    if isinstance(exc, SchemaResolutionError):
        error = exc.to_error_dto()
        return WarningDTO(
            code=error.code,
            message=error.message,
            path=error.path,
            details={**error.details, "e_ref": e_ref},
        )
    warning = exc.to_warning_dto()
    return WarningDTO(
        code=warning.code,
        message=warning.message,
        path=warning.path,
        details={**warning.details, "e_ref": e_ref},
    )


__all__ = [
    "EntityViewError",
    "execute_read_request",
    "hydrate_entities",
    "hydrate_entity",
]
