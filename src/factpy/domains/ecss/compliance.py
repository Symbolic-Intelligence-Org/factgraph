from __future__ import annotations

from typing import Any

from factpy.domains.ecss.vcd import (
    ECSS_COMPLIANCE_STATUS_PRED_ID,
    ECSS_REQUIREMENT_PRED_ID,
    ECSS_REQUIREMENT_RID_PRED_ID,
    ECSS_REVIEW_MILESTONE_PRED_ID,
    ECSS_VCD_PRED_IDS,
    ECSS_VERIFICATION_METHOD_PRED_ID,
    ecss_vcd_predicates,
    extend_schema_ir_with_ecss_vcd_predicates,
)

from factpy.audit.assertions import AuditAssertionIndex


class AuditComplianceError(Exception):
    pass


def build_compliance_matrix_rows(assertion_index: AuditAssertionIndex) -> list[dict[str, Any]]:
    if not isinstance(assertion_index, AuditAssertionIndex):
        raise AuditComplianceError("assertion_index must be AuditAssertionIndex")

    rows_by_requirement_ref: dict[str, dict[str, Any]] = {}
    for asrt_id, claim in assertion_index.claims.items():
        pred_id = claim.get("pred_id")
        if pred_id not in ECSS_VCD_PRED_IDS:
            continue
        if _is_revoked(assertion_index, asrt_id):
            continue

        requirement_ref = claim.get("e_ref")
        if not isinstance(requirement_ref, str) or not requirement_ref:
            raise AuditComplianceError(f"requirement claim missing e_ref for asrt_id={asrt_id}")
        row = rows_by_requirement_ref.setdefault(requirement_ref, _empty_row(requirement_ref))
        values = _claim_arg_values(assertion_index, asrt_id)
        ingested_at = _read_required_ingested_at(assertion_index, asrt_id)

        if pred_id == ECSS_REQUIREMENT_PRED_ID:
            req_id, title, standard_ref = _parse_requirement_values(values, asrt_id=asrt_id)
            _maybe_replace_single_pick(
                row,
                key="_requirement_pick",
                candidate={
                    "asrt_id": asrt_id,
                    "ingested_at": ingested_at,
                    "req_id": req_id,
                    "title": title,
                    "standard_ref": standard_ref,
                },
            )
            continue

        if pred_id == ECSS_COMPLIANCE_STATUS_PRED_ID:
            status = _parse_single_string_value(values, asrt_id=asrt_id, pred_id=pred_id)
            _maybe_replace_single_pick(
                row,
                key="_status_pick",
                candidate={
                    "asrt_id": asrt_id,
                    "ingested_at": ingested_at,
                    "status": status,
                },
            )
            continue

        if pred_id == ECSS_REVIEW_MILESTONE_PRED_ID:
            milestone = _parse_single_string_value(values, asrt_id=asrt_id, pred_id=pred_id)
            _maybe_replace_single_pick(
                row,
                key="_milestone_pick",
                candidate={
                    "asrt_id": asrt_id,
                    "ingested_at": ingested_at,
                    "milestone": milestone,
                },
            )
            continue

        if pred_id == ECSS_VERIFICATION_METHOD_PRED_ID:
            method = _parse_single_string_value(values, asrt_id=asrt_id, pred_id=pred_id)
            row["_verification_methods"].setdefault(method, set()).add(asrt_id)
            continue

        if pred_id == ECSS_REQUIREMENT_RID_PRED_ID:
            rid_id = _parse_single_string_value(values, asrt_id=asrt_id, pred_id=pred_id)
            row["_rid_links"].setdefault(rid_id, set()).add(asrt_id)
            continue

    output: list[dict[str, Any]] = []
    for requirement_ref in sorted(rows_by_requirement_ref):
        row = rows_by_requirement_ref[requirement_ref]
        requirement_pick = row["_requirement_pick"]
        status_pick = row["_status_pick"]
        milestone_pick = row["_milestone_pick"]
        req_id = requirement_pick["req_id"] if requirement_pick is not None else requirement_ref
        output.append(
            {
                "req_id": req_id,
                "requirement_ref": requirement_ref,
                "title": requirement_pick["title"] if requirement_pick is not None else None,
                "standard_ref": requirement_pick["standard_ref"] if requirement_pick is not None else None,
                "requirement_asrt_id": requirement_pick["asrt_id"] if requirement_pick is not None else None,
                "status": status_pick["status"] if status_pick is not None else None,
                "status_asrt_id": status_pick["asrt_id"] if status_pick is not None else None,
                "review_milestone": milestone_pick["milestone"] if milestone_pick is not None else None,
                "review_milestone_asrt_id": milestone_pick["asrt_id"] if milestone_pick is not None else None,
                "verification_methods": [
                    {"method": method, "asrt_ids": sorted(asrt_ids)}
                    for method, asrt_ids in sorted(row["_verification_methods"].items())
                ],
                "rid_links": [
                    {"rid_id": rid_id, "asrt_ids": sorted(asrt_ids)}
                    for rid_id, asrt_ids in sorted(row["_rid_links"].items())
                ],
            }
        )

    output.sort(key=lambda item: str(item.get("req_id") or ""))
    return output


def _empty_row(requirement_ref: str) -> dict[str, Any]:
    return {
        "requirement_ref": requirement_ref,
        "_requirement_pick": None,
        "_status_pick": None,
        "_milestone_pick": None,
        "_verification_methods": {},
        "_rid_links": {},
    }


def _is_revoked(assertion_index: AuditAssertionIndex, asrt_id: str) -> bool:
    return bool(assertion_index.revoked_by.get(asrt_id))


def _claim_arg_values(assertion_index: AuditAssertionIndex, asrt_id: str) -> list[Any]:
    rows = assertion_index.claim_args.get(asrt_id, [])
    if not rows:
        return []
    values: list[Any] = []
    for expected_idx, row in enumerate(rows):
        idx = row.get("idx")
        if idx != expected_idx:
            raise AuditComplianceError(f"claim_arg idx must be contiguous for asrt_id={asrt_id}")
        values.append(row.get("val"))
    return values


def _read_required_ingested_at(assertion_index: AuditAssertionIndex, asrt_id: str) -> int:
    rows = [
        row
        for row in assertion_index.meta.get(asrt_id, {}).get("time", [])
        if row.get("key") == "ingested_at"
    ]
    if len(rows) != 1:
        raise AuditComplianceError(f"asrt_id={asrt_id} must have exactly one ingested_at meta row")
    value = rows[0].get("value")
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuditComplianceError(f"asrt_id={asrt_id} ingested_at must be int")
    return value


def _parse_requirement_values(values: list[Any], *, asrt_id: str) -> tuple[str, str, str | None]:
    if len(values) not in {2, 3}:
        raise AuditComplianceError(
            f"{ECSS_REQUIREMENT_PRED_ID} expects 2 or 3 args for asrt_id={asrt_id}; got {len(values)}"
        )
    req_id = values[0]
    title = values[1]
    if not isinstance(req_id, str) or not req_id:
        raise AuditComplianceError(f"{ECSS_REQUIREMENT_PRED_ID} req_id must be non-empty string")
    if not isinstance(title, str) or not title:
        raise AuditComplianceError(f"{ECSS_REQUIREMENT_PRED_ID} title must be non-empty string")
    if len(values) == 2:
        return req_id, title, None
    standard_ref = values[2]
    if not isinstance(standard_ref, str):
        raise AuditComplianceError(f"{ECSS_REQUIREMENT_PRED_ID} standard_ref must be string")
    return req_id, title, standard_ref or None


def _parse_single_string_value(values: list[Any], *, asrt_id: str, pred_id: str) -> str:
    if len(values) != 1:
        raise AuditComplianceError(f"{pred_id} expects exactly 1 arg for asrt_id={asrt_id}; got {len(values)}")
    value = values[0]
    if not isinstance(value, str) or not value:
        raise AuditComplianceError(f"{pred_id} value must be non-empty string for asrt_id={asrt_id}")
    return value


def _maybe_replace_single_pick(row: dict[str, Any], *, key: str, candidate: dict[str, Any]) -> None:
    current = row.get(key)
    if not isinstance(current, dict):
        row[key] = candidate
        return
    current_ingested_at = current["ingested_at"]
    candidate_ingested_at = candidate["ingested_at"]
    if candidate_ingested_at > current_ingested_at:
        row[key] = candidate
        return
    if candidate_ingested_at == current_ingested_at and candidate["asrt_id"] < current["asrt_id"]:
        row[key] = candidate


__all__ = [
    "AuditComplianceError",
    "ECSS_REQUIREMENT_PRED_ID",
    "ECSS_VERIFICATION_METHOD_PRED_ID",
    "ECSS_COMPLIANCE_STATUS_PRED_ID",
    "ECSS_REQUIREMENT_RID_PRED_ID",
    "ECSS_REVIEW_MILESTONE_PRED_ID",
    "ECSS_VCD_PRED_IDS",
    "ecss_vcd_predicates",
    "extend_schema_ir_with_ecss_vcd_predicates",
    "build_compliance_matrix_rows",
]
