from __future__ import annotations

from typing import Any

from kernel.authoring.schemas import compile_authoring_schema_v1, schema_preflight_authoring

from .errors import SDKSchemaError
from .schema import Entity, Relationship


def build_authoring_schema_from_classes(classes: list[type[Any]]) -> dict[str, Any]:
    if not isinstance(classes, list) or not classes:
        raise SDKSchemaError("classes must be non-empty list[Entity|Relationship]")
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    for index, cls in enumerate(classes):
        if isinstance(cls, type) and issubclass(cls, Relationship) and cls is not Relationship:
            relationships.append(dict(cls.sdk_relationship_spec()))
            continue
        if isinstance(cls, type) and issubclass(cls, Entity) and cls is not Entity:
            entities.append(dict(cls.sdk_entity_spec()))
            continue
        raise SDKSchemaError(f"classes[{index}] must be Entity or Relationship subclass")
    out: dict[str, Any] = {"entities": entities}
    if relationships:
        out["relationships"] = relationships
    return out


def compile_schema_from_classes(
    classes: list[type[Any]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_authoring_schema_from_classes(classes)
    return compile_authoring_schema_v1(payload, generated_at=generated_at)


def schema_preflight_from_classes(
    classes: list[type[Any]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_authoring_schema_from_classes(classes)
    return schema_preflight_authoring(payload, generated_at=generated_at)
