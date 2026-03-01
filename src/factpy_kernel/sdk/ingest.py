from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from factpy_kernel.core.derivation.candidates import CandidateSet

from .errors import SDKStoreError

if TYPE_CHECKING:
    from .store import SDKStore


HARD_RESERVED_META_KEYS: frozenset[str] = frozenset({"ingested_at", "ingest_key", "revoked_asrt_id"})
# Proposed future reserved key (spec-level, not enforced by write_protocol yet).
SUGGESTED_HARD_RESERVED_META_KEYS: frozenset[str] = frozenset({"meta_origin"})

SENSITIVE_SEMANTIC_META_KEYS: frozenset[str] = frozenset(
    {
        "derived_rule_id",
        "derived_rule_version",
        "run_id",
        "support_digest",
        "support_kind",
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
# - {"kind": "set", "field": <sdk.Field>, "e_ref": str, "value": Any, "dims"?: dict|list|tuple, "meta"?: dict}
# - {"kind": "add", "field": <sdk.Field>, "e_ref": str, "value": Any, "dims"?: dict|list|tuple, "meta"?: dict}
# - {"kind": "retract", "asrt_id": str, "meta"?: dict}
# Notes:
# - top-level ingest(meta=...) is merged with item meta (item keys override)
# - "retract" targets a claim assertion id via item["asrt_id"]; users must not set reserved meta key "revoked_asrt_id"


@dataclass(frozen=True)
class IngestResult:
    written_assertion_ids: list[str]
    skipped_count: int
    duplicate_count: int
    warnings: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    diagnostics_contract_version: int = 1


@dataclass(frozen=True)
class ValidationReport:
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
    dims: Any = None
    asrt_id: str | None = None
    meta: dict[str, Any] | None = None


def sdk_validate_provenance(
    sdk: "SDKStore",
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
    sdk: "SDKStore",
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
            asrt_id = _ingest_set_or_add_prepared(sdk, prepared, kind="set", path=path)
            is_duplicate = asrt_id in existing_claim_ids
            if is_duplicate:
                duplicate_count += 1
                skipped_count += 1
            else:
                existing_claim_ids.add(asrt_id)
                written_assertion_ids.append(asrt_id)
            continue

        if prepared.kind == "add":
            asrt_id = _ingest_set_or_add_prepared(sdk, prepared, kind="add", path=path)
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
            revoker_id = sdk.retract(prepared.asrt_id, meta=prepared.meta)
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
    sdk: "SDKStore",
    item: _PreparedIngestItem,
    *,
    kind: str,
    path: str,
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
    dims = item.dims
    if kind == "set":
        return sdk.set(field, e_ref, value, dims=dims, meta=item.meta)
    return sdk.add(field, e_ref, value, dims=dims, meta=item.meta)


_MISSING = object()


def _prepare_ingest_items(
    sdk: "SDKStore",
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
    sdk: "SDKStore",
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

        dims = raw_item.get("dims")
        if schema_pred is not None and value is not _MISSING:
            cardinality = schema_pred.get("cardinality", "functional")
            if kind == "set" and cardinality != "functional":
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
                sdk._rest_terms_for_field(schema_pred, dims=dims, value=value)
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
            dims=dims,
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
    if isinstance(obj, CandidateSet):
        return {
            "derived_rule_id": obj.derivation_id,
            "derived_rule_version": obj.derivation_version,
            "run_id": obj.run_id,
            "support_digest": obj.support_digest,
            "support_kind": obj.support_kind,
        }
    if isinstance(obj, dict):
        return dict(obj)
    raise SDKStoreError(
        "validate_provenance(...) currently supports CandidateSet or meta dict input"
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
            raise SDKStoreError(f"{path}[{key!r}] is reserved and system-managed")
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
