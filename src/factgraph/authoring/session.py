from __future__ import annotations

from typing import Any

from factgraph.authoring.diagnostic_codes import build_diagnostics_contract_meta_v1
from factgraph.authoring.dto import (
    build_schema_preflight_dto,
    build_schema_preflight_from_authoring_dto,
)
from factgraph.authoring.schema_compile import AuthoringSchemaCompileError, compile_authoring_schema_v1


class AuthoringSessionError(Exception):
    pass


def build_authoring_session_dto(
    *,
    store: Any | None = None,
    schema_ir: dict[str, Any] | None = None,
    authoring_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an authoring session DTO covering schema preflight only.

    Q8 Phase 2 removed `rule_request` / `derivation_request` parameters along
    with the internal `_build_rule_section` / `_build_derivation_section`
    helpers. Schema-only call shape is preserved per Q6 schema-only transition.
    """
    sections: dict[str, Any] = {}
    order: list[str] = []

    if schema_ir is not None and authoring_schema is not None:
        raise AuthoringSessionError("provide only one of schema_ir or authoring_schema")

    if authoring_schema is not None:
        try:
            compiled_schema_ir = compile_authoring_schema_v1(authoring_schema)
        except AuthoringSchemaCompileError:
            sections["schema_preflight"] = build_schema_preflight_from_authoring_dto(authoring_schema)
        else:
            sections["schema_preflight"] = build_schema_preflight_dto(compiled_schema_ir)
        order.append("schema_preflight")

    if schema_ir is not None:
        sections["schema_preflight"] = build_schema_preflight_dto(schema_ir)
        if "schema_preflight" not in order:
            order.append("schema_preflight")

    if not order:
        raise AuthoringSessionError(
            "at least one of schema_ir/authoring_schema is required"
        )

    normalized_sections = {
        name: sections.get(name)
        for name in ("schema_preflight",)
    }
    diagnostic_count = sum(_section_count(sections[name], "diagnostic_count") for name in order)
    warning_count = sum(_section_count(sections[name], "warning_count") for name in order)
    ok = all(bool(sections[name].get("ok")) for name in order)
    status = _aggregate_status([str(sections[name].get("status", "ok")) for name in order])

    return {
        "authoring_session_dto_version": "authoring_session_dto_v1",
        "kind": "authoring_session",
        "diagnostics_contract": build_diagnostics_contract_meta_v1(),
        "ok": ok,
        "status": status,
        "order": order,
        "sections": normalized_sections,
        "summary": {
            "section_count": len(order),
            "present_sections": list(order),
            "diagnostic_count": diagnostic_count,
            "warning_count": warning_count,
            "status_counts": _status_counts([str(sections[name].get("status", "ok")) for name in order]),
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
