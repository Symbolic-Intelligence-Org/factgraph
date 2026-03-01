from __future__ import annotations

from typing import Any

from .query import AuditQuery, AuditQueryError


class AuditDTOError(Exception):
    pass


def build_run_list_dto(query: AuditQuery) -> dict[str, Any]:
    _ensure_query(query)
    runs = query.list_runs()
    items = [_run_summary_item(row) for row in runs]
    return {
        "audit_ui_dto_version": "audit_ui_dto_v1",
        "kind": "run_list",
        "count": len(items),
        "runs": items,
    }


def build_run_detail_dto(query: AuditQuery, run_id: str) -> dict[str, Any]:
    _ensure_query(query)
    try:
        bundle = query.get_run_bundle(run_id)
    except AuditQueryError as exc:
        raise AuditDTOError(str(exc)) from exc

    run = dict(bundle["run"])
    decisions = [dict(row) for row in bundle["decisions"]]
    accept_writes = [dict(row) for row in bundle["accept_writes"]]
    candidates = [dict(row) for row in bundle["candidates"]]
    failures = [dict(row) for row in bundle["failures"]]
    timeline = _build_timeline(decisions, failures)

    return {
        "audit_ui_dto_version": "audit_ui_dto_v1",
        "kind": "run_detail",
        "run_id": run_id,
        "run": run,
        "stats": {
            "accept_write_count": len(accept_writes),
            "candidate_count": len(candidates),
            "decision_count": len(decisions),
            "failure_count": len(failures),
            "has_failures": bool(run.get("has_failures")),
        },
        "decision_ids": [row.get("decision_id") for row in decisions if isinstance(row.get("decision_id"), str)],
        "candidate_ids": [row.get("candidate_id") for row in accept_writes if isinstance(row.get("candidate_id"), str)],
        "decisions": decisions,
        "accept_writes": accept_writes,
        "candidates": candidates,
        "failures": failures,
        "timeline": timeline,
        "event_source_counts": dict(run.get("event_source_counts") or {}),
        "event_kind_counts": dict(run.get("event_kind_counts") or {}),
    }


def build_decision_detail_dto(query: AuditQuery, decision_id: str) -> dict[str, Any]:
    _ensure_query(query)
    try:
        decision = query.get_decision(decision_id)
    except AuditQueryError as exc:
        raise AuditDTOError(str(exc)) from exc
    if decision is None:
        raise AuditDTOError(f"decision not found: {decision_id}")

    failures = [row for row in query.list_failures() if row.get("decision_id") == decision_id]
    candidate_ids = _sorted_strings(decision.get("candidate_ids"))
    run_ids = _sorted_strings(decision.get("run_ids"))
    if isinstance(decision.get("candidate_id"), str):
        candidate_ids = sorted({*candidate_ids, decision["candidate_id"]})
    if isinstance(decision.get("run_id"), str):
        run_ids = sorted({*run_ids, decision["run_id"]})

    accept_writes: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        accept_writes.extend(query.list_accept_writes(candidate_id=candidate_id))
    accept_writes = _dedupe_rows(accept_writes, keys=("candidate_id", "asrt_id"))

    candidates = _dedupe_rows(
        [row for row in query.list_candidates() if row.get("decision_id") == decision_id],
        keys=("candidate_id", "asrt_id", "decision_id"),
    )
    runs = [row for row in query.list_runs() if row.get("run_id") in set(run_ids)]
    runs = sorted(runs, key=lambda row: str(row.get("run_id", "")))

    return {
        "audit_ui_dto_version": "audit_ui_dto_v1",
        "kind": "decision_detail",
        "decision_id": decision_id,
        "decision": dict(decision),
        "runs": runs,
        "accept_writes": accept_writes,
        "candidates": candidates,
        "failures": [dict(row) for row in failures],
        "related": {
            "run_ids": run_ids,
            "candidate_ids": candidate_ids,
        },
    }


def build_authoring_apply_run_list_dto(query: AuditQuery) -> dict[str, Any]:
    _ensure_query(query)
    runs = query.list_authoring_apply_runs()
    items = []
    for row in runs:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        items.append(
            {
                "apply_request_id": row.get("apply_request_id"),
                "status": row.get("status"),
                "ok": bool(row.get("ok")),
                "applied_count": summary.get("applied_count", 0),
                "noop_count": summary.get("noop_count", 0),
                "blocked_count": summary.get("blocked_count", 0),
                "skipped_count": summary.get("skipped_count", 0),
            }
        )
    return {
        "audit_ui_dto_version": "audit_ui_dto_v1",
        "kind": "authoring_apply_run_list",
        "count": len(items),
        "runs": items,
    }


def build_authoring_apply_run_detail_dto(query: AuditQuery, apply_request_id: str) -> dict[str, Any]:
    _ensure_query(query)
    try:
        bundle = query.get_authoring_apply_bundle(apply_request_id)
    except AuditQueryError as exc:
        raise AuditDTOError(str(exc)) from exc
    run = dict(bundle["run"])
    events = [dict(row) for row in bundle["events"]]
    action_events = [row for row in events if row.get("kind") == "authoring_apply_execute_action"]
    action_status_counts: dict[str, int] = {}
    action_reason_code_counts: dict[str, int] = {}
    action_diag_code_counts: dict[str, int] = {}
    first_failure_action_id: str | None = None
    first_failure_section: str | None = None
    for row in action_events:
        status = row.get("status")
        if isinstance(status, str) and status:
            action_status_counts[status] = action_status_counts.get(status, 0) + 1
            if first_failure_action_id is None and status == "blocked":
                action_id = row.get("action_id")
                section = row.get("section")
                first_failure_action_id = action_id if isinstance(action_id, str) and action_id else None
                first_failure_section = section if isinstance(section, str) and section else None
        reason_code = row.get("reason_code")
        if isinstance(reason_code, str) and reason_code:
            action_reason_code_counts[reason_code] = action_reason_code_counts.get(reason_code, 0) + 1
        row_diag_codes_seen = False
        diag_summary = row.get("diagnostics_summary")
        if isinstance(diag_summary, dict):
            diag_codes = diag_summary.get("codes")
            if isinstance(diag_codes, list):
                for code in diag_codes:
                    if isinstance(code, str) and code:
                        row_diag_codes_seen = True
                        action_diag_code_counts[code] = action_diag_code_counts.get(code, 0) + 1
        diagnostics = row.get("diagnostics")
        if not row_diag_codes_seen and isinstance(diagnostics, list):
            for diag in diagnostics:
                if not isinstance(diag, dict):
                    continue
                code = diag.get("code")
                if isinstance(code, str) and code:
                    action_diag_code_counts[code] = action_diag_code_counts.get(code, 0) + 1
    idempotency = run.get("idempotency") if isinstance(run.get("idempotency"), dict) else {}
    transaction = run.get("transaction") if isinstance(run.get("transaction"), dict) else {}
    run_summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    blocked_count = run_summary.get("blocked_count", 0) if isinstance(run_summary.get("blocked_count", 0), int) else 0
    partial_apply = bool(transaction.get("partial_apply"))
    prevalidate_before_write = bool(transaction.get("prevalidate_before_write"))
    failure_phase = transaction.get("failure_phase") if isinstance(transaction.get("failure_phase"), str) else None
    prevalidate_status = (
        transaction.get("prevalidate_status")
        if isinstance(transaction.get("prevalidate_status"), str)
        else None
    )
    classifications = {
        "replayed": bool(idempotency.get("replayed")),
        "conflict": bool(idempotency.get("conflict")),
        "prevalidate_blocked": bool(
            (failure_phase == "prevalidate")
            or (
                str(run.get("status", "")) == "error"
                and prevalidate_before_write
                and not partial_apply
                and blocked_count > 0
                and prevalidate_status in (None, "blocked")
            )
        ),
        "runtime_blocked_after_write": bool(
            (failure_phase == "write" and str(run.get("status", "")) == "error")
            or (
                str(run.get("status", "")) == "error"
                and partial_apply
                and blocked_count > 0
                and failure_phase is None
            )
        ),
    }
    execution_path = _authoring_apply_execution_path(
        run_status=str(run.get("status", "")),
        classifications=classifications,
    )
    execution_path_label = _authoring_apply_execution_path_label(execution_path)
    execution_path_counts = {execution_path: 1}
    return {
        "audit_ui_dto_version": "audit_ui_dto_v1",
        "kind": "authoring_apply_run_detail",
        "apply_request_id": apply_request_id,
        "run": run,
        "idempotency": dict(idempotency),
        "transaction": dict(transaction),
        "events": events,
        "summary": dict(bundle["summary"]),
        "stats": {
            "event_count": len(events),
            "action_event_count": len(action_events),
            "run_event_count": sum(1 for row in events if row.get("kind") == "authoring_apply_execute_run"),
        },
        "action_stats": {
            "status_counts": {k: action_status_counts[k] for k in sorted(action_status_counts)},
            "reason_code_counts": {k: action_reason_code_counts[k] for k in sorted(action_reason_code_counts)},
            "diagnostic_code_counts": {k: action_diag_code_counts[k] for k in sorted(action_diag_code_counts)},
        },
        "failure_summary": {
            "first_failure_action_id": first_failure_action_id,
            "first_failure_section": first_failure_section,
            "blocked_action_reason_codes": sorted(action_reason_code_counts),
            "blocked_action_diagnostic_codes": sorted(action_diag_code_counts),
        },
        "classifications": classifications,
        "execution_path": execution_path,
        "execution_path_label": execution_path_label,
        "execution_path_counts": execution_path_counts,
    }


def _ensure_query(query: AuditQuery) -> None:
    if not isinstance(query, AuditQuery):
        raise AuditDTOError("query must be AuditQuery")


def _run_summary_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": row.get("run_id"),
        "claim_count": row.get("claim_count", 0),
        "decision_count": row.get("decision_count", 0),
        "error_count": row.get("error_count", 0),
        "has_failures": bool(row.get("has_failures")),
        "event_ts_min": row.get("event_ts_min"),
        "event_ts_max": row.get("event_ts_max"),
        "candidate_ids": _sorted_strings(row.get("candidate_ids")),
        "pred_ids": _sorted_strings(row.get("pred_ids")),
    }


def _authoring_apply_execution_path(*, run_status: str, classifications: dict[str, Any]) -> str:
    if bool(classifications.get("replayed")):
        return "replay"
    if bool(classifications.get("conflict")):
        return "idempotency_conflict"
    if bool(classifications.get("prevalidate_blocked")):
        return "prevalidate_blocked"
    if bool(classifications.get("runtime_blocked_after_write")):
        return "runtime_partial"
    if run_status == "ok":
        return "success"
    if run_status == "warning":
        return "success_with_warnings"
    if run_status == "error":
        return "runtime_error"
    return "unknown"


def _authoring_apply_execution_path_label(execution_path: str) -> str:
    mapping = {
        "success": "Success",
        "success_with_warnings": "Success (warnings)",
        "replay": "Idempotency replay",
        "idempotency_conflict": "Idempotency conflict",
        "prevalidate_blocked": "Prevalidate blocked",
        "runtime_partial": "Runtime partial apply",
        "runtime_error": "Runtime error",
        "unknown": "Unknown",
    }
    return mapping.get(execution_path, "Unknown")


def _build_timeline(
    decisions: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for row in decisions:
        entries.append(
            {
                "entry_kind": "decision",
                "decision_id": row.get("decision_id"),
                "event_source": row.get("event_source"),
                "event_kind": row.get("event_kind"),
                "event_ts": row.get("event_ts"),
            }
        )
    for row in failures:
        entries.append(
            {
                "entry_kind": "failure",
                "decision_id": row.get("decision_id"),
                "event_source": row.get("event_source"),
                "event_kind": row.get("event_kind"),
                "event_ts": row.get("event_ts"),
                "error_class": row.get("error_class"),
                "message": row.get("message"),
            }
        )
    return sorted(entries, key=_timeline_sort_key)


def _timeline_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    event_ts = row.get("event_ts")
    event_ts_key = event_ts if isinstance(event_ts, int) and not isinstance(event_ts, bool) else -1
    return (
        event_ts_key,
        str(row.get("decision_id", "")),
        str(row.get("entry_kind", "")),
    )


def _sorted_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted([item for item in value if isinstance(item, str)])


def _dedupe_rows(rows: list[dict[str, Any]], *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(str(row.get(name, "")) for name in keys)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return sorted(out, key=lambda row: tuple(str(row.get(name, "")) for name in keys))
