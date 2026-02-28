from __future__ import annotations

from typing import Any

from factpy_kernel.core.rules.rule_ir import RuleCompileError, RuleRegistry, RuleSpec, run_rule
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.authoring.diagnostic_codes import (
    CODE_AUTHORING_DERIVATION_COMPILE_ERROR,
    CODE_AUTHORING_RULE_COMPILE_ERROR,
    CODE_AUTHORING_SCHEMA_COMPILE_ERROR,
    CODE_DERIVATION_PREVIEW_ERROR,
    CODE_EMPTY_PREDICATES,
    CODE_PREVIEW_TRUNCATED,
    CODE_REGISTRY_RULE_ERROR,
    CODE_RULE_COMPILE_ERROR,
    CODE_RULE_SPEC_ERROR,
    CODE_SCHEMA_VALIDATION_ERROR,
    CODE_SOUFFLE_BINARY_MISSING,
    CODE_TEMPORAL_CURRENT_NO_PRED_REFS,
    CODE_TEMPORAL_CURRENT_NO_TEMPORAL_SCHEMA_PREDICATES,
    CODE_TEMPORAL_CURRENT_NO_TEMPORAL_WHERE_PREDICATES,
    PHASE_DERIVATION_AUTHORING_COMPILE,
    PHASE_DERIVATION_PREVIEW,
    PHASE_DERIVATION_PREVIEW_ENV,
    PHASE_RULE_AUTHORING_COMPILE,
    PHASE_RULE_COMPILE,
    PHASE_RULE_PARSE,
    PHASE_RULE_PREFLIGHT,
    PHASE_RULE_REGISTRY,
    PHASE_SCHEMA_AUTHORING_COMPILE,
    PHASE_SCHEMA_PREFLIGHT,
    PHASE_SCHEMA_VALIDATE,
)
from factpy_kernel.authoring.schema_compile import (
    AuthoringSchemaCompileError,
    compile_authoring_schema_v1,
)
from factpy_kernel.authoring.rule_compile import (
    AuthoringRuleCompileError,
    compile_authoring_rule_v1,
)
from factpy_kernel.authoring.derivation_compile import (
    AuthoringDerivationCompileError,
    compile_authoring_derivation_v1,
)
from factpy_kernel.core.schema.schema_ir import (
    SchemaIRValidationError,
    ensure_schema_ir,
    schema_digest,
)
from factpy_kernel.core.store.runtime import Store


class AuthoringPreflightError(Exception):
    pass


def schema_preflight_authoring(
    authoring_schema: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    try:
        schema_ir = compile_authoring_schema_v1(authoring_schema, generated_at=generated_at)
    except AuthoringSchemaCompileError as exc:
        diagnostics = [
            _diag(
                phase=PHASE_SCHEMA_AUTHORING_COMPILE,
                code=CODE_AUTHORING_SCHEMA_COMPILE_ERROR,
                message=str(exc),
                path=getattr(exc, "path", "$"),
            )
        ]
        return {
            "preflight_version": "authoring_preflight_v1",
            "kind": "schema",
            "ok": False,
            "diagnostics": diagnostics,
            "warnings": [],
            "errors": diagnostics,
        }
    return schema_preflight(schema_ir)


def schema_preflight(schema_ir: dict[str, Any]) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    try:
        validated = ensure_schema_ir(schema_ir)
    except SchemaIRValidationError as exc:
        diagnostics = [
            _diag(
                phase=PHASE_SCHEMA_VALIDATE,
                code=CODE_SCHEMA_VALIDATION_ERROR,
                message=str(exc),
                path="$",
            )
        ]
        return {
            "preflight_version": "authoring_preflight_v1",
            "kind": "schema",
            "ok": False,
            "diagnostics": diagnostics,
            "warnings": warnings,
            "errors": diagnostics,
        }

    predicates = validated.get("predicates") if isinstance(validated, dict) else []
    entities = validated.get("entities") if isinstance(validated, dict) else []
    if isinstance(predicates, list) and len(predicates) == 0:
        warnings.append(
            _warn(
                phase=PHASE_SCHEMA_PREFLIGHT,
                code=CODE_EMPTY_PREDICATES,
                message="schema has zero predicates; authoring preview/evaluate will produce no business outputs",
                path="$.predicates",
            )
        )
    return {
        "preflight_version": "authoring_preflight_v1",
        "kind": "schema",
        "ok": True,
        "schema_digest": schema_digest(validated),
        "summary": {
            "entity_count": len(entities) if isinstance(entities, list) else 0,
            "predicate_count": len(predicates) if isinstance(predicates, list) else 0,
            "pred_ids": sorted(
                [
                    pred.get("pred_id")
                    for pred in predicates
                    if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str)
                ]
            )
            if isinstance(predicates, list)
            else [],
        },
        "diagnostics": [],
        "warnings": warnings,
        "errors": [],
    }


def rule_preflight(
    *,
    store: Store,
    rule_spec_payload: dict[str, Any],
    registry_payloads: list[dict[str, Any]] | None = None,
    temporal_view: str = "record",
) -> dict[str, Any]:
    if not isinstance(store, Store):
        raise AuthoringPreflightError("store must be Store")
    if temporal_view not in {"record", "current"}:
        raise AuthoringPreflightError("temporal_view must be 'record' or 'current'")

    registry = RuleRegistry()
    diagnostics: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if registry_payloads is not None:
        if not isinstance(registry_payloads, list):
            raise AuthoringPreflightError("registry_payloads must be list or None")
        for idx, payload in enumerate(registry_payloads):
            try:
                registry.register(_rule_spec_from_payload(payload))
            except (RuleCompileError, TypeError, ValueError, KeyError) as exc:
                diagnostics.append(
                    _diag(
                        phase=PHASE_RULE_REGISTRY,
                        code=CODE_REGISTRY_RULE_ERROR,
                        message=f"registry_payloads[{idx}]: {exc}",
                        path=f"$.registry_payloads[{idx}]",
                    )
                )

    try:
        rule_spec = _rule_spec_from_payload(rule_spec_payload)
    except (RuleCompileError, TypeError, ValueError, KeyError) as exc:
        error_diag = _diag(
            phase=PHASE_RULE_PARSE,
            code=CODE_RULE_SPEC_ERROR,
            message=str(exc),
            path="$.rule_spec_payload",
        )
        return {
            "preflight_version": "authoring_preflight_v1",
            "kind": "rule",
            "ok": False,
            "diagnostics": [error_diag, *diagnostics],
            "warnings": warnings,
            "errors": [error_diag, *diagnostics],
        }

    if temporal_view == "current":
        maybe_warning = _temporal_current_no_effect_warning(
            schema_ir=store.schema_ir,
            where=rule_spec.where,
            phase=PHASE_RULE_PREFLIGHT,
            path="$.rule_spec_payload.where",
        )
        if maybe_warning is not None:
            warnings.append(maybe_warning)

    try:
        rows = run_rule(store, rule_spec, registry, temporal_view=temporal_view)
    except (RuleCompileError, WhereValidationError) as exc:
        error_diag = _diag(
            phase=PHASE_RULE_COMPILE,
            code=CODE_RULE_COMPILE_ERROR,
            message=str(exc),
            path="$.rule_spec_payload.where",
        )
        return {
            "preflight_version": "authoring_preflight_v1",
            "kind": "rule",
            "ok": False,
            "rule": {
                "rule_id": rule_spec.rule_id,
                "version": rule_spec.version,
                "expose": rule_spec.expose,
            },
            "diagnostics": [error_diag, *diagnostics],
            "warnings": warnings,
            "errors": [error_diag, *diagnostics],
        }

    preview_rows = [list(row) for row in rows[:20]]
    if len(rows) > 20:
        warnings.append(
            _warn(
                phase=PHASE_RULE_PREFLIGHT,
                code=CODE_PREVIEW_TRUNCATED,
                message=f"rule preview truncated to 20 rows (total={len(rows)})",
                path="$.summary.preview_rows",
            )
        )
    return {
        "preflight_version": "authoring_preflight_v1",
        "kind": "rule",
        "ok": len(diagnostics) == 0,
        "rule": {
            "rule_id": rule_spec.rule_id,
            "version": rule_spec.version,
            "expose": rule_spec.expose,
            "select_vars": list(rule_spec.select_vars),
        },
        "summary": {
            "row_count": len(rows),
            "preview_limit": 20,
            "preview_rows": preview_rows,
        },
        "diagnostics": diagnostics,
        "warnings": warnings,
        "errors": diagnostics,
    }


def rule_preflight_authoring(
    *,
    store: Store,
    authoring_rule_payload: dict[str, Any],
    registry_payloads: list[dict[str, Any]] | None = None,
    temporal_view: str = "record",
) -> dict[str, Any]:
    try:
        rule_spec_payload = compile_authoring_rule_v1(authoring_rule_payload, schema_ir=store.schema_ir)
    except AuthoringRuleCompileError as exc:
        diagnostics = [
            _diag(
                phase=PHASE_RULE_AUTHORING_COMPILE,
                code=CODE_AUTHORING_RULE_COMPILE_ERROR,
                message=str(exc),
                path=getattr(exc, "path", "$.authoring_rule_payload"),
            )
        ]
        return {
            "preflight_version": "authoring_preflight_v1",
            "kind": "rule",
            "ok": False,
            "diagnostics": diagnostics,
            "warnings": [],
            "errors": diagnostics,
        }
    return rule_preflight(
        store=store,
        rule_spec_payload=rule_spec_payload,
        registry_payloads=registry_payloads,
        temporal_view=temporal_view,
    )


def derivation_dry_run_preview(
    *,
    store: Store,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: list[Any],
    where: list[Any],
    mode: str = "python",
    temporal_view: str = "record",
    materialize_as: str | None = None,
    head: dict[str, Any] | None = None,
    id_policy: Any | None = None,
) -> dict[str, Any]:
    if not isinstance(store, Store):
        raise AuthoringPreflightError("store must be Store")
    if mode not in {"python", "engine"}:
        raise AuthoringPreflightError("mode must be 'python' or 'engine'")
    if temporal_view not in {"record", "current"}:
        raise AuthoringPreflightError("temporal_view must be 'record' or 'current'")

    warnings: list[dict[str, Any]] = []
    if mode == "engine" and _find_souffle_binary_safe() is None:
        warnings.append(
            _warn(
                phase=PHASE_DERIVATION_PREVIEW_ENV,
                code=CODE_SOUFFLE_BINARY_MISSING,
                message="Soufflé binary not found; engine preview may fail because noop fallback is rejected",
                path="$.mode",
            )
        )
    if temporal_view == "current":
        maybe_warning = _temporal_current_no_effect_warning(
            schema_ir=store.schema_ir,
            where=where,
            phase=PHASE_DERIVATION_PREVIEW,
            path="$.where",
        )
        if maybe_warning is not None:
            warnings.append(maybe_warning)

    try:
        candidates = store.evaluate(
            derivation_id=derivation_id,
            version=version,
            target_pred_id=target_pred_id,
            head_vars=head_vars,
            where=where,
            mode=mode,
            temporal_view=temporal_view,
            materialize_as=materialize_as,
            head=head,
            id_policy=id_policy,
        )
    except (WhereValidationError, ValueError) as exc:
        diagnostics = [
            _diag(
                phase=PHASE_DERIVATION_PREVIEW,
                code=CODE_DERIVATION_PREVIEW_ERROR,
                message=str(exc),
                path="$.where",
            )
        ]
        return {
            "preflight_version": "authoring_preflight_v1",
            "kind": "derivation_dry_run",
            "ok": False,
            "diagnostics": diagnostics,
            "warnings": warnings,
            "errors": diagnostics,
        }

    preview_candidates = []
    for cand in candidates[:20]:
        payload = cand.payload if isinstance(cand.payload, dict) else {}
        preview_candidates.append(
            {
                "target": cand.target,
                "e_ref": payload.get("e_ref"),
                "rest_terms": payload.get("rest_terms"),
                "materialize_as": payload.get("materialize_as"),
                "record_type": payload.get("record_type"),
                "roles": payload.get("roles"),
                "key_tuple_digest": cand.key_tuple_digest,
                "tup_digest": cand.tup_digest,
                "run_id": cand.run_id,
            }
        )

    if len(candidates) > 20:
        warnings.append(
            _warn(
                phase=PHASE_DERIVATION_PREVIEW,
                code=CODE_PREVIEW_TRUNCATED,
                message=f"candidate preview truncated to 20 rows (total={len(candidates)})",
                path="$.summary.preview_candidates",
            )
        )

    return {
        "preflight_version": "authoring_preflight_v1",
        "kind": "derivation_dry_run",
        "ok": True,
        "mode": mode,
        "temporal_view": temporal_view,
        "summary": {
            "candidate_count": len(candidates),
            "preview_limit": 20,
            "preview_candidates": preview_candidates,
            "targets": sorted({cand.target for cand in candidates}),
        },
        "diagnostics": [],
        "warnings": warnings,
        "errors": [],
    }


def derivation_dry_run_preview_authoring(
    *,
    store: Store,
    authoring_derivation_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        compiled = compile_authoring_derivation_v1(authoring_derivation_payload, schema_ir=store.schema_ir)
    except AuthoringDerivationCompileError as exc:
        diagnostics = [
            _diag(
                phase=PHASE_DERIVATION_AUTHORING_COMPILE,
                code=CODE_AUTHORING_DERIVATION_COMPILE_ERROR,
                message=str(exc),
                path=getattr(exc, "path", "$.authoring_derivation_payload"),
            )
        ]
        return {
            "preflight_version": "authoring_preflight_v1",
            "kind": "derivation_dry_run",
            "ok": False,
            "diagnostics": diagnostics,
            "warnings": [],
            "errors": diagnostics,
        }
    return derivation_dry_run_preview(
        store=store,
        derivation_id=compiled["derivation_id"],
        version=compiled["version"],
        target_pred_id=compiled["target_pred_id"],
        head_vars=compiled["head_vars"],
        where=compiled["where"],
        mode=compiled["mode"],
        temporal_view=compiled["temporal_view"],
        materialize_as=compiled.get("materialize_as"),
        head=compiled.get("head"),
        id_policy=compiled.get("id_policy"),
    )


def _rule_spec_from_payload(payload: dict[str, Any]) -> RuleSpec:
    if not isinstance(payload, dict):
        raise RuleCompileError("rule_spec payload must be object")
    return RuleSpec(
        rule_id=payload["rule_id"],
        version=payload["version"],
        select_vars=payload["select_vars"],
        where=payload["where"],
        expose=bool(payload.get("expose", False)),
    )


def _diag(*, phase: str, code: str, message: str, path: str | None) -> dict[str, Any]:
    return {
        "phase": phase,
        "code": code,
        "path": path,
        "message": message,
        "severity": "error",
    }


def _warn(*, phase: str, code: str, message: str, path: str | None) -> dict[str, Any]:
    return {
        "phase": phase,
        "code": code,
        "path": path,
        "message": message,
        "severity": "warning",
    }


def _find_souffle_binary_safe() -> Any:
    try:
        from factpy_kernel.adapters.souffle.runner import find_souffle_binary
    except Exception:
        return None
    try:
        return find_souffle_binary()
    except Exception:
        return None


def _temporal_current_no_effect_warning(
    *,
    schema_ir: dict[str, Any],
    where: Any,
    phase: str,
    path: str,
) -> dict[str, Any] | None:
    pred_ids = _collect_pred_ids_from_where(where)
    if not pred_ids:
        return _warn(
            phase=phase,
            code=CODE_TEMPORAL_CURRENT_NO_PRED_REFS,
            message="temporal_view='current' is set but where references no predicates; current view selection has no effect",
            path=path,
        )

    temporal_pred_ids = {
        pred.get("pred_id")
        for pred in schema_ir.get("predicates", [])
        if isinstance(pred, dict)
        and pred.get("cardinality") == "temporal"
        and isinstance(pred.get("pred_id"), str)
    }
    if not temporal_pred_ids:
        return _warn(
            phase=phase,
            code=CODE_TEMPORAL_CURRENT_NO_TEMPORAL_SCHEMA_PREDICATES,
            message="temporal_view='current' is set but schema has no temporal predicates; current view selection has no effect",
            path=path,
        )

    if pred_ids.isdisjoint(temporal_pred_ids):
        return _warn(
            phase=phase,
            code=CODE_TEMPORAL_CURRENT_NO_TEMPORAL_WHERE_PREDICATES,
            message="temporal_view='current' is set but where references no temporal predicates; current view selection has no effect",
            path=path,
        )
    return None


def _collect_pred_ids_from_where(where: Any) -> set[str]:
    out: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, tuple) and node:
            kind = node[0]
            if kind == "pred" and len(node) >= 2 and isinstance(node[1], str):
                out.add(node[1])
                return
            if kind == "not" and len(node) == 2:
                walk(node[1])
                return
            return
        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(where)
    return out
