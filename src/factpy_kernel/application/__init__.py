"""Application-layer modules built on top of core runtime primitives."""

from .entity_view import (
    EntityViewError,
    execute_read_request,
    hydrate_entities,
    hydrate_entity,
)
from .entity_write import (
    EntityWriteError,
    apply_write_plan,
    plan_write_command,
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
    "EntityWriteError",
    "EntityTypeInfo",
    "FieldTypeInfo",
    "IdentityFieldInfo",
    "PredicateInfo",
    "SchemaIndex",
    "SchemaResolutionError",
    "apply_write_plan",
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
    "plan_write_command",
    "resolve_selector",
]
