from __future__ import annotations

from typing import Any

from factgraph.authoring.diagnostic_codes import build_diagnostics_contract_meta_v1
from factgraph.authoring.dto import (
    AuthoringDTOError,
    build_derivation_preview_dto,
    build_derivation_preview_from_authoring_dto,
    build_rule_preflight_from_authoring_dto,
    build_rule_preflight_dto,
    build_schema_preflight_dto,
    build_schema_preflight_from_authoring_dto,
)
from factgraph.authoring.schema_compile import AuthoringSchemaCompileError, compile_authoring_schema_v1
from factgraph.core.store.runtime import Store


class AuthoringSessionError(Exception):
    pass


def build_authoring_session_dto(
    *,
    store: Store | None = None,
    schema_ir: dict[str, Any] | None = None,
    authoring_schema: dict[str, Any] | None = None,
    rule_request: dict[str, Any] | None = None,
    derivation_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    order: list[str] = []
    compiled_schema_ir: dict[str, Any] | None = None

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

    effective_store = store
    if effective_store is None and (rule_request is not None or derivation_request is not None):
        if compiled_schema_ir is not None:
            effective_store = Store(schema_ir=compiled_schema_ir)

    if rule_request is not None:
        if not isinstance(effective_store, Store):
            raise AuthoringSessionError("store is required for rule_request")
        if not isinstance(rule_request, dict):
            raise AuthoringSessionError("rule_request must be dict")
        sections["rule_preflight"] = _build_rule_section(effective_store, rule_request)
        order.append("rule_preflight")

    if derivation_request is not None:
        if not isinstance(effective_store, Store):
            raise AuthoringSessionError("store is required for derivation_request")
        if not isinstance(derivation_request, dict):
            raise AuthoringSessionError("derivation_request must be dict")
        sections["derivation_preview"] = _build_derivation_section(effective_store, derivation_request)
        order.append("derivation_preview")

    if not order:
        raise AuthoringSessionError(
            "at least one of schema_ir/authoring_schema/rule_request/derivation_request is required"
        )

    normalized_sections = {
        name: sections.get(name)
        for name in ("schema_preflight", "rule_preflight", "derivation_preview")
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


def _build_rule_section(store: Store, request: dict[str, Any]) -> dict[str, Any]:
    try:
        if "authoring_rule_payload" in request:
            return build_rule_preflight_from_authoring_dto(
                store=store,
                authoring_rule_payload=request["authoring_rule_payload"],
                registry_payloads=request.get("registry_payloads"),
            )
        return build_rule_preflight_dto(
            store=store,
            rule_spec_payload=request["rule_spec_payload"],
            registry_payloads=request.get("registry_payloads"),
        )
    except KeyError as exc:
        raise AuthoringSessionError(f"rule_request missing key: {exc.args[0]}") from exc
    except AuthoringDTOError as exc:
        raise AuthoringSessionError(str(exc)) from exc


def _build_derivation_section(store: Store, request: dict[str, Any]) -> dict[str, Any]:
    try:
        if "authoring_derivation_payload" in request:
            return build_derivation_preview_from_authoring_dto(
                store=store,
                authoring_derivation_payload=request["authoring_derivation_payload"],
            )
        return build_derivation_preview_dto(
            store=store,
            derivation_id=str(request["derivation_id"]),
            version=str(request["version"]),
            target_pred_id=str(request["target_pred_id"]),
            head_vars=request["head_vars"],
            where=request["where"],
            mode=str(request.get("mode", "native")),
        )
    except KeyError as exc:
        raise AuthoringSessionError(f"derivation_request missing key: {exc.args[0]}") from exc
    except AuthoringDTOError as exc:
        raise AuthoringSessionError(str(exc)) from exc


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
