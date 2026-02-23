from __future__ import annotations

from typing import Any

from factpy_kernel.authoring.diagnostic_codes import (
    CODE_APPLY_BLOCKED_ACTION,
    CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
    CODE_APPLY_SKIPPED_ACTION,
    CODE_APPLY_SKIPPED_ACTIONS_PRESENT,
    CODE_PUBLISH_BLOCKED_MISSING_OR_INVALID_SECTION,
    CODE_PUBLISH_BLOCKED_SECTION_ERROR,
    CODE_PUBLISH_SKIPPED_UNSUPPORTED_SECTION,
    PHASE_PUBLISH_APPLY,
    PHASE_PUBLISH_PLAN,
    build_diagnostics_contract_meta_v1,
)


class AuthoringPublishError(Exception):
    pass


def build_authoring_publish_plan_dto(session_dto: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(session_dto, dict):
        raise AuthoringPublishError("session_dto must be dict")
    if session_dto.get("authoring_session_dto_version") != "authoring_session_dto_v1":
        raise AuthoringPublishError("unsupported authoring_session_dto_version")
    if session_dto.get("kind") != "authoring_session":
        raise AuthoringPublishError("session_dto.kind must be 'authoring_session'")

    order = session_dto.get("order")
    sections = session_dto.get("sections")
    if not isinstance(order, list):
        raise AuthoringPublishError("session_dto.order must be list")
    if not isinstance(sections, dict):
        raise AuthoringPublishError("session_dto.sections must be object")

    actions: list[dict[str, Any]] = []
    status_counts = {"planned": 0, "blocked": 0, "skipped": 0}
    diagnostics: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for idx, section_name in enumerate(order):
        if not isinstance(section_name, str):
            raise AuthoringPublishError("session_dto.order entries must be strings")
        section = sections.get(section_name)
        action = _build_action(idx=idx, section_name=section_name, section=section)
        actions.append(action)
        action_status = action["status"]
        if action_status in status_counts:
            status_counts[action_status] += 1
        diagnostics.extend(_normalize_issue_list(action.get("diagnostics")))
        warnings.extend(_normalize_issue_list(action.get("warnings")))

    session_status = str(session_dto.get("status", "ok"))
    session_ok = bool(session_dto.get("ok"))
    plan_status = _aggregate_plan_status(session_status, actions)

    return {
        "authoring_publish_plan_dto_version": "authoring_publish_plan_dto_v1",
        "kind": "authoring_publish_plan",
        "mode": "dry_run_only",
        "diagnostics_contract": build_diagnostics_contract_meta_v1(),
        "ok": plan_status != "error" and session_ok,
        "status": plan_status,
        "source": {
            "session_status": session_status,
            "session_ok": session_ok,
            "order": list(order),
            "present_sections": [name for name in order if isinstance(name, str)],
        },
        "diagnostics": diagnostics,
        "warnings": warnings,
        "actions": actions,
        "summary": {
            "action_count": len(actions),
            "planned_count": status_counts["planned"],
            "blocked_count": status_counts["blocked"],
            "skipped_count": status_counts["skipped"],
            "diagnostic_count": len(diagnostics),
            "warning_count": len(warnings),
            "status_counts": dict(status_counts),
        },
    }


def build_authoring_apply_dry_run_result_dto(plan_dto: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan_dto, dict):
        raise AuthoringPublishError("plan_dto must be dict")
    if plan_dto.get("authoring_publish_plan_dto_version") != "authoring_publish_plan_dto_v1":
        raise AuthoringPublishError("unsupported authoring_publish_plan_dto_version")
    if plan_dto.get("kind") != "authoring_publish_plan":
        raise AuthoringPublishError("plan_dto.kind must be 'authoring_publish_plan'")
    if plan_dto.get("mode") != "dry_run_only":
        raise AuthoringPublishError("plan_dto.mode must be 'dry_run_only'")

    actions_in = plan_dto.get("actions")
    if not isinstance(actions_in, list):
        raise AuthoringPublishError("plan_dto.actions must be list")

    diagnostics = _normalize_issue_list(plan_dto.get("diagnostics"))
    warnings = _normalize_issue_list(plan_dto.get("warnings"))
    out_actions: list[dict[str, Any]] = []
    status_counts = {"would_apply": 0, "blocked": 0, "skipped": 0}

    for idx, action in enumerate(actions_in):
        if not isinstance(action, dict):
            raise AuthoringPublishError(f"plan_dto.actions[{idx}] must be object")
        out_action = _build_apply_action_from_plan(idx=idx, action=action)
        out_actions.append(out_action)
        out_status = str(out_action["status"])
        if out_status in status_counts:
            status_counts[out_status] += 1

    plan_status = str(plan_dto.get("status", "ok"))
    plan_ok = bool(plan_dto.get("ok"))
    apply_status = _aggregate_apply_status(plan_status, out_actions)
    if status_counts["blocked"] > 0:
        diagnostics.append(
            _issue(
                phase=PHASE_PUBLISH_APPLY,
                code=CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
                path="$.actions",
                message=f"{status_counts['blocked']} blocked action(s) prevent apply dry-run from being fully applicable",
                severity="error",
            )
        )
    if status_counts["skipped"] > 0:
        warnings.append(
            _issue(
                phase=PHASE_PUBLISH_APPLY,
                code=CODE_APPLY_SKIPPED_ACTIONS_PRESENT,
                path="$.actions",
                message=f"{status_counts['skipped']} action(s) are skipped in apply dry-run",
                severity="warning",
            )
        )

    return {
        "authoring_apply_result_dto_version": "authoring_apply_result_dto_v1",
        "kind": "authoring_apply_result",
        "mode": "dry_run_only",
        "diagnostics_contract": _json_safe(
            plan_dto.get("diagnostics_contract") or build_diagnostics_contract_meta_v1()
        ),
        "ok": apply_status != "error" and plan_ok,
        "status": apply_status,
        "source": {
            "plan_status": plan_status,
            "plan_ok": plan_ok,
            "action_count": len(actions_in),
        },
        "diagnostics": diagnostics,
        "warnings": warnings,
        "actions": out_actions,
        "summary": {
            "action_count": len(out_actions),
            "would_apply_count": status_counts["would_apply"],
            "blocked_count": status_counts["blocked"],
            "skipped_count": status_counts["skipped"],
            "diagnostic_count": len(diagnostics),
            "warning_count": len(warnings),
            "status_counts": dict(status_counts),
        },
    }


def _build_action(*, idx: int, section_name: str, section: Any) -> dict[str, Any]:
    action_id = f"action:{idx}:{section_name}"
    action_name = _action_name_for_section(section_name)

    if action_name is None:
        return {
            "action_id": action_id,
            "section": section_name,
            "action": "unsupported_section",
            "status": "skipped",
            "dry_run": True,
            "reason_code": CODE_PUBLISH_SKIPPED_UNSUPPORTED_SECTION,
            "reason": "unsupported_section",
            "diagnostics": [],
            "warnings": [
                _warn_issue(
                    code=CODE_PUBLISH_SKIPPED_UNSUPPORTED_SECTION,
                    path=f"$.sections.{section_name}",
                    message=f"section '{section_name}' is unsupported by publish planner and is skipped",
                )
            ],
        }

    if not isinstance(section, dict):
        return {
            "action_id": action_id,
            "section": section_name,
            "action": action_name,
            "status": "blocked",
            "dry_run": True,
            "reason_code": CODE_PUBLISH_BLOCKED_MISSING_OR_INVALID_SECTION,
            "reason": "missing_or_invalid_section",
            "diagnostics": [
                _diag_issue(
                    code=CODE_PUBLISH_BLOCKED_MISSING_OR_INVALID_SECTION,
                    path=f"$.sections.{section_name}",
                    message=f"section '{section_name}' is missing or invalid",
                )
            ],
            "warnings": [],
        }

    section_status = str(section.get("status", "ok"))
    section_ok = bool(section.get("ok"))
    diagnostics = section.get("diagnostics")
    warnings = section.get("warnings")

    action: dict[str, Any] = {
        "action_id": action_id,
        "section": section_name,
        "action": action_name,
        "status": "planned" if section_ok and section_status != "error" else "blocked",
        "dry_run": True,
        "section_status": section_status,
        "counts": _json_safe(
            {
                "diagnostic_count": _issue_count(diagnostics),
                "warning_count": _issue_count(warnings),
            }
        ),
        "diagnostics": [],
        "warnings": [],
        "payload_summary": _payload_summary_for_section(section_name, section),
    }
    if action["status"] == "blocked":
        action["reason_code"] = CODE_PUBLISH_BLOCKED_SECTION_ERROR
        action["reason"] = "section_error"
        action["diagnostics"] = [
            _diag_issue(
                code=CODE_PUBLISH_BLOCKED_SECTION_ERROR,
                path=f"$.sections.{section_name}",
                message=f"section '{section_name}' has status={section_status}; publish action is blocked",
            )
        ]
    return action


def _action_name_for_section(section_name: str) -> str | None:
    mapping = {
        "schema_preflight": "upsert_schema_ir",
        "rule_preflight": "register_rule_spec",
        "derivation_preview": "preview_derivation",
    }
    return mapping.get(section_name)


def _payload_summary_for_section(section_name: str, section: dict[str, Any]) -> dict[str, Any]:
    if section_name == "schema_preflight":
        summary = section.get("summary") if isinstance(section.get("summary"), dict) else {}
        return _json_safe(
            {
                "schema_digest": section.get("schema_digest"),
                "entity_count": summary.get("entity_count"),
                "predicate_count": summary.get("predicate_count"),
                "pred_ids": summary.get("pred_ids"),
            }
        )

    if section_name == "rule_preflight":
        summary = section.get("summary") if isinstance(section.get("summary"), dict) else {}
        rule = section.get("rule") if isinstance(section.get("rule"), dict) else {}
        return _json_safe(
            {
                "rule_id": rule.get("rule_id"),
                "version": rule.get("version"),
                "expose": rule.get("expose"),
                "select_vars": rule.get("select_vars"),
                "row_count": summary.get("row_count"),
                "preview_limit": summary.get("preview_limit"),
            }
        )

    if section_name == "derivation_preview":
        summary = section.get("summary") if isinstance(section.get("summary"), dict) else {}
        return _json_safe(
            {
                "mode": section.get("mode"),
                "temporal_view": section.get("temporal_view"),
                "candidate_count": summary.get("candidate_count"),
                "preview_limit": summary.get("preview_limit"),
                "targets": summary.get("targets"),
            }
        )

    return {}


def _aggregate_plan_status(session_status: str, actions: list[dict[str, Any]]) -> str:
    if session_status == "error" or any(action.get("status") == "blocked" for action in actions):
        return "error"
    if session_status == "warning" or any(_action_has_warning(action) for action in actions):
        return "warning"
    return "ok"


def _aggregate_apply_status(plan_status: str, actions: list[dict[str, Any]]) -> str:
    if plan_status == "error" or any(action.get("status") == "blocked" for action in actions):
        return "error"
    if plan_status == "warning" or any(action.get("status") == "skipped" for action in actions):
        return "warning"
    return "ok"


def _action_has_warning(action: dict[str, Any]) -> bool:
    direct_warnings = action.get("warnings")
    if isinstance(direct_warnings, list) and any(isinstance(item, dict) for item in direct_warnings):
        return True
    counts = action.get("counts")
    if not isinstance(counts, dict):
        return False
    value = counts.get("warning_count", 0)
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _build_apply_action_from_plan(*, idx: int, action: dict[str, Any]) -> dict[str, Any]:
    plan_status = action.get("status")
    if not isinstance(plan_status, str):
        raise AuthoringPublishError("plan action missing status")
    if plan_status not in {"planned", "blocked", "skipped"}:
        raise AuthoringPublishError(f"unsupported plan action status: {plan_status}")

    out_status = {
        "planned": "would_apply",
        "blocked": "blocked",
        "skipped": "skipped",
    }[plan_status]
    out: dict[str, Any] = {
        "action_id": action.get("action_id"),
        "section": action.get("section"),
        "action": action.get("action"),
        "status": out_status,
        "plan_status": plan_status,
        "dry_run": True,
        "payload_summary": _json_safe(action.get("payload_summary") or {}),
        "counts": _json_safe(action.get("counts") or {}),
        "diagnostics": _normalize_issue_list(action.get("diagnostics")),
        "warnings": _normalize_issue_list(action.get("warnings")),
    }
    if "reason" in action:
        out["reason"] = action.get("reason")
    if "reason_code" in action:
        out["reason_code"] = action.get("reason_code")
    if out_status == "blocked":
        out["diagnostics"].append(
            _issue(
                phase=PHASE_PUBLISH_APPLY,
                code=CODE_APPLY_BLOCKED_ACTION,
                path=f"$.actions[{idx}]",
                message=f"apply dry-run action '{out.get('action_id')}' is blocked",
                severity="error",
            )
        )
    elif out_status == "skipped":
        out["warnings"].append(
            _issue(
                phase=PHASE_PUBLISH_APPLY,
                code=CODE_APPLY_SKIPPED_ACTION,
                path=f"$.actions[{idx}]",
                message=f"apply dry-run action '{out.get('action_id')}' is skipped",
                severity="warning",
            )
        )
    return out


def _issue_count(items: Any) -> int:
    if not isinstance(items, list):
        return 0
    return len([item for item in items if isinstance(item, dict)])


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _diag_issue(*, code: str, path: str, message: str) -> dict[str, Any]:
    return _issue(
        phase=PHASE_PUBLISH_PLAN,
        code=code,
        path=path,
        message=message,
        severity="error",
    )


def _warn_issue(*, code: str, path: str, message: str) -> dict[str, Any]:
    return _issue(
        phase=PHASE_PUBLISH_PLAN,
        code=code,
        path=path,
        message=message,
        severity="warning",
    )


def _issue(*, phase: str, code: str, path: str, message: str, severity: str) -> dict[str, Any]:
    return {
        "phase": phase,
        "code": code,
        "path": path,
        "message": message,
        "severity": severity,
    }


def _normalize_issue_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "phase": item.get("phase"),
                "code": item.get("code"),
                "path": item.get("path"),
                "message": item.get("message"),
                "severity": item.get("severity"),
            }
        )
    return out
