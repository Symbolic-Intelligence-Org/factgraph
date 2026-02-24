from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.evidence.write_protocol import WriteProtocolError, set_field
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.protocol.digests import sha256_hex, sha256_token
from factpy_kernel.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factpy_kernel.core.store.ledger import Ledger


@dataclass(frozen=True)
class AcceptOptions:
    approved_by: str | None = None
    note: str | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class AcceptResult:
    materialize_id: str
    run_id: str
    accepted_count: int
    skipped_count: int
    written_assertions: list[dict[str, Any]]
    skipped_reason_counts: dict[str, int]
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    diagnostics_contract_version: int = 1


_RECORD_STAGE_MARKER_PRED_ID = "__factpy_internal:record_stage"
_RECORD_STAGE_BEGIN = "begin"
_RECORD_STAGE_ROLES_WRITTEN = "roles_written"
_RECORD_STAGE_COMMITTED = "committed"
_RECORD_STAGE_ABORTED = "aborted"


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


def accept_candidate_set(
    ledger: Ledger,
    candidate_set: CandidateSet,
    options: AcceptOptions,
    derived_rule_id: str,
    derived_rule_version: str,
    *,
    schema_digest_token: str | None = None,
    policy_digest_token: str | None = None,
) -> AcceptResult:
    if not isinstance(ledger, Ledger):
        raise WriteProtocolError("ledger must be Ledger")
    if not isinstance(candidate_set, CandidateSet):
        raise WriteProtocolError("candidate_set must be CandidateSet")
    if not isinstance(options, AcceptOptions):
        raise WriteProtocolError("options must be AcceptOptions")
    if not isinstance(derived_rule_id, str) or not derived_rule_id:
        raise WriteProtocolError("derived_rule_id must be non-empty string")
    if not isinstance(derived_rule_version, str) or not derived_rule_version:
        raise WriteProtocolError("derived_rule_version must be non-empty string")

    payload = candidate_set.payload
    if not isinstance(payload, dict):
        raise WriteProtocolError("candidate payload must be object")
    if not isinstance(candidate_set.target, str) or not candidate_set.target:
        raise WriteProtocolError("candidate target must be non-empty string")
    if not isinstance(candidate_set.key_tuple_digest, str) or not candidate_set.key_tuple_digest.startswith("sha256:"):
        raise WriteProtocolError("candidate key_tuple_digest must start with sha256:")

    materialize_kind = payload.get("materialize_as", "fact")
    if materialize_kind not in {"fact", "record"}:
        raise WriteProtocolError("candidate payload materialize_as must be 'fact' or 'record'")

    if materialize_kind == "record":
        return _accept_record_candidate(
            ledger=ledger,
            candidate_set=candidate_set,
            payload=payload,
            options=options,
            derived_rule_id=derived_rule_id,
            derived_rule_version=derived_rule_version,
            schema_digest_token=schema_digest_token,
            policy_digest_token=policy_digest_token,
        )

    e_ref = payload.get("e_ref")
    rest_terms = payload.get("rest_terms")

    if not isinstance(e_ref, str) or not e_ref:
        raise WriteProtocolError("candidate payload missing e_ref")
    if not isinstance(rest_terms, list):
        raise WriteProtocolError("candidate payload missing rest_terms")

    computed_materialize_id = _compute_materialize_id(candidate_set)

    if options.dry_run:
        return AcceptResult(
            materialize_id=computed_materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=1,
            skipped_count=0,
            written_assertions=[
                {
                    "asrt_id": "<dry_run>",
                    "pred_id": candidate_set.target,
                    "key_tuple_digest": candidate_set.key_tuple_digest,
                }
            ],
            skipped_reason_counts={},
        )

    materialize_id = _existing_materialize_id(
        ledger=ledger,
        pred_id=candidate_set.target,
        e_ref=e_ref,
        key_tuple_digest=candidate_set.key_tuple_digest,
    )
    if materialize_id is None:
        materialize_id = computed_materialize_id

    cand_key_digest = _compute_cand_key_digest(candidate_set.target, candidate_set.key_tuple_digest)

    existing_written = _find_existing_written_assertions(
        ledger=ledger,
        pred_id=candidate_set.target,
        e_ref=e_ref,
        key_tuple_digest=candidate_set.key_tuple_digest,
        materialize_id=materialize_id,
        cand_key_digest=cand_key_digest,
    )
    if existing_written:
        _assert_duplicate_meta_compatible(ledger=ledger, written_assertions=existing_written, options=options)
        return AcceptResult(
            materialize_id=materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"duplicate": 1},
        )

    write_meta: dict[str, Any] = {
        "source": "derivation.accept",
        "source_loc": f"{derived_rule_id}:{derived_rule_version}",
        "trace_id": candidate_set.run_id,
        "derived_rule_id": derived_rule_id,
        "derived_rule_version": derived_rule_version,
        "run_id": candidate_set.run_id,
        "materialize_id": materialize_id,
        "key_tuple_digest": candidate_set.key_tuple_digest,
        "cand_key_digest": cand_key_digest,
        "support_digest": candidate_set.support_digest,
        "support_kind": candidate_set.support_kind,
    }
    if isinstance(schema_digest_token, str) and schema_digest_token:
        write_meta["schema_digest"] = schema_digest_token
    if isinstance(policy_digest_token, str) and policy_digest_token:
        write_meta["policy_digest"] = policy_digest_token
    if options.approved_by is not None:
        write_meta["approved_by"] = options.approved_by
    if options.note is not None:
        write_meta["note"] = options.note

    asrt_id = set_field(
        ledger=ledger,
        pred_id=candidate_set.target,
        e_ref=e_ref,
        rest_terms=rest_terms,
        meta=write_meta,
    )

    return AcceptResult(
        materialize_id=materialize_id,
        run_id=candidate_set.run_id,
        accepted_count=1,
        skipped_count=0,
        written_assertions=[
            {
                "asrt_id": asrt_id,
                "pred_id": candidate_set.target,
                "key_tuple_digest": candidate_set.key_tuple_digest,
            }
        ],
        skipped_reason_counts={},
    )


def _accept_record_candidate(
    *,
    ledger: Ledger,
    candidate_set: CandidateSet,
    payload: dict[str, Any],
    options: AcceptOptions,
    derived_rule_id: str,
    derived_rule_version: str,
    schema_digest_token: str | None = None,
    policy_digest_token: str | None = None,
) -> AcceptResult:
    record_type = payload.get("record_type", candidate_set.target)
    if not isinstance(record_type, str) or not record_type:
        raise WriteProtocolError("record payload missing record_type")
    if candidate_set.target != record_type:
        raise WriteProtocolError("candidate target must equal record_type for materialize_as='record'")

    id_policy = payload.get("id_policy")
    record_exists_pred_id = payload.get("record_exists_pred_id")
    if not isinstance(record_exists_pred_id, str) or not record_exists_pred_id:
        raise WriteProtocolError("record payload missing record_exists_pred_id")

    roles_raw = payload.get("roles")
    if not isinstance(roles_raw, list) or not roles_raw:
        raise WriteProtocolError("record payload roles must be non-empty list")
    roles = _normalize_record_roles(roles_raw)
    record_e_ref = _derive_record_e_ref(
        record_type=record_type,
        id_policy=id_policy,
        candidate_set=candidate_set,
        roles=roles,
    )

    computed_materialize_id = _compute_materialize_id(candidate_set)

    if options.dry_run:
        dry_rows = [{"asrt_id": "<dry_run>", "pred_id": record_exists_pred_id, "key_tuple_digest": candidate_set.key_tuple_digest}]
        for role in roles:
            dry_rows.append({"asrt_id": "<dry_run>", "pred_id": role["pred_id"], "key_tuple_digest": candidate_set.key_tuple_digest})
        return AcceptResult(
            materialize_id=computed_materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=1,
            skipped_count=0,
            written_assertions=dry_rows,
            skipped_reason_counts={},
        )

    materialize_id = _existing_materialize_id(
        ledger=ledger,
        pred_id=record_exists_pred_id,
        e_ref=record_e_ref,
        key_tuple_digest=candidate_set.key_tuple_digest,
    )
    if materialize_id is None:
        materialize_id = computed_materialize_id
    cand_key_digest = _compute_cand_key_digest(candidate_set.target, candidate_set.key_tuple_digest)

    existing_written = _find_existing_written_assertions_record(
        ledger=ledger,
        materialize_id=materialize_id,
        cand_key_digest=cand_key_digest,
        key_tuple_digest=candidate_set.key_tuple_digest,
    )
    expected_record_digest = _compute_record_roles_digest(roles)
    stage_state = _read_record_stage_state(
        ledger=ledger,
        record_e_ref=record_e_ref,
        materialize_id=materialize_id,
    )
    progress_before = _record_materialization_progress(
        ledger=ledger,
        existing_written=existing_written,
        expected_roles=roles,
        record_exists_pred_id=record_exists_pred_id,
    )

    if stage_state["stage"] == _RECORD_STAGE_ABORTED:
        return AcceptResult(
            materialize_id=materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"aborted": 1},
            diagnostics=[
                _diag_item(
                    code="ACCEPT_RECORD_ABORTED_STATE",
                    severity="error",
                    path="$.accept.record",
                    message="record accept is aborted and cannot be retried",
                    data={
                        "stage_before": stage_state["stage"],
                        "stage_after": stage_state["stage"],
                        "expected_digest": expected_record_digest,
                        "marker_digest": stage_state.get("aborted_digest"),
                        "missing_roles_count": progress_before["missing_roles_count"],
                        "extra_roles_count": progress_before["extra_roles_count"],
                    },
                )
            ],
        )

    if stage_state["stage"] == _RECORD_STAGE_COMMITTED:
        committed_digest = stage_state.get("committed_digest")
        if committed_digest != expected_record_digest:
            _write_record_stage_marker(
                ledger=ledger,
                record_e_ref=record_e_ref,
                materialize_id=materialize_id,
                stage=_RECORD_STAGE_ABORTED,
                record_digest=expected_record_digest,
                marker_meta=_record_stage_marker_meta(
                    write_meta_base={},
                    record_type=record_type,
                    materialize_id=materialize_id,
                    record_e_ref=record_e_ref,
                    key_tuple_digest=candidate_set.key_tuple_digest,
                    cand_key_digest=cand_key_digest,
                    record_digest=expected_record_digest,
                ),
            )
            return AcceptResult(
                materialize_id=materialize_id,
                run_id=candidate_set.run_id,
                accepted_count=0,
                skipped_count=1,
                written_assertions=existing_written,
                skipped_reason_counts={"conflict": 1},
                diagnostics=[
                    _diag_item(
                        code="ACCEPT_RECORD_COMMITTED_DIGEST_CONFLICT",
                        severity="error",
                        path="$.accept.record",
                        message="committed record digest conflicts with candidate digest",
                        data={
                            "stage_before": stage_state["stage"],
                            "stage_after": _RECORD_STAGE_ABORTED,
                            "expected_digest": expected_record_digest,
                            "committed_digest": committed_digest,
                        },
                    )
                ],
            )
        if not progress_before["is_complete"] or progress_before["actual_digest"] != expected_record_digest:
            _write_record_stage_marker(
                ledger=ledger,
                record_e_ref=record_e_ref,
                materialize_id=materialize_id,
                stage=_RECORD_STAGE_ABORTED,
                record_digest=expected_record_digest,
                marker_meta=_record_stage_marker_meta(
                    write_meta_base={},
                    record_type=record_type,
                    materialize_id=materialize_id,
                    record_e_ref=record_e_ref,
                    key_tuple_digest=candidate_set.key_tuple_digest,
                    cand_key_digest=cand_key_digest,
                    record_digest=expected_record_digest,
                ),
            )
            return AcceptResult(
                materialize_id=materialize_id,
                run_id=candidate_set.run_id,
                accepted_count=0,
                skipped_count=1,
                written_assertions=existing_written,
                skipped_reason_counts={"conflict": 1},
                diagnostics=[
                    _diag_item(
                        code="ACCEPT_RECORD_COMMITTED_STATE_INCOMPLETE",
                        severity="error",
                        path="$.accept.record",
                        message="committed record materialization is incomplete or corrupted",
                        data={
                            "stage_before": stage_state["stage"],
                            "stage_after": _RECORD_STAGE_ABORTED,
                            "expected_digest": expected_record_digest,
                            "actual_digest": progress_before["actual_digest"],
                            "missing_roles_count": progress_before["missing_roles_count"],
                            "extra_roles_count": progress_before["extra_roles_count"],
                            "exists_missing": progress_before["exists_missing"],
                        },
                    )
                ],
            )
        _assert_duplicate_meta_compatible(ledger=ledger, written_assertions=existing_written, options=options)
        return AcceptResult(
            materialize_id=materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"duplicate": 1},
        )

    write_meta: dict[str, Any] = {
        "source": "derivation.accept",
        "source_loc": f"{derived_rule_id}:{derived_rule_version}",
        "trace_id": candidate_set.run_id,
        "derived_rule_id": derived_rule_id,
        "derived_rule_version": derived_rule_version,
        "run_id": candidate_set.run_id,
        "materialize_id": materialize_id,
        "key_tuple_digest": candidate_set.key_tuple_digest,
        "cand_key_digest": cand_key_digest,
        "support_digest": candidate_set.support_digest,
        "support_kind": candidate_set.support_kind,
        "materialize_kind": "record",
        "record_type": record_type,
        "record_e_ref": record_e_ref,
        "record_id_policy": _record_id_policy_kind(id_policy),
        "record_digest": expected_record_digest,
    }
    if isinstance(schema_digest_token, str) and schema_digest_token:
        write_meta["schema_digest"] = schema_digest_token
    if isinstance(policy_digest_token, str) and policy_digest_token:
        write_meta["policy_digest"] = policy_digest_token
    if options.approved_by is not None:
        write_meta["approved_by"] = options.approved_by
    if options.note is not None:
        write_meta["note"] = options.note

    marker_meta = _record_stage_marker_meta(
        write_meta_base=write_meta,
        record_type=record_type,
        materialize_id=materialize_id,
        record_e_ref=record_e_ref,
        key_tuple_digest=candidate_set.key_tuple_digest,
        cand_key_digest=cand_key_digest,
        record_digest=expected_record_digest,
    )
    _write_record_stage_marker(
        ledger=ledger,
        record_e_ref=record_e_ref,
        materialize_id=materialize_id,
        stage=_RECORD_STAGE_BEGIN,
        record_digest=expected_record_digest,
        marker_meta=marker_meta,
    )

    if progress_before["extra_roles_count"] > 0:
        _write_record_stage_marker(
            ledger=ledger,
            record_e_ref=record_e_ref,
            materialize_id=materialize_id,
            stage=_RECORD_STAGE_ABORTED,
            record_digest=expected_record_digest,
            marker_meta=marker_meta,
        )
        return AcceptResult(
            materialize_id=materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"conflict": 1},
            diagnostics=[
                _diag_item(
                    code="ACCEPT_RECORD_EXTRA_ROLES_CONFLICT",
                    severity="error",
                    path="$.accept.record",
                    message="existing record roles conflict with candidate and cannot be recovered safely",
                    data={
                        "stage_before": stage_state["stage"],
                        "stage_after": _RECORD_STAGE_ABORTED,
                        "expected_digest": expected_record_digest,
                        "actual_digest": progress_before["actual_digest"],
                        "missing_roles_count": progress_before["missing_roles_count"],
                        "extra_roles_count": progress_before["extra_roles_count"],
                    },
                )
            ],
        )

    written: list[dict[str, str]] = list(existing_written)
    for role in progress_before["missing_roles"]:
        asrt_id = set_field(
            ledger=ledger,
            pred_id=role["pred_id"],
            e_ref=record_e_ref,
            rest_terms=role["rest_terms"],
            meta=write_meta,
        )
        written.append(
            {"asrt_id": asrt_id, "pred_id": role["pred_id"], "key_tuple_digest": candidate_set.key_tuple_digest}
        )
    _write_record_stage_marker(
        ledger=ledger,
        record_e_ref=record_e_ref,
        materialize_id=materialize_id,
        stage=_RECORD_STAGE_ROLES_WRITTEN,
        record_digest=expected_record_digest,
        marker_meta=marker_meta,
    )
    if progress_before["exists_missing"]:
        exists_asrt = set_field(
            ledger=ledger,
            pred_id=record_exists_pred_id,
            e_ref=record_e_ref,
            rest_terms=[],
            meta=write_meta,
        )
        written.append(
            {
                "asrt_id": exists_asrt,
                "pred_id": record_exists_pred_id,
                "key_tuple_digest": candidate_set.key_tuple_digest,
            }
        )

    existing_written_after = _find_existing_written_assertions_record(
        ledger=ledger,
        materialize_id=materialize_id,
        cand_key_digest=cand_key_digest,
        key_tuple_digest=candidate_set.key_tuple_digest,
    )
    progress_after = _record_materialization_progress(
        ledger=ledger,
        existing_written=existing_written_after,
        expected_roles=roles,
        record_exists_pred_id=record_exists_pred_id,
    )
    if not progress_after["is_complete"] or progress_after["actual_digest"] != expected_record_digest:
        _write_record_stage_marker(
            ledger=ledger,
            record_e_ref=record_e_ref,
            materialize_id=materialize_id,
            stage=_RECORD_STAGE_ABORTED,
            record_digest=expected_record_digest,
            marker_meta=marker_meta,
        )
        return AcceptResult(
            materialize_id=materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written_after,
            skipped_reason_counts={"conflict": 1},
            diagnostics=[
                _diag_item(
                    code="ACCEPT_RECORD_FINALIZE_CONFLICT",
                    severity="error",
                    path="$.accept.record",
                    message="record materialization could not be finalized consistently",
                    data={
                        "stage_before": stage_state["stage"],
                        "stage_after": _RECORD_STAGE_ABORTED,
                        "expected_digest": expected_record_digest,
                        "actual_digest": progress_after["actual_digest"],
                        "missing_roles_count": progress_after["missing_roles_count"],
                        "extra_roles_count": progress_after["extra_roles_count"],
                        "exists_missing": progress_after["exists_missing"],
                    },
                )
            ],
        )
    _write_record_stage_marker(
        ledger=ledger,
        record_e_ref=record_e_ref,
        materialize_id=materialize_id,
        stage=_RECORD_STAGE_COMMITTED,
        record_digest=expected_record_digest,
        marker_meta=marker_meta,
    )
    existing_written_after.sort(key=lambda row: (row["pred_id"], row["asrt_id"]))
    diagnostics: list[dict[str, Any]] = []
    if stage_state["stage"] in {_RECORD_STAGE_BEGIN, _RECORD_STAGE_ROLES_WRITTEN} or progress_before["exists_missing"] or progress_before["missing_roles_count"] > 0:
        diagnostics.append(
            _diag_item(
                code="ACCEPT_RECORD_RECOVERED_PARTIAL",
                severity="warning",
                path="$.accept.record",
                message="record accept recovered and finalized a partial materialization",
                data={
                    "stage_before": stage_state["stage"],
                    "stage_after": _RECORD_STAGE_COMMITTED,
                    "expected_digest": expected_record_digest,
                    "missing_roles_count": progress_before["missing_roles_count"],
                    "extra_roles_count": progress_before["extra_roles_count"],
                    "exists_missing_before": progress_before["exists_missing"],
                },
            )
        )

    return AcceptResult(
        materialize_id=materialize_id,
        run_id=candidate_set.run_id,
        accepted_count=1,
        skipped_count=0,
        written_assertions=existing_written_after,
        skipped_reason_counts={},
        diagnostics=diagnostics,
    )


def _compute_materialize_id(candidate_set: CandidateSet) -> str:
    parts = [
        b"factpy\x00mat_v1\x00",
        candidate_set.run_id.encode("utf-8"),
        b"\x00",
        candidate_set.derivation_id.encode("utf-8"),
        b"\x00",
        candidate_set.derivation_version.encode("utf-8"),
        b"\x00",
    ]
    return f"mat_v1:{sha256_hex(b''.join(parts))}"


def _compute_cand_key_digest(target: str, key_tuple_digest: str) -> str:
    parts = [
        b"factpy\x00cand_key_v1\x00",
        target.encode("utf-8"),
        b"\x00",
        key_tuple_digest.encode("utf-8"),
        b"\x00",
    ]
    return sha256_token(b"".join(parts))


def _existing_materialize_id(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    key_tuple_digest: str,
) -> str | None:
    for claim in ledger.find_claims(pred_id=pred_id, e_ref=e_ref):
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        if _meta_value(ledger, claim.asrt_id, "key_tuple_digest") != key_tuple_digest:
            continue
        materialize_id = _meta_value(ledger, claim.asrt_id, "materialize_id")
        if materialize_id:
            return materialize_id
    return None


def _find_existing_written_assertions(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    key_tuple_digest: str,
    materialize_id: str,
    cand_key_digest: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for claim in ledger.find_claims(pred_id=pred_id, e_ref=e_ref):
        if ledger.has_active_revocation(claim.asrt_id):
            continue

        if _meta_value(ledger, claim.asrt_id, "materialize_id") != materialize_id:
            continue
        if _meta_value(ledger, claim.asrt_id, "cand_key_digest") != cand_key_digest:
            continue
        if _meta_value(ledger, claim.asrt_id, "key_tuple_digest") != key_tuple_digest:
            continue

        rows.append(
            {
                "asrt_id": claim.asrt_id,
                "pred_id": claim.pred_id,
                "key_tuple_digest": key_tuple_digest,
            }
        )
    return rows


def _find_existing_written_assertions_record(
    *,
    ledger: Ledger,
    materialize_id: str,
    cand_key_digest: str,
    key_tuple_digest: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for claim in ledger.find_claims():
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        if _meta_value(ledger, claim.asrt_id, "materialize_kind") != "record":
            continue
        if _meta_value(ledger, claim.asrt_id, "materialize_id") != materialize_id:
            continue
        if _meta_value(ledger, claim.asrt_id, "cand_key_digest") != cand_key_digest:
            continue
        if _meta_value(ledger, claim.asrt_id, "key_tuple_digest") != key_tuple_digest:
            continue
        rows.append(
            {"asrt_id": claim.asrt_id, "pred_id": claim.pred_id, "key_tuple_digest": key_tuple_digest}
        )
    rows.sort(key=lambda row: (row["pred_id"], row["asrt_id"]))
    return rows


def _record_stage_marker_meta(
    *,
    write_meta_base: dict[str, Any],
    record_type: str,
    materialize_id: str,
    record_e_ref: str,
    key_tuple_digest: str,
    cand_key_digest: str,
    record_digest: str,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "source": "derivation.accept.record_stage",
        "materialize_kind": "record_stage",
        "record_type": record_type,
        "record_e_ref": record_e_ref,
        "materialize_id": materialize_id,
        "key_tuple_digest": key_tuple_digest,
        "cand_key_digest": cand_key_digest,
        "record_digest": record_digest,
    }
    for key in (
        "source_loc",
        "trace_id",
        "derived_rule_id",
        "derived_rule_version",
        "run_id",
        "schema_digest",
        "policy_digest",
        "approved_by",
        "note",
    ):
        value = write_meta_base.get(key)
        if value is None:
            continue
        meta[key] = value
    return meta


def _write_record_stage_marker(
    *,
    ledger: Ledger,
    record_e_ref: str,
    materialize_id: str,
    stage: str,
    record_digest: str,
    marker_meta: dict[str, Any],
) -> str:
    if stage not in {
        _RECORD_STAGE_BEGIN,
        _RECORD_STAGE_ROLES_WRITTEN,
        _RECORD_STAGE_COMMITTED,
        _RECORD_STAGE_ABORTED,
    }:
        raise WriteProtocolError(f"unsupported record stage marker: {stage}")
    return set_field(
        ledger=ledger,
        pred_id=_RECORD_STAGE_MARKER_PRED_ID,
        e_ref=record_e_ref,
        rest_terms=[
            ("string", materialize_id),
            ("string", stage),
            ("string", record_digest),
        ],
        meta=marker_meta,
    )


def _parse_record_stage_marker_claim(claim: Any) -> tuple[str, str, str] | None:
    if not hasattr(claim, "pred_id") or claim.pred_id != _RECORD_STAGE_MARKER_PRED_ID:
        return None
    rest_terms = getattr(claim, "rest_terms", None)
    if not isinstance(rest_terms, list) or len(rest_terms) != 3:
        return None
    parts: list[str] = []
    for term in rest_terms:
        if not (isinstance(term, tuple) and len(term) == 2):
            return None
        tag, value = term
        if tag != "string" or not isinstance(value, str) or not value:
            return None
        parts.append(value)
    materialize_id, stage, record_digest = parts
    if stage not in {
        _RECORD_STAGE_BEGIN,
        _RECORD_STAGE_ROLES_WRITTEN,
        _RECORD_STAGE_COMMITTED,
        _RECORD_STAGE_ABORTED,
    }:
        return None
    return materialize_id, stage, record_digest


def _read_record_stage_state(
    *,
    ledger: Ledger,
    record_e_ref: str,
    materialize_id: str,
) -> dict[str, Any]:
    stage_digests: dict[str, set[str]] = {
        _RECORD_STAGE_BEGIN: set(),
        _RECORD_STAGE_ROLES_WRITTEN: set(),
        _RECORD_STAGE_COMMITTED: set(),
        _RECORD_STAGE_ABORTED: set(),
    }
    for claim in ledger.find_claims(pred_id=_RECORD_STAGE_MARKER_PRED_ID, e_ref=record_e_ref):
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        parsed = _parse_record_stage_marker_claim(claim)
        if parsed is None:
            continue
        marker_materialize_id, stage, record_digest = parsed
        if marker_materialize_id != materialize_id:
            continue
        stage_digests[stage].add(record_digest)

    state: dict[str, Any] = {
        "stage": None,
        "begin_digests": sorted(stage_digests[_RECORD_STAGE_BEGIN]),
        "roles_written_digests": sorted(stage_digests[_RECORD_STAGE_ROLES_WRITTEN]),
        "committed_digests": sorted(stage_digests[_RECORD_STAGE_COMMITTED]),
        "aborted_digests": sorted(stage_digests[_RECORD_STAGE_ABORTED]),
        "committed_digest": None,
        "aborted_digest": None,
    }
    if stage_digests[_RECORD_STAGE_ABORTED]:
        state["stage"] = _RECORD_STAGE_ABORTED
        state["aborted_digest"] = sorted(stage_digests[_RECORD_STAGE_ABORTED])[0]
        return state
    if stage_digests[_RECORD_STAGE_COMMITTED]:
        state["stage"] = _RECORD_STAGE_COMMITTED
        state["committed_digest"] = sorted(stage_digests[_RECORD_STAGE_COMMITTED])[0]
        return state
    if stage_digests[_RECORD_STAGE_ROLES_WRITTEN]:
        state["stage"] = _RECORD_STAGE_ROLES_WRITTEN
        return state
    if stage_digests[_RECORD_STAGE_BEGIN]:
        state["stage"] = _RECORD_STAGE_BEGIN
    return state


def _record_role_entry_bytes(pred_id: str, rest_terms: list[tuple[str, Any]]) -> bytes:
    return canonical_bytes_tup_v1([("string", pred_id), *rest_terms])


def _record_roles_digest_from_entries(entries: list[bytes]) -> str:
    sorted_entries = sorted(entries)
    return sha256_token(canonical_bytes_tup_v1([("bytes", entry) for entry in sorted_entries]))


def _compute_record_roles_digest(roles: list[dict[str, Any]]) -> str:
    return _record_roles_digest_from_entries(
        [_record_role_entry_bytes(role["pred_id"], role["rest_terms"]) for role in roles]
    )


def _record_materialization_progress(
    *,
    ledger: Ledger,
    existing_written: list[dict[str, str]],
    expected_roles: list[dict[str, Any]],
    record_exists_pred_id: str,
) -> dict[str, Any]:
    expected_entries = [_record_role_entry_bytes(role["pred_id"], role["rest_terms"]) for role in expected_roles]
    expected_counter = Counter(expected_entries)

    actual_entries: list[bytes] = []
    exists_missing = True
    for row in existing_written:
        claim = ledger.get_claim(row["asrt_id"])
        if claim is None or ledger.has_active_revocation(row["asrt_id"]):
            continue
        if claim.pred_id == record_exists_pred_id:
            if claim.rest_terms == []:
                exists_missing = False
            continue
        actual_entries.append(_record_role_entry_bytes(claim.pred_id, claim.rest_terms))

    actual_counter = Counter(actual_entries)
    missing_counter = expected_counter - actual_counter
    extra_counter = actual_counter - expected_counter

    remaining_actual = Counter(actual_entries)
    missing_roles: list[dict[str, Any]] = []
    for role in expected_roles:
        role_entry = _record_role_entry_bytes(role["pred_id"], role["rest_terms"])
        if remaining_actual[role_entry] > 0:
            remaining_actual[role_entry] -= 1
            continue
        missing_roles.append(role)

    actual_digest = _record_roles_digest_from_entries(actual_entries)
    return {
        "is_complete": (sum(missing_counter.values()) == 0 and sum(extra_counter.values()) == 0 and not exists_missing),
        "exists_missing": exists_missing,
        "missing_roles": missing_roles,
        "missing_roles_count": sum(missing_counter.values()),
        "extra_roles_count": sum(extra_counter.values()),
        "actual_digest": actual_digest,
    }


def _assert_duplicate_meta_compatible(
    *,
    ledger: Ledger,
    written_assertions: list[dict[str, str]],
    options: AcceptOptions,
) -> None:
    if options.approved_by is None and options.note is None:
        return

    for row in written_assertions:
        asrt_id = row["asrt_id"]
        if options.approved_by is not None:
            existing_approved_by = _meta_value(ledger, asrt_id, "approved_by")
            if existing_approved_by != options.approved_by:
                raise WriteProtocolError("duplicate accept approved_by mismatch")
        if options.note is not None:
            existing_note = _meta_value(ledger, asrt_id, "note")
            if existing_note != options.note:
                raise WriteProtocolError("duplicate accept note mismatch")


def _record_id_policy_kind(id_policy: Any) -> str:
    if isinstance(id_policy, str):
        return id_policy
    if isinstance(id_policy, dict):
        kind = id_policy.get("kind")
        if isinstance(kind, str):
            return kind
    raise WriteProtocolError("record payload id_policy must be string or object with kind")


def _derive_record_e_ref(
    *,
    record_type: str,
    id_policy: Any,
    candidate_set: CandidateSet,
    roles: list[dict[str, Any]],
) -> str:
    kind = _record_id_policy_kind(id_policy)
    if kind != "key_tuple_digest_v1":
        if kind == "identity_fields_v1":
            return _derive_record_e_ref_from_identity_fields(
                record_type=record_type,
                id_policy=id_policy,
                roles=roles,
            )
        raise WriteProtocolError(
            "record id_policy.kind must be 'key_tuple_digest_v1' or 'identity_fields_v1' in v1"
        )
    return encode_idref_v1(
        record_type,
        [("key_tuple_digest", "string", candidate_set.key_tuple_digest)],
    )


def _derive_record_e_ref_from_identity_fields(
    *,
    record_type: str,
    id_policy: Any,
    roles: list[dict[str, Any]],
) -> str:
    if not isinstance(id_policy, dict):
        raise WriteProtocolError("record id_policy identity_fields_v1 must be object")
    fields = id_policy.get("fields")
    if not isinstance(fields, list) or not fields:
        raise WriteProtocolError("record id_policy.fields must be non-empty list")

    role_map: dict[str, tuple[str, Any]] = {}
    for idx, role in enumerate(roles):
        field_name = role.get("field_name")
        pred_id = role.get("pred_id")
        if not isinstance(field_name, str) or not field_name:
            if isinstance(pred_id, str) and ":" in pred_id:
                field_name = pred_id.split(":", 1)[1]
            elif isinstance(pred_id, str) and pred_id:
                field_name = pred_id
            else:
                raise WriteProtocolError(f"record roles[{idx}] missing field_name")
        rest_terms = role.get("rest_terms")
        if not isinstance(rest_terms, list) or len(rest_terms) != 1:
            raise WriteProtocolError(
                f"record roles[{idx}].rest_terms must contain exactly one term for identity_fields_v1"
            )
        term = rest_terms[0]
        if not (isinstance(term, tuple) and len(term) == 2):
            raise WriteProtocolError(f"record roles[{idx}].rest_terms[0] must be (tag,value)")
        tag, value = term
        if not isinstance(tag, str) or not tag:
            raise WriteProtocolError(f"record roles[{idx}] role term tag must be non-empty string")
        if field_name in role_map:
            raise WriteProtocolError(f"duplicate record role field_name for id_policy: {field_name}")
        role_map[field_name] = (tag, value)

    identity_fields: list[tuple[str, str, Any]] = []
    for idx, item in enumerate(fields):
        if not isinstance(item, dict):
            raise WriteProtocolError(f"id_policy.fields[{idx}] must be object")
        name = item.get("name")
        role_name = item.get("role", item.get("from_role"))
        type_domain = item.get("type_domain")
        if not isinstance(name, str) or not name:
            raise WriteProtocolError(f"id_policy.fields[{idx}].name must be non-empty string")
        if not isinstance(role_name, str) or not role_name:
            raise WriteProtocolError(f"id_policy.fields[{idx}].role must be non-empty string")
        if not isinstance(type_domain, str) or not type_domain:
            raise WriteProtocolError(f"id_policy.fields[{idx}].type_domain must be non-empty string")
        role_term = role_map.get(role_name)
        if role_term is None:
            raise WriteProtocolError(f"id_policy.fields[{idx}] references unknown role: {role_name}")
        actual_tag, value = role_term
        if actual_tag != type_domain:
            raise WriteProtocolError(
                f"id_policy.fields[{idx}].type_domain mismatches role tag: {actual_tag}"
            )
        identity_fields.append((name, type_domain, value))

    return encode_idref_v1(record_type, identity_fields)


def _normalize_record_roles(roles_raw: list[Any]) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    for idx, item in enumerate(roles_raw):
        if not isinstance(item, dict):
            raise WriteProtocolError(f"record roles[{idx}] must be object")
        pred_id = item.get("pred_id")
        field_name = item.get("field_name")
        rest_terms = item.get("rest_terms")
        if not isinstance(pred_id, str) or not pred_id:
            raise WriteProtocolError(f"record roles[{idx}].pred_id must be non-empty string")
        if field_name is not None and (not isinstance(field_name, str) or not field_name):
            raise WriteProtocolError(f"record roles[{idx}].field_name must be non-empty string when provided")
        if not isinstance(rest_terms, list):
            raise WriteProtocolError(f"record roles[{idx}].rest_terms must be list")
        normalized: dict[str, Any] = {"pred_id": pred_id, "rest_terms": rest_terms}
        if isinstance(field_name, str):
            normalized["field_name"] = field_name
        type_domain = item.get("type_domain")
        if type_domain is not None:
            if not isinstance(type_domain, str) or not type_domain:
                raise WriteProtocolError(f"record roles[{idx}].type_domain must be non-empty string when provided")
            normalized["type_domain"] = type_domain
        roles.append(normalized)
    return roles


def _meta_value(ledger: Ledger, asrt_id: str, key: str) -> str | None:
    for row in ledger.find_meta(asrt_id=asrt_id, key=key):
        if isinstance(row.value, str):
            return row.value
    return None
