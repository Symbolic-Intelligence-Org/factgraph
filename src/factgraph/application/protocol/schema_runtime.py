from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

from .common import (
    JSONValue,
    ProtocolShapeError,
    _require_non_empty_str,
    _require_optional_non_empty_str,
    _validate_json_mapping,
)

IdentityValue: TypeAlias = dict[str, JSONValue]


@dataclass(frozen=True)
class EntitySelector:
    entity_type: str
    identity: IdentityValue = field(default_factory=dict)
    encoded_ref: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.entity_type, field_name="entity_type")
        object.__setattr__(self, "identity", _validate_json_mapping(self.identity, field_name="identity"))
        _require_optional_non_empty_str(self.encoded_ref, field_name="encoded_ref")


@dataclass(frozen=True)
class EntityRef:
    entity_type: str
    identity: IdentityValue
    encoded_ref: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.entity_type, field_name="entity_type")
        identity = _validate_json_mapping(self.identity, field_name="identity")
        if not identity:
            raise ProtocolShapeError("identity must be non-empty for EntityRef")
        object.__setattr__(self, "identity", identity)
        _require_optional_non_empty_str(self.encoded_ref, field_name="encoded_ref")


@dataclass(frozen=True)
class FieldPath:
    entity_type: str
    field_name: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.entity_type, field_name="entity_type")
        _require_non_empty_str(self.field_name, field_name="field_name")


@dataclass(frozen=True)
class SchemaCapability:
    supports_atomic_multi_write: bool = False
    supports_post_write_recompute: bool = False
    supports_write_retract_combo: bool = False

    def __post_init__(self) -> None:
        _require_bool(self.supports_atomic_multi_write, field_name="supports_atomic_multi_write")
        _require_bool(self.supports_post_write_recompute, field_name="supports_post_write_recompute")
        _require_bool(self.supports_write_retract_combo, field_name="supports_write_retract_combo")


__all__ = [
    "EntityRef",
    "EntitySelector",
    "FieldPath",
    "IdentityValue",
    "SchemaCapability",
]
