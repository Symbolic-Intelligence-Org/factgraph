from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import reprlib
from typing import Any, TYPE_CHECKING, Literal

from factpy_kernel.core.policy.active import is_active
from factpy_kernel.core.policy.chosen import PolicyNonDeterminismError, compute_chosen_for_predicate
from factpy_kernel.core.view.projector import project_view_facts

from .errors import (
    CardinalityError,
    EditorClosedError,
    EntityNotFoundError,
    FrozenSnapshotError,
    SDKSchemaError,
    SDKStoreError,
)

if TYPE_CHECKING:
    from factpy_kernel.core.store.ledger import Claim
    from .batch import BatchCommitResult, BatchPlan
    from .store import SDKStore


_TemporalView = Literal["record", "current"]


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
    materialize_id: str | None
    raw: dict[str, Any]

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "AssertionMeta":
        source = raw.get("source") if isinstance(raw.get("source"), str) else None
        trace_id = raw.get("trace_id") if isinstance(raw.get("trace_id"), str) else None
        approved_by = raw.get("approved_by") if isinstance(raw.get("approved_by"), str) else None
        note = raw.get("note") if isinstance(raw.get("note"), str) else None
        materialize_id = raw.get("materialize_id") if isinstance(raw.get("materialize_id"), str) else None
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
            materialize_id=materialize_id,
            raw=dict(raw),
        )


@dataclass(frozen=True)
class AssertionRecord:
    asrt_id: str
    value: Any
    dims: dict[str, Any]
    is_active: bool
    is_revoked: bool
    meta: AssertionMeta


@dataclass(frozen=True)
class DimensionedValue:
    value: Any
    dims: dict[str, Any]


class FieldAssertions:
    def __init__(
        self,
        *,
        field_name: str,
        cardinality: str,
        has_dims: bool,
        chosen_record: AssertionRecord | None,
        active_records: tuple[AssertionRecord, ...],
        history_records: tuple[AssertionRecord, ...],
    ) -> None:
        self._field_name = field_name
        self._cardinality = cardinality
        self._has_dims = has_dims
        self._chosen_record = chosen_record
        self._active_records = active_records
        self._history_records = history_records

    @property
    def chosen(self) -> AssertionRecord | None:
        if self._cardinality != "functional":
            raise CardinalityError(
                f"field '{self._field_name}' has cardinality={self._cardinality}; .chosen is only valid for functional"
            )
        if self._has_dims:
            raise CardinalityError(
                f"field '{self._field_name}' has dims; .chosen is undefined for dimmed functional field"
            )
        return self._chosen_record

    @property
    def active(self) -> tuple[AssertionRecord, ...]:
        return self._active_records

    @property
    def history(self) -> tuple[AssertionRecord, ...]:
        return self._history_records


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
        dims: dict[str, Any] | list[Any] | tuple[Any, ...] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> "EntityEditor":
        self._editor._ensure_open()
        cardinality = self._cardinality()
        if cardinality != "functional":
            raise CardinalityError(
                f"field '{self._field_name}' has cardinality={cardinality}; .set is only valid for functional",
                field_name=self._field_name,
                actual_cardinality=cardinality,
                operation="set",
            )
        handle = self._editor._handle
        getattr(handle, self._field_name).set(value, dims=dims, meta=meta)
        return self._editor

    def add(
        self,
        value: Any,
        *,
        dims: dict[str, Any] | list[Any] | tuple[Any, ...] | None = None,
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
        getattr(handle, self._field_name).add(value, dims=dims, meta=meta)
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


class EntityEditor:
    def __init__(self, sdk: "SDKStore", entity_cls: type[Any], identity_values: dict[str, Any]) -> None:
        self._sdk = sdk
        self._entity_cls = entity_cls
        self._identity_values = dict(identity_values)
        self._tx = sdk.batch()
        self._handle = self._tx.entity(entity_cls, **dict(identity_values))
        self._closed = False
        self._field_editors: dict[str, FieldEditor] = {}
        object.__setattr__(self, "ref", self._handle.e_ref)
        object.__setattr__(self, "entity_type", entity_cls.__name__)

    def __getattr__(self, name: str) -> Any:
        self._ensure_open()
        descriptor = getattr(self._entity_cls, name, None)
        from .schema import Field  # local import to avoid cycle at import-time

        if isinstance(descriptor, Field):
            editor = self._field_editors.get(name)
            if editor is None:
                editor = FieldEditor(self, name)
                self._field_editors[name] = editor
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
    e_ref = sdk.ref(entity_cls, **dict(identity_kwargs))
    view_facts = project_view_facts(sdk.ledger, sdk.schema_ir, temporal_view="record")
    if not _entity_visible_in_view(sdk, entity_cls, e_ref=e_ref, view_facts=view_facts):
        return None
    return _build_snapshot(
        sdk,
        entity_cls,
        e_ref=e_ref,
        temporal_view="record",
        view_facts=view_facts,
        known_identity_values=identity_kwargs,
    )


def sdk_find(
    sdk: "SDKStore",
    entity_cls: type[Any],
    *,
    temporal_view: _TemporalView = "record",
    limit: int | None = None,
    **filter_kwargs: Any,
) -> list[EntitySnapshot]:
    _validate_entity_cls(sdk, entity_cls)
    if temporal_view not in {"record", "current"}:
        raise SDKStoreError("temporal_view must be 'record' or 'current'")
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

    field_rows = {name: (decl, pred) for name, decl, pred in _entity_field_rows(sdk, entity_cls)}
    for key in value_filters:
        row = field_rows.get(key)
        if row is None:
            continue
        _, schema_pred = row
        dims_names = schema_pred.get("dims")
        if isinstance(dims_names, list) and any(isinstance(x, str) for x in dims_names):
            raise SDKSchemaError(f"find() dims-field filtering is not supported yet: {entity_cls.__name__}.{key}")

    if identity_filters:
        if set(identity_filters.keys()) != set(identity_names):
            missing = sorted(set(identity_names) - set(identity_filters.keys()))
            raise SDKSchemaError(
                f"find identity filters must include all identity fields for {entity_cls.__name__}; missing: {missing}"
            )
        e_ref = sdk.ref(entity_cls, **dict(identity_filters))
        view_facts = project_view_facts(sdk.ledger, sdk.schema_ir, temporal_view=temporal_view)
        if not _entity_visible_in_view(sdk, entity_cls, e_ref=e_ref, view_facts=view_facts):
            return []
        snapshot = _build_snapshot(
            sdk,
            entity_cls,
            e_ref=e_ref,
            temporal_view=temporal_view,
            view_facts=view_facts,
            known_identity_values=identity_filters,
        )
        if _snapshot_matches_filters(sdk, entity_cls, snapshot, value_filters):
            return [snapshot]
        return []

    view_facts = project_view_facts(sdk.ledger, sdk.schema_ir, temporal_view=temporal_view)
    e_refs = _candidate_entity_refs(sdk, entity_cls, view_facts=view_facts)
    out: list[EntitySnapshot] = []
    for e_ref in sorted(e_refs):
        snap = _build_snapshot(sdk, entity_cls, e_ref=e_ref, temporal_view=temporal_view, view_facts=view_facts)
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


def _record_exists_pred_id_for_entity(sdk: "SDKStore", entity_cls: type[Any]) -> str | None:
    entity_type = sdk._entity_spec_by_class[entity_cls].get("entity_type")
    if not isinstance(entity_type, str):
        return None
    for pred in sdk.schema_ir.get("predicates", []):
        if not isinstance(pred, dict):
            continue
        if pred.get("owner_type") != entity_type:
            continue
        if pred.get("is_record_exists") is not True:
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
    exists_pred = _record_exists_pred_id_for_entity(sdk, entity_cls)
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
    exists_pred = _record_exists_pred_id_for_entity(sdk, entity_cls)
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
    temporal_view: _TemporalView,
    view_facts: dict[str, list[tuple[Any, ...]]] | None = None,
    known_identity_values: dict[str, Any] | None = None,
) -> EntitySnapshot:
    if view_facts is None:
        view_facts = project_view_facts(sdk.ledger, sdk.schema_ir, temporal_view=temporal_view)
    spec = sdk._entity_spec_by_class[entity_cls]
    entity_type = spec.get("entity_type")
    if not isinstance(entity_type, str) or not entity_type:
        raise SDKStoreError(f"invalid entity spec for {entity_cls.__name__}")

    field_values: dict[str, Any] = {}
    field_assertions: dict[str, FieldAssertions] = {}
    for field_name, field_decl, schema_pred in _entity_field_rows(sdk, entity_cls):
        pred_id = schema_pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        cardinality = str(field_decl.get("cardinality", schema_pred.get("cardinality", "functional")))
        dims_names = schema_pred.get("dims")
        if not isinstance(dims_names, list):
            dims_names = []
        rows = [row for row in view_facts.get(pred_id, []) if row and row[0] == e_ref]
        field_values[field_name] = _current_value_from_rows(rows, cardinality=cardinality, dims_names=dims_names)
        field_assertions[field_name] = _field_assertions_for_entity_field(
            sdk,
            e_ref=e_ref,
            field_name=field_name,
            schema_pred=schema_pred,
            cardinality=cardinality,
            dims_names=dims_names,
        )

    identity_values = dict(known_identity_values or {})
    return EntitySnapshot(
        ref=e_ref,
        entity_type=entity_type,
        field_values=field_values,
        field_assertions=field_assertions,
        identity_values=identity_values,
        identity_available=(known_identity_values is not None),
    )


def _current_value_from_rows(rows: list[tuple[Any, ...]], *, cardinality: str, dims_names: list[Any]) -> Any:
    dim_names = [d for d in dims_names if isinstance(d, str)]
    if not dim_names:
        if cardinality == "functional":
            if not rows:
                return None
            return rows[0][-1]
        # multi/temporal return all visible rows in stable tuple
        return tuple(row[-1] for row in rows)
    dimmed = tuple(
        DimensionedValue(
            value=row[-1],
            dims={name: row[idx + 1] for idx, name in enumerate(dim_names)},
        )
        for row in rows
    )
    return dimmed


def _field_assertions_for_entity_field(
    sdk: "SDKStore",
    *,
    e_ref: str,
    field_name: str,
    schema_pred: dict[str, Any],
    cardinality: str,
    dims_names: list[str],
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

    chosen_record: AssertionRecord | None = None
    if cardinality == "functional" and not dims_names:
        try:
            chosen_map = compute_chosen_for_predicate(sdk.ledger, schema_pred)
            chosen_asrt = chosen_map.get((pred_id, e_ref))
            if isinstance(chosen_asrt, str):
                for rec in active_records:
                    if rec.asrt_id == chosen_asrt:
                        chosen_record = rec
                        break
        except PolicyNonDeterminismError:
            # Surface active/history even if chosen policy cannot be resolved.
            chosen_record = None

    return FieldAssertions(
        field_name=field_name,
        cardinality=cardinality,
        has_dims=bool(dims_names),
        chosen_record=chosen_record,
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
    dims, value = _decode_claim_rest_terms(schema_pred, claim.rest_terms)
    raw_meta = _meta_raw_for_assertion(sdk, claim.asrt_id)
    active = is_active(sdk.ledger, claim.asrt_id)
    return AssertionRecord(
        asrt_id=claim.asrt_id,
        value=value,
        dims=dims,
        is_active=active,
        is_revoked=not active,
        meta=AssertionMeta.from_raw(raw_meta),
    )


def _decode_claim_rest_terms(schema_pred: dict[str, Any], rest_terms: list[tuple[str, Any]]) -> tuple[dict[str, Any], Any]:
    dims_names = schema_pred.get("dims")
    if not isinstance(dims_names, list):
        dims_names = []
    dim_names = [d for d in dims_names if isinstance(d, str)]
    if not rest_terms:
        return ({}, None)
    if len(rest_terms) != len(dim_names) + 1:
        # Best-effort fallback: treat everything but last as unnamed dims.
        dims = {f"dim{idx}": term[1] for idx, term in enumerate(rest_terms[:-1])}
        return (dims, rest_terms[-1][1])
    dims = {name: rest_terms[idx][1] for idx, name in enumerate(dim_names)}
    return (dims, rest_terms[-1][1])


def _meta_raw_for_assertion(sdk: "SDKStore", asrt_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in sdk.ledger.find_meta(asrt_id=asrt_id):
        out[row.key] = row.value
    return out


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
        cardinality = str(field_decl.get("cardinality", schema_pred.get("cardinality", "functional")))
        if cardinality == "functional":
            if current_value != expected:
                return False
        elif cardinality in {"multi", "temporal"}:
            if not isinstance(current_value, tuple):
                return False
            if expected not in current_value:
                return False
        else:
            if current_value != expected:
                return False
    return True
