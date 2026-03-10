"""Application-layer modules built on top of core runtime primitives."""

from .entity_view import (
    EntityViewError,
    execute_read_request,
    hydrate_entities,
    hydrate_entity,
)
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
    entity_type_from_ref,
    field_predicate,
    field_value_type,
    materialize_identity,
    resolve_selector,
)

__all__ = [
    "EntityViewError",
    "EntityTypeInfo",
    "FieldTypeInfo",
    "IdentityFieldInfo",
    "PredicateInfo",
    "SchemaIndex",
    "SchemaResolutionError",
    "build_schema_index",
    "encode_entity_ref",
    "entity_info",
    "entity_type_from_ref",
    "execute_read_request",
    "field_predicate",
    "field_value_type",
    "hydrate_entities",
    "hydrate_entity",
    "materialize_identity",
    "resolve_selector",
]
