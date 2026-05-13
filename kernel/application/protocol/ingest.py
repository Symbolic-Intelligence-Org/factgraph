from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from .common import (
    ErrorDTO,
    JSONValue,
    ProtocolShapeError,
    WarningDTO,
    _require_literal,
    _require_non_empty_str,
    _validate_json_mapping,
    _validate_tuple_items,
)
from .entity_read import FieldValue, _validate_field_value
from .schema_runtime import EntitySelector, FieldPath


@dataclass(frozen=True)
class IngestSetItem:
    target: EntitySelector
    field: FieldPath
    value: FieldValue
    meta: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, EntitySelector):
            raise ProtocolShapeError("target must be EntitySelector")
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError("field must be FieldPath")
        if self.field.entity_type != self.target.entity_type:
            raise ProtocolShapeError(
                f"field.entity_type must match target.entity_type={self.target.entity_type!r}"
            )
        _validate_field_value(self.value, field_name="value")
        object.__setattr__(self, "meta", _validate_json_mapping(self.meta, field_name="meta"))


@dataclass(frozen=True)
class IngestAddItem:
    target: EntitySelector
    field: FieldPath
    value: FieldValue
    meta: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, EntitySelector):
            raise ProtocolShapeError("target must be EntitySelector")
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError("field must be FieldPath")
        if self.field.entity_type != self.target.entity_type:
            raise ProtocolShapeError(
                f"field.entity_type must match target.entity_type={self.target.entity_type!r}"
            )
        _validate_field_value(self.value, field_name="value")
        object.__setattr__(self, "meta", _validate_json_mapping(self.meta, field_name="meta"))


@dataclass(frozen=True)
class IngestRetractItem:
    assertion_id: str
    meta: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.assertion_id, field_name="assertion_id")
        object.__setattr__(self, "meta", _validate_json_mapping(self.meta, field_name="meta"))


IngestItem: TypeAlias = IngestSetItem | IngestAddItem | IngestRetractItem


@dataclass(frozen=True)
class IngestRequest:
    items: tuple[IngestItem, ...]
    collect_mode: Literal["stop", "collect"] = "stop"

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise ProtocolShapeError("items must be tuple")
        for idx, item in enumerate(self.items):
            if not isinstance(item, (IngestSetItem, IngestAddItem, IngestRetractItem)):
                raise ProtocolShapeError(
                    f"items[{idx}] must be IngestSetItem | IngestAddItem | IngestRetractItem"
                )
        _require_literal(self.collect_mode, field_name="collect_mode", allowed=("stop", "collect"))


@dataclass(frozen=True)
class IngestResult:
    written_assertion_ids: tuple[str, ...] = ()
    skipped_indices: tuple[int, ...] = ()
    duplicate_indices: tuple[int, ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.written_assertion_ids, tuple):
            raise ProtocolShapeError("written_assertion_ids must be tuple")
        for idx, item in enumerate(self.written_assertion_ids):
            if not isinstance(item, str):
                raise ProtocolShapeError(f"written_assertion_ids[{idx}] must be str")
        for name in ("skipped_indices", "duplicate_indices"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise ProtocolShapeError(f"{name} must be tuple")
            for idx, item in enumerate(value):
                if isinstance(item, bool) or not isinstance(item, int):
                    raise ProtocolShapeError(f"{name}[{idx}] must be int")
                if item < 0:
                    raise ProtocolShapeError(f"{name}[{idx}] must be non-negative")
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)


__all__ = [
    "IngestAddItem",
    "IngestItem",
    "IngestRequest",
    "IngestResult",
    "IngestRetractItem",
    "IngestSetItem",
]
