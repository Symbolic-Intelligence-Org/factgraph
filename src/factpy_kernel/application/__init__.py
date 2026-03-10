"""Application-layer modules built on top of core runtime primitives."""

from .schema_runtime import (
    EntityTypeInfo,
    FieldTypeInfo,
    IdentityFieldInfo,
    PredicateInfo,
    SchemaIndex,
    SchemaResolutionError,
    build_schema_index,
    encode_entity_ref,
    entity_info,
    field_predicate,
    field_value_type,
    materialize_identity,
    resolve_selector,
)

__all__ = [
    "EntityTypeInfo",
    "FieldTypeInfo",
    "IdentityFieldInfo",
    "PredicateInfo",
    "SchemaIndex",
    "SchemaResolutionError",
    "build_schema_index",
    "encode_entity_ref",
    "entity_info",
    "field_predicate",
    "field_value_type",
    "materialize_identity",
    "resolve_selector",
]
