from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factgraph.authoring.schemas import compile_authoring_schema_v1, schema_preflight_authoring
from factgraph.core.schema.meta_policy import (
    MetaKeyPolicy,
    MetaKeyPolicyError,
    typed_meta_keys_to_authoring,
)

from .errors import SDKSchemaError
from .schema import Entity, Relationship


def build_authoring_schema_from_classes(
    classes: list[type[Any]],
    *,
    meta_keys: Mapping[str, MetaKeyPolicy] | None = None,
) -> dict[str, Any]:
    """Build authoring-schema input from SDK schema classes.

    This is the lower-level bridge used before schema compilation. Most users
    should pass `schema_classes=[...]` to `FactGraph.create(...)` instead.

    Args:
        classes: Non-empty list of `Entity` or `Relationship` subclasses.
        meta_keys: Optional schema-global typed meta-key declarations.

    Returns:
        Authoring-schema payload with `entities` and optional `relationships`.
    """
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
    try:
        meta_keys_out = typed_meta_keys_to_authoring(meta_keys)
    except MetaKeyPolicyError as exc:
        raise SDKSchemaError(str(exc)) from exc
    if meta_keys_out is not None:
        out["meta_keys"] = meta_keys_out
    return out


def compile_schema_from_classes(
    classes: list[type[Any]],
    *,
    generated_at: str | None = None,
    meta_keys: Mapping[str, MetaKeyPolicy] | None = None,
) -> dict[str, Any]:
    """Compile SDK schema classes into canonical schema IR.

    Use this helper when you need the exact schema dictionary that backs a
    `FactGraph`. Normal graph construction calls it for you.

    Args:
        classes: Non-empty list of `Entity` or `Relationship` subclasses.
        generated_at: Optional timestamp override for deterministic tests.
        meta_keys: Optional schema-global typed meta-key declarations.

    Returns:
        Canonical schema IR dictionary.
    """
    payload = build_authoring_schema_from_classes(classes, meta_keys=meta_keys)
    return compile_authoring_schema_v1(payload, generated_at=generated_at)


def schema_preflight_from_classes(
    classes: list[type[Any]],
    *,
    generated_at: str | None = None,
    meta_keys: Mapping[str, MetaKeyPolicy] | None = None,
) -> dict[str, Any]:
    """Validate SDK schema classes without creating a graph.

    This returns the authoring preflight report produced by the schema compiler.
    It is useful for tools that want schema diagnostics before constructing a
    `FactGraph`.

    Args:
        classes: Non-empty list of `Entity` or `Relationship` subclasses.
        generated_at: Optional timestamp override for deterministic tests.
        meta_keys: Optional schema-global typed meta-key declarations.

    Returns:
        Schema preflight report dictionary.
    """
    payload = build_authoring_schema_from_classes(classes, meta_keys=meta_keys)
    return schema_preflight_authoring(payload, generated_at=generated_at)
