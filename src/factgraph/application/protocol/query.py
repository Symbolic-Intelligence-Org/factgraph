from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from .common import (
    ErrorDTO,
    ProtocolShapeError,
    WarningDTO,
    _require_literal,
    _require_non_empty_str,
    _require_optional_non_empty_str,
    _validate_tuple_items,
)
from .entity_read import EntitySnapshotDTO, FieldValue
from .schema_runtime import FieldPath

WhereIR: TypeAlias = list[Any]


@dataclass(frozen=True)
class QueryReturnSlot:
    alias: str
    kind: Literal["entity", "scalar"]
    var: str
    field_path: FieldPath | None = None
    entity_type: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.alias, field_name="alias")
        _require_literal(self.kind, field_name="kind", allowed=("entity", "scalar"))
        _require_non_empty_str(self.var, field_name="var")
        if self.kind == "entity":
            if self.field_path is not None:
                raise ProtocolShapeError("field_path must be None when kind='entity'")
        if self.kind == "scalar":
            if self.field_path is None:
                raise ProtocolShapeError("field_path is required when kind='scalar'")
            if not isinstance(self.field_path, FieldPath):
                raise ProtocolShapeError("field_path must be FieldPath when kind='scalar'")
            if self.entity_type is not None:
                raise ProtocolShapeError("entity_type must be None when kind='scalar'")
        if self.entity_type is not None and not isinstance(self.entity_type, str):
            raise ProtocolShapeError("entity_type must be str or None")
        if isinstance(self.entity_type, str) and not self.entity_type:
            raise ProtocolShapeError("entity_type must be non-empty when provided")


@dataclass(frozen=True)
class QueryReturnContract:
    slots: tuple[QueryReturnSlot, ...]

    def __post_init__(self) -> None:
        _validate_tuple_items(self.slots, field_name="slots", item_type=QueryReturnSlot)
        if not self.slots:
            raise ProtocolShapeError("slots must not be empty")
        seen: set[str] = set()
        for idx, slot in enumerate(self.slots):
            if slot.alias in seen:
                raise ProtocolShapeError(f"slots[{idx}] alias must be unique: {slot.alias!r}")
            seen.add(slot.alias)


@dataclass(frozen=True)
class QueryRuntimeRequest:
    entity_type: str
    where_ir: WhereIR
    return_contract: QueryReturnContract
    on_missing: Literal["skip", "error", "null"] = "skip"
    on_type_mismatch: Literal["error", "skip", "null"] = "error"
    query_id: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.entity_type, field_name="entity_type")
        if not isinstance(self.where_ir, list):
            raise ProtocolShapeError("where_ir must be list")
        if not isinstance(self.return_contract, QueryReturnContract):
            raise ProtocolShapeError("return_contract must be QueryReturnContract")
        _require_literal(
            self.on_missing,
            field_name="on_missing",
            allowed=("skip", "error", "null"),
        )
        _require_literal(
            self.on_type_mismatch,
            field_name="on_type_mismatch",
            allowed=("error", "skip", "null"),
        )
        _require_optional_non_empty_str(self.query_id, field_name="query_id")
        _require_optional_non_empty_str(self.version, field_name="version")


QueryRowValue: TypeAlias = EntitySnapshotDTO | FieldValue | None


@dataclass(frozen=True)
class QueryRuntimeResponse:
    rows: tuple[dict[str, QueryRowValue], ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple):
            raise ProtocolShapeError("rows must be tuple")
        for idx, row in enumerate(self.rows):
            if not isinstance(row, dict):
                raise ProtocolShapeError(f"rows[{idx}] must be dict")
            for key in row:
                if not isinstance(key, str):
                    raise ProtocolShapeError(f"rows[{idx}] keys must be str")
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)


__all__ = [
    "QueryReturnContract",
    "QueryReturnSlot",
    "QueryRowValue",
    "QueryRuntimeRequest",
    "QueryRuntimeResponse",
    "WhereIR",
]
