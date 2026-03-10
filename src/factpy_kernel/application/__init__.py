"""Application-layer modules built on top of core runtime primitives."""

from .schema_runtime import (
    EntityTypeInfo,
    IdentityFieldInfo,
    PredicateInfo,
    SchemaIndex,
    SchemaResolutionError,
    build_schema_index,
    encode_entity_ref,
    entity_info,
    field_predicate,
    materialize_identity,
    resolve_selector,
)

__all__ = [
    "EntityTypeInfo",
    "IdentityFieldInfo",
    "PredicateInfo",
    "SchemaIndex",
    "SchemaResolutionError",
    "build_schema_index",
    "encode_entity_ref",
    "entity_info",
    "field_predicate",
    "materialize_identity",
    "resolve_selector",
]
