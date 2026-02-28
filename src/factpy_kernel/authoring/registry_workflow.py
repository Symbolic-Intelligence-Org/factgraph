from __future__ import annotations

"""
High-level authoring entrypoints for registry-backed workflow/session operations.

This groups the registry filesystem backend together with publish/apply/session
helpers so callers can stay on a smaller module surface.
"""

from .apply_execute import (
    AuthoringApplyExecuteError,
    build_authoring_apply_execute_result_dto,
    build_authoring_publish_workflow_apply_bundle_dto,
)
from .dsl_bridge import (
    AuthoringDSLBridgeError,
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto,
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto,
    build_authoring_session_from_dsl_inputs_dto,
    build_authoring_session_from_dsl_inputs_safe_dto,
)
from .publish import (
    AuthoringPublishError,
    build_authoring_apply_dry_run_result_dto,
    build_authoring_publish_plan_dto,
)
from .registry_fs import AuthoringRegistryFSError, FileAuthoringRegistry
from .session import AuthoringSessionError, build_authoring_session_dto
from .workflow import AuthoringWorkflowError, build_authoring_publish_workflow_dry_run_bundle_dto

__all__ = [
    "AuthoringApplyExecuteError",
    "AuthoringDSLBridgeError",
    "AuthoringPublishError",
    "AuthoringRegistryFSError",
    "AuthoringSessionError",
    "AuthoringWorkflowError",
    "FileAuthoringRegistry",
    "build_authoring_apply_dry_run_result_dto",
    "build_authoring_apply_execute_result_dto",
    "build_authoring_publish_plan_dto",
    "build_authoring_publish_workflow_apply_bundle_dto",
    "build_authoring_publish_workflow_dry_run_bundle_dto",
    "build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto",
    "build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto",
    "build_authoring_session_dto",
    "build_authoring_session_from_dsl_inputs_dto",
    "build_authoring_session_from_dsl_inputs_safe_dto",
]
