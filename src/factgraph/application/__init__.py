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
    build_proof_frame_recheck_request,
    build_round_event_payload,
    build_rule_add_condition_request,
    build_rule_disable_request,
    build_rule_literal_replace_request,
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
from .entity_visibility import (
    is_entity_identity_bundle_active,
)
from .entity_write import (
    EntityWriteError,
    apply_create_plan,
    apply_delete_plan,
    apply_write_plan,
    apply_write_plans,
    plan_create_command,
    plan_delete_command,
    plan_write_command,
    planned_ops_to_inputs,
)
from .fact_overlay_runtime import check_fact_overlay_binding
from .ingest_runtime import (
    IngestRuntimeError,
    apply_ingest_request,
)
from .walker import (
    AssertionView,
    ConditionKeyView,
    FrozenTupleView,
    IRAtomView,
    IRBodyWalker,
    ProofFrameDiffView,
    ProofFrameView,
    SupportArtifactView,
    frozen_collection,
    parse_condition_key,
)
from .workspace_runtime import (
    WORKSPACE_LEDGER,
    WORKSPACE_MANIFEST_NAME,
    WORKSPACE_SAVE_SCOPE,
    WORKSPACE_VERSION,
    WorkspacePaths,
    WorkspaceRuntimeError,
    copy_ledger_to_workspace,
    load_workspace,
    resolve_workspace_paths,
    save_workspace,
    save_workspace_manifest,
    validate_workspace_manifest,
    workspace_manifest_payload,
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
    render_entity_repr,
    resolve_selector,
)
from .semantic_port_runtime import (
    ResolvedRuleBundle,
    SemanticPortResolutionError,
    assert_rule_contract_current,
    build_resolved_rule,
    resolve_rule_contract,
)
from .semantic_address_runtime import (
    ManagedRuleOccurrence,
    SemanticAddressResolutionError,
    SemanticAddressSpace,
    manage_rule_occurrence,
)
from .policy_runtime import (
    CompiledPolicyV0,
    PolicyCompiledBranch,
    PolicyRulePin,
    compile_policy,
)
from .evaluation_query_runtime import (
    CompiledEvaluationQueryV0,
    compile_evaluation_query,
)
from .evaluation_expectation_runtime import (
    EvaluationExpectationError,
    assert_compiled_contains_row_expectation_current,
    compile_contains_row_expectations_v0,
    evaluate_contains_row_expectations_v0,
)
from .evaluation_query_target_runtime import (
    EvaluationQueryTargetError,
    ResolvedEvaluationQueryTargetV1,
    TargetedCompiledEvaluationQueryV0,
    assert_targeted_evaluation_query_current,
    compile_targeted_evaluation_query,
    resolve_evaluation_query_target,
)
from .evaluation_run_bundle_runtime import (
    evaluation_run_bundle_bytes,
    evaluation_run_bundle_from_bytes,
)
from .evaluation_run_verification_runtime import verify_evaluation_run_bundle
from .evaluation_run_evidence_runtime import evaluation_run_bundle_evidence
from .policy_explanation_runtime import project_policy_explanation_v0
from .scenario_run_runtime import (
    scenario_run_bytes,
    scenario_run_from_bytes,
)
from .authoring_runtime import AuthoringRuntimeError
from .why_not_runtime import (
    WhyNotRuntimeError,
    check_why_not_universe,
)

__all__ = [
    "AssertionView",
    "EvaluationExpectationError",
    "assert_compiled_contains_row_expectation_current",
    "compile_contains_row_expectations_v0",
    "evaluate_contains_row_expectations_v0",
    "ConditionKeyView",
    "AuthoringRuntimeError",
    "CheckRuntimeError",
    "CompiledPolicyV0",
    "CompiledEvaluationQueryV0",
    "EvaluationQueryTargetError",
    "scenario_run_bytes",
    "scenario_run_from_bytes",
    "CapabilityHelperError",
    "DerivationRuntimeError",
    "DiagnoseRuntimeError",
    "EntityTypeInfo",
    "EntityViewError",
    "EntityWriteError",
    "FieldTypeInfo",
    "FrozenTupleView",
    "IdentityFieldInfo",
    "IngestRuntimeError",
    "IRAtomView",
    "IRBodyWalker",
    "OriginPackageError",
    "ManagedRuleOccurrence",
    "PredicateInfo",
    "PolicyCompiledBranch",
    "PolicyRulePin",
    "ProofFrameDiffView",
    "ProofFrameView",
    "QueryRuntimeError",
    "ResolvedRuleBundle",
    "ResolvedEvaluationQueryTargetV1",
    "SchemaIndex",
    "SchemaResolutionError",
    "SemanticPortResolutionError",
    "SemanticAddressResolutionError",
    "SemanticAddressSpace",
    "SupportArtifactView",
    "TargetedCompiledEvaluationQueryV0",
    "WORKSPACE_LEDGER",
    "WORKSPACE_MANIFEST_NAME",
    "WORKSPACE_SAVE_SCOPE",
    "WORKSPACE_VERSION",
    "WorkspacePaths",
    "WorkspaceRuntimeError",
    "WhyNotRuntimeError",
    "accept_derivation_candidate_set",
    "accept_derivation_candidate_sets",
    "apply_ingest_request",
    "apply_create_plan",
    "apply_delete_plan",
    "apply_write_plan",
    "apply_write_plans",
    "build_check_request",
    "build_diagnose_request",
    "build_evaluation_overlay",
    "build_fact_remove_action",
    "build_schema_index",
    "build_fact_value_override",
    "build_frontier_view_facts",
    "build_proof_frame_recheck_request",
    "build_round_event_payload",
    "build_resolved_rule",
    "build_rule_add_condition_request",
    "build_rule_disable_request",
    "build_rule_literal_replace_request",
    "build_why_not_candidate_universe",
    "check_derivation_binding",
    "check_fact_overlay_binding",
    "check_rule_add_condition_action",
    "check_rule_disable_action",
    "check_rule_literal_replace_action",
    "check_why_not_universe",
    "compile_policy",
    "compile_evaluation_query",
    "compile_targeted_evaluation_query",
    "evaluation_run_bundle_bytes",
    "evaluation_run_bundle_from_bytes",
    "evaluation_run_bundle_evidence",
    "project_policy_explanation_v0",
    "verify_evaluation_run_bundle",
    "copy_ledger_to_workspace",
    "diagnose_derivation_binding",
    "encode_entity_ref",
    "entity_info",
    "entity_type_from_ref",
    "evaluate_derivation_plans",
    "execute_query",
    "execute_read_request",
    "field_predicate",
    "field_value_type",
    "frozen_collection",
    "hydrate_entities",
    "hydrate_entity",
    "is_entity_identity_bundle_active",
    "load_workspace",
    "materialize_identity",
    "manage_rule_occurrence",
    "parse_condition_key",
    "planned_ops_to_inputs",
    "plan_create_command",
    "plan_delete_command",
    "plan_write_command",
    "recheck_proof_frame",
    "render_entity_repr",
    "resolve_rule_contract",
    "resolve_evaluation_query_target",
    "render_proof_frame_narrative",
    "resolve_workspace_paths",
    "save_workspace",
    "save_workspace_manifest",
    "resolve_selector",
    "assert_rule_contract_current",
    "assert_targeted_evaluation_query_current",
    "validate_workspace_manifest",
    "workspace_manifest_payload",
]
