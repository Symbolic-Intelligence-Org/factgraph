from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from factpy_kernel.core.evidence.write_protocol import add_field, set_field
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.ecss.vcd import (
    ECSS_COMPLIANCE_STATUS_PRED_ID,
    ECSS_REQUIREMENT_PRED_ID,
    ECSS_REQUIREMENT_RID_PRED_ID,
    ECSS_REVIEW_MILESTONE_PRED_ID,
    ECSS_VCD_PRED_IDS,
    ECSS_VERIFICATION_METHOD_PRED_ID,
    ecss_vcd_predicates,
    extend_schema_ir_with_ecss_vcd_predicates,
)

from .errors import SDKStoreError
from .store import SDKStore


def apply_ecss_vcd_schema(schema_ir: dict[str, Any]) -> dict[str, Any]:
    return extend_schema_ir_with_ecss_vcd_predicates(schema_ir)


def make_ecss_requirement_ref(req_id: str) -> str:
    _require_non_empty_string(req_id, name="req_id")
    return encode_idref_v1("ECSSRequirement", [("req_id", "string", req_id)])


def write_ecss_requirement_bundle(
    sdk: SDKStore,
    *,
    req_id: str,
    title: str,
    standard_ref: str | None = None,
    status: str | None = None,
    verification_methods: Sequence[str] = (),
    rid_links: Sequence[str] = (),
    review_milestone: str | None = None,
    requirement_ref: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(sdk, SDKStore):
        raise SDKStoreError("sdk must be SDKStore")
    if meta is not None and not isinstance(meta, dict):
        raise SDKStoreError("meta must be dict when provided")

    _ensure_ecss_vcd_schema_present(sdk)

    _require_non_empty_string(req_id, name="req_id")
    _require_non_empty_string(title, name="title")
    if requirement_ref is None:
        requirement_ref = make_ecss_requirement_ref(req_id)
    elif not isinstance(requirement_ref, str) or not requirement_ref:
        raise SDKStoreError("requirement_ref must be non-empty string when provided")

    verification_method_list = _normalize_string_sequence(verification_methods, name="verification_methods")
    rid_link_list = _normalize_string_sequence(rid_links, name="rid_links")
    if status is not None:
        _require_non_empty_string(status, name="status")
    if review_milestone is not None:
        _require_non_empty_string(review_milestone, name="review_milestone")
    if standard_ref is not None and not isinstance(standard_ref, str):
        raise SDKStoreError("standard_ref must be string when provided")

    ledger = sdk.store.ledger
    requirement_asrt_id = set_field(
        ledger,
        ECSS_REQUIREMENT_PRED_ID,
        requirement_ref,
        [
            ("string", req_id),
            ("string", title),
            ("string", standard_ref or ""),
        ],
        meta,
    )

    status_asrt_id: str | None = None
    if status is not None:
        status_asrt_id = set_field(
            ledger,
            ECSS_COMPLIANCE_STATUS_PRED_ID,
            requirement_ref,
            [("string", status)],
            meta,
        )

    review_milestone_asrt_id: str | None = None
    if review_milestone is not None:
        review_milestone_asrt_id = set_field(
            ledger,
            ECSS_REVIEW_MILESTONE_PRED_ID,
            requirement_ref,
            [("string", review_milestone)],
            meta,
        )

    verification_method_asrt_ids = [
        add_field(
            ledger,
            ECSS_VERIFICATION_METHOD_PRED_ID,
            requirement_ref,
            [("string", method)],
            meta,
        )
        for method in verification_method_list
    ]
    rid_asrt_ids = [
        add_field(
            ledger,
            ECSS_REQUIREMENT_RID_PRED_ID,
            requirement_ref,
            [("string", rid_id)],
            meta,
        )
        for rid_id in rid_link_list
    ]

    return {
        "requirement_ref": requirement_ref,
        "requirement_asrt_id": requirement_asrt_id,
        "status_asrt_id": status_asrt_id,
        "review_milestone_asrt_id": review_milestone_asrt_id,
        "verification_method_asrt_ids": verification_method_asrt_ids,
        "rid_asrt_ids": rid_asrt_ids,
    }


def _ensure_ecss_vcd_schema_present(sdk: SDKStore) -> None:
    pred_ids = {
        pred.get("pred_id")
        for pred in sdk.schema_ir.get("predicates", [])
        if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str)
    }
    missing = [pred_id for pred_id in ECSS_VCD_PRED_IDS if pred_id not in pred_ids]
    if missing:
        raise SDKStoreError(
            "ECSS VCD predicates are not present in schema_ir; "
            "apply factpy_kernel.sdk.ecss.apply_ecss_vcd_schema(...) first"
        )


def _require_non_empty_string(value: Any, *, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise SDKStoreError(f"{name} must be non-empty string")


def _normalize_string_sequence(values: Sequence[str], *, name: str) -> list[str]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise SDKStoreError(f"{name} must be sequence[str]")
    out: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value:
            raise SDKStoreError(f"{name}[{index}] must be non-empty string")
        out.append(value)
    return out


__all__ = [
    "ECSS_REQUIREMENT_PRED_ID",
    "ECSS_VERIFICATION_METHOD_PRED_ID",
    "ECSS_COMPLIANCE_STATUS_PRED_ID",
    "ECSS_REQUIREMENT_RID_PRED_ID",
    "ECSS_REVIEW_MILESTONE_PRED_ID",
    "ECSS_VCD_PRED_IDS",
    "ecss_vcd_predicates",
    "extend_schema_ir_with_ecss_vcd_predicates",
    "apply_ecss_vcd_schema",
    "make_ecss_requirement_ref",
    "write_ecss_requirement_bundle",
]
