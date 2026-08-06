from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from .common import (
    ErrorDTO,
    JSONValue,
    ProtocolShapeError,
    WarningDTO,
    _require_bool,
    _require_literal,
    _require_non_empty_str,
    _require_optional_non_empty_str,
    _validate_json_mapping,
    _validate_json_value,
    _validate_tuple_items,
)
from .schema_runtime import EntityRef, EntitySelector, FieldPath

FieldValue: TypeAlias = JSONValue | bytes | EntityRef
FieldFilterValue: TypeAlias = FieldValue | tuple[FieldValue, ...]


def _validate_field_value(value: Any, *, field_name: str, value_kind: str | None = None) -> None:
    if isinstance(value, EntityRef):
        if value_kind == "scalar":
            raise ProtocolShapeError(f"{field_name} must be scalar value")
        return
    if value_kind == "entity_ref":
        raise ProtocolShapeError(f"{field_name} must be EntityRef")
    if isinstance(value, bytes):
        return
    _validate_json_value(value, field_name=field_name)


@dataclass(frozen=True)
class FieldValueDTO:
    field: FieldPath
    value_kind: Literal["scalar", "entity_ref"]
    cardinality: Literal["single", "multi"]
    value: FieldValue | tuple[FieldValue, ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError("field must be FieldPath")
        value_kind = _require_literal(self.value_kind, field_name="value_kind", allowed=("scalar", "entity_ref"))
        cardinality = _require_literal(self.cardinality, field_name="cardinality", allowed=("single", "multi"))
        if self.value is None:
            return
        if cardinality == "single":
            if isinstance(self.value, tuple):
                raise ProtocolShapeError("value must not be tuple when cardinality='single'")
            _validate_field_value(self.value, field_name="value", value_kind=value_kind)
            return
        if not isinstance(self.value, tuple):
            raise ProtocolShapeError("value must be tuple when cardinality='multi'")
        for idx, item in enumerate(self.value):
            _validate_field_value(item, field_name=f"value[{idx}]", value_kind=value_kind)


@dataclass(frozen=True)
class AssertionRecordDTO:
    assertion_id: str
    value: FieldValue | None = None
    active: bool = True
    meta: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.assertion_id, field_name="assertion_id")
        if self.value is not None:
            _validate_field_value(self.value, field_name="value")
        _require_bool(self.active, field_name="active")
        object.__setattr__(self, "meta", _validate_json_mapping(self.meta, field_name="meta"))


@dataclass(frozen=True)
class FieldAssertionsDTO:
    field: FieldPath
    active: tuple[AssertionRecordDTO, ...] = ()
    history: tuple[AssertionRecordDTO, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError("field must be FieldPath")
        _validate_tuple_items(self.active, field_name="active", item_type=AssertionRecordDTO)
        _validate_tuple_items(self.history, field_name="history", item_type=AssertionRecordDTO)


@dataclass(frozen=True)
class EntitySnapshotDTO:
    ref: EntityRef
    fields: dict[str, FieldValueDTO] = field(default_factory=dict)
    assertions: dict[str, FieldAssertionsDTO] = field(default_factory=dict)
    identity_available: bool = True
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.ref, EntityRef):
            raise ProtocolShapeError("ref must be EntityRef")
        if not isinstance(self.fields, dict):
            raise ProtocolShapeError("fields must be dict[str, FieldValueDTO]")
        for key, value in self.fields.items():
            _require_non_empty_str(key, field_name="fields.<key>")
            if not isinstance(value, FieldValueDTO):
                raise ProtocolShapeError(f"fields[{key!r}] must be FieldValueDTO")
            if value.field.field_name != key:
                raise ProtocolShapeError(f"fields[{key!r}] key must match FieldValueDTO.field.field_name")
            if value.field.entity_type != self.ref.entity_type:
                raise ProtocolShapeError(f"fields[{key!r}] must target entity_type={self.ref.entity_type!r}")
        if not isinstance(self.assertions, dict):
            raise ProtocolShapeError("assertions must be dict[str, FieldAssertionsDTO]")
        for key, value in self.assertions.items():
            _require_non_empty_str(key, field_name="assertions.<key>")
            if not isinstance(value, FieldAssertionsDTO):
                raise ProtocolShapeError(f"assertions[{key!r}] must be FieldAssertionsDTO")
            if value.field.field_name != key:
                raise ProtocolShapeError(f"assertions[{key!r}] key must match FieldAssertionsDTO.field.field_name")
            if value.field.entity_type != self.ref.entity_type:
                raise ProtocolShapeError(f"assertions[{key!r}] must target entity_type={self.ref.entity_type!r}")
        _require_bool(self.identity_available, field_name="identity_available")
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)


@dataclass(frozen=True)
class EntityReadRequest:
    mode: Literal["get", "find"]
    entity_type: str
    selector: EntitySelector | None = None
    field_filters: dict[str, FieldFilterValue] = field(default_factory=dict)
    limit: int | None = None
    include_assertions: bool = False
    include_history: bool = False
    at_time_ns: int | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        mode = _require_literal(self.mode, field_name="mode", allowed=("get", "find"))
        entity_type = _require_non_empty_str(self.entity_type, field_name="entity_type")
        if self.selector is not None:
            if not isinstance(self.selector, EntitySelector):
                raise ProtocolShapeError("selector must be EntitySelector")
            if self.selector.entity_type != entity_type:
                raise ProtocolShapeError("selector.entity_type must match entity_type")
        if mode == "get" and self.selector is None:
            raise ProtocolShapeError("selector is required when mode='get'")
        if mode != "find" and self.limit is not None:
            raise ProtocolShapeError("limit is only valid when mode='find'")
        if self.limit is not None and (isinstance(self.limit, bool) or not isinstance(self.limit, int) or self.limit < 0):
            raise ProtocolShapeError("limit must be non-negative int")
        _require_bool(self.include_assertions, field_name="include_assertions")
        _require_bool(self.include_history, field_name="include_history")
        if self.at_time_ns is not None:
            if isinstance(self.at_time_ns, bool) or not isinstance(self.at_time_ns, int):
                raise ProtocolShapeError("at_time_ns must be int")
        _require_optional_non_empty_str(self.version, field_name="version")
        if self.at_time_ns is not None and self.version is not None:
            raise ProtocolShapeError("at_time_ns and version are mutually exclusive")
        if not isinstance(self.field_filters, dict):
            raise ProtocolShapeError("field_filters must be dict[str, FieldFilterValue]")
        for key, value in self.field_filters.items():
            _require_non_empty_str(key, field_name="field_filters.<key>")
            if isinstance(value, tuple):
                for idx, item in enumerate(value):
                    _validate_field_value(item, field_name=f"field_filters[{key!r}][{idx}]")
            else:
                _validate_field_value(value, field_name=f"field_filters[{key!r}]")

    @property
    def effective_include_assertions(self) -> bool:
        return self.include_assertions or self.include_history


@dataclass(frozen=True)
class EntityReadResponse:
    mode: Literal["get", "find"]
    entity_type: str
    items: tuple[EntitySnapshotDTO, ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        mode = _require_literal(self.mode, field_name="mode", allowed=("get", "find"))
        entity_type = _require_non_empty_str(self.entity_type, field_name="entity_type")
        _validate_tuple_items(self.items, field_name="items", item_type=EntitySnapshotDTO)
        if mode == "get" and len(self.items) > 1:
            raise ProtocolShapeError("items must contain at most one snapshot when mode='get'")
        for idx, item in enumerate(self.items):
            if item.ref.entity_type != entity_type:
                raise ProtocolShapeError(f"items[{idx}] must target entity_type={entity_type!r}")
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)


__all__ = [
    "AssertionRecordDTO",
    "EntityReadRequest",
    "EntityReadResponse",
    "EntitySnapshotDTO",
    "FieldAssertionsDTO",
    "FieldFilterValue",
    "FieldValue",
    "FieldValueDTO",
]
