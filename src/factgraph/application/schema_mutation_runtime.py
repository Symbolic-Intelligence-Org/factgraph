"""Application-layer helpers for additive schema mutation.

This module owns schema-extension validation and transition planning. SDK
facades adapt these pure helpers into ``fg.schema.register(...)`` /
``fg.schema.extend(...)`` / ``fg.schema.apply(...)``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factgraph.core.schema.schema_ir import ensure_schema_ir, schema_digest
from factgraph.sdk.compile import compile_schema_from_classes
from factgraph.sdk.errors import SDKStoreError
from factgraph.sdk.schema import Entity


@dataclass(frozen=True)
class SchemaAddResult:
    """Result returned by additive schema registration or extension calls.

    `old_digest` and `new_digest` identify the schema transition. New entity
    types appear in `added_entities`; new non-identity fields on existing
    entity types appear in `added_fields` as strings such as
    `"User.nickname"`.
    """

    old_digest: str
    new_digest: str
    added_entities: list[str]
    added_fields: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.old_digest, field_name="old_digest")
        _validate_non_empty_text(self.new_digest, field_name="new_digest")
        _validate_text_list(self.added_entities, field_name="added_entities")
        _validate_text_list(self.added_fields, field_name="added_fields")


@dataclass(frozen=True)
class AdditiveExtensionResult:
    schema_ir: dict[str, Any]
    schema_digest: str
    classes: list[type[Entity]]
    added_entities: list[str]
    added_fields: list[str] = field(default_factory=list)


def validate_additive_schema_extension(
    *,
    current_schema_ir: dict[str, Any],
    candidate_schema_ir: dict[str, Any],
) -> None:
    current = ensure_schema_ir(current_schema_ir)
    candidate = ensure_schema_ir(candidate_schema_ir)

    current_entities = _entities_by_type(current)
    candidate_entities = _entities_by_type(candidate)
    for entity_type, current_entity in current_entities.items():
        candidate_entity = candidate_entities.get(entity_type)
        if candidate_entity is None:
            raise SDKStoreError(f"existing entity type removed: {entity_type}")
        if current_entity.get("identity_fields") != candidate_entity.get("identity_fields"):
            raise SDKStoreError(f"identity field changed for existing entity type: {entity_type}")

    current_predicates = _predicates_by_id(current)
    candidate_predicates = _predicates_by_id(candidate)
    duplicate_candidate_pred_ids = _duplicate_predicate_ids(candidate)
    for pred_id in sorted(duplicate_candidate_pred_ids):
        if pred_id in current_predicates:
            raise SDKStoreError(f"predicate id collision for additive schema extension: {pred_id}")
        raise SDKStoreError(f"duplicate predicate id in candidate schema: {pred_id}")

    for pred_id, current_predicate in current_predicates.items():
        candidate_predicate = candidate_predicates.get(pred_id)
        if candidate_predicate is None:
            raise SDKStoreError(f"existing predicate id removed or changed: {pred_id}")
        if _relationship_targets(current_predicate) != _relationship_targets(candidate_predicate):
            raise SDKStoreError(f"relationship target changed for existing predicate: {pred_id}")
        if _predicate_stable_projection(current_predicate) != _predicate_stable_projection(candidate_predicate):
            raise SDKStoreError(f"existing field changed for predicate: {pred_id}")

    added_entity_types = set(candidate_entities) - set(current_entities)
    for pred_id, candidate_predicate in candidate_predicates.items():
        if pred_id in current_predicates:
            continue
        owner_type = candidate_predicate.get("owner_type")
        if not isinstance(owner_type, str) or not owner_type:
            raise SDKStoreError(f"new predicate owner_type missing for additive schema extension: {pred_id}")
        if owner_type in added_entity_types:
            continue
        if owner_type not in current_entities:
            raise SDKStoreError(f"new predicate owner is not an entity type in additive schema extension: {pred_id}")
        if candidate_predicate.get("is_identity_field") is True:
            raise SDKStoreError(f"identity field addition is not supported: {pred_id}")
        if candidate_predicate.get("is_entity_exists") is True:
            raise SDKStoreError(f"entity-exists predicate addition is not supported for existing entity: {pred_id}")
        if "relationship_type" in candidate_predicate:
            raise SDKStoreError(f"relationship predicate addition is not supported in field-add slice: {pred_id}")


def add_schema_classes(
    *,
    current_classes: list[type[Entity]],
    schema_classes: list[type[Entity]],
) -> AdditiveExtensionResult:
    if not isinstance(current_classes, list) or not current_classes:
        raise SDKStoreError("current_classes must be non-empty list[Entity]")
    additions = _normalize_entity_classes(schema_classes, field_name="schema_classes")
    current_by_type = _classes_by_entity_type(current_classes)
    additions_by_type = _classes_by_entity_type(additions)

    next_classes = list(current_classes)
    added_entities: list[str] = []
    added_fields: list[str] = []
    for entity_type, cls in additions_by_type.items():
        if entity_type in current_by_type:
            current_cls = current_by_type[entity_type]
            current_schema = compile_schema_from_classes([current_cls])
            candidate_schema = compile_schema_from_classes([cls])
            validate_additive_schema_extension(
                current_schema_ir=current_schema,
                candidate_schema_ir=candidate_schema,
            )
            field_additions = _added_fields_for_entity(
                current_cls=current_cls,
                candidate_cls=cls,
                entity_type=entity_type,
            )
            if field_additions:
                next_classes = [cls if existing is current_cls else existing for existing in next_classes]
                added_fields.extend(field_additions)
            continue
        next_classes.append(cls)
        added_entities.append(entity_type)

    current_schema_ir = compile_schema_from_classes(current_classes)
    candidate_schema_ir = compile_schema_from_classes(next_classes)
    validate_additive_schema_extension(
        current_schema_ir=current_schema_ir,
        candidate_schema_ir=candidate_schema_ir,
    )
    return AdditiveExtensionResult(
        schema_ir=candidate_schema_ir,
        schema_digest=schema_digest(candidate_schema_ir),
        classes=next_classes,
        added_entities=added_entities,
        added_fields=added_fields,
    )


def _validate_non_empty_text(value: Any, *, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise SDKStoreError(f"{field_name} must be non-empty string")


def _validate_text_list(value: Any, *, field_name: str) -> None:
    if not isinstance(value, list):
        raise SDKStoreError(f"{field_name} must be list[str]")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise SDKStoreError(f"{field_name}[{index}] must be non-empty string")


def _normalize_entity_classes(value: Any, *, field_name: str) -> list[type[Entity]]:
    if isinstance(value, type) and issubclass(value, Entity) and value is not Entity:
        return [value]
    if not isinstance(value, list) or not value:
        raise SDKStoreError(f"{field_name} must be non-empty list[Entity]")
    out: list[type[Entity]] = []
    for index, cls in enumerate(value):
        if not isinstance(cls, type) or not issubclass(cls, Entity) or cls is Entity:
            raise SDKStoreError(f"{field_name}[{index}] must be Entity subclass")
        out.append(cls)
    return out


def _added_fields_for_entity(
    *,
    current_cls: type[Entity],
    candidate_cls: type[Entity],
    entity_type: str,
) -> list[str]:
    current_fields = {
        field.get("py_name")
        for field in current_cls.sdk_entity_spec().get("fields", [])
        if isinstance(field, dict) and isinstance(field.get("py_name"), str)
    }
    out: list[str] = []
    for field_row in candidate_cls.sdk_entity_spec().get("fields", []):
        if not isinstance(field_row, dict):
            continue
        py_name = field_row.get("py_name")
        if isinstance(py_name, str) and py_name not in current_fields:
            out.append(f"{entity_type}.{py_name}")
    return out


def _classes_by_entity_type(classes: list[type[Entity]]) -> dict[str, type[Entity]]:
    out: dict[str, type[Entity]] = {}
    for cls in _normalize_entity_classes(classes, field_name="classes"):
        entity_type = str(cls.sdk_entity_spec()["entity_type"])
        if entity_type in out:
            raise SDKStoreError(f"duplicate entity type: {entity_type}")
        out[entity_type] = cls
    return out


def _entities_by_type(schema_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entity in schema_ir.get("entities", []):
        entity_type = entity.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type:
            raise SDKStoreError("schema_ir.entities[*].entity_type must be non-empty string")
        if entity_type in out:
            raise SDKStoreError(f"duplicate entity type in schema_ir: {entity_type}")
        out[entity_type] = dict(entity)
    return out


def _predicates_by_id(schema_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for predicate in schema_ir.get("predicates", []):
        pred_id = predicate.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            raise SDKStoreError("schema_ir.predicates[*].pred_id must be non-empty string")
        out[pred_id] = dict(predicate)
    return out


def _duplicate_predicate_ids(schema_ir: dict[str, Any]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for predicate in schema_ir.get("predicates", []):
        pred_id = predicate.get("pred_id")
        if isinstance(pred_id, str):
            if pred_id in seen:
                duplicates.add(pred_id)
            seen.add(pred_id)
    return duplicates


def _relationship_targets(predicate: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (
        predicate.get("relationship_type"),
        predicate.get("from_entity_type"),
        predicate.get("to_entity_type"),
    )


def _predicate_stable_projection(predicate: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "arg_specs",
        "arity",
        "cardinality",
        "from_entity_type",
        "group_key_indexes",
        "is_entity_exists",
        "is_identity_field",
        "owner_type",
        "pred_id",
        "py_field_name",
        "relationship_type",
        "to_entity_type",
    }
    return {key: predicate.get(key) for key in keys if key in predicate}


__all__ = [
    "AdditiveExtensionResult",
    "SchemaAddResult",
    "add_schema_classes",
    "validate_additive_schema_extension",
]
