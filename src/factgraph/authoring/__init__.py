from __future__ import annotations

from .cli import AuthoringCLIError
from .cli import main as authoring_cli_main
from .derivations import (
    AuthoringDerivationCompileError,
    AuthoringDerivationDSLParseError,
    AuthoringPreflightError,
    compile_authoring_derivation_v1,
    derivation_dry_run_preview,
    derivation_dry_run_preview_authoring,
    parse_authoring_derivation_dsl_v1,
)
from .diagnostic_codes import (
    AUTHORING_DIAGNOSTIC_CODES_V1,
    AUTHORING_DIAGNOSTIC_PHASES_V1,
    build_diagnostics_contract_meta_v1,
)
from .dsl_bridge import (
    AuthoringDSLBridgeError,
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto,
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto,
    build_authoring_session_from_dsl_inputs_dto,
    build_authoring_session_from_dsl_inputs_safe_dto,
)
from .dto import (
    AuthoringDTOError,
    build_derivation_preview_dto,
    build_derivation_preview_from_authoring_dto,
    build_rule_preflight_dto,
    build_rule_preflight_from_authoring_dto,
    build_schema_preflight_dto,
    build_schema_preflight_from_authoring_dto,
)
from .publish import (
    AuthoringPublishError,
    build_authoring_apply_dry_run_result_dto,
    build_authoring_publish_plan_dto,
)
from .rules import (
    AuthoringRuleCompileError,
    AuthoringRuleDSLParseError,
    compile_authoring_rule_v1,
    parse_authoring_rule_dsl_v1,
    rule_preflight,
    rule_preflight_authoring,
)
from .schemas import (
    AuthoringSchemaCompileError,
    AuthoringSchemaDSLParseError,
    compile_authoring_schema_v1,
    parse_authoring_schema_dsl_v1,
    schema_preflight,
    schema_preflight_authoring,
)
from .session import AuthoringSessionError, build_authoring_session_dto
from .workflow import (
    AuthoringWorkflowError,
    build_authoring_publish_workflow_dry_run_bundle_dto,
)

__all__ = [
    "AUTHORING_DIAGNOSTIC_CODES_V1",
    "AUTHORING_DIAGNOSTIC_PHASES_V1",
    "build_diagnostics_contract_meta_v1",
    "AuthoringPreflightError",
    "schema_preflight",
    "rule_preflight",
    "rule_preflight_authoring",
    "derivation_dry_run_preview",
    "derivation_dry_run_preview_authoring",
    "schema_preflight_authoring",
    "AuthoringDTOError",
    "build_schema_preflight_dto",
    "build_schema_preflight_from_authoring_dto",
    "build_rule_preflight_dto",
    "build_rule_preflight_from_authoring_dto",
    "build_derivation_preview_dto",
    "build_derivation_preview_from_authoring_dto",
    "AuthoringSessionError",
    "build_authoring_session_dto",
    "AuthoringPublishError",
    "build_authoring_publish_plan_dto",
    "build_authoring_apply_dry_run_result_dto",
    "AuthoringWorkflowError",
    "build_authoring_publish_workflow_dry_run_bundle_dto",
    "AuthoringDSLBridgeError",
    "build_authoring_session_from_dsl_inputs_dto",
    "build_authoring_session_from_dsl_inputs_safe_dto",
    "build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto",
    "build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto",
    "AuthoringSchemaCompileError",
    "compile_authoring_schema_v1",
    "AuthoringSchemaDSLParseError",
    "parse_authoring_schema_dsl_v1",
    "AuthoringRuleCompileError",
    "compile_authoring_rule_v1",
    "AuthoringRuleDSLParseError",
    "parse_authoring_rule_dsl_v1",
    "AuthoringDerivationCompileError",
    "compile_authoring_derivation_v1",
    "AuthoringDerivationDSLParseError",
    "parse_authoring_derivation_dsl_v1",
    "AuthoringCLIError",
    "authoring_cli_main",
]
