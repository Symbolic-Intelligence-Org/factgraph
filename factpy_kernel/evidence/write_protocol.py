from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from factpy_kernel.protocol.digests import sha256_token
from factpy_kernel.protocol.tup_v1 import canonical_bytes_tup_v1, claim_args_from_rest_terms
from factpy_kernel.store.ledger import Claim, ClaimArg, Ledger, MetaRow, Revokes


class WriteProtocolError(Exception):
    pass


class PolicyNonDeterminismError(WriteProtocolError):
    pass


_SYSTEM_MANAGED_META_KEYS = {"ingested_at", "ingest_key", "revoked_asrt_id"}


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

    existing_asrt_id = _find_active_claim_by_ingest_key(ledger, ingest_key)
    if existing_asrt_id is not None:
        return existing_asrt_id

    asrt_id = new_assertion_id()
    ledger.append_claim(Claim(asrt_id=asrt_id, pred_id=pred_id, e_ref=e_ref, rest_terms=list(rest_terms)))

    claim_arg_rows = claim_args_from_rest_terms(rest_terms)
    ledger.append_claim_args(
        [
            ClaimArg(asrt_id=asrt_id, idx=idx, val_atom=val_atom, tag=tag)
            for idx, val_atom, tag in claim_arg_rows
        ]
    )

    ingested_at = now_epoch_nanos()
    ledger.append_meta(_meta_rows_for_claim(asrt_id, normalized_meta, ingest_key, ingested_at))
    return asrt_id


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
    if ledger.get_claim(revoked_asrt_id) is None:
        raise WriteProtocolError(f"unknown revoked_asrt_id: {revoked_asrt_id}")

    existing_revoker = ledger.find_revoker(revoked_asrt_id)
    if existing_revoker is not None:
        return existing_revoker

    normalized_meta = _normalize_meta(meta)
    revoker_asrt_id = new_assertion_id()
    ledger.append_revokes(
        Revokes(revoker_asrt_id=revoker_asrt_id, revoked_asrt_id=revoked_asrt_id)
    )

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
    ledger.append_meta(meta_rows)
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
    _validate_write_inputs(ledger, pred_id, e_ref, new_rest_terms)

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
        if key in _SYSTEM_MANAGED_META_KEYS:
            raise WriteProtocolError(f"meta[{key}] is reserved and system-managed")
    return dict(meta)


def _compute_ingest_key(
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],
    meta: dict[str, Any],
) -> str:
    source_material = {
        "source": meta.get("source"),
        "source_loc": meta.get("source_loc"),
        "trace_id": meta.get("trace_id"),
    }
    for key, value in source_material.items():
        if value is not None and not isinstance(value, str):
            raise WriteProtocolError(f"meta[{key}] must be string when provided")

    source_material_bytes = json.dumps(
        source_material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    ingest_terms = [
        ("string", pred_id),
        ("entity_ref", e_ref),
        *rest_terms,
        ("bytes", source_material_bytes),
    ]
    ingest_bytes = canonical_bytes_tup_v1(ingest_terms)
    return sha256_token(ingest_bytes)


def _find_active_claim_by_ingest_key(ledger: Ledger, ingest_key: str) -> str | None:
    for row in ledger.find_meta(key="ingest_key", kind="str"):
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
    if key == "ingested_at":
        if isinstance(value, bool) or not isinstance(value, int):
            raise WriteProtocolError("ingested_at must be epoch-nanos int")
        return "time"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "str"
    if isinstance(value, int):
        return "num"
    raise WriteProtocolError(f"unsupported meta type for {key}: {type(value).__name__}")


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
