"""Application-layer modules built on top of core runtime primitives."""

from .derivation_check_runtime import (
    CheckRuntimeError,
    check_derivation_binding,
)
from .derivation_runtime import (
    DerivationRuntimeError,
    accept_derivation_candidate_set,
    accept_derivation_candidate_sets,
    evaluate_derivation_plans,
)
from .diagnose_runtime import (
    DiagnoseRuntimeError,
    diagnose_derivation_binding,
)
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
from .ingest_runtime import (
    IngestRuntimeError,
    apply_ingest_request,
)
from .query_runtime import (
    QueryRuntimeError,
    execute_query,
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
    "CheckRuntimeError",
    "DerivationRuntimeError",
    "DiagnoseRuntimeError",
    "EntityTypeInfo",
    "EntityViewError",
    "EntityWriteError",
    "FieldTypeInfo",
    "IdentityFieldInfo",
    "IngestRuntimeError",
    "PredicateInfo",
    "QueryRuntimeError",
    "SchemaIndex",
    "SchemaResolutionError",
    "accept_derivation_candidate_set",
    "accept_derivation_candidate_sets",
    "apply_ingest_request",
    "apply_write_plan",
    "build_schema_index",
    "check_derivation_binding",
    "diagnose_derivation_binding",
    "encode_entity_ref",
    "entity_info",
    "entity_type_from_ref",
    "evaluate_derivation_plans",
    "execute_query",
    "execute_read_request",
    "field_predicate",
    "field_value_type",
    "hydrate_entities",
    "hydrate_entity",
    "materialize_identity",
    "plan_write_command",
    "resolve_selector",
]
