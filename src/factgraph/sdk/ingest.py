from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from factgraph.application import apply_ingest_request, entity_type_from_ref, field_value_type
from factgraph.application.protocol import (
    EntityRef,
    EntitySelector,
    FieldPath,
    IngestAddItem,
    IngestRequest,
    IngestRetractItem,
    IngestSetItem,
    ProtocolShapeError,
)
from factgraph.core.derivation.candidates import DerivationOutput
from factgraph.core.evidence.write_protocol import add_field, set_field
from factgraph.core.schema.meta_policy import (
    EVENT_TIME_META_KEY,
    SYSTEM_MANAGED_META_KEYS,
)

from .errors import SDKStoreError

if TYPE_CHECKING:
    from .store import SDKStore


HARD_RESERVED_META_KEYS = SYSTEM_MANAGED_META_KEYS
# Proposed future reserved key (spec-level, not enforced by write_protocol yet).
SUGGESTED_HARD_RESERVED_META_KEYS: frozenset[str] = frozenset({"meta_origin"})

SENSITIVE_SEMANTIC_META_KEYS: frozenset[str] = frozenset(
    {
        "derived_rule_id",
        "derived_rule_version",
        "run_id",
        "support_digest",
        "support_kind",
        "confidence_kind",
        "candidate_id",
        "candidate_key",
        "candidate_kind",
        "key_tuple_digest",
        "cand_key_digest",
        "schema_digest",
        "policy_digest",
        "meta_origin",
    }
)

CONVENTION_META_KEYS: frozenset[str] = frozenset(
    {
        "source",
        "source_loc",
        "trace_id",
        "confidence",
        "approved_by",
        "note",
    }
)

DEDUP_AFFECTING_META_KEYS: frozenset[str] = frozenset({"source", "source_loc", "trace_id"})

# Normalized ingest item schema (v1 draft, dict-based; intentionally not frozen to TypedDict yet):
# - {"kind": "set", "field": <sdk.Field>, "e_ref": str, "value": Any, "meta"?: dict}
# - {"kind": "add", "field": <sdk.Field>, "e_ref": str, "value": Any, "meta"?: dict}
# - {"kind": "retract", "asrt_id": str, "meta"?: dict}
# Notes:
# - top-level ingest(meta=...) is merged with item meta (item keys override)
# - "retract" targets a claim assertion id via item["asrt_id"]; users must not set reserved meta key "revoked_asrt_id"


@dataclass(frozen=True)
class IngestResult:
    """Summary, diagnostics and assertion ids produced by SDK ingest."""

    written_assertion_ids: list[str]
    skipped_count: int
    duplicate_count: int
    warnings: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    diagnostics_contract_version: int = 1


@dataclass(frozen=True)
class ValidationReport:
    """Structured validation status, warnings and errors for ingest provenance."""

    ok: bool
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    diagnostics_contract_version: int = 1


@dataclass(frozen=True)
class _PreparedIngestItem:
    kind: str
    field: Any | None = None
    e_ref: str | None = None
    value: Any = None
    asrt_id: str | None = None
    meta: dict[str, Any] | None = None


def sdk_validate_provenance(
    sdk: SDKStore,
    obj: Any,
    *,
    standard: str = "derivation_v1",
) -> ValidationReport:
    del sdk  # reserved for future schema-/policy-aware validation extensions
    if standard != "derivation_v1":
        raise SDKStoreError(f"unsupported provenance validation standard: {standard!r}")

    source_obj = _coerce_provenance_input(obj)
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    _require_non_empty_str(
        source_obj,
        "derived_rule_id",
        errors=errors,
        path="$.provenance.derived_rule_id",
    )
    _require_non_empty_str(
        source_obj,
        "derived_rule_version",
        errors=errors,
        path="$.provenance.derived_rule_version",
    )
    _require_non_empty_str(
        source_obj,
        "run_id",
        errors=errors,
        path="$.provenance.run_id",
    )
    _require_non_empty_str(
        source_obj,
        "support_kind",
        errors=errors,
        path="$.provenance.support_kind",
    )
    _require_sha256_token(
        source_obj,
        "support_digest",
        errors=errors,
        path="$.provenance.support_digest",
    )

    # Optional but semantically meaningful if present.
    for key in ("schema_digest", "policy_digest"):
        if key in source_obj and source_obj.get(key) is not None:
            if not _is_sha256_token(source_obj.get(key)):
                warnings.append(
                    _diag(
                        code="provenance_optional_digest_malformed",
                        severity="warning",
                        path=f"$.provenance.{key}",
                        message=f"{key} should be 'sha256:<hex>' when provided",
                        data={"key": key},
                    )
                )

    return ValidationReport(ok=not errors, warnings=warnings, errors=errors)


def sdk_ingest(
    sdk: SDKStore,
    data: Any,
    *,
    meta: dict[str, Any] | None = None,
    allow_sensitive_meta: bool = False,
) -> IngestResult:
    base_meta = _normalize_user_meta(meta, path="meta")
    warnings: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    if not allow_sensitive_meta:
        warnings.extend(_sensitive_meta_warnings(base_meta, path="meta"))

    if not isinstance(data, (list, tuple)):
        raise SDKStoreError("ingest(data=...) currently requires list/tuple of normalized fact write items")

    # SDK-layer precheck is UX-oriented: collect path-aware diagnostics (items[i].*) before writing.
    # Core write_protocol validation remains the contract-level final barrier for callers bypassing SDK.
    prepared_items, precheck_diagnostics = _prepare_ingest_items(
        sdk,
        data,
        base_meta=base_meta,
        allow_sensitive_meta=allow_sensitive_meta,
        warnings=warnings,
    )
    diagnostics.extend(precheck_diagnostics)
    # Warnings never block writes. Only error diagnostics trigger collect-and-stop behavior.
    if any(row.get("severity") == "error" for row in diagnostics):
        return IngestResult(
            written_assertion_ids=[],
            skipped_count=0,
            duplicate_count=0,
            warnings=warnings,
            diagnostics=diagnostics,
        )

    existing_claim_ids = {row.asrt_id for row in sdk.ledger.find_claims()}
    existing_revoker_ids = {row.revoker_asrt_id for row in sdk.ledger.revokes}

    written_assertion_ids: list[str] = []
    duplicate_count = 0
    skipped_count = 0

    for idx, prepared in enumerate(prepared_items):
        path = f"items[{idx}]"
        if prepared.kind == "set":
            asrt_id = _ingest_set_or_add_prepared(
                sdk,
                prepared,
                kind="set",
                path=path,
                warnings=warnings,
            )
            is_duplicate = asrt_id in existing_claim_ids
            if is_duplicate:
                duplicate_count += 1
                skipped_count += 1
            else:
                existing_claim_ids.add(asrt_id)
                written_assertion_ids.append(asrt_id)
            continue

        if prepared.kind == "add":
            asrt_id = _ingest_set_or_add_prepared(
                sdk,
                prepared,
                kind="add",
                path=path,
                warnings=warnings,
            )
            is_duplicate = asrt_id in existing_claim_ids
            if is_duplicate:
                duplicate_count += 1
                skipped_count += 1
            else:
                existing_claim_ids.add(asrt_id)
                written_assertion_ids.append(asrt_id)
            continue

        if prepared.kind == "retract":
            if not isinstance(prepared.asrt_id, str) or not prepared.asrt_id:
                raise SDKStoreError(f"{path}.asrt_id must be non-empty string for retract")
            revoker_id = _app_ingest_retract(sdk, prepared, path=path, warnings=warnings)
            if not isinstance(revoker_id, str) or not revoker_id:
                diagnostics.append(
                    _diag(
                        code="ingest_retract_noop",
                        severity="warning",
                        path=path,
                        message="retract returned no revoker assertion id",
                    )
                )
                skipped_count += 1
                continue
            if revoker_id in existing_revoker_ids:
                duplicate_count += 1
                skipped_count += 1
            else:
                existing_revoker_ids.add(revoker_id)
                written_assertion_ids.append(revoker_id)
            continue

        raise SDKStoreError(
            f"{path}.kind unsupported: {prepared.kind!r} (expected 'set', 'add', or 'retract')"
        )

    return IngestResult(
        written_assertion_ids=written_assertion_ids,
        skipped_count=skipped_count,
        duplicate_count=duplicate_count,
        warnings=warnings,
        diagnostics=diagnostics,
    )


def _ingest_set_or_add_prepared(
    sdk: SDKStore,
    item: _PreparedIngestItem,
    *,
    kind: str,
    path: str,
    warnings: list[dict[str, Any]],
) -> str:
    field = item.field
    e_ref = item.e_ref
    if not isinstance(e_ref, str) or not e_ref:
        raise SDKStoreError(f"{path}.e_ref must be non-empty string")
    if item.meta is None:
        raise SDKStoreError(f"{path}.meta missing in prepared item")
    if item.field is None:
        raise SDKStoreError(f"{path}.field missing in prepared item")
    value = item.value
    if value is _MISSING:
        raise SDKStoreError(f"{path}.value is required for {kind}")
    pred = sdk._schema_pred_for_field(field)
    owner_type = pred.get("owner_type")
    field_name = pred.get("py_field_name")
    if not isinstance(owner_type, str) or not owner_type or not isinstance(field_name, str) or not field_name:
        return _legacy_ingest_set_or_add(sdk, item, kind=kind, path=path)
    identity = _identity_dict_for_e_ref(sdk, e_ref, owner_type=owner_type)
    if identity is None:
        return _legacy_ingest_set_or_add(sdk, item, kind=kind, path=path)
    app_value = _app_value_for_ingest(sdk, value, owner_type=owner_type, field_name=field_name)
    if app_value is _APP_FALLBACK:
        return _legacy_ingest_set_or_add(sdk, item, kind=kind, path=path)
    try:
        return _app_ingest_set_or_add(
            sdk,
            item,
            kind=kind,
            identity=identity,
            owner_type=owner_type,
            field_name=field_name,
            value=app_value,
            path=path,
            warnings=warnings,
        )
    except ProtocolShapeError:
        return _legacy_ingest_set_or_add(sdk, item, kind=kind, path=path)


def _legacy_ingest_set_or_add(
    sdk: SDKStore,
    item: _PreparedIngestItem,
    *,
    kind: str,
    path: str,
) -> str:
    database = sdk._database_for_application_write("fg.ingest")
    if database is not None:
        raise SDKStoreError(
            f"{path}: ingest item cannot be represented by the application write protocol",
            code="INGEST_PLAN_FAILED",
            path=path,
        )
    field = item.field
    e_ref = item.e_ref
    if not isinstance(e_ref, str) or not e_ref:
        raise SDKStoreError(f"{path}.e_ref must be non-empty string")
    if item.meta is None:
        raise SDKStoreError(f"{path}.meta missing in prepared item")
    if item.field is None:
        raise SDKStoreError(f"{path}.field missing in prepared item")
    value = item.value
    if value is _MISSING:
        raise SDKStoreError(f"{path}.value is required for {kind}")
    schema_pred = sdk._schema_pred_for_field(field)
    rest_terms = sdk._rest_terms_for_field(schema_pred, value=value)
    if kind == "set":
        return set_field(sdk.store.ledger, schema_pred["pred_id"], e_ref, rest_terms, item.meta)
    return add_field(sdk.store.ledger, schema_pred["pred_id"], e_ref, rest_terms, item.meta)


_MISSING = object()
_APP_FALLBACK = object()


def _identity_dict_for_e_ref(sdk: SDKStore, e_ref: str, *, owner_type: str) -> dict[str, Any] | None:
    if entity_type_from_ref(e_ref) != owner_type:
        return None
    identity = sdk._identity_values_by_e_ref.get(e_ref)
    if not isinstance(identity, dict) or not identity:
        return None
    return dict(identity)


def _app_value_for_ingest(
    sdk: SDKStore,
    value: Any,
    *,
    owner_type: str,
    field_name: str,
) -> Any:
    field_type = field_value_type(sdk._application_schema_index, owner_type, field_name)
    if field_type.value_kind != "entity_ref":
        return value
    if isinstance(value, EntityRef):
        return value
    if not isinstance(value, str):
        return _APP_FALLBACK
    ref_entity_type = entity_type_from_ref(value)
    if ref_entity_type is None:
        return _APP_FALLBACK
    identity = _identity_dict_for_e_ref(sdk, value, owner_type=ref_entity_type)
    if identity is None:
        return _APP_FALLBACK
    return EntityRef(entity_type=ref_entity_type, identity=identity, encoded_ref=value)


def _app_ingest_set_or_add(
    sdk: SDKStore,
    item: _PreparedIngestItem,
    *,
    kind: str,
    identity: dict[str, Any],
    owner_type: str,
    field_name: str,
    value: Any,
    path: str,
    warnings: list[dict[str, Any]],
) -> str:
    if item.meta is None:
        raise SDKStoreError(f"{path}.meta missing in prepared item")
    item_cls = IngestSetItem if kind == "set" else IngestAddItem
    app_item = item_cls(
        target=EntitySelector(entity_type=owner_type, identity=identity),
        field=FieldPath(entity_type=owner_type, field_name=field_name),
        value=value,
        meta=dict(item.meta),
    )
    result = apply_ingest_request(
        IngestRequest(items=(app_item,), collect_mode="stop"),
        store=sdk._store,
        index=sdk._application_schema_index,
        database=sdk._database_for_application_write("fg.ingest"),
    )
    warnings.extend(_app_warnings_to_sdk(result.warnings, fallback_path=path))
    if result.errors:
        raise _sdk_error_from_app_error(result.errors[0], fallback_path=path)
    if not result.written_assertion_ids:
        raise SDKStoreError(
            f"{path}: ingest application write returned no assertion id",
            code="INGEST_PLAN_FAILED",
            path=path,
        )
    return result.written_assertion_ids[-1]


def _app_ingest_retract(
    sdk: SDKStore,
    item: _PreparedIngestItem,
    *,
    path: str,
    warnings: list[dict[str, Any]],
) -> str | None:
    if item.meta is None:
        raise SDKStoreError(f"{path}.meta missing in prepared item")
    if not isinstance(item.asrt_id, str) or not item.asrt_id:
        raise SDKStoreError(f"{path}.asrt_id must be non-empty string for retract")
    result = apply_ingest_request(
        IngestRequest(
            items=(IngestRetractItem(assertion_id=item.asrt_id, meta=dict(item.meta)),),
            collect_mode="stop",
        ),
        store=sdk._store,
        index=sdk._application_schema_index,
        database=sdk._database_for_application_write("fg.ingest"),
    )
    warnings.extend(_app_warnings_to_sdk(result.warnings, fallback_path=path))
    if result.errors:
        raise _sdk_error_from_app_error(result.errors[0], fallback_path=path)
    if result.skipped_indices:
        return None
    return result.written_assertion_ids[0] if result.written_assertion_ids else None


def _sdk_error_from_app_error(error: Any, *, fallback_path: str) -> SDKStoreError:
    return SDKStoreError(
        error.message,
        code=error.code,
        path=_sdk_path_from_app_path(error.path, fallback_path=fallback_path),
    )


def _app_warnings_to_sdk(warnings: tuple[Any, ...], *, fallback_path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for warning in warnings:
        out.append(
            _diag(
                code=warning.code,
                severity="warning",
                path=_sdk_path_from_app_path(warning.path, fallback_path=fallback_path),
                message=warning.message,
                data=dict(warning.details),
            )
        )
    return out


def _sdk_path_from_app_path(path: tuple[str, ...], *, fallback_path: str) -> str:
    if len(path) >= 2 and path[0] == "items" and path[1] == "0":
        rest = path[2:]
        return ".".join((fallback_path, *rest)) if rest else fallback_path
    if path:
        return ".".join((fallback_path, *path))
    return fallback_path


def _prepare_ingest_items(
    sdk: SDKStore,
    data: list[Any] | tuple[Any, ...],
    *,
    base_meta: dict[str, Any],
    allow_sensitive_meta: bool,
    warnings: list[dict[str, Any]],
) -> tuple[list[_PreparedIngestItem], list[dict[str, Any]]]:
    prepared: list[_PreparedIngestItem] = []
    diagnostics: list[dict[str, Any]] = []
    for idx, raw_item in enumerate(data):
        item_path = f"items[{idx}]"
        item_prepared = _prepare_single_ingest_item(
            sdk,
            raw_item,
            item_path=item_path,
            base_meta=base_meta,
            allow_sensitive_meta=allow_sensitive_meta,
            warnings=warnings,
            diagnostics=diagnostics,
        )
        if item_prepared is not None:
            prepared.append(item_prepared)
    return prepared, diagnostics


def _prepare_single_ingest_item(
    sdk: SDKStore,
    raw_item: Any,
    *,
    item_path: str,
    base_meta: dict[str, Any],
    allow_sensitive_meta: bool,
    warnings: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> _PreparedIngestItem | None:
    if not isinstance(raw_item, dict):
        diagnostics.append(
            _diag(
                code="ingest_item_invalid_type",
                severity="error",
                path=item_path,
                message="item must be dict (normalized fact write item)",
            )
        )
        return None

    kind = raw_item.get("kind")
    if not isinstance(kind, str) or not kind:
        diagnostics.append(
            _diag(
                code="ingest_item_kind_invalid",
                severity="error",
                path=f"{item_path}.kind",
                message="kind must be non-empty string",
            )
        )
        return None

    item_meta = _normalize_user_meta_no_raise(raw_item.get("meta"), path=f"{item_path}.meta", diagnostics=diagnostics)
    if item_meta is None:
        return None
    if not allow_sensitive_meta:
        warnings.extend(_sensitive_meta_warnings(item_meta, path=f"{item_path}.meta"))
    effective_meta = {**base_meta, **item_meta}

    if kind in {"set", "add"}:
        field = raw_item.get("field")
        schema_pred = None
        try:
            schema_pred = sdk._schema_pred_for_field(field)
        except Exception as exc:
            diagnostics.append(
                _diag(
                    code="ingest_item_field_invalid",
                    severity="error",
                    path=f"{item_path}.field",
                    message=str(exc),
                )
            )

        e_ref = raw_item.get("e_ref")
        if not isinstance(e_ref, str) or not e_ref:
            diagnostics.append(
                _diag(
                    code="ingest_item_e_ref_invalid",
                    severity="error",
                    path=f"{item_path}.e_ref",
                    message="e_ref must be non-empty string",
                )
            )

        value = raw_item.get("value", _MISSING)
        if value is _MISSING:
            diagnostics.append(
                _diag(
                    code="ingest_item_value_missing",
                    severity="error",
                    path=f"{item_path}.value",
                    message=f"value is required for {kind}",
                )
            )

        if schema_pred is not None and value is not _MISSING:
            cardinality = schema_pred.get("cardinality", "single")
            if kind == "set" and cardinality != "single":
                diagnostics.append(
                    _diag(
                        code="ingest_item_cardinality_mismatch",
                        severity="error",
                        path=f"{item_path}.kind",
                        message=f"field only supports add(...) in ingest: cardinality={cardinality}",
                    )
                )
            if kind == "add" and cardinality != "multi":
                diagnostics.append(
                    _diag(
                        code="ingest_item_cardinality_mismatch",
                        severity="error",
                        path=f"{item_path}.kind",
                        message=f"field only supports set(...) in ingest: cardinality={cardinality}",
                    )
                )
        if schema_pred is not None and value is not _MISSING:
            try:
                sdk._rest_terms_for_field(schema_pred, value=value)
            except Exception as exc:
                diagnostics.append(
                    _diag(
                        code="ingest_item_field_value_invalid",
                        severity="error",
                        path=f"{item_path}.value",
                        message=str(exc),
                    )
                )

        if any(d.get("severity") == "error" and str(d.get("path", "")).startswith(item_path) for d in diagnostics):
            return None

        return _PreparedIngestItem(
            kind=kind,
            field=field,
            e_ref=e_ref,
            value=value,
            meta=effective_meta,
        )

    if kind == "retract":
        asrt_id = raw_item.get("asrt_id")
        if not isinstance(asrt_id, str) or not asrt_id:
            diagnostics.append(
                _diag(
                    code="ingest_item_target_asrt_id_invalid",
                    severity="error",
                    path=f"{item_path}.asrt_id",
                    message="asrt_id must be non-empty string for retract",
                )
            )
            return None
        if sdk.ledger.get_claim(asrt_id) is None:
            diagnostics.append(
                _diag(
                    code="ingest_item_target_asrt_id_unknown",
                    severity="error",
                    path=f"{item_path}.asrt_id",
                    message=f"unknown asrt_id: {asrt_id}",
                )
            )
            return None
        return _PreparedIngestItem(kind=kind, asrt_id=asrt_id, meta=effective_meta)

    diagnostics.append(
        _diag(
            code="ingest_item_kind_unsupported",
            severity="error",
            path=f"{item_path}.kind",
            message=f"unsupported kind: {kind!r} (expected 'set', 'add', or 'retract')",
        )
    )
    return None


def _coerce_provenance_input(obj: Any) -> dict[str, Any]:
    if isinstance(obj, DerivationOutput):
        return {
            "derived_rule_id": obj.derivation_id,
            "derived_rule_version": obj.derivation_version,
            "run_id": obj.run_id,
            "support_digest": obj.support_digest,
            "support_kind": obj.support_kind,
            "confidence_kind": obj.confidence_kind,
        }
    if isinstance(obj, dict):
        return dict(obj)
    raise SDKStoreError(
        "validate_provenance(...) currently supports DerivationOutput "
        "(including the legacy CandidateSet alias) or meta dict input"
    )


def _normalize_user_meta(meta: Any, *, path: str) -> dict[str, Any]:
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise SDKStoreError(f"{path} must be dict when provided")
    out: dict[str, Any] = {}
    for key, value in meta.items():
        if not isinstance(key, str) or not key:
            raise SDKStoreError(f"{path}: meta keys must be non-empty strings")
        if key in HARD_RESERVED_META_KEYS:
            raise SDKStoreError(
                f"{path}[{key!r}] is reserved and system-managed; "
                f"use {EVENT_TIME_META_KEY!r} for source event time"
            )
        out[key] = value
    return out


def _normalize_user_meta_no_raise(
    meta: Any,
    *,
    path: str,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any] | None:
    try:
        return _normalize_user_meta(meta, path=path)
    except SDKStoreError as exc:
        diagnostics.append(
            _diag(
                code="ingest_item_meta_invalid",
                severity="error",
                path=path,
                message=str(exc),
            )
        )
        return None


def _sensitive_meta_warnings(meta: dict[str, Any], *, path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in sorted(meta.keys()):
        if key not in SENSITIVE_SEMANTIC_META_KEYS:
            continue
        out.append(
            _diag(
                code="ingest_sensitive_meta_key_present",
                severity="warning",
                path=f"{path}.{key}",
                message=(
                    f"meta key '{key}' has sensitive semantic meaning in audit/explain; "
                    "prefer validate_provenance() or system-generated provenance where applicable"
                ),
                data={"key": key},
            )
        )
    return out


def _require_non_empty_str(
    data: dict[str, Any],
    key: str,
    *,
    errors: list[dict[str, Any]],
    path: str,
) -> None:
    value = data.get(key)
    if isinstance(value, str) and value:
        return
    errors.append(
        _diag(
            code="provenance_required_field_missing_or_invalid",
            severity="error",
            path=path,
            message=f"{key} must be non-empty string",
            data={"key": key},
        )
    )


def _require_sha256_token(
    data: dict[str, Any],
    key: str,
    *,
    errors: list[dict[str, Any]],
    path: str,
) -> None:
    if _is_sha256_token(data.get(key)):
        return
    errors.append(
        _diag(
            code="provenance_required_digest_missing_or_invalid",
            severity="error",
            path=path,
            message=f"{key} must be 'sha256:<hex>'",
            data={"key": key},
        )
    )


def _is_sha256_token(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if not value.startswith("sha256:"):
        return False
    hex_part = value[7:]
    if len(hex_part) != 64:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in hex_part)


def _diag(
    *,
    code: str,
    severity: str,
    message: str,
    path: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
        "data": {} if data is None else dict(data),
    }
