from __future__ import annotations

from typing import Any

from factpy_kernel.core.store.ledger import Claim, Ledger

RECORD_STAGE_MARKER_PRED_ID = "__factpy_internal:record_stage"
RECORD_STAGE_BEGIN = "begin"
RECORD_STAGE_ROLES_WRITTEN = "roles_written"
RECORD_STAGE_COMMITTED = "committed"
RECORD_STAGE_ABORTED = "aborted"

RECORD_STAGE_VALUES = {
    RECORD_STAGE_BEGIN,
    RECORD_STAGE_ROLES_WRITTEN,
    RECORD_STAGE_COMMITTED,
    RECORD_STAGE_ABORTED,
}


def _diag_item(
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


def meta_str(ledger: Ledger, asrt_id: str, key: str) -> str | None:
    for row in ledger.find_meta(asrt_id=asrt_id, key=key):
        if isinstance(row.value, str):
            return row.value
    return None


def meta_int(ledger: Ledger, asrt_id: str, key: str) -> int | None:
    for row in ledger.find_meta(asrt_id=asrt_id, key=key):
        if isinstance(row.value, bool):
            continue
        if isinstance(row.value, int):
            return row.value
    return None


def parse_record_stage_marker_claim(claim: Claim) -> tuple[str, str, str] | None:
    if claim.pred_id != RECORD_STAGE_MARKER_PRED_ID:
        return None
    if len(claim.rest_terms) != 3:
        return None
    vals: list[str] = []
    for term in claim.rest_terms:
        if not (isinstance(term, tuple) and len(term) == 2):
            return None
        tag, value = term
        if tag != "string" or not isinstance(value, str) or not value:
            return None
        vals.append(value)
    materialize_id, stage, record_digest = vals
    if stage not in RECORD_STAGE_VALUES:
        return None
    return materialize_id, stage, record_digest


def resolve_record_stage_status(
    *,
    stage_digests: dict[str, set[str]],
    roles_count_expected_values: set[int] | None = None,
    path: str = "$.record_staging",
) -> dict[str, Any]:
    begin_digests = set(stage_digests.get(RECORD_STAGE_BEGIN, set()))
    roles_written_digests = set(stage_digests.get(RECORD_STAGE_ROLES_WRITTEN, set()))
    committed_digests = set(stage_digests.get(RECORD_STAGE_COMMITTED, set()))
    aborted_digests = set(stage_digests.get(RECORD_STAGE_ABORTED, set()))
    all_digests = begin_digests | roles_written_digests | committed_digests | aborted_digests
    count_values = set(roles_count_expected_values or set())

    diagnostics: list[dict[str, Any]] = []
    status = "none"
    digest: str | None = None
    reason: str | None = None

    if len(count_values) > 1:
        status = "conflict"
        reason = "roles_count_expected_mismatch"
        diagnostics.append(
            _diag_item(
                code="RECORD_MARKER_CONFLICT_ROLES_COUNT_EXPECTED_MISMATCH",
                severity="error",
                path=path,
                message="record stage markers disagree on roles_count_expected",
                data={"roles_count_expected_values": sorted(count_values)},
            )
        )

    if len(committed_digests) > 1:
        status = "conflict"
        reason = "multi_committed"
        diagnostics.append(
            _diag_item(
                code="RECORD_MARKER_CONFLICT_MULTI_COMMITTED",
                severity="error",
                path=path,
                message="multiple committed record marker digests found",
                data={"committed_digests": sorted(committed_digests)},
            )
        )

    if len(aborted_digests) > 1:
        status = "conflict"
        reason = "multi_aborted"
        diagnostics.append(
            _diag_item(
                code="RECORD_MARKER_CONFLICT_MULTI_ABORTED",
                severity="error",
                path=path,
                message="multiple aborted record marker digests found",
                data={"aborted_digests": sorted(aborted_digests)},
            )
        )

    if committed_digests and aborted_digests:
        status = "conflict"
        reason = "committed_and_aborted"
        diagnostics.append(
            _diag_item(
                code="RECORD_MARKER_CONFLICT_COMMITTED_AND_ABORTED",
                severity="error",
                path=path,
                message="record has both committed and aborted markers",
                data={
                    "committed_digests": sorted(committed_digests),
                    "aborted_digests": sorted(aborted_digests),
                },
            )
        )

    inflight_digests = begin_digests | roles_written_digests
    committed_mismatch_inflight = committed_digests and bool(inflight_digests - committed_digests)
    if committed_mismatch_inflight:
        status = "conflict"
        reason = "committed_and_inflight_mismatch"
        diagnostics.append(
            _diag_item(
                code="RECORD_MARKER_CONFLICT_COMMITTED_AND_INFLIGHT_MISMATCH",
                severity="error",
                path=path,
                message="record has committed marker and mismatched in-flight marker digest",
                data={
                    "committed_digests": sorted(committed_digests),
                    "inflight_digests": sorted(inflight_digests),
                    "inflight_mismatch_digests": sorted(inflight_digests - committed_digests),
                },
            )
        )

    if len(inflight_digests) > 1 and status != "conflict":
        diagnostics.append(
            _diag_item(
                code="RECORD_MARKER_CONFLICT_INFLIGHT_MULTI_DIGEST",
                severity="warning",
                path=path,
                message="record has multiple in-flight marker digests",
                data={
                    "begin_digests": sorted(begin_digests),
                    "roles_written_digests": sorted(roles_written_digests),
                },
            )
        )
        reason = reason or "inflight_multi_digest"

    if status != "conflict":
        if committed_digests:
            status = RECORD_STAGE_COMMITTED
            digest = next(iter(committed_digests)) if len(committed_digests) == 1 else None
        elif aborted_digests:
            status = RECORD_STAGE_ABORTED
            digest = next(iter(aborted_digests)) if len(aborted_digests) == 1 else None
        elif roles_written_digests:
            status = RECORD_STAGE_ROLES_WRITTEN
            if len(roles_written_digests) == 1:
                digest = next(iter(roles_written_digests))
        elif begin_digests:
            status = RECORD_STAGE_BEGIN
            if len(begin_digests) == 1:
                digest = next(iter(begin_digests))

    roles_count_expected = next(iter(count_values)) if len(count_values) == 1 else None
    return {
        "status": status,
        "digest": digest,
        "digests": all_digests,
        "reason": reason,
        "diag": diagnostics,
        "roles_count_expected": roles_count_expected,
        "roles_count_expected_values": count_values,
        "stage_digests": {
            RECORD_STAGE_BEGIN: begin_digests,
            RECORD_STAGE_ROLES_WRITTEN: roles_written_digests,
            RECORD_STAGE_COMMITTED: committed_digests,
            RECORD_STAGE_ABORTED: aborted_digests,
        },
    }


def read_record_stage_status(
    *,
    ledger: Ledger,
    record_e_ref: str,
    materialize_id: str,
    path: str = "$.record_staging",
) -> dict[str, Any]:
    stage_digests: dict[str, set[str]] = {
        RECORD_STAGE_BEGIN: set(),
        RECORD_STAGE_ROLES_WRITTEN: set(),
        RECORD_STAGE_COMMITTED: set(),
        RECORD_STAGE_ABORTED: set(),
    }
    roles_count_expected_values: set[int] = set()
    for claim in ledger.find_claims(pred_id=RECORD_STAGE_MARKER_PRED_ID, e_ref=record_e_ref):
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        parsed = parse_record_stage_marker_claim(claim)
        if parsed is None:
            continue
        marker_materialize_id, stage, record_digest = parsed
        if marker_materialize_id != materialize_id:
            continue
        stage_digests[stage].add(record_digest)
        roles_count_expected = meta_int(ledger, claim.asrt_id, "roles_count_expected")
        if roles_count_expected is not None and roles_count_expected >= 0:
            roles_count_expected_values.add(roles_count_expected)

    return resolve_record_stage_status(
        stage_digests=stage_digests,
        roles_count_expected_values=roles_count_expected_values,
        path=path,
    )
