from __future__ import annotations

import json
from typing import Any

from kernel.authoring.derivation_compile import (
    AuthoringDerivationCompileError,
    compile_authoring_derivation_v1,
)
from kernel.authoring.diagnostic_codes import (
    CODE_APPLY_BLOCKED_ACTION,
    CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
    CODE_APPLY_PREVALIDATE_BLOCKED_ACTION,
    CODE_APPLY_PREVALIDATE_BLOCKED_ACTIONS_PRESENT,
    CODE_APPLY_SKIPPED_ACTION,
    CODE_APPLY_SKIPPED_ACTIONS_PRESENT,
    PHASE_PUBLISH_APPLY,
    build_diagnostics_contract_meta_v1,
)
from kernel.authoring.publish import (
    build_authoring_apply_dry_run_result_dto,
    build_authoring_publish_plan_dto,
)
from kernel.authoring.registry_fs import AuthoringRegistryFSError, FileAuthoringRegistry
from kernel.authoring.rule_compile import AuthoringRuleCompileError, compile_authoring_rule_v1
from kernel.authoring.schema_compile import AuthoringSchemaCompileError, compile_authoring_schema_v1
from kernel.authoring.session import build_authoring_session_dto
from kernel.core.protocol.digests import sha256_token


class AuthoringApplyExecuteError(Exception):
    pass


TRANSACTION_POLICY_V1 = "best_effort_no_rollback_v1"
TRANSACTION_POLICY_V2_STRICT = "prevalidate_no_partial_strict_v2"


def build_authoring_apply_execute_result_dto(
    plan_dto: dict[str, Any],
    *,
    registry: FileAuthoringRegistry,
    section_payloads: dict[str, Any] | None = None,
    apply_request_id: str | None = None,
    transaction_policy: str | None = None,
) -> dict[str, Any]:
    if not isinstance(registry, FileAuthoringRegistry):
        raise AuthoringApplyExecuteError("registry must be FileAuthoringRegistry")
    if not isinstance(plan_dto, dict):
        raise AuthoringApplyExecuteError("plan_dto must be dict")
    if plan_dto.get("authoring_publish_plan_dto_version") != "authoring_publish_plan_dto_v1":
        raise AuthoringApplyExecuteError("unsupported authoring_publish_plan_dto_version")
    if plan_dto.get("kind") != "authoring_publish_plan":
        raise AuthoringApplyExecuteError("plan_dto.kind must be 'authoring_publish_plan'")
    if apply_request_id is not None and (not isinstance(apply_request_id, str) or not apply_request_id):
        raise AuthoringApplyExecuteError("apply_request_id must be non-empty string when provided")
    if transaction_policy is not None and (not isinstance(transaction_policy, str) or not transaction_policy):
        raise AuthoringApplyExecuteError("transaction_policy must be non-empty string when provided")
    current_plan_digest = _plan_digest(plan_dto)
    policy = transaction_policy or TRANSACTION_POLICY_V1
    if policy not in {TRANSACTION_POLICY_V1, TRANSACTION_POLICY_V2_STRICT}:
        return _build_apply_execute_unsupported_policy_result(
            plan_dto=plan_dto,
            registry=registry,
            apply_request_id=apply_request_id,
            current_plan_digest=current_plan_digest,
            requested_policy=policy,
        )

    if apply_request_id is not None:
        prior = registry.find_apply_execute_run(apply_request_id)
        if isinstance(prior, dict):
            prior_transaction = prior.get("transaction") if isinstance(prior.get("transaction"), dict) else {}
            prior_policy = str(prior_transaction.get("policy", TRANSACTION_POLICY_V1))
            prior_plan_digest = prior.get("plan_digest")
            if (
                isinstance(prior_plan_digest, str)
                and prior_plan_digest
                and prior_plan_digest != current_plan_digest
            ):
                return _build_apply_execute_request_conflict_result(
                    plan_dto=plan_dto,
                    registry=registry,
                    apply_request_id=apply_request_id,
                    current_plan_digest=current_plan_digest,
                    prior=prior,
                    transaction_policy=policy,
                )
            if prior_policy != policy:
                return _build_apply_execute_request_conflict_result(
                    plan_dto=plan_dto,
                    registry=registry,
                    apply_request_id=apply_request_id,
                    current_plan_digest=current_plan_digest,
                    prior=prior,
                    transaction_policy=policy,
                    conflict_path="$.apply_execute_options.transaction_policy",
                    conflict_message="apply_request_id already used with different transaction policy",
                    extra_details={
                        "prior_transaction_policy": prior_policy,
                        "current_transaction_policy": policy,
                    },
                )
            return _build_apply_execute_replay_result(
                plan_dto=plan_dto,
                registry=registry,
                prior=prior,
                current_plan_digest=current_plan_digest,
                transaction_policy=prior_policy,
            )

    dry_run = build_authoring_apply_dry_run_result_dto(plan_dto)
    payloads = section_payloads if isinstance(section_payloads, dict) else {}

    prevalidate_rows = _run_prevalidate_pass(
        dry_run=dry_run,
        registry=registry,
        payloads=payloads,
        apply_request_id=apply_request_id,
    )
    prevalidate_blocked = any(str(row.get("status")) == "blocked" for row in prevalidate_rows)
    if prevalidate_blocked:
        return _build_apply_execute_prevalidate_abort_result(
            plan_dto=plan_dto,
            registry=registry,
            apply_request_id=apply_request_id,
            current_plan_digest=current_plan_digest,
            dry_run=dry_run,
            prevalidate_rows=prevalidate_rows,
            transaction_policy=policy,
        )

    out_actions: list[dict[str, Any]] = []
    diagnostics = _normalize_issues(dry_run.get("diagnostics"))
    warnings = _normalize_issues(dry_run.get("warnings"))
    counts = {"applied": 0, "noop": 0, "blocked": 0, "skipped": 0}

    for idx, action in enumerate(dry_run.get("actions", [])):
        if not isinstance(action, dict):
            raise AuthoringApplyExecuteError(f"dry_run.actions[{idx}] must be object")
        out = _execute_action(
            idx=idx,
            action=action,
            registry=registry,
            payloads=payloads,
            apply_request_id=apply_request_id,
        )
        out_actions.append(out)
        status = str(out.get("status"))
        if status in counts:
            counts[status] += 1
        diagnostics.extend(_normalize_issues(out.get("diagnostics")))
        warnings.extend(_normalize_issues(out.get("warnings")))

    if counts["blocked"] > 0:
        diagnostics.append(
            _issue(
                code=CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
                path="$.actions",
                message=f"{counts['blocked']} action(s) blocked during apply execute",
                severity="error",
                details=(
                    {"transaction_policy": policy}
                    if policy == TRANSACTION_POLICY_V2_STRICT
                    else None
                ),
            )
        )
    if counts["skipped"] > 0:
        warnings.append(
            _issue(
                code=CODE_APPLY_SKIPPED_ACTIONS_PRESENT,
                path="$.actions",
                message=f"{counts['skipped']} action(s) skipped during apply execute",
                severity="warning",
            )
        )

    status = _aggregate_status(
        plan_status=str(plan_dto.get("status", "ok")),
        actions=out_actions,
        warnings=warnings,
    )
    ok = status != "error"
    partial_apply = (counts["applied"] + counts["noop"] > 0) and (counts["blocked"] > 0)
    if policy == TRANSACTION_POLICY_V2_STRICT and partial_apply:
        diagnostics.append(
            _issue(
                code=CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
                path="$.transaction.partial_apply",
                message="v2 strict transaction policy observed partial apply during runtime write failure",
                severity="error",
                details={
                    "transaction_policy": policy,
                    "strict_no_partial_violation": True,
                },
            )
        )

    result = {
        "authoring_apply_execute_result_dto_version": "authoring_apply_execute_result_dto_v1",
        "kind": "authoring_apply_execute_result",
        "mode": "apply_execute_v1",
        "diagnostics_contract": _json_safe(
            plan_dto.get("diagnostics_contract") or build_diagnostics_contract_meta_v1()
        ),
        "ok": ok,
        "status": status,
        "source": {
            "plan_status": plan_dto.get("status"),
            "plan_ok": bool(plan_dto.get("ok")),
            "action_count": len(out_actions),
        },
        "idempotency": {
            "apply_request_id": apply_request_id,
            "plan_digest": current_plan_digest,
            "replayed": False,
        },
        "transaction": {
            "policy": policy,
            "rollback_supported": False,
            "rollback_attempted": False,
            "prevalidate_before_write": True,
            "prevalidate_status": "passed",
            "writes_started": True,
            "failure_phase": "write" if status == "error" else "none",
            "partial_apply": partial_apply,
        },
        "registry": {
            "backend": "file_registry_fs_v1",
            "root_dir": str(registry.root_dir),
            "manifest_path": str(registry.manifest_path),
        },
        "diagnostics": diagnostics,
        "warnings": warnings,
        "actions": out_actions,
        "summary": {
            "action_count": len(out_actions),
            "applied_count": counts["applied"],
            "noop_count": counts["noop"],
            "blocked_count": counts["blocked"],
            "skipped_count": counts["skipped"],
            "diagnostic_count": len(diagnostics),
            "warning_count": len(warnings),
        },
    }
    registry.append_apply_event(
        {
            "kind": "authoring_apply_execute_run",
            "apply_request_id": apply_request_id,
            "plan_digest": current_plan_digest,
            "status": result["status"],
            "ok": result["ok"],
            "partial_apply": partial_apply,
            "idempotency": result["idempotency"],
            "transaction": result["transaction"],
            "summary": result["summary"],
        }
    )
    return result


def build_authoring_publish_workflow_apply_bundle_dto(
    *,
    registry: FileAuthoringRegistry,
    store: Any | None = None,
    schema_ir: dict[str, Any] | None = None,
    authoring_schema: dict[str, Any] | None = None,
    rule_request: dict[str, Any] | None = None,
    derivation_request: dict[str, Any] | None = None,
    apply_request_id: str | None = None,
    transaction_policy: str | None = None,
) -> dict[str, Any]:
    session_dto = build_authoring_session_dto(
        store=store,
        schema_ir=schema_ir,
        authoring_schema=authoring_schema,
        rule_request=rule_request,
        derivation_request=derivation_request,
    )
    publish_plan = build_authoring_publish_plan_dto(session_dto)
    section_payloads = _build_section_payloads(
        schema_ir=schema_ir,
        authoring_schema=authoring_schema,
        rule_request=rule_request,
        derivation_request=derivation_request,
        plan_dto=publish_plan,
    )
    apply_dry_run = build_authoring_apply_dry_run_result_dto(publish_plan)
    apply_execute = build_authoring_apply_execute_result_dto(
        publish_plan,
        registry=registry,
        section_payloads=section_payloads,
        apply_request_id=apply_request_id,
        transaction_policy=transaction_policy,
    )

    bundle_status = _bundle_status(
        str(session_dto.get("status", "ok")),
        str(publish_plan.get("status", "ok")),
        str(apply_dry_run.get("status", "ok")),
        str(apply_execute.get("status", "ok")),
    )
    bundle_ok = all(
        bool(item.get("ok"))
        for item in (session_dto, publish_plan, apply_dry_run, apply_execute)
        if isinstance(item, dict)
    )

    return {
        "authoring_publish_workflow_apply_bundle_dto_version": "authoring_publish_workflow_apply_bundle_dto_v1",
        "kind": "authoring_publish_workflow_apply_bundle",
        "mode": "apply_execute_v1",
        "diagnostics_contract": _json_safe(
            apply_execute.get("diagnostics_contract")
            or apply_dry_run.get("diagnostics_contract")
            or publish_plan.get("diagnostics_contract")
            or session_dto.get("diagnostics_contract")
            or build_diagnostics_contract_meta_v1()
        ),
        "ok": bundle_ok,
        "status": bundle_status,
        "session": _json_safe(session_dto),
        "publish_plan": _json_safe(publish_plan),
        "apply_dry_run": _json_safe(apply_dry_run),
        "apply_execute": _json_safe(apply_execute),
        "summary": {
            "session_status": session_dto.get("status"),
            "publish_plan_status": publish_plan.get("status"),
            "apply_dry_run_status": apply_dry_run.get("status"),
            "apply_execute_status": apply_execute.get("status"),
            "apply_execute_partial_apply": bool(
                apply_execute.get("transaction", {}).get("partial_apply")
                if isinstance(apply_execute.get("transaction"), dict)
                else False
            ),
            "publish_action_count": _nested_int(publish_plan, "summary", "action_count"),
            "apply_execute_applied_count": _nested_int(apply_execute, "summary", "applied_count"),
            "apply_execute_noop_count": _nested_int(apply_execute, "summary", "noop_count"),
            "apply_execute_blocked_count": _nested_int(apply_execute, "summary", "blocked_count"),
            "apply_execute_skipped_count": _nested_int(apply_execute, "summary", "skipped_count"),
        },
    }


def _execute_action(
    *,
    idx: int,
    action: dict[str, Any],
    registry: FileAuthoringRegistry,
    payloads: dict[str, Any],
    apply_request_id: str | None,
) -> dict[str, Any]:
    dry_run_status = str(action.get("status", ""))
    plan_status = str(action.get("plan_status", dry_run_status))
    section = action.get("section")
    action_name = action.get("action")
    out: dict[str, Any] = {
        "action_id": action.get("action_id"),
        "section": section,
        "action": action_name,
        "status_from_dry_run": dry_run_status,
        "plan_status": plan_status,
        "dry_run": False,
        "payload_summary": _json_safe(action.get("payload_summary") or {}),
        "counts": _json_safe(action.get("counts") or {}),
        "diagnostics": [],
        "warnings": [],
        "apply_request_id": apply_request_id,
    }
    for key in ("reason", "reason_code"):
        if key in action:
            out[key] = action.get(key)

    if dry_run_status == "blocked":
        out["status"] = "blocked"
        out["diagnostics"] = _normalize_issues(action.get("diagnostics"))
        out["diagnostics"].append(
            _issue(
                code=CODE_APPLY_BLOCKED_ACTION,
                path=f"$.actions[{idx}]",
                message=f"apply execute action '{out.get('action_id')}' is blocked by plan",
                severity="error",
            )
        )
        return out
    if dry_run_status == "skipped":
        out["status"] = "skipped"
        out["warnings"] = _normalize_issues(action.get("warnings"))
        out["warnings"].append(
            _issue(
                code=CODE_APPLY_SKIPPED_ACTION,
                path=f"$.actions[{idx}]",
                message=f"apply execute action '{out.get('action_id')}' is skipped by plan",
                severity="warning",
            )
        )
        return out
    if dry_run_status != "would_apply":
        out["status"] = "blocked"
        out["diagnostics"] = [
            _issue(
                code=CODE_APPLY_BLOCKED_ACTION,
                path=f"$.actions[{idx}]",
                message=f"unexpected dry-run apply action status: {dry_run_status}",
                severity="error",
            )
        ]
        return out

    try:
        backend_result = _dispatch_registry_write(
            section=section,
            action_name=str(action_name),
            payloads=payloads,
            registry=registry,
        )
    except (AuthoringRegistryFSError, KeyError, TypeError, ValueError) as exc:
        out["status"] = "blocked"
        details = _registry_error_details(exc)
        out["diagnostics"] = [
            _issue(
                code=CODE_APPLY_BLOCKED_ACTION,
                path=f"$.actions[{idx}]",
                message=f"apply execute failed: {exc}",
                severity="error",
                details=details,
            )
        ]
        out["reason_code"] = CODE_APPLY_BLOCKED_ACTION
        registry.append_apply_event(
            {
                "kind": "authoring_apply_execute_action",
                "action_id": out.get("action_id"),
                "section": section,
                "action": action_name,
                "status": out.get("status"),
                "reason_code": out.get("reason_code"),
                "diagnostics_summary": {
                    "count": len(out["diagnostics"]),
                    "codes": [
                        str(row.get("code"))
                        for row in out["diagnostics"]
                        if isinstance(row, dict) and isinstance(row.get("code"), str)
                    ],
                },
                "diagnostics": _json_safe(out.get("diagnostics") or []),
                "apply_request_id": out.get("apply_request_id"),
            }
        )
        return out

    out["status"] = str(backend_result.get("status", "applied"))
    out["backend_result"] = _json_safe(backend_result)
    registry.append_apply_event(
        {
            "kind": "authoring_apply_execute_action",
            "action_id": out.get("action_id"),
            "section": section,
            "action": action_name,
            "status": out.get("status"),
            "backend_result": out.get("backend_result"),
            "apply_request_id": out.get("apply_request_id"),
        }
    )
    return out


def _dispatch_registry_write(
    *,
    section: Any,
    action_name: str,
    payloads: dict[str, Any],
    registry: FileAuthoringRegistry,
) -> dict[str, Any]:
    if not isinstance(section, str):
        raise AuthoringRegistryFSError("action section must be string")
    if section not in payloads:
        raise AuthoringRegistryFSError(f"missing payload for section '{section}'")
    payload = payloads[section]
    if section == "schema_preflight" and action_name == "upsert_schema_ir":
        return registry.upsert_schema_ir(payload)
    if section == "rule_preflight" and action_name == "register_rule_spec":
        return registry.register_rule_spec(payload)
    if section == "derivation_preview" and action_name == "preview_derivation":
        result = registry.register_derivation_spec(payload)
        result["executed_action"] = "register_derivation_spec"
        return result
    raise AuthoringRegistryFSError(f"unsupported executable action: {section}/{action_name}")


def _dispatch_registry_prevalidate(
    *,
    section: Any,
    action_name: str,
    payloads: dict[str, Any],
    registry: FileAuthoringRegistry,
) -> dict[str, Any]:
    if not isinstance(section, str):
        raise AuthoringRegistryFSError("action section must be string")
    if section not in payloads:
        raise AuthoringRegistryFSError(f"missing payload for section '{section}'")
    payload = payloads[section]
    if section == "schema_preflight" and action_name == "upsert_schema_ir":
        return registry.preview_upsert_schema_ir(payload)
    if section == "rule_preflight" and action_name == "register_rule_spec":
        return registry.preview_register_rule_spec(payload)
    if section == "derivation_preview" and action_name == "preview_derivation":
        result = registry.preview_register_derivation_spec(payload)
        result["executed_action"] = "register_derivation_spec"
        return result
    raise AuthoringRegistryFSError(f"unsupported executable action: {section}/{action_name}")


def _build_section_payloads(
    *,
    schema_ir: dict[str, Any] | None,
    authoring_schema: dict[str, Any] | None,
    rule_request: dict[str, Any] | None,
    derivation_request: dict[str, Any] | None,
    plan_dto: dict[str, Any],
) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    planned_sections = {
        str(action.get("section"))
        for action in plan_dto.get("actions", [])
        if isinstance(action, dict) and str(action.get("status")) == "planned"
    }
    if "schema_preflight" in planned_sections:
        if authoring_schema is not None:
            try:
                payloads["schema_preflight"] = compile_authoring_schema_v1(authoring_schema)
            except AuthoringSchemaCompileError as exc:
                raise AuthoringApplyExecuteError(str(exc)) from exc
        elif schema_ir is not None:
            payloads["schema_preflight"] = schema_ir
    if "rule_preflight" in planned_sections and rule_request is not None:
        if "authoring_rule_payload" in rule_request:
            try:
                payloads["rule_preflight"] = compile_authoring_rule_v1(rule_request["authoring_rule_payload"])
            except AuthoringRuleCompileError as exc:
                raise AuthoringApplyExecuteError(str(exc)) from exc
        elif "rule_spec_payload" in rule_request:
            payloads["rule_preflight"] = rule_request["rule_spec_payload"]
    if "derivation_preview" in planned_sections and derivation_request is not None:
        if "authoring_derivation_payload" in derivation_request:
            try:
                payloads["derivation_preview"] = compile_authoring_derivation_v1(
                    derivation_request["authoring_derivation_payload"]
                )
            except AuthoringDerivationCompileError as exc:
                raise AuthoringApplyExecuteError(str(exc)) from exc
        else:
            canonical = {
                key: derivation_request[key]
                for key in (
                    "derivation_id",
                    "version",
                    "target_pred_id",
                    "head_vars",
                    "where",
                    "mode",
                )
                if key in derivation_request
            }
            payloads["derivation_preview"] = compile_authoring_derivation_v1(canonical)
    return payloads


def _run_prevalidate_pass(
    *,
    dry_run: dict[str, Any],
    registry: FileAuthoringRegistry,
    payloads: dict[str, Any],
    apply_request_id: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, action in enumerate(dry_run.get("actions", [])):
        if not isinstance(action, dict):
            raise AuthoringApplyExecuteError(f"dry_run.actions[{idx}] must be object")
        dry_status = str(action.get("status", ""))
        if dry_status in {"blocked", "skipped"}:
            rows.append(
                _execute_action(
                    idx=idx,
                    action=action,
                    registry=registry,
                    payloads=payloads,
                    apply_request_id=apply_request_id,
                )
            )
            continue
        if dry_status != "would_apply":
            rows.append(
                {
                    "action_id": action.get("action_id"),
                    "section": action.get("section"),
                    "action": action.get("action"),
                    "status": "blocked",
                    "status_from_dry_run": dry_status,
                    "plan_status": action.get("plan_status", dry_status),
                    "dry_run": False,
                    "payload_summary": _json_safe(action.get("payload_summary") or {}),
                    "counts": _json_safe(action.get("counts") or {}),
                    "diagnostics": [
                        _issue(
                            code=CODE_APPLY_BLOCKED_ACTION,
                            path=f"$.actions[{idx}]",
                            message=f"unexpected dry-run apply action status during prevalidate: {dry_status}",
                            severity="error",
                        )
                    ],
                    "warnings": [],
                    "apply_request_id": apply_request_id,
                }
            )
            continue
        rows.append(
            _prevalidate_action(
                idx=idx,
                action=action,
                registry=registry,
                payloads=payloads,
                apply_request_id=apply_request_id,
            )
        )
    return rows


def _prevalidate_action(
    *,
    idx: int,
    action: dict[str, Any],
    registry: FileAuthoringRegistry,
    payloads: dict[str, Any],
    apply_request_id: str | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "action_id": action.get("action_id"),
        "section": action.get("section"),
        "action": action.get("action"),
        "status_from_dry_run": action.get("status"),
        "plan_status": action.get("plan_status", action.get("status")),
        "dry_run": False,
        "payload_summary": _json_safe(action.get("payload_summary") or {}),
        "counts": _json_safe(action.get("counts") or {}),
        "diagnostics": [],
        "warnings": [],
        "apply_request_id": apply_request_id,
    }
    for key in ("reason", "reason_code"):
        if key in action:
            out[key] = action.get(key)
    try:
        preview = _dispatch_registry_prevalidate(
            section=action.get("section"),
            action_name=str(action.get("action")),
            payloads=payloads,
            registry=registry,
        )
    except (AuthoringRegistryFSError, KeyError, TypeError, ValueError) as exc:
        out["status"] = "blocked"
        details = _registry_error_details(exc)
        details["prevalidate"] = True
        out["diagnostics"] = [
            _issue(
                code=CODE_APPLY_PREVALIDATE_BLOCKED_ACTION,
                path=f"$.actions[{idx}]",
                message=f"apply prevalidate failed: {exc}",
                severity="error",
                details=details,
            )
        ]
        return out
    out["status"] = "prevalidated"
    out["backend_preview"] = _json_safe(preview)
    return out


def _normalize_issues(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        row = {
            "phase": item.get("phase"),
            "code": item.get("code"),
            "path": item.get("path"),
            "message": item.get("message"),
            "severity": item.get("severity"),
        }
        if isinstance(item.get("details"), dict):
            row["details"] = _json_safe(item["details"])
        out.append(row)
    return out


def _issue(
    *,
    code: str,
    path: str,
    message: str,
    severity: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "phase": PHASE_PUBLISH_APPLY,
        "code": code,
        "path": path,
        "message": message,
        "severity": severity,
    }
    if isinstance(details, dict) and details:
        row["details"] = _json_safe(details)
    return row


def _aggregate_status(*, plan_status: str, actions: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    if plan_status == "error" or any(str(a.get("status")) == "blocked" for a in actions):
        return "error"
    if plan_status == "warning" or warnings or any(str(a.get("status")) == "skipped" for a in actions):
        return "warning"
    return "ok"


def _bundle_status(session_status: str, plan_status: str, dry_status: str, exec_status: str) -> str:
    if "error" in {session_status, plan_status, dry_status, exec_status}:
        return "error"
    if "warning" in {session_status, plan_status, dry_status, exec_status}:
        return "warning"
    return "ok"


def _nested_int(payload: dict[str, Any], parent_key: str, key: str) -> int:
    parent = payload.get(parent_key)
    if not isinstance(parent, dict):
        return 0
    value = parent.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _registry_error_details(exc: Exception) -> dict[str, Any]:
    if not isinstance(exc, AuthoringRegistryFSError):
        return {}
    details: dict[str, Any] = {}
    if isinstance(getattr(exc, "code", None), str):
        details["registry_error_code"] = exc.code
    if isinstance(getattr(exc, "path", None), str):
        details["registry_error_path"] = exc.path
    extra = getattr(exc, "details", None)
    if isinstance(extra, dict):
        for key, value in extra.items():
            if key not in details:
                details[key] = value
    return details


def _build_apply_execute_replay_result(
    *,
    plan_dto: dict[str, Any],
    registry: FileAuthoringRegistry,
    prior: dict[str, Any],
    current_plan_digest: str,
    transaction_policy: str,
) -> dict[str, Any]:
    prior_status = str(prior.get("status", "ok"))
    prior_ok = bool(prior.get("ok", prior_status != "error"))
    prior_summary = prior.get("summary") if isinstance(prior.get("summary"), dict) else {}
    return {
        "authoring_apply_execute_result_dto_version": "authoring_apply_execute_result_dto_v1",
        "kind": "authoring_apply_execute_result",
        "mode": "apply_execute_v1",
        "diagnostics_contract": _json_safe(
            plan_dto.get("diagnostics_contract") or build_diagnostics_contract_meta_v1()
        ),
        "ok": prior_ok,
        "status": prior_status,
        "source": {
            "plan_status": plan_dto.get("status"),
            "plan_ok": bool(plan_dto.get("ok")),
            "action_count": len(plan_dto.get("actions", [])) if isinstance(plan_dto.get("actions"), list) else 0,
        },
        "idempotency": {
            "apply_request_id": prior.get("apply_request_id"),
            "plan_digest": prior.get("plan_digest") if isinstance(prior.get("plan_digest"), str) else current_plan_digest,
            "replayed": True,
        },
        "transaction": {
            "policy": transaction_policy,
            "rollback_supported": False,
            "rollback_attempted": False,
            "prevalidate_before_write": True,
            "prevalidate_status": "skipped_idempotency_replay",
            "writes_started": False,
            "failure_phase": "none",
            "partial_apply": bool(prior.get("partial_apply")),
        },
        "registry": {
            "backend": "file_registry_fs_v1",
            "root_dir": str(registry.root_dir),
            "manifest_path": str(registry.manifest_path),
        },
        "diagnostics": [],
        "warnings": [],
        "actions": [],
        "summary": {
            "action_count": _coerce_int(prior_summary.get("action_count")),
            "applied_count": _coerce_int(prior_summary.get("applied_count")),
            "noop_count": _coerce_int(prior_summary.get("noop_count")),
            "blocked_count": _coerce_int(prior_summary.get("blocked_count")),
            "skipped_count": _coerce_int(prior_summary.get("skipped_count")),
            "diagnostic_count": 0,
            "warning_count": 0,
        },
    }


def _build_apply_execute_request_conflict_result(
    *,
    plan_dto: dict[str, Any],
    registry: FileAuthoringRegistry,
    apply_request_id: str,
    current_plan_digest: str,
    prior: dict[str, Any],
    transaction_policy: str,
    conflict_path: str = "$.idempotency.apply_request_id",
    conflict_message: str = "apply_request_id already used with different plan digest",
    extra_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prior_plan_digest = prior.get("plan_digest") if isinstance(prior.get("plan_digest"), str) else None
    diagnostics = [
        _issue(
            code=CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
            path=conflict_path,
            message=conflict_message,
            severity="error",
            details={
                "apply_request_id": apply_request_id,
                "prior_plan_digest": prior_plan_digest,
                "current_plan_digest": current_plan_digest,
                **(extra_details or {}),
            },
        )
    ]
    return {
        "authoring_apply_execute_result_dto_version": "authoring_apply_execute_result_dto_v1",
        "kind": "authoring_apply_execute_result",
        "mode": "apply_execute_v1",
        "diagnostics_contract": _json_safe(
            plan_dto.get("diagnostics_contract") or build_diagnostics_contract_meta_v1()
        ),
        "ok": False,
        "status": "error",
        "source": {
            "plan_status": plan_dto.get("status"),
            "plan_ok": bool(plan_dto.get("ok")),
            "action_count": len(plan_dto.get("actions", [])) if isinstance(plan_dto.get("actions"), list) else 0,
        },
        "idempotency": {
            "apply_request_id": apply_request_id,
            "plan_digest": current_plan_digest,
            "replayed": False,
            "conflict": True,
            "prior_plan_digest": prior_plan_digest,
        },
        "transaction": {
            "policy": transaction_policy,
            "rollback_supported": False,
            "rollback_attempted": False,
            "prevalidate_before_write": True,
            "prevalidate_status": "skipped_idempotency_conflict",
            "writes_started": False,
            "failure_phase": "idempotency_conflict",
            "partial_apply": False,
        },
        "registry": {
            "backend": "file_registry_fs_v1",
            "root_dir": str(registry.root_dir),
            "manifest_path": str(registry.manifest_path),
        },
        "diagnostics": diagnostics,
        "warnings": [],
        "actions": [],
        "summary": {
            "action_count": 0,
            "applied_count": 0,
            "noop_count": 0,
            "blocked_count": 0,
            "skipped_count": 0,
            "diagnostic_count": len(diagnostics),
            "warning_count": 0,
        },
    }


def _build_apply_execute_prevalidate_abort_result(
    *,
    plan_dto: dict[str, Any],
    registry: FileAuthoringRegistry,
    apply_request_id: str | None,
    current_plan_digest: str,
    dry_run: dict[str, Any],
    prevalidate_rows: list[dict[str, Any]],
    transaction_policy: str,
) -> dict[str, Any]:
    diagnostics = _normalize_issues(dry_run.get("diagnostics"))
    warnings = _normalize_issues(dry_run.get("warnings"))
    out_actions: list[dict[str, Any]] = []
    counts = {"applied": 0, "noop": 0, "blocked": 0, "skipped": 0}
    for row in prevalidate_rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", ""))
        if status == "blocked":
            out_actions.append(row)
            counts["blocked"] += 1
            diagnostics.extend(_normalize_issues(row.get("diagnostics")))
            warnings.extend(_normalize_issues(row.get("warnings")))
        elif status == "skipped":
            out_actions.append(row)
            counts["skipped"] += 1
            diagnostics.extend(_normalize_issues(row.get("diagnostics")))
            warnings.extend(_normalize_issues(row.get("warnings")))
    diagnostics.append(
        _issue(
            code=CODE_APPLY_PREVALIDATE_BLOCKED_ACTIONS_PRESENT,
            path="$.prevalidate",
            message="apply prevalidate blocked one or more actions; no writes executed",
            severity="error",
            details={"blocked_count": counts["blocked"]},
        )
    )
    return {
        "authoring_apply_execute_result_dto_version": "authoring_apply_execute_result_dto_v1",
        "kind": "authoring_apply_execute_result",
        "mode": "apply_execute_v1",
        "diagnostics_contract": _json_safe(
            plan_dto.get("diagnostics_contract") or build_diagnostics_contract_meta_v1()
        ),
        "ok": False,
        "status": "error",
        "source": {
            "plan_status": plan_dto.get("status"),
            "plan_ok": bool(plan_dto.get("ok")),
            "action_count": len(dry_run.get("actions", [])) if isinstance(dry_run.get("actions"), list) else 0,
        },
        "idempotency": {
            "apply_request_id": apply_request_id,
            "plan_digest": current_plan_digest,
            "replayed": False,
        },
        "transaction": {
            "policy": transaction_policy,
            "rollback_supported": False,
            "rollback_attempted": False,
            "prevalidate_before_write": True,
            "prevalidate_status": "blocked",
            "writes_started": False,
            "failure_phase": "prevalidate",
            "partial_apply": False,
        },
        "registry": {
            "backend": "file_registry_fs_v1",
            "root_dir": str(registry.root_dir),
            "manifest_path": str(registry.manifest_path),
        },
        "diagnostics": diagnostics,
        "warnings": warnings,
        "actions": out_actions,
        "summary": {
            "action_count": len(out_actions),
            "applied_count": 0,
            "noop_count": 0,
            "blocked_count": counts["blocked"],
            "skipped_count": counts["skipped"],
            "diagnostic_count": len(diagnostics),
            "warning_count": len(warnings),
        },
    }


def _coerce_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _build_apply_execute_unsupported_policy_result(
    *,
    plan_dto: dict[str, Any],
    registry: FileAuthoringRegistry,
    apply_request_id: str | None,
    current_plan_digest: str,
    requested_policy: str,
) -> dict[str, Any]:
    diagnostics = [
        _issue(
            code=CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
            path="$.apply_execute_options.transaction_policy",
            message=f"unsupported transaction policy: {requested_policy}",
            severity="error",
            details={
                "requested_policy": requested_policy,
                "supported_policies": [TRANSACTION_POLICY_V1],
                "v2_reserved_not_implemented": requested_policy == TRANSACTION_POLICY_V2_STRICT,
            },
        )
    ]
    return {
        "authoring_apply_execute_result_dto_version": "authoring_apply_execute_result_dto_v1",
        "kind": "authoring_apply_execute_result",
        "mode": "apply_execute_v1",
        "diagnostics_contract": _json_safe(
            plan_dto.get("diagnostics_contract") or build_diagnostics_contract_meta_v1()
        ),
        "ok": False,
        "status": "error",
        "source": {
            "plan_status": plan_dto.get("status"),
            "plan_ok": bool(plan_dto.get("ok")),
            "action_count": len(plan_dto.get("actions", [])) if isinstance(plan_dto.get("actions"), list) else 0,
        },
        "idempotency": {
            "apply_request_id": apply_request_id,
            "plan_digest": current_plan_digest,
            "replayed": False,
        },
        "transaction": {
            "policy": requested_policy,
            "rollback_supported": False,
            "rollback_attempted": False,
            "prevalidate_before_write": False,
            "prevalidate_status": "skipped_transaction_policy_unsupported",
            "writes_started": False,
            "failure_phase": "prevalidate",
            "partial_apply": False,
        },
        "registry": {
            "backend": "file_registry_fs_v1",
            "root_dir": str(registry.root_dir),
            "manifest_path": str(registry.manifest_path),
        },
        "diagnostics": diagnostics,
        "warnings": [],
        "actions": [],
        "summary": {
            "action_count": 0,
            "applied_count": 0,
            "noop_count": 0,
            "blocked_count": 0,
            "skipped_count": 0,
            "diagnostic_count": len(diagnostics),
            "warning_count": 0,
        },
    }


def _plan_digest(plan_dto: dict[str, Any]) -> str:
    data = json.dumps(plan_dto, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_token(data)
