from __future__ import annotations

from typing import Any

from factpy_kernel.authoring.preflight import schema_preflight_authoring
from factpy_kernel.authoring.schema_compile import compile_authoring_schema_v1

from .errors import SDKSchemaError
from .schema import Entity


def build_authoring_schema_from_classes(classes: list[type[Entity]]) -> dict[str, Any]:
    if not isinstance(classes, list) or not classes:
        raise SDKSchemaError("classes must be non-empty list[Entity]")
    entities: list[dict[str, Any]] = []
    for index, cls in enumerate(classes):
        if not isinstance(cls, type) or not issubclass(cls, Entity):
            raise SDKSchemaError(f"classes[{index}] must be Entity subclass")
        entities.append(dict(cls.sdk_entity_spec()))
    return {"entities": entities}


def compile_schema_from_classes(
    classes: list[type[Entity]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_authoring_schema_from_classes(classes)
    return compile_authoring_schema_v1(payload, generated_at=generated_at)


def schema_preflight_from_classes(
    classes: list[type[Entity]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_authoring_schema_from_classes(classes)
    return schema_preflight_authoring(payload, generated_at=generated_at)

