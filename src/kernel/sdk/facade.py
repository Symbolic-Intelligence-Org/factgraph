from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import reprlib
from typing import Any, TYPE_CHECKING

from kernel.application import execute_read_request, hydrate_entity
from kernel.application.protocol import (
    AssertionRecordDTO,
    EntityReadRequest,
    EntityRef as AppEntityRef,
    EntitySelector as AppEntitySelector,
    EntitySnapshotDTO,
    FieldAssertionsDTO,
)
from kernel.application.schema_runtime import encode_entity_ref as encode_app_entity_ref
from kernel.core.policy.active import is_active

from .errors import (
    CardinalityError,
    EditorClosedError,
    EntityNotFoundError,
    FrozenSnapshotError,
    SDKSchemaError,
    SDKStoreError,
)

if TYPE_CHECKING:
    from kernel.core.store.ledger import Claim
    from .batch import BatchCommitResult, BatchPlan
    from .store import SDKStore


@dataclass(frozen=True)
class AssertionMeta:
    source: str | None
    trace_id: str | None
    ingested_at: datetime | None
    confidence: float | None
    approved_by: str | None
    note: str | None
    derived_rule_id: str | None
    derived_rule_version: str | None
    candidate_id: str | None
    candidate_key: str | None
    candidate_kind: str | None
    raw: dict[str, Any]

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "AssertionMeta":
        source = raw.get("source") if isinstance(raw.get("source"), str) else None
        trace_id = raw.get("trace_id") if isinstance(raw.get("trace_id"), str) else None
        approved_by = raw.get("approved_by") if isinstance(raw.get("approved_by"), str) else None
        note = raw.get("note") if isinstance(raw.get("note"), str) else None
        candidate_id = raw.get("candidate_id") if isinstance(raw.get("candidate_id"), str) else None
        candidate_key = raw.get("candidate_key") if isinstance(raw.get("candidate_key"), str) else None
        candidate_kind = raw.get("candidate_kind") if isinstance(raw.get("candidate_kind"), str) else None
        derived_rule_id = None
        for key in ("derived_rule_id", "derivation_id"):
            if isinstance(raw.get(key), str):
                derived_rule_id = raw[key]
                break
        derived_rule_version = None
        for key in ("derived_rule_version", "derivation_version"):
            if isinstance(raw.get(key), str):
                derived_rule_version = raw[key]
                break
        ingested_at = None
        if isinstance(raw.get("ingested_at"), int) and not isinstance(raw.get("ingested_at"), bool):
            ingested_at = datetime.fromtimestamp(raw["ingested_at"] / 1_000_000_000, tz=timezone.utc)
        confidence = None
        conf = raw.get("confidence")
        if isinstance(conf, (int, float)) and not isinstance(conf, bool):
            confidence = float(conf)
        return cls(
            source=source,
            trace_id=trace_id,
            ingested_at=ingested_at,
            confidence=confidence,
            approved_by=approved_by,
            note=note,
            derived_rule_id=derived_rule_id,
            derived_rule_version=derived_rule_version,
            candidate_id=candidate_id,
            candidate_key=candidate_key,
            candidate_kind=candidate_kind,
            raw=dict(raw),
        )


@dataclass(frozen=True)
class AssertionRecord:
    asrt_id: str
    value: Any
    is_active: bool
    is_revoked: bool
    meta: AssertionMeta


_ASSERTION_FILTER_MISSING = object()


class AssertionRecordSet(tuple):
    def __new__(cls, records: Any = ()) -> "AssertionRecordSet":
        return super().__new__(cls, tuple(records))

    def __getitem__(self, index: Any) -> Any:
        value = super().__getitem__(index)
        if isinstance(index, slice):
            return type(self)(value)
        return value

    def __add__(self, other: Any) -> "AssertionRecordSet":
        if not isinstance(other, tuple):
            return NotImplemented
        return type(self)(tuple(self) + tuple(other))

    def __radd__(self, other: Any) -> "AssertionRecordSet":
        if not isinstance(other, tuple):
            return NotImplemented
        return type(self)(tuple(other) + tuple(self))

    def __mul__(self, count: Any) -> "AssertionRecordSet":
        if not isinstance(count, int):
            return NotImplemented
        return type(self)(tuple(self) * count)

    __rmul__ = __mul__

    def where(
        self,
        *,
        value: Any = _ASSERTION_FILTER_MISSING,
        source: Any = _ASSERTION_FILTER_MISSING,
        trace_id: Any = _ASSERTION_FILTER_MISSING,
        confidence: Any = _ASSERTION_FILTER_MISSING,
        version: Any = _ASSERTION_FILTER_MISSING,
        meta: dict[str, Any] | None = None,
    ) -> "AssertionRecordSet":
        if meta is not None and not isinstance(meta, dict):
            raise SDKStoreError("where(meta=...) expects a dict when provided")

        def matches(record: AssertionRecord) -> bool:
            if value is not _ASSERTION_FILTER_MISSING and record.value != value:
                return False
            if source is not _ASSERTION_FILTER_MISSING and record.meta.source != source:
                return False
            if trace_id is not _ASSERTION_FILTER_MISSING and record.meta.trace_id != trace_id:
                return False
            if confidence is not _ASSERTION_FILTER_MISSING and record.meta.confidence != confidence:
                return False
            if version is not _ASSERTION_FILTER_MISSING and record.meta.raw.get("version") != version:
                return False
            if meta is not None:
                for key, expected in meta.items():
                    if key not in record.meta.raw or record.meta.raw[key] != expected:
                        return False
            return True

        return type(self)(record for record in self if matches(record))

    def one(self) -> AssertionRecord:
        count = len(self)
        if count != 1:
            raise SDKStoreError(f"expected exactly one assertion record; found {count}")
        return self[0]

    def all(self) -> tuple[AssertionRecord, ...]:
        return tuple(self)

    def first(self) -> AssertionRecord | None:
        if not self:
            return None
        return self[0]


class FieldAssertions:
    def __init__(
        self,
        *,
        field_name: str,
        cardinality: str,
        active_records: tuple[AssertionRecord, ...],
        history_records: tuple[AssertionRecord, ...],
    ) -> None:
        self._field_name = field_name
        self._cardinality = cardinality
        self._active_records = AssertionRecordSet(active_records)
        self._history_records = AssertionRecordSet(history_records)

    @property
    def active(self) -> AssertionRecordSet:
        return self._active_records

    @property
    def history(self) -> AssertionRecordSet:
        return self._history_records

    def at(self, t: str) -> AssertionRecordSet:
        at_time = _validate_iso8601_text(
            t,
            context=f"{self._field_name}.at(t)",
        )
        return AssertionRecordSet(
            record
            for record in self._active_records
            if _is_assertion_visible_at(
                record,
                at_time=at_time,
                field_name=self._field_name,
            )
        )

    def version(self, v: str | int) -> AssertionRecordSet:
        expected_version = _validate_version_selector(
            v,
            context=f"{self._field_name}.version(v)",
        )
        return AssertionRecordSet(
            record
            for record in self._active_records
            if _read_assertion_version(record, field_name=self._field_name) == expected_version
        )


class AssertionNamespace:
    def __init__(self, field_map: dict[str, FieldAssertions]) -> None:
        object.__setattr__(self, "_field_map", dict(field_map))

    def __getattr__(self, field_name: str) -> FieldAssertions:
        field_map = object.__getattribute__(self, "_field_map")
        if field_name not in field_map:
            raise AttributeError(field_name)
        return field_map[field_name]

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("AssertionNamespace is read-only")


class EntitySnapshot:
    def __init__(
        self,
        *,
        ref: str,
        entity_type: str,
        field_values: dict[str, Any],
        field_assertions: dict[str, FieldAssertions],
        identity_values: dict[str, Any] | None = None,
        identity_available: bool = False,
    ) -> None:
        object.__setattr__(self, "ref", ref)
        object.__setattr__(self, "entity_type", entity_type)
        object.__setattr__(self, "_field_values", dict(field_values))
        object.__setattr__(self, "_identity_values", dict(identity_values or {}))
        object.__setattr__(self, "identity_available", bool(identity_available))
        object.__setattr__(self, "assertions", AssertionNamespace(field_assertions))

    @property
    def identity(self) -> dict[str, Any]:
        """Known identity kwargs usable for sdk.edit(...), when identity_available=True."""
        return dict(object.__getattribute__(self, "_identity_values"))

    def __getattr__(self, name: str) -> Any:
        field_values = object.__getattribute__(self, "_field_values")
        if name in field_values:
            return field_values[name]
        identity_values = object.__getattribute__(self, "_identity_values")
        if name in identity_values:
            return identity_values[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("EntitySnapshot is read-only")

    def __repr__(self) -> str:
        field_values = object.__getattribute__(self, "_field_values")
        identity_values = object.__getattribute__(self, "_identity_values")
        items: list[str] = []
        for name in sorted(identity_values.keys()):
            items.append(f"{name}={reprlib.repr(identity_values[name])}")
        for name in sorted(field_values.keys()):
            items.append(f"{name}={reprlib.repr(field_values[name])}")
        preview = ", ".join(items[:8])
        if len(items) > 8:
            preview += f", ... (+{len(items) - 8} fields)"
        if preview:
            preview = ", " + preview
        return f"EntitySnapshot(entity_type={self.entity_type!r}, ref={self.ref!r}{preview})"

    def field(self, name: str) -> FieldAssertions:
        return getattr(self.assertions, name)


class FieldEditor:
    def __init__(self, editor: "EntityEditor", field_name: str) -> None:
        self._editor = editor
        self._field_name = field_name

    def _cardinality(self) -> str:
        descriptor = getattr(self._editor._entity_cls, self._field_name, None)
        return str(getattr(descriptor, "cardinality", ""))

    def set(
        self,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> "EntityEditor":
        self._editor._ensure_open()
        cardinality = self._cardinality()
        if cardinality != "single":
            raise CardinalityError(
                f"field '{self._field_name}' has cardinality={cardinality}; .set is only valid for single",
                field_name=self._field_name,
                actual_cardinality=cardinality,
                operation="set",
            )
        handle = self._editor._handle
        getattr(handle, self._field_name).set(value, meta=meta)
        return self._editor

    def add(
        self,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> "EntityEditor":
        self._editor._ensure_open()
        cardinality = self._cardinality()
        if cardinality != "multi":
            raise CardinalityError(
                f"field '{self._field_name}' has cardinality={cardinality}; .add is only valid for multi",
                field_name=self._field_name,
                actual_cardinality=cardinality,
                operation="add",
            )
        handle = self._editor._handle
        getattr(handle, self._field_name).add(value, meta=meta)
        return self._editor

    def retract(
        self,
        *,
        asrt_id: str,
        meta: dict[str, Any] | None = None,
    ) -> "EntityEditor":
        self._editor._ensure_open()
        handle = self._editor._handle
        getattr(handle, self._field_name).retract(asrt_id, meta=meta)
        return self._editor


class IdentityEditor:
    def __init__(self, editor: "EntityEditor", field_name: str) -> None:
        self._editor = editor
        self._field_name = field_name

    @property
    def value(self) -> Any:
        return self._editor._identity_values.get(self._field_name)

    def __repr__(self) -> str:
        return repr(self.value)

    __str__ = __repr__

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, other: Any) -> bool:  # type: ignore[override]
        return self.value == other

    def set(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise SDKStoreError(
            f"identity field '{self._field_name}' is immutable in editor; "
            "open a new editor with different identity instead"
        )

    def add(self, *args: Any, **kwargs: Any) -> None:
        self.set(*args, **kwargs)

    def retract(self, *args: Any, **kwargs: Any) -> None:
        self.set(*args, **kwargs)


class EntityEditor:
    def __init__(self, sdk: "SDKStore", entity_cls: type[Any], identity_values: dict[str, Any]) -> None:
        self._sdk = sdk
        self._entity_cls = entity_cls
        self._identity_values = dict(identity_values)
        self._tx = sdk.batch()
        self._handle = self._tx.entity(entity_cls, **dict(identity_values))
        self._closed = False
        self._field_editors: dict[str, FieldEditor] = {}
        self._identity_editors: dict[str, IdentityEditor] = {}
        object.__setattr__(self, "ref", self._handle.e_ref)
        object.__setattr__(self, "entity_type", entity_cls.__name__)

    def __getattr__(self, name: str) -> Any:
        self._ensure_open()
        descriptor = getattr(self._entity_cls, name, None)
        from .schema import Field, Identity  # local import to avoid cycle at import-time

        if isinstance(descriptor, Field):
            editor = self._field_editors.get(name)
            if editor is None:
                editor = FieldEditor(self, name)
                self._field_editors[name] = editor
            return editor
        if isinstance(descriptor, Identity):
            editor = self._identity_editors.get(name)
            if editor is None:
                editor = IdentityEditor(self, name)
                self._identity_editors[name] = editor
            return editor
        if name in self._identity_values:
            return self._identity_values[name]
        raise AttributeError(name)

    def _ensure_open(self) -> None:
        if self._closed:
            raise EditorClosedError("editor is closed")

    def preview(self) -> "BatchPlan":
        self._ensure_open()
        return self._tx.preview(objects=[self._handle])

    def commit(self, *, meta: dict[str, Any] | None = None) -> "BatchCommitResult":
        self._ensure_open()
        try:
            return self._tx.commit(objects=[self._handle], commit_meta=meta)
        finally:
            self._closed = True

    def rollback(self) -> None:
        self._ensure_open()
        self._closed = True

    def __enter__(self) -> "EntityEditor":
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._closed:
            return False
        if exc_type is not None:
            self.rollback()
            return False
        self.commit()
        return False


def sdk_get(sdk: "SDKStore", entity_cls: type[Any], **identity_kwargs: Any) -> EntitySnapshot | None:
    _validate_entity_cls(sdk, entity_cls)
    spec = sdk._entity_spec_by_class[entity_cls]
    _validate_identity_kwargs_for_get(spec, entity_cls, identity_kwargs)
    identity_names = [field["name"] for field in spec.get("identity_fields", []) if isinstance(field, dict)]
    request = EntityReadRequest(
        mode="get",
        entity_type=entity_cls.__name__,
        selector=AppEntitySelector(
            entity_type=entity_cls.__name__,
            identity=dict(identity_kwargs),
            allow_identity_defaults=any(name not in identity_kwargs for name in identity_names),
        ),
        include_assertions=True,
        include_history=True,
    )
    response = execute_read_request(
        request,
        store=sdk.store,
        index=sdk._application_schema_index,
    )
    if response.errors:
        error = response.errors[0]
        if error.code == "ENTITY_NOT_FOUND":
            return None
        raise _sdk_store_error_from_dto(error)
    if not response.items:
        return None
    return _dto_to_sdk_snapshot(
        response.items[0],
        sdk=sdk,
        entity_cls=entity_cls,
        known_identity_values=identity_kwargs,
    )


def sdk_find(
    sdk: "SDKStore",
    entity_cls: type[Any],
    *,
    limit: int | None = None,
    **filter_kwargs: Any,
) -> list[EntitySnapshot]:
    _validate_entity_cls(sdk, entity_cls)
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        raise SDKStoreError("limit must be non-negative int when provided")
    if limit == 0:
        return []

    spec = sdk._entity_spec_by_class[entity_cls]
    identity_names = [field["name"] for field in spec.get("identity_fields", []) if isinstance(field, dict)]
    field_names = [field["py_name"] for field in spec.get("fields", []) if isinstance(field, dict)]
    allowed = set(identity_names) | set(field_names)
    unknown = sorted([k for k in filter_kwargs.keys() if k not in allowed])
    if unknown:
        raise SDKSchemaError(f"unknown filter fields for {entity_cls.__name__}: {unknown}")

    identity_filters = {k: v for k, v in filter_kwargs.items() if k in set(identity_names)}
    value_filters = {k: v for k, v in filter_kwargs.items() if k in set(field_names)}

    if identity_filters and set(identity_filters.keys()) == set(identity_names):
        response = execute_read_request(
            EntityReadRequest(
                mode="get",
                entity_type=entity_cls.__name__,
                selector=AppEntitySelector(
                    entity_type=entity_cls.__name__,
                    identity=dict(identity_filters),
                    allow_identity_defaults=False,
                ),
                include_assertions=True,
                include_history=True,
            ),
            store=sdk.store,
            index=sdk._application_schema_index,
        )
        if response.errors:
            error = response.errors[0]
            if error.code == "ENTITY_NOT_FOUND":
                return []
            raise _sdk_store_error_from_dto(error)
        if not response.items:
            return []
        snapshot = _dto_to_sdk_snapshot(
            response.items[0],
            sdk=sdk,
            entity_cls=entity_cls,
            known_identity_values=identity_filters,
        )
        if _snapshot_matches_filters(sdk, entity_cls, snapshot, value_filters):
            return [snapshot]
        return []

    out: list[EntitySnapshot] = []
    response = execute_read_request(
        EntityReadRequest(
            mode="find",
            entity_type=entity_cls.__name__,
            include_assertions=True,
            include_history=True,
        ),
        store=sdk.store,
        index=sdk._application_schema_index,
    )
    if response.errors:
        raise _sdk_store_error_from_dto(response.errors[0])
    for dto in response.items:
        if identity_filters and not _dto_matches_identity_filters(dto, identity_filters):
            continue
        known_identity_values = dict(dto.ref.identity) if identity_filters else None
        snap = _dto_to_sdk_snapshot(
            dto,
            sdk=sdk,
            entity_cls=entity_cls,
            known_identity_values=known_identity_values,
        )
        if _snapshot_matches_filters(sdk, entity_cls, snap, value_filters):
            out.append(snap)
            if limit is not None and len(out) >= limit:
                break
    return out


def sdk_edit(sdk: "SDKStore", entity_cls: type[Any], **identity_kwargs: Any) -> EntityEditor:
    snapshot = sdk_get(sdk, entity_cls, **identity_kwargs)
    if snapshot is None:
        raise EntityNotFoundError(
            f"entity not found: {getattr(entity_cls, '__name__', entity_cls)} with identity {identity_kwargs}",
            entity_type=getattr(entity_cls, "__name__", str(entity_cls)),
            identity_kwargs=dict(identity_kwargs),
        )
    return EntityEditor(sdk, entity_cls, identity_kwargs)


def _validate_entity_cls(sdk: "SDKStore", entity_cls: type[Any]) -> None:
    if entity_cls not in sdk._entity_spec_by_class:
        raise SDKStoreError(f"unknown Entity class: {getattr(entity_cls, '__name__', entity_cls)!r}")


def _validate_identity_kwargs_for_get(spec: dict[str, Any], entity_cls: type[Any], identity_kwargs: dict[str, Any]) -> None:
    identity_names = [field["name"] for field in spec.get("identity_fields", []) if isinstance(field, dict)]
    extra = sorted(set(identity_kwargs.keys()) - set(identity_names))
    if extra:
        raise SDKSchemaError(f"get() accepts only identity fields for {entity_cls.__name__}: {extra}")
    by_name = _identity_spec_by_name(spec)
    # Allow uuid4/default identity fields to be omitted for `get`, but note this can point to a different random ref.
    # For v1, require callers to pass all identity fields except explicit literal defaults.
    uuid_missing = [
        name
        for name in identity_names
        if name not in identity_kwargs
        and by_name.get(name, {}).get("default_factory") == "uuid4"
    ]
    if uuid_missing:
        raise SDKSchemaError(
            f"get() requires explicit identity value(s) for uuid4 identity fields on {entity_cls.__name__}: {uuid_missing}"
        )
    missing = [
        name
        for name in identity_names
        if name not in identity_kwargs and name not in uuid_missing and "default" not in by_name.get(name, {})
    ]
    if missing:
        raise SDKSchemaError(f"missing identity fields for get({entity_cls.__name__}): {missing}")


def _identity_spec_by_name(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in spec.get("identity_fields", []):
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            out[row["name"]] = row
    return out


def _entity_exists_pred_id_for_entity(sdk: "SDKStore", entity_cls: type[Any]) -> str | None:
    entity_type = sdk._entity_spec_by_class[entity_cls].get("entity_type")
    if not isinstance(entity_type, str):
        return None
    for pred in sdk.schema_ir.get("predicates", []):
        if not isinstance(pred, dict):
            continue
        if pred.get("owner_type") != entity_type:
            continue
        if pred.get("is_entity_exists") is not True:
            continue
        pred_id = pred.get("pred_id")
        if isinstance(pred_id, str) and pred_id:
            return pred_id
    return None


def _entity_field_rows(sdk: "SDKStore", entity_cls: type[Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    spec = sdk._entity_spec_by_class[entity_cls]
    out: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for field_decl in spec.get("fields", []):
        if not isinstance(field_decl, dict):
            continue
        py_name = field_decl.get("py_name")
        if not isinstance(py_name, str) or not py_name:
            continue
        descriptor = getattr(entity_cls, py_name, None)
        if descriptor is None:
            continue
        schema_pred = sdk._field_pred_by_descriptor.get(descriptor)
        if isinstance(schema_pred, dict):
            out.append((py_name, field_decl, schema_pred))
    return out


def _entity_visible_in_view(sdk: "SDKStore", entity_cls: type[Any], *, e_ref: str, view_facts: dict[str, list[tuple[Any, ...]]]) -> bool:
    exists_pred = _entity_exists_pred_id_for_entity(sdk, entity_cls)
    if isinstance(exists_pred, str):
        for row in view_facts.get(exists_pred, []):
            if row and row[0] == e_ref:
                return True
    for _, _, schema_pred in _entity_field_rows(sdk, entity_cls):
        pred_id = schema_pred.get("pred_id")
        if not isinstance(pred_id, str):
            continue
        for row in view_facts.get(pred_id, []):
            if row and row[0] == e_ref:
                return True
    return False


def _candidate_entity_refs(sdk: "SDKStore", entity_cls: type[Any], *, view_facts: dict[str, list[tuple[Any, ...]]]) -> set[str]:
    out: set[str] = set()
    exists_pred = _entity_exists_pred_id_for_entity(sdk, entity_cls)
    if isinstance(exists_pred, str):
        for row in view_facts.get(exists_pred, []):
            if row and isinstance(row[0], str):
                out.add(row[0])
    for _, _, schema_pred in _entity_field_rows(sdk, entity_cls):
        pred_id = schema_pred.get("pred_id")
        if not isinstance(pred_id, str):
            continue
        for row in view_facts.get(pred_id, []):
            if row and isinstance(row[0], str):
                out.add(row[0])
    return out


def _build_snapshot(
    sdk: "SDKStore",
    entity_cls: type[Any],
    *,
    e_ref: str,
    view_facts: dict[str, list[tuple[Any, ...]]] | None = None,
    known_identity_values: dict[str, Any] | None = None,
) -> EntitySnapshot:
    del view_facts
    try:
        dto = hydrate_entity(
            e_ref,
            store=sdk.store,
            index=sdk._application_schema_index,
            include_assertions=True,
            include_history=True,
        )
    except Exception as exc:
        raise SDKStoreError(f"failed to hydrate snapshot for {entity_cls.__name__}: {exc}") from exc
    return _dto_to_sdk_snapshot(
        dto,
        sdk=sdk,
        entity_cls=entity_cls,
        known_identity_values=known_identity_values,
    )


def _dto_to_sdk_snapshot(
    dto: EntitySnapshotDTO,
    *,
    sdk: "SDKStore",
    entity_cls: type[Any],
    known_identity_values: dict[str, Any] | None = None,
) -> EntitySnapshot:
    field_values = {
        field_name: _dto_value_to_sdk_value(field_dto.value, sdk=sdk)
        for field_name, field_dto in dto.fields.items()
    }
    field_assertions = {
        field_name: _dto_assertions_to_sdk(
            assertions_dto,
            sdk=sdk,
            entity_cls=entity_cls,
        )
        for field_name, assertions_dto in dto.assertions.items()
    }
    identity_values = dict(known_identity_values or {})
    identity_available = known_identity_values is not None
    return EntitySnapshot(
        ref=_dto_ref_to_sdk_ref(dto.ref, sdk=sdk),
        entity_type=dto.ref.entity_type,
        field_values=field_values,
        field_assertions=field_assertions,
        identity_values=identity_values,
        identity_available=identity_available,
    )


def _dto_assertions_to_sdk(
    dto: FieldAssertionsDTO,
    *,
    sdk: "SDKStore",
    entity_cls: type[Any],
) -> FieldAssertions:
    cardinality = _sdk_field_cardinality(entity_cls, dto.field.field_name)
    return FieldAssertions(
        field_name=dto.field.field_name,
        cardinality=cardinality,
        active_records=tuple(_dto_assertion_record_to_sdk(record, sdk=sdk) for record in dto.active),
        history_records=tuple(_dto_assertion_record_to_sdk(record, sdk=sdk) for record in dto.history),
    )


def _dto_assertion_record_to_sdk(dto: AssertionRecordDTO, *, sdk: "SDKStore") -> AssertionRecord:
    return AssertionRecord(
        asrt_id=dto.assertion_id,
        value=_dto_value_to_sdk_value(dto.value, sdk=sdk),
        is_active=dto.active,
        is_revoked=not dto.active,
        meta=AssertionMeta.from_raw(dict(dto.meta)),
    )


def _dto_value_to_sdk_value(value: Any, *, sdk: "SDKStore") -> Any:
    if isinstance(value, tuple):
        return tuple(_dto_value_to_sdk_value(item, sdk=sdk) for item in value)
    if isinstance(value, AppEntityRef):
        return _dto_ref_to_sdk_ref(value, sdk=sdk)
    return value


def _dto_ref_to_sdk_ref(ref: AppEntityRef, *, sdk: "SDKStore") -> str:
    if isinstance(ref.encoded_ref, str) and ref.encoded_ref:
        return ref.encoded_ref
    return encode_app_entity_ref(ref, index=sdk._application_schema_index)


def _sdk_field_cardinality(entity_cls: type[Any], field_name: str) -> str:
    descriptor = getattr(entity_cls, field_name, None)
    return str(getattr(descriptor, "cardinality", "single"))


def _sdk_store_error_from_dto(error: Any) -> SDKStoreError:
    path = None
    if isinstance(getattr(error, "path", None), tuple) and error.path:
        path = ".".join(error.path)
    return SDKStoreError(str(error.message), code=getattr(error, "code", None), path=path)


def _current_value_from_rows(rows: list[tuple[Any, ...]], *, cardinality: str) -> Any:
    if cardinality == "single":
        if not rows:
            return None
        return rows[0][-1]
    return tuple(row[-1] for row in rows)


def _field_assertions_for_entity_field(
    sdk: "SDKStore",
    *,
    e_ref: str,
    field_name: str,
    schema_pred: dict[str, Any],
    cardinality: str,
) -> FieldAssertions:
    pred_id = schema_pred.get("pred_id")
    if not isinstance(pred_id, str) or not pred_id:
        raise SDKStoreError(f"schema predicate missing pred_id for field {field_name}")

    claims = sdk.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
    history_records = tuple(
        _assertion_record_from_claim(sdk, claim, schema_pred=schema_pred)
        for claim in sorted(claims, key=lambda c: _claim_sort_key(sdk, c))
    )
    active_records = tuple(rec for rec in history_records if rec.is_active)

    return FieldAssertions(
        field_name=field_name,
        cardinality=cardinality,
        active_records=active_records,
        history_records=history_records,
    )


def _claim_sort_key(sdk: "SDKStore", claim: "Claim") -> tuple[int, bytes]:
    rows = sdk.ledger.find_meta(asrt_id=claim.asrt_id, key="ingested_at")
    ingested = -1
    if rows:
        row = rows[-1]
        if row.kind == "time" and isinstance(row.value, int) and not isinstance(row.value, bool):
            ingested = row.value
    return (ingested, claim.asrt_id.encode("utf-8"))


def _assertion_record_from_claim(sdk: "SDKStore", claim: "Claim", *, schema_pred: dict[str, Any]) -> AssertionRecord:
    value = _decode_claim_rest_terms(schema_pred, claim.rest_terms)
    raw_meta = _meta_raw_for_assertion(sdk, claim.asrt_id)
    active = is_active(sdk.ledger, claim.asrt_id)
    return AssertionRecord(
        asrt_id=claim.asrt_id,
        value=value,
        is_active=active,
        is_revoked=not active,
        meta=AssertionMeta.from_raw(raw_meta),
    )


def _decode_claim_rest_terms(schema_pred: dict[str, Any], rest_terms: list[tuple[str, Any]]) -> Any:
    del schema_pred
    if not rest_terms:
        return None
    return rest_terms[-1][1]


def _meta_raw_for_assertion(sdk: "SDKStore", asrt_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in sdk.ledger.find_meta(asrt_id=asrt_id):
        out[row.key] = row.value
    return out


_ISO_8601_PATTERN = re.compile(
    r"^\d{4}(?:-\d{2}(?:-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+\-]\d{2}:\d{2})?)?)?)?$"
)


def _validate_iso8601_text(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise SDKStoreError(f"{context} expects non-empty ISO 8601 string")
    if not _is_valid_iso8601_text(value):
        raise SDKStoreError(
            f"{context} expects ISO 8601 string; got {value!r}"
        )
    return value


def _is_valid_iso8601_text(value: str) -> bool:
    if _ISO_8601_PATTERN.fullmatch(value) is None:
        return False

    if len(value) >= 7:
        month = int(value[5:7])
        if month < 1 or month > 12:
            return False

    if len(value) >= 10:
        try:
            datetime.fromisoformat(value[:10])
        except ValueError:
            return False

    if "T" in value:
        normalized = value.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(normalized)
        except ValueError:
            return False
    return True


def _validate_version_selector(value: Any, *, context: str) -> str | int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise SDKStoreError(f"{context} expects string|int version selector")
    return value


def _is_assertion_visible_at(
    record: AssertionRecord,
    *,
    at_time: str,
    field_name: str,
) -> bool:
    valid_from = _read_assertion_time_meta(record, key="valid_from", field_name=field_name)
    if valid_from is None:
        return False
    valid_to = _read_assertion_time_meta(record, key="valid_to", field_name=field_name)
    return valid_from <= at_time and (valid_to is None or valid_to > at_time)


def _read_assertion_time_meta(
    record: AssertionRecord,
    *,
    key: str,
    field_name: str,
) -> str | None:
    value = record.meta.raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise SDKStoreError(
            f"{field_name}.at(t) encountered invalid meta.{key} for assertion {record.asrt_id!r}; "
            "expected ISO 8601 string"
        )
    try:
        return _validate_iso8601_text(
            value,
            context=f"{field_name}.at(t) meta.{key} for assertion {record.asrt_id!r}",
        )
    except SDKStoreError as exc:
        raise SDKStoreError(
            f"{field_name}.at(t) encountered invalid meta.{key} for assertion {record.asrt_id!r}; "
            f"got {value!r}"
        ) from exc


def _read_assertion_version(record: AssertionRecord, *, field_name: str) -> str | int | None:
    value = record.meta.raw.get("version")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise SDKStoreError(
            f"{field_name}.version(v) encountered invalid meta.version for assertion {record.asrt_id!r}; "
            "expected string|int"
        )
    return value


def _snapshot_matches_filters(
    sdk: "SDKStore",
    entity_cls: type[Any],
    snapshot: EntitySnapshot,
    filters: dict[str, Any],
) -> bool:
    if not filters:
        return True
    field_rows = {name: (decl, pred) for name, decl, pred in _entity_field_rows(sdk, entity_cls)}
    for key, raw_expected in filters.items():
        if key not in field_rows:
            continue
        field_decl, schema_pred = field_rows[key]
        expected = raw_expected.ref if isinstance(raw_expected, EntitySnapshot) else raw_expected
        current_value = getattr(snapshot, key)
        cardinality = str(field_decl.get("cardinality", schema_pred.get("cardinality", "single")))
        if cardinality == "single":
            if current_value != expected:
                return False
        elif cardinality == "multi":
            if not isinstance(current_value, tuple):
                return False
            if expected not in current_value:
                return False
        else:
            if current_value != expected:
                return False
    return True


def _dto_matches_identity_filters(dto: EntitySnapshotDTO, filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        if dto.ref.identity.get(key) != expected:
            return False
    return True
