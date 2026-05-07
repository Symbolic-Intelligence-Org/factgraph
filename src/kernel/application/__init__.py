"""Application-layer modules built on top of core runtime primitives."""

from .capability_helpers import (
    CapabilityHelperError,
    OriginPackageError,
    build_check_request,
    build_diagnose_request,
    build_evaluation_overlay,
    build_fact_remove_action,
    build_fact_value_override,
    build_frontier_view_facts,
    build_why_not_candidate_universe,
)
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
from .fact_overlay_runtime import check_fact_overlay_binding
from .ingest_runtime import (
    IngestRuntimeError,
    apply_ingest_request,
)
from .query_runtime import (
    QueryRuntimeError,
    execute_query,
)
from .rule_disable_runtime import check_rule_disable_action
from .rule_add_condition_runtime import check_rule_add_condition_action
from .rule_literal_replace_runtime import check_rule_literal_replace_action
from .proofframe_runtime import (
    recheck_proof_frame,
    render_proof_frame_narrative,
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
from .why_not_runtime import (
    WhyNotRuntimeError,
    check_why_not_universe,
)

__all__ = [
    "CheckRuntimeError",
    "CapabilityHelperError",
    "DerivationRuntimeError",
    "DiagnoseRuntimeError",
    "EntityTypeInfo",
    "EntityViewError",
    "EntityWriteError",
    "FieldTypeInfo",
    "IdentityFieldInfo",
    "IngestRuntimeError",
    "OriginPackageError",
    "PredicateInfo",
    "QueryRuntimeError",
    "SchemaIndex",
    "SchemaResolutionError",
    "WhyNotRuntimeError",
    "accept_derivation_candidate_set",
    "accept_derivation_candidate_sets",
    "apply_ingest_request",
    "apply_write_plan",
    "build_check_request",
    "build_diagnose_request",
    "build_evaluation_overlay",
    "build_fact_remove_action",
    "build_schema_index",
    "build_fact_value_override",
    "build_frontier_view_facts",
    "build_why_not_candidate_universe",
    "check_derivation_binding",
    "check_fact_overlay_binding",
    "check_rule_add_condition_action",
    "check_rule_disable_action",
    "check_rule_literal_replace_action",
    "check_why_not_universe",
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
    "recheck_proof_frame",
    "render_proof_frame_narrative",
    "resolve_selector",
]
