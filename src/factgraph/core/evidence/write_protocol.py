from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from factgraph.core.protocol.annotation_v1 import (
    SHARED_ANNOTATION_KEYS,
    initial_meta_annotation_v1,
)
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1, claim_args_from_rest_terms
from factgraph.core.schema.meta_policy import (
    EVENT_TIME_META_KEY,
    SYSTEM_MANAGED_META_KEYS,
)
from factgraph.core.store.ledger import (
    _ANNOTATION_COMPAT_PREFIX,
    AnnotationRow,
    Claim,
    ClaimArg,
    Idempotency,
    Ledger,
    MetaRow,
    Revokes,
    _is_reserved_annotation_meta_key,
)


class WriteProtocolError(Exception):
    pass


class PolicyNonDeterminismError(WriteProtocolError):
    pass


_SYSTEM_MANAGED_META_KEYS = SYSTEM_MANAGED_META_KEYS
_CONVENTION_META_KEYS = {
    "source",
    "source_loc",
    "trace_id",
    "raw_kind",
    "bound",
    "approved_by",
    "note",
    EVENT_TIME_META_KEY,
}
_REMOVED_UNCERTAINTY_META_KEYS = {"probability", "bound_lower", "bound_upper", "confidence", "confidence_source"}
_RAW_UNCERTAINTY_KINDS = {"probabilistic", "possibilistic"}
_SENSITIVE_SEMANTIC_META_KEYS = {
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
_KEY_KIND_MAP = {
    "ingested_at": "time",
    "ingest_key": "str",
    "revoked_asrt_id": "str",
    "accepted_at": "time",
    EVENT_TIME_META_KEY: "time",
    "source": "str",
    "source_loc": "str",
    "trace_id": "str",
    "raw_kind": "str",
    "bound": "json",
    "approved_by": "str",
    "accepted_by": "str",
    "note": "str",
    "derived_rule_id": "str",
    "derived_rule_version": "str",
    "derivation_id": "str",
    "derivation_version": "str",
    "run_id": "str",
    "support_digest": "str",
    "support_kind": "str",
    "confidence_kind": "str",
    "candidate_id": "str",
    "candidate_key": "str",
    "candidate_kind": "str",
    "key_tuple_digest": "str",
    "cand_key_digest": "str",
    "schema_digest": "str",
    "policy_digest": "str",
    "meta_origin": "str",
    "entity_type": "str",
    "entity_ref": "str",
    "identity_override_digest": "str",
    "subject_e_ref": "str",
    "materialize_id": "str",
}
_required_kind_keys = _CONVENTION_META_KEYS | _SENSITIVE_SEMANTIC_META_KEYS
_missing_kind_map_keys = sorted(_required_kind_keys - set(_KEY_KIND_MAP.keys()))
if _missing_kind_map_keys:
    raise RuntimeError(f"_KEY_KIND_MAP is missing required keys: {', '.join(_missing_kind_map_keys)}")

_SHARED_ANNOTATION_WHITELIST = SHARED_ANNOTATION_KEYS

__all__ = [
    "WriteProtocolError",
    "PolicyNonDeterminismError",
    "_SYSTEM_MANAGED_META_KEYS",
    "new_assertion_id",
    "now_epoch_nanos",
    "set_field",
    "add_field",
    "retract_by_asrt",
    "replace_field",
]


def new_assertion_id() -> str:
    return uuid4().hex


def now_epoch_nanos() -> int:
    return time.time_ns()


def set_field(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],
    meta: dict[str, Any] | None = None,
) -> str:
    _validate_write_inputs(ledger, pred_id, e_ref, rest_terms)
    normalized_meta = _normalize_meta(meta)
    ingest_key = _compute_ingest_key(pred_id, e_ref, rest_terms, normalized_meta)

    asrt_id = new_assertion_id()
    ingested_at = now_epoch_nanos()
    claim = Claim(asrt_id=asrt_id, pred_id=pred_id, e_ref=e_ref, rest_terms=list(rest_terms))
    claim_arg_rows = claim_args_from_rest_terms(rest_terms)
    args = [
        ClaimArg(asrt_id=asrt_id, idx=idx, val_atom=val_atom, tag=tag)
        for idx, val_atom, tag in claim_arg_rows
    ]
    meta_rows = _meta_rows_for_claim(asrt_id, normalized_meta, ingest_key, ingested_at)
    annotation_rows = _annotation_rows_for_claim(asrt_id, normalized_meta)
    result = ledger.append_assertion(
        claim=claim,
        claim_args=args,
        meta_rows=meta_rows,
        annotation_rows=annotation_rows,
        idempotency=Idempotency(ingest_key=ingest_key, on_conflict="skip"),
        asrt_id=asrt_id,
    )
    return result.asrt_id


def add_field(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],
    meta: dict[str, Any] | None = None,
) -> str:
    return set_field(ledger, pred_id, e_ref, rest_terms, meta)


def retract_by_asrt(
    ledger: Ledger,
    revoked_asrt_id: str,
    meta: dict[str, Any] | None = None,
) -> str | None:
    if not isinstance(ledger, Ledger):
        raise WriteProtocolError("ledger must be Ledger")
    if not isinstance(revoked_asrt_id, str) or not revoked_asrt_id:
        raise WriteProtocolError("revoked_asrt_id must be non-empty string")
    target = ledger._get_claim_including_system(revoked_asrt_id)
    if target is None:
        raise WriteProtocolError(f"unknown revoked_asrt_id: {revoked_asrt_id}")
    if target.pred_id.startswith("__system__."):
        raise WriteProtocolError(
            f"INV-12 part 2: target {revoked_asrt_id!r} is a system claim "
            f"(pred_id={target.pred_id!r}); revoke-of-revoke is forbidden. "
            "See ADR-SYS-B §4.1.5."
        )

    existing_revoker = ledger.find_revoker(revoked_asrt_id)
    if existing_revoker is not None:
        return existing_revoker

    normalized_meta = _normalize_meta(meta)
    revoker_asrt_id = new_assertion_id()
    ingested_at = now_epoch_nanos()
    meta_rows = [
        MetaRow(asrt_id=revoker_asrt_id, key="ingested_at", kind="time", value=ingested_at),
        MetaRow(
            asrt_id=revoker_asrt_id,
            key="revoked_asrt_id",
            kind="str",
            value=revoked_asrt_id,
        ),
    ]
    meta_rows.extend(_user_meta_rows(revoker_asrt_id, normalized_meta))
    ledger.append_revocation(
        revokes=Revokes(revoker_asrt_id=revoker_asrt_id, revoked_asrt_id=revoked_asrt_id),
        meta_rows=meta_rows,
        idempotency=None,
        revoker_asrt_id=revoker_asrt_id,
    )
    return revoker_asrt_id


def replace_field(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    old_rest_terms: list[tuple[str, Any]],
    new_rest_terms: list[tuple[str, Any]],
    meta: dict[str, Any] | None = None,
) -> tuple[str | None, str]:
    _validate_write_inputs(ledger, pred_id, e_ref, old_rest_terms)
    _preflight_new_assertion(ledger, pred_id, e_ref, new_rest_terms, meta)

    old_asrt_id = _find_active_matching_claim(ledger, pred_id, e_ref, old_rest_terms)
    if old_asrt_id is None:
        raise WriteProtocolError("replace_field requires an active old assertion")

    revoker_asrt_id = retract_by_asrt(ledger, old_asrt_id, meta)
    new_asrt_id = set_field(ledger, pred_id, e_ref, new_rest_terms, meta)
    return revoker_asrt_id, new_asrt_id


def _validate_write_inputs(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],
) -> None:
    if not isinstance(ledger, Ledger):
        raise WriteProtocolError("ledger must be Ledger")
    if not isinstance(pred_id, str) or not pred_id:
        raise WriteProtocolError("pred_id must be non-empty string")
    if pred_id.startswith("__system__."):
        raise WriteProtocolError(
            "general field writes cannot use the reserved '__system__.' namespace; "
            "use retract_by_asrt for revocations"
        )
    if not isinstance(e_ref, str) or not e_ref:
        raise WriteProtocolError("e_ref must be non-empty string")
    if not isinstance(rest_terms, list):
        raise WriteProtocolError("rest_terms must be list")

    try:
        canonical_bytes_tup_v1(rest_terms)
    except ValueError as exc:
        raise WriteProtocolError(str(exc)) from exc


def _normalize_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise WriteProtocolError("meta must be dict")
    for key in meta:
        if not isinstance(key, str) or not key:
            raise WriteProtocolError("meta keys must be non-empty strings")
        if _is_reserved_annotation_meta_key(key):
            raise WriteProtocolError(
                "meta key uses the reserved annotation storage namespace: "
                f"{_ANNOTATION_COMPAT_PREFIX}"
            )
        if key in _SYSTEM_MANAGED_META_KEYS:
            raise WriteProtocolError(
                f"meta[{key}] is reserved and system-managed; "
                f"use meta[{EVENT_TIME_META_KEY}] for source event time"
            )
    result = dict(meta)
    _validate_no_removed_uncertainty_keys(result)
    _normalize_raw_uncertainty_meta(result)
    return result


def _validate_no_removed_uncertainty_keys(meta: dict[str, Any]) -> None:
    for key in sorted(_REMOVED_UNCERTAINTY_META_KEYS):
        if key in meta:
            if key in {"confidence", "confidence_source"}:
                raise WriteProtocolError(
                    f"meta[{key}] was removed. Use raw_kind / bound for uncertainty inputs."
                )
            raise WriteProtocolError(
                f"meta[{key}] is not accepted as user-authored raw uncertainty; "
                "use meta[raw_kind] and meta[bound]"
            )


def _normalize_raw_uncertainty_meta(meta: dict[str, Any]) -> None:
    has_raw_kind = "raw_kind" in meta
    has_bound = "bound" in meta
    if has_raw_kind != has_bound:
        raise WriteProtocolError("meta[raw_kind] and meta[bound] must be provided together")
    if not has_raw_kind:
        return

    raw_kind = meta["raw_kind"]
    if not isinstance(raw_kind, str) or raw_kind not in _RAW_UNCERTAINTY_KINDS:
        allowed = ", ".join(sorted(_RAW_UNCERTAINTY_KINDS))
        raise WriteProtocolError(f"meta[raw_kind] must be one of: {allowed}")

    meta["bound"] = _normalize_uncertainty_bound(meta["bound"])


def _normalize_uncertainty_bound(value: Any) -> list[float]:
    if not isinstance(value, list):
        raise WriteProtocolError("meta[bound] must be a two-element JSON list")
    if len(value) != 2:
        raise WriteProtocolError("meta[bound] must be a two-element JSON list")

    lower_raw, upper_raw = value
    if isinstance(lower_raw, bool) or isinstance(upper_raw, bool):
        raise WriteProtocolError("meta[bound] values must be numeric and not bool")
    if not isinstance(lower_raw, (int, float)) or not isinstance(upper_raw, (int, float)):
        raise WriteProtocolError("meta[bound] values must be numeric")

    lower = float(lower_raw)
    upper = float(upper_raw)
    if lower < 0.0 or upper > 1.0:
        raise WriteProtocolError("meta[bound] values must be within [0,1]")
    if lower > upper:
        raise WriteProtocolError("meta[bound] lower must be <= upper")
    return [lower, upper]


def _compute_ingest_key(
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],
    meta: dict[str, Any],
) -> str:
    source_idempotency_material = {
        "source": meta.get("source"),
        "source_loc": meta.get("source_loc"),
        "trace_id": meta.get("trace_id"),
    }
    for key, value in source_idempotency_material.items():
        if value is not None and not isinstance(value, str):
            raise WriteProtocolError(f"meta[{key}] must be string when provided")

    temporal_idempotency_material = {
        "valid_from": meta.get("valid_from"),
        "valid_to": meta.get("valid_to"),
        "version": meta.get("version"),
    }
    valid_from = temporal_idempotency_material["valid_from"]
    valid_to = temporal_idempotency_material["valid_to"]
    version = temporal_idempotency_material["version"]
    if valid_from is not None and not isinstance(valid_from, str):
        raise WriteProtocolError("meta[valid_from] must be string when provided")
    if valid_to is not None and not isinstance(valid_to, str):
        raise WriteProtocolError("meta[valid_to] must be string when provided")
    if version is not None and (isinstance(version, bool) or not isinstance(version, (str, int))):
        raise WriteProtocolError("meta[version] must be string or int when provided")

    source_material_bytes = json.dumps(
        source_idempotency_material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    temporal_material_bytes = json.dumps(
        temporal_idempotency_material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    ingest_terms = [
        ("string", "ingest_key_v2"),
        ("string", pred_id),
        ("entity_ref", e_ref),
        *rest_terms,
        ("bytes", source_material_bytes),
        ("bytes", temporal_material_bytes),
    ]
    ingest_bytes = canonical_bytes_tup_v1(ingest_terms)
    return sha256_token(ingest_bytes)


def _find_active_claim_by_ingest_key(ledger: Ledger, ingest_key: str) -> str | None:
    for row in ledger.effective_meta_rows(key="ingest_key", kind="str"):
        if row.value != ingest_key:
            continue
        if ledger.has_active_revocation(row.asrt_id):
            continue
        if ledger.get_claim(row.asrt_id) is None:
            continue
        return row.asrt_id
    return None


def _meta_rows_for_claim(
    asrt_id: str,
    meta: dict[str, Any],
    ingest_key: str,
    ingested_at: int,
) -> list[MetaRow]:
    rows = [
        MetaRow(asrt_id=asrt_id, key="ingested_at", kind="time", value=ingested_at),
        MetaRow(asrt_id=asrt_id, key="ingest_key", kind="str", value=ingest_key),
    ]
    rows.extend(_user_meta_rows(asrt_id, meta))
    return rows


def _annotation_rows_for_claim(
    asrt_id: str,
    meta: dict[str, Any],
) -> list[AnnotationRow]:
    """Project whitelisted shared meta keys into canonical annotation rows."""
    rows: list[AnnotationRow] = []
    for key in sorted(meta.keys()):
        projection = initial_meta_annotation_v1(key)
        if projection is None:
            continue
        value = meta[key]
        kind = _KEY_KIND_MAP.get(key)
        if kind is None:
            kind = _infer_meta_kind_by_value(key, value)
        rows.append(
            AnnotationRow(
                asrt_id=asrt_id,
                namespace=projection.namespace,
                category=projection.category,
                key=key,
                kind=kind,
                value=value,
                origin=projection.origin,
                derivation=projection.derivation,
            )
        )
    return rows


def _user_meta_rows(asrt_id: str, meta: dict[str, Any]) -> list[MetaRow]:
    rows: list[MetaRow] = []
    for key in sorted(meta.keys()):
        if key in _SYSTEM_MANAGED_META_KEYS:
            continue
        value = meta[key]
        kind = _infer_meta_kind(key, value)
        rows.append(MetaRow(asrt_id=asrt_id, key=key, kind=kind, value=value))
    return rows


def _infer_meta_kind(key: str, value: Any) -> str:
    mapped_kind = _KEY_KIND_MAP.get(key)
    if mapped_kind is not None:
        _validate_meta_value_for_kind(key, mapped_kind, value)
        return mapped_kind
    return _infer_meta_kind_by_value(key, value)


def _infer_meta_kind_by_value(key: str, value: Any) -> str:
    if key in {"ingested_at", EVENT_TIME_META_KEY}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise WriteProtocolError(f"{key} must be epoch-nanos int")
        return "time"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "str"
    if isinstance(value, float):
        return "float"
    if isinstance(value, int):
        return "int"
    raise WriteProtocolError(f"unsupported meta type for {key}: {type(value).__name__}")


def _validate_meta_value_for_kind(key: str, kind: str, value: Any) -> None:
    if kind == "str":
        if not isinstance(value, str):
            raise WriteProtocolError(f"meta[{key}] must be str")
        return
    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise WriteProtocolError(f"meta[{key}] must be int")
        return
    if kind == "float":
        if isinstance(value, bool) or not isinstance(value, float):
            raise WriteProtocolError(f"meta[{key}] must be float")
        return
    if kind == "bool":
        if not isinstance(value, bool):
            raise WriteProtocolError(f"meta[{key}] must be bool")
        return
    if kind == "time":
        if isinstance(value, bool) or not isinstance(value, int):
            raise WriteProtocolError(f"meta[{key}] must be epoch-nanos int")
        return
    if kind == "json":
        try:
            json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except Exception as exc:  # pragma: no cover - defensive
            raise WriteProtocolError(f"meta[{key}] must be JSON-serializable") from exc
        return
    raise WriteProtocolError(f"unsupported mapped meta kind for {key}: {kind}")


def _preflight_new_assertion(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],
    meta: dict[str, Any] | None,
) -> None:
    """Dry-run set_field validation. Raises before any DB writes."""
    _validate_write_inputs(ledger, pred_id, e_ref, rest_terms)
    meta_dict = _normalize_meta(meta)
    ingest_key = _compute_ingest_key(pred_id, e_ref, rest_terms, meta_dict)
    _meta_rows_for_claim("_preflight_", meta_dict, ingest_key, 0)
    _annotation_rows_for_claim("_preflight_", meta_dict)


def _find_active_matching_claim(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],
) -> str | None:
    for claim in ledger.find_claims(pred_id=pred_id, e_ref=e_ref):
        if claim.rest_terms != rest_terms:
            continue
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        return claim.asrt_id
    return None
