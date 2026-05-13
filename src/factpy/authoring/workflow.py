from __future__ import annotations

from typing import Any

from factpy.authoring.apply_execute import (
    build_authoring_publish_workflow_apply_bundle_dto,
)
from factpy.authoring.publish import (
    AuthoringPublishError,
    build_authoring_apply_dry_run_result_dto,
    build_authoring_publish_plan_dto,
)


class AuthoringWorkflowError(Exception):
    pass


__all__ = [
    "AuthoringWorkflowError",
    "build_authoring_publish_workflow_dry_run_bundle_dto",
    "build_authoring_publish_workflow_apply_bundle_dto",
]


def build_authoring_publish_workflow_dry_run_bundle_dto(
    session_dto: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(session_dto, dict):
        raise AuthoringWorkflowError("session_dto must be dict")
    try:
        publish_plan = build_authoring_publish_plan_dto(session_dto)
        apply_result = build_authoring_apply_dry_run_result_dto(publish_plan)
    except AuthoringPublishError as exc:
        raise AuthoringWorkflowError(str(exc)) from exc

    diagnostics_contract = (
        apply_result.get("diagnostics_contract")
        or publish_plan.get("diagnostics_contract")
        or session_dto.get("diagnostics_contract")
        or {}
    )
    session_status = str(session_dto.get("status", "ok"))
    plan_status = str(publish_plan.get("status", "ok"))
    apply_status = str(apply_result.get("status", "ok"))
    status = _aggregate_bundle_status(session_status, plan_status, apply_status)
    ok = bool(session_dto.get("ok")) and bool(publish_plan.get("ok")) and bool(apply_result.get("ok"))

    return {
        "authoring_publish_workflow_bundle_dto_version": "authoring_publish_workflow_bundle_dto_v1",
        "kind": "authoring_publish_workflow_bundle",
        "mode": "dry_run_only",
        "diagnostics_contract": _json_safe(diagnostics_contract),
        "ok": ok,
        "status": status,
        "session": _json_safe(session_dto),
        "publish_plan": _json_safe(publish_plan),
        "apply_result": _json_safe(apply_result),
        "summary": {
            "session_status": session_status,
            "publish_plan_status": plan_status,
            "apply_result_status": apply_status,
            "session_section_count": _nested_int(session_dto, "summary", "section_count"),
            "publish_action_count": _nested_int(publish_plan, "summary", "action_count"),
            "apply_action_count": _nested_int(apply_result, "summary", "action_count"),
            "diagnostic_count": _nested_int(apply_result, "summary", "diagnostic_count"),
            "warning_count": _nested_int(apply_result, "summary", "warning_count"),
        },
    }


def _aggregate_bundle_status(session_status: str, plan_status: str, apply_status: str) -> str:
    if "error" in {session_status, plan_status, apply_status}:
        return "error"
    if "warning" in {session_status, plan_status, apply_status}:
        return "warning"
    return "ok"


def _nested_int(payload: dict[str, Any], parent_key: str, key: str) -> int:
    parent = payload.get(parent_key)
    if not isinstance(parent, dict):
        return 0
    value = parent.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value
