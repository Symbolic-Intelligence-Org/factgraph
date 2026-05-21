from __future__ import annotations

from typing import Any

from factgraph.authoring.diagnostic_codes import (
    CODE_AUTHORING_SCHEMA_DSL_PARSE_ERROR,
    PHASE_SCHEMA_DSL_PARSE,
    build_diagnostics_contract_meta_v1,
)
from factgraph.authoring.schema_dsl_parse import (
    AuthoringSchemaDSLParseError,
    parse_authoring_schema_dsl_v1,
)
from factgraph.authoring.session import AuthoringSessionError, build_authoring_session_dto
from factgraph.authoring.workflow import (
    AuthoringWorkflowError,
    build_authoring_publish_workflow_dry_run_bundle_dto,
)
from factgraph.core.store.runtime import Store


class AuthoringDSLBridgeError(Exception):
    pass


# Q8 Phase 2 (Slice 6) note:
#   The DSL bridge no longer accepts `rule_dsl` / `derivation_dsl` /
#   `rule_registry_payloads` / `derivation_mode` parameters. Rule/inference
#   DSL bridge code paths were removed alongside SavedRule persistence. The
#   four public function names below are preserved for caller compatibility
#   but operate schema-only.


def build_authoring_session_from_dsl_inputs_dto(
    *,
    store: Store | None = None,
    schema_dsl: str | None = None,
) -> dict[str, Any]:
    try:
        authoring_schema = parse_authoring_schema_dsl_v1(schema_dsl) if schema_dsl is not None else None
    except AuthoringSchemaDSLParseError as exc:
        raise AuthoringDSLBridgeError(str(exc)) from exc

    try:
        return build_authoring_session_dto(
            store=store,
            authoring_schema=authoring_schema,
        )
    except AuthoringSessionError as exc:
        raise AuthoringDSLBridgeError(str(exc)) from exc


def build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto(
    *,
    store: Store | None = None,
    schema_dsl: str | None = None,
) -> dict[str, Any]:
    try:
        session = build_authoring_session_from_dsl_inputs_dto(
            store=store,
            schema_dsl=schema_dsl,
        )
        return build_authoring_publish_workflow_dry_run_bundle_dto(session)
    except AuthoringWorkflowError as exc:
        raise AuthoringDSLBridgeError(str(exc)) from exc


def build_authoring_session_from_dsl_inputs_safe_dto(
    *,
    store: Store | None = None,
    schema_dsl: str | None = None,
) -> dict[str, Any]:
    parsed_schema: dict[str, Any] | None = None
    parse_error_section: dict[str, Any] | None = None

    if schema_dsl is not None:
        try:
            parsed_schema = parse_authoring_schema_dsl_v1(schema_dsl)
        except AuthoringSchemaDSLParseError as exc:
            parse_error_section = _dsl_parse_error_section(
                kind="schema_preflight",
                code=CODE_AUTHORING_SCHEMA_DSL_PARSE_ERROR,
                phase=PHASE_SCHEMA_DSL_PARSE,
                path=_normalize_dsl_parse_path(exc.path, root="$.schema_dsl"),
                dsl_error_kind=_dsl_error_kind(exc),
                details=_dsl_error_details(exc),
                message=str(exc),
            )

    if parse_error_section is None:
        return build_authoring_session_from_dsl_inputs_dto(
            store=store,
            schema_dsl=schema_dsl,
        )

    base_sections: dict[str, Any] = {"schema_preflight": parse_error_section}
    if parsed_schema is not None:
        try:
            base_session = build_authoring_session_dto(
                store=store,
                authoring_schema=parsed_schema,
            )
            base_sections["schema_preflight"] = base_session["sections"].get("schema_preflight") or parse_error_section
        except AuthoringSessionError:
            pass

    if schema_dsl is None and parsed_schema is None:
        raise AuthoringDSLBridgeError(
            "schema_dsl is required for safe DSL session build"
        )

    return _build_session_from_sections(order=["schema_preflight"], sections=base_sections)


def build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto(
    *,
    store: Store | None = None,
    schema_dsl: str | None = None,
) -> dict[str, Any]:
    session = build_authoring_session_from_dsl_inputs_safe_dto(
        store=store,
        schema_dsl=schema_dsl,
    )
    try:
        return build_authoring_publish_workflow_dry_run_bundle_dto(session)
    except AuthoringWorkflowError as exc:
        raise AuthoringDSLBridgeError(str(exc)) from exc


def _dsl_parse_error_section(
    *,
    kind: str,
    code: str,
    phase: str,
    path: str,
    dsl_error_kind: str,
    details: dict[str, Any] | None,
    message: str,
) -> dict[str, Any]:
    diagnostic = {
        "phase": phase,
        "code": code,
        "path": path,
        "message": message,
        "severity": "error",
        "dsl_error_kind": dsl_error_kind,
    }
    if details:
        diagnostic["details"] = details
    return {
        "authoring_ui_dto_version": "authoring_ui_dto_v1",
        "kind": kind,
        "source_kind": "dsl_parse",
        "diagnostics_contract": build_diagnostics_contract_meta_v1(),
        "status": "error",
        "ok": False,
        "diagnostics": [diagnostic],
        "warnings": [],
        "errors": [diagnostic],
        "counts": {"diagnostic_count": 1, "warning_count": 0},
    }


def _normalize_dsl_parse_path(path: str | None, *, root: str) -> str:
    if not isinstance(root, str) or not root.startswith("$."):
        return root
    if not path or path == "$":
        return root
    if path.startswith("$.dsl"):
        return root + path[len("$.dsl") :]
    if path.startswith("$"):
        return root + path[1:]
    return root


def _dsl_error_kind(exc: Exception) -> str:
    kind = getattr(exc, "kind", None)
    if kind in {"syntax", "structure", "input_type"}:
        return str(kind)
    return "structure"


def _dsl_error_details(exc: Exception) -> dict[str, Any] | None:
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return None
    normalized: dict[str, Any] = {}
    for key, value in details.items():
        if not isinstance(key, str) or not key:
            continue
        if isinstance(value, (str, int, bool)):
            normalized[key] = value
    return normalized or None


def _build_session_from_sections(*, order: list[str], sections: dict[str, Any]) -> dict[str, Any]:
    normalized = {"schema_preflight": sections.get("schema_preflight")}
    statuses = [str((sections.get(name) or {}).get("status", "ok")) for name in order]
    diagnostic_count = sum(_section_count(sections.get(name), "diagnostic_count") for name in order)
    warning_count = sum(_section_count(sections.get(name), "warning_count") for name in order)
    ok = all(bool((sections.get(name) or {}).get("ok")) for name in order)
    status = _aggregate_status(statuses)
    return {
        "authoring_session_dto_version": "authoring_session_dto_v1",
        "kind": "authoring_session",
        "diagnostics_contract": build_diagnostics_contract_meta_v1(),
        "ok": ok,
        "status": status,
        "order": list(order),
        "sections": normalized,
        "summary": {
            "section_count": len(order),
            "present_sections": list(order),
            "diagnostic_count": diagnostic_count,
            "warning_count": warning_count,
            "status_counts": _status_counts(statuses),
        },
    }


def _section_count(section: Any, key: str) -> int:
    if not isinstance(section, dict):
        return 0
    counts = section.get("counts")
    if not isinstance(counts, dict):
        return 0
    value = counts.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _aggregate_status(statuses: list[str]) -> str:
    if any(status == "error" for status in statuses):
        return "error"
    if any(status == "warning" for status in statuses):
        return "warning"
    return "ok"


def _status_counts(statuses: list[str]) -> dict[str, int]:
    counts = {"ok": 0, "warning": 0, "error": 0}
    for status in statuses:
        if status in counts:
            counts[status] += 1
    return counts
