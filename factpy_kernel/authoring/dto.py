from __future__ import annotations

from typing import Any

from factpy_kernel.authoring.diagnostic_codes import build_diagnostics_contract_meta_v1
from factpy_kernel.authoring.preflight import (
    derivation_dry_run_preview,
    derivation_dry_run_preview_authoring,
    rule_preflight,
    rule_preflight_authoring,
    schema_preflight,
    schema_preflight_authoring,
)
from factpy_kernel.store.api import Store


class AuthoringDTOError(Exception):
    pass


def build_schema_preflight_dto(schema_ir: dict[str, Any]) -> dict[str, Any]:
    payload = schema_preflight(schema_ir)
    return _wrap_preflight_payload("schema_preflight", payload)


def build_schema_preflight_from_authoring_dto(
    authoring_schema: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = schema_preflight_authoring(authoring_schema, generated_at=generated_at)
    return _wrap_preflight_payload("schema_preflight", payload)


def build_rule_preflight_dto(
    *,
    store: Store,
    rule_spec_payload: dict[str, Any],
    registry_payloads: list[dict[str, Any]] | None = None,
    temporal_view: str = "record",
) -> dict[str, Any]:
    payload = rule_preflight(
        store=store,
        rule_spec_payload=rule_spec_payload,
        registry_payloads=registry_payloads,
        temporal_view=temporal_view,
    )
    return _wrap_preflight_payload("rule_preflight", payload)


def build_rule_preflight_from_authoring_dto(
    *,
    store: Store,
    authoring_rule_payload: dict[str, Any],
    registry_payloads: list[dict[str, Any]] | None = None,
    temporal_view: str = "record",
) -> dict[str, Any]:
    payload = rule_preflight_authoring(
        store=store,
        authoring_rule_payload=authoring_rule_payload,
        registry_payloads=registry_payloads,
        temporal_view=temporal_view,
    )
    return _wrap_preflight_payload("rule_preflight", payload)


def build_derivation_preview_dto(
    *,
    store: Store,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: list[Any],
    where: list[Any],
    mode: str = "python",
    temporal_view: str = "record",
) -> dict[str, Any]:
    payload = derivation_dry_run_preview(
        store=store,
        derivation_id=derivation_id,
        version=version,
        target_pred_id=target_pred_id,
        head_vars=head_vars,
        where=where,
        mode=mode,
        temporal_view=temporal_view,
    )
    return _wrap_preflight_payload("derivation_preview", payload)


def build_derivation_preview_from_authoring_dto(
    *,
    store: Store,
    authoring_derivation_payload: dict[str, Any],
) -> dict[str, Any]:
    payload = derivation_dry_run_preview_authoring(
        store=store,
        authoring_derivation_payload=authoring_derivation_payload,
    )
    return _wrap_preflight_payload("derivation_preview", payload)


def _wrap_preflight_payload(dto_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AuthoringDTOError("preflight payload must be dict")
    if payload.get("preflight_version") != "authoring_preflight_v1":
        raise AuthoringDTOError("unsupported preflight_version")

    diagnostics = _normalize_issue_list(payload.get("diagnostics"))
    warnings = _normalize_issue_list(payload.get("warnings"))
    ok = bool(payload.get("ok"))
    status = "error" if not ok else ("warning" if warnings else "ok")

    dto: dict[str, Any] = {
        "authoring_ui_dto_version": "authoring_ui_dto_v1",
        "kind": dto_kind,
        "source_kind": payload.get("kind"),
        "diagnostics_contract": build_diagnostics_contract_meta_v1(),
        "status": status,
        "ok": ok,
        "diagnostics": diagnostics,
        "warnings": warnings,
        "counts": {
            "diagnostic_count": len(diagnostics),
            "warning_count": len(warnings),
        },
    }

    if isinstance(payload.get("summary"), dict):
        dto["summary"] = _json_safe_copy(payload["summary"])

    for key in ("schema_digest", "rule", "mode", "temporal_view"):
        if key in payload:
            dto[key] = _json_safe_copy(payload[key])

    if not ok and "errors" in payload:
        dto["errors"] = _normalize_issue_list(payload.get("errors"))

    return dto


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


def _json_safe_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_copy(v) for v in value]
    return value
