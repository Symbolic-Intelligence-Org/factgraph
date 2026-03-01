from __future__ import annotations

import json
import warnings
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from factpy_kernel.core.derivation.candidates import CandidateSet, extract_candidate_refs
from factpy_kernel.core.evidence.write_protocol import (
    WriteProtocolError,
    now_epoch_nanos,
    retract_by_asrt,
    set_field,
)
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.protocol.digests import sha256_hex, sha256_token
from factpy_kernel.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factpy_kernel.core.record_staging import (
    RECORD_STAGE_ABORTED,
    RECORD_STAGE_BEGIN,
    RECORD_STAGE_COMMITTED,
    RECORD_STAGE_MARKER_PRED_ID,
    RECORD_STAGE_ROLES_WRITTEN,
    RECORD_STAGE_VALUES,
    read_record_stage_status,
)
from factpy_kernel.core.store.ledger import Ledger


@dataclass(frozen=True)
class AcceptOptions:
    approved_by: str | None = None
    note: str | None = None
    dry_run: bool = False
    identity_override: dict[str, Any] | None = None


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
    entity_ref: str | None = None


@dataclass(frozen=True)
class AcceptRequest:
    candidate_set: CandidateSet
    identity_override: dict[str, Any] | None = None
    approved_by: str | None = None
    note: str | None = None


class LegacyAcceptFallbackWarning(RuntimeWarning):
    pass

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
    schema_ir: dict[str, Any] | None = None,
    resolved_candidate_refs: dict[str, str] | None = None,
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

    if candidate_set.candidate_kind == "entity":
        if _is_v2_entity_payload(payload):
            return _accept_entity_candidate_v2(
                ledger=ledger,
                candidate_set=candidate_set,
                payload=payload,
                options=options,
                derived_rule_id=derived_rule_id,
                derived_rule_version=derived_rule_version,
                schema_digest_token=schema_digest_token,
                policy_digest_token=policy_digest_token,
                schema_ir=schema_ir,
            )
        # TODO(remove in vX): Drop this legacy entity(record) payload fallback once
        # all external callers stop sending v1 record payload shapes and CI asserts
        # no LegacyAcceptFallbackWarning is emitted.
        # v1 compatibility path.
        warnings.warn(
            "accept() fallback to legacy record payload path; migrate candidate payload to v2 entity shape",
            LegacyAcceptFallbackWarning,
            stacklevel=2,
        )
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

    if isinstance(payload.get("terms"), list):
        return _accept_fact_candidate_v2(
            ledger=ledger,
            candidate_set=candidate_set,
            payload=payload,
            options=options,
            derived_rule_id=derived_rule_id,
            derived_rule_version=derived_rule_version,
            schema_digest_token=schema_digest_token,
            policy_digest_token=policy_digest_token,
            resolved_candidate_refs=resolved_candidate_refs,
        )
    materialize_kind = payload.get("materialize_as", "fact")
    if materialize_kind == "record":
        # TODO(remove in vX): Remove materialize_as='record' fallback after all
        # callers migrate to v2 candidate_kind/terms payloads and fallback-warning
        # telemetry remains zero in CI/runtime checks.
        # Legacy payload compatibility.
        warnings.warn(
            "accept() fallback to legacy materialize_as='record' payload; migrate to v2 candidate_kind/terms",
            LegacyAcceptFallbackWarning,
            stacklevel=2,
        )
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
    if materialize_kind != "fact":
        raise WriteProtocolError("candidate payload materialize_as must be 'fact' or 'record'")
    return _accept_fact_candidate_v1(
        ledger=ledger,
        candidate_set=candidate_set,
        payload=payload,
        options=options,
        derived_rule_id=derived_rule_id,
        derived_rule_version=derived_rule_version,
        schema_digest_token=schema_digest_token,
        policy_digest_token=policy_digest_token,
    )


def accept_many_candidate_sets(
    ledger: Ledger,
    requests: list[AcceptRequest | CandidateSet | dict[str, Any]],
    *,
    mode: str = "atomic",
    idempotent_duplicate_ok: bool = True,
    schema_digest_token: str | None = None,
    policy_digest_token: str | None = None,
    schema_ir: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(ledger, Ledger):
        raise WriteProtocolError("ledger must be Ledger")
    if mode not in {"atomic", "best_effort"}:
        raise WriteProtocolError("mode must be 'atomic' or 'best_effort'")
    norm_requests = _normalize_accept_requests(requests)
    if not norm_requests:
        return []

    ordered_indexes, dep_keys_by_index, key_to_indexes = _topological_request_order(norm_requests)
    results: list[dict[str, Any] | None] = [None] * len(norm_requests)

    blocked_keys: set[str] = set()
    accepted_entity_refs: dict[str, str] = {}
    written_asrt_ids_by_index: dict[int, list[str]] = {}
    processed_indexes: list[int] = []

    for idx in ordered_indexes:
        req = norm_requests[idx]
        candidate = req.candidate_set
        candidate_key = candidate.candidate_key
        deps_in_batch = [dep for dep in dep_keys_by_index[idx] if dep in key_to_indexes]
        if mode == "best_effort" and any(dep in blocked_keys for dep in deps_in_batch):
            results[idx] = _accept_many_item(
                candidate=candidate,
                state="BLOCKED_DEPENDENCY",
                entity_ref=None,
                error_code="BLOCKED_DEPENDENCY",
                error_message="dependency candidate failed or is blocked",
            )
            blocked_keys.add(candidate_key)
            processed_indexes.append(idx)
            continue

        call_options = AcceptOptions(
            approved_by=req.approved_by,
            note=req.note,
            dry_run=False,
            identity_override=req.identity_override,
        )
        try:
            result = accept_candidate_set(
                ledger=ledger,
                candidate_set=candidate,
                options=call_options,
                derived_rule_id=candidate.derivation_id,
                derived_rule_version=candidate.derivation_version,
                schema_digest_token=schema_digest_token,
                policy_digest_token=policy_digest_token,
                schema_ir=schema_ir,
                resolved_candidate_refs=accepted_entity_refs,
            )
        except Exception as exc:
            code = _error_code_from_exception(exc)
            state = "FAILED_VALIDATION" if isinstance(exc, WriteProtocolError) else "FAILED_RUNTIME"
            results[idx] = _accept_many_item(
                candidate=candidate,
                state=state,
                entity_ref=None,
                error_code=code,
                error_message=str(exc),
            )
            blocked_keys.add(candidate_key)
            processed_indexes.append(idx)
            if mode == "atomic":
                _rollback_atomic_accept_many(
                    ledger=ledger,
                    results=results,
                    processed_indexes=processed_indexes,
                    written_asrt_ids_by_index=written_asrt_ids_by_index,
                    failed_index=idx,
                )
                _fill_unprocessed_atomic_abort(
                    results=results,
                    requests=norm_requests,
                )
                return [item for item in results if isinstance(item, dict)]
            continue

        asrt_ids = [row["asrt_id"] for row in result.written_assertions if row.get("asrt_id") != "<dry_run>"]
        if asrt_ids:
            written_asrt_ids_by_index[idx] = asrt_ids
        state = "ACCEPTED"
        if result.skipped_reason_counts.get("duplicate", 0) > 0:
            if idempotent_duplicate_ok:
                state = "DUPLICATE"
            else:
                results[idx] = _accept_many_item(
                    candidate=candidate,
                    state="FAILED_VALIDATION",
                    entity_ref=result.entity_ref,
                    error_code="DUPLICATE_NOT_ALLOWED",
                    error_message="duplicate candidate encountered while idempotent_duplicate_ok=False",
                )
                blocked_keys.add(candidate_key)
                processed_indexes.append(idx)
                if mode == "atomic":
                    _rollback_atomic_accept_many(
                        ledger=ledger,
                        results=results,
                        processed_indexes=processed_indexes,
                        written_asrt_ids_by_index=written_asrt_ids_by_index,
                        failed_index=idx,
                    )
                    _fill_unprocessed_atomic_abort(
                        results=results,
                        requests=norm_requests,
                    )
                    return [item for item in results if isinstance(item, dict)]
                continue
        if isinstance(result.entity_ref, str) and result.entity_ref:
            accepted_entity_refs[candidate_key] = result.entity_ref
        results[idx] = _accept_many_item(
            candidate=candidate,
            state=state,
            entity_ref=result.entity_ref,
            error_code=None,
            error_message=None,
        )
        processed_indexes.append(idx)

    return [item for item in results if isinstance(item, dict)]


def _accept_many_item(
    *,
    candidate: CandidateSet,
    state: str,
    entity_ref: str | None,
    error_code: str | None,
    error_message: str | None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "candidate_key": candidate.candidate_key,
        "state": state,
        "entity_ref": entity_ref,
        "error": None
        if error_code is None
        else {"code": error_code, "message": error_message or error_code},
    }


def _normalize_accept_requests(
    requests: list[AcceptRequest | CandidateSet | dict[str, Any]],
) -> list[AcceptRequest]:
    if not isinstance(requests, list):
        raise WriteProtocolError("requests must be list")
    out: list[AcceptRequest] = []
    for idx, item in enumerate(requests):
        if isinstance(item, AcceptRequest):
            out.append(item)
            continue
        if isinstance(item, CandidateSet):
            out.append(AcceptRequest(candidate_set=item))
            continue
        if not isinstance(item, dict):
            raise WriteProtocolError(f"requests[{idx}] must be AcceptRequest|CandidateSet|object")
        candidate_raw = item.get("candidate_set", item.get("candidate"))
        if not isinstance(candidate_raw, CandidateSet):
            raise WriteProtocolError(f"requests[{idx}].candidate_set must be CandidateSet")
        identity_override = item.get("identity_override")
        if identity_override is not None and not isinstance(identity_override, dict):
            raise WriteProtocolError(f"requests[{idx}].identity_override must be object when provided")
        approved_by = item.get("approved_by")
        note = item.get("note")
        if approved_by is not None and not isinstance(approved_by, str):
            raise WriteProtocolError(f"requests[{idx}].approved_by must be string when provided")
        if note is not None and not isinstance(note, str):
            raise WriteProtocolError(f"requests[{idx}].note must be string when provided")
        out.append(
            AcceptRequest(
                candidate_set=candidate_raw,
                identity_override=dict(identity_override) if isinstance(identity_override, dict) else None,
                approved_by=approved_by,
                note=note,
            )
        )
    return out


def _topological_request_order(
    requests: list[AcceptRequest],
) -> tuple[list[int], dict[int, set[str]], dict[str, list[int]]]:
    key_to_indexes: dict[str, list[int]] = defaultdict(list)
    dep_keys_by_index: dict[int, set[str]] = {}
    dep_keys_by_key: dict[str, set[str]] = defaultdict(set)

    for idx, req in enumerate(requests):
        cand = req.candidate_set
        key_to_indexes[cand.candidate_key].append(idx)
        deps = extract_candidate_refs(cand)
        dep_keys_by_index[idx] = deps
        dep_keys_by_key[cand.candidate_key].update(deps)

    node_keys = set(key_to_indexes.keys())
    in_degree: dict[str, int] = {key: 0 for key in node_keys}
    outgoing: dict[str, set[str]] = {key: set() for key in node_keys}
    for key, deps in dep_keys_by_key.items():
        for dep in deps:
            if dep not in node_keys:
                continue
            in_degree[key] += 1
            outgoing[dep].add(key)

    queue: deque[str] = deque(sorted([key for key, deg in in_degree.items() if deg == 0]))
    ordered_keys: list[str] = []
    while queue:
        key = queue.popleft()
        ordered_keys.append(key)
        for to_key in sorted(outgoing[key]):
            in_degree[to_key] -= 1
            if in_degree[to_key] == 0:
                queue.append(to_key)

    if len(ordered_keys) != len(node_keys):
        raise WriteProtocolError("CANDIDATE_DEPENDENCY_CYCLE: candidate dependency graph has cycle")

    ordered_indexes: list[int] = []
    for key in ordered_keys:
        ordered_indexes.extend(key_to_indexes[key])
    return ordered_indexes, dep_keys_by_index, key_to_indexes


def _rollback_atomic_accept_many(
    *,
    ledger: Ledger,
    results: list[dict[str, Any] | None],
    processed_indexes: list[int],
    written_asrt_ids_by_index: dict[int, list[str]],
    failed_index: int,
) -> None:
    for idx in processed_indexes:
        for asrt_id in written_asrt_ids_by_index.get(idx, []):
            retract_by_asrt(
                ledger=ledger,
                revoked_asrt_id=asrt_id,
                meta={
                    "source": "derivation.accept_many.rollback",
                    "failed_candidate_id": results[failed_index]["candidate_id"] if isinstance(results[failed_index], dict) else "",
                },
            )
    for idx in processed_indexes:
        row = results[idx]
        if not isinstance(row, dict):
            continue
        if row.get("state") != "ACCEPTED":
            continue
        results[idx] = {
            "candidate_id": row.get("candidate_id"),
            "candidate_key": row.get("candidate_key"),
            "state": "FAILED_RUNTIME",
            "entity_ref": None,
            "error": {
                "code": "ATOMIC_ROLLBACK",
                "message": "atomic accept_many rolled back due to batch failure",
            },
        }


def _fill_unprocessed_atomic_abort(
    *,
    results: list[dict[str, Any] | None],
    requests: list[AcceptRequest],
) -> None:
    for idx, row in enumerate(results):
        if isinstance(row, dict):
            continue
        candidate = requests[idx].candidate_set
        results[idx] = _accept_many_item(
            candidate=candidate,
            state="BLOCKED_DEPENDENCY",
            entity_ref=None,
            error_code="ATOMIC_ABORTED",
            error_message="atomic accept_many aborted before this candidate was executed",
        )


def _error_code_from_exception(exc: Exception) -> str:
    message = str(exc)
    if ":" in message:
        head, _ = message.split(":", 1)
        if head and head.strip().isupper():
            return head.strip()
    if isinstance(exc, WriteProtocolError):
        return "WRITE_PROTOCOL_ERROR"
    return type(exc).__name__


def _is_v2_entity_payload(payload: dict[str, Any]) -> bool:
    return (
        isinstance(payload.get("entity_type"), str)
        and isinstance(payload.get("identity_fields"), list)
        and isinstance(payload.get("resolved_identity"), dict)
        and isinstance(payload.get("missing_identity_fields"), list)
    )


def _accept_fact_candidate_v1(
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
        "derivation_id": candidate_set.derivation_id,
        "derivation_version": candidate_set.derivation_version,
        "run_id": candidate_set.run_id,
        "materialize_id": materialize_id,
        "key_tuple_digest": candidate_set.key_tuple_digest,
        "cand_key_digest": cand_key_digest,
        "support_digest": candidate_set.support_digest,
        "support_kind": candidate_set.support_kind,
        "candidate_id": candidate_set.candidate_id,
        "candidate_key": candidate_set.candidate_key,
        "candidate_kind": candidate_set.candidate_kind,
        "accepted_at": now_epoch_nanos(),
    }
    if isinstance(schema_digest_token, str) and schema_digest_token:
        write_meta["schema_digest"] = schema_digest_token
    if isinstance(policy_digest_token, str) and policy_digest_token:
        write_meta["policy_digest"] = policy_digest_token
    if options.approved_by is not None:
        write_meta["approved_by"] = options.approved_by
        write_meta["accepted_by"] = options.approved_by
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


def _accept_fact_candidate_v2(
    *,
    ledger: Ledger,
    candidate_set: CandidateSet,
    payload: dict[str, Any],
    options: AcceptOptions,
    derived_rule_id: str,
    derived_rule_version: str,
    schema_digest_token: str | None = None,
    policy_digest_token: str | None = None,
    resolved_candidate_refs: dict[str, str] | None = None,
) -> AcceptResult:
    terms = payload.get("terms")
    if not isinstance(terms, list):
        raise WriteProtocolError("INVALID_TERMS: fact candidate payload.terms must be list")
    pred_id = payload.get("pred_id")
    if not isinstance(pred_id, str) or not pred_id:
        pred_id = candidate_set.target

    e_ref, rest_terms = _resolve_fact_terms(
        ledger=ledger,
        terms=terms,
        resolved_candidate_refs=resolved_candidate_refs,
    )
    return _accept_fact_claim(
        ledger=ledger,
        candidate_set=candidate_set,
        pred_id=pred_id,
        e_ref=e_ref,
        rest_terms=rest_terms,
        options=options,
        derived_rule_id=derived_rule_id,
        derived_rule_version=derived_rule_version,
        schema_digest_token=schema_digest_token,
        policy_digest_token=policy_digest_token,
    )


def _accept_fact_claim(
    *,
    ledger: Ledger,
    candidate_set: CandidateSet,
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],
    options: AcceptOptions,
    derived_rule_id: str,
    derived_rule_version: str,
    schema_digest_token: str | None,
    policy_digest_token: str | None,
) -> AcceptResult:
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
                    "pred_id": pred_id,
                    "key_tuple_digest": candidate_set.key_tuple_digest,
                }
            ],
            skipped_reason_counts={},
        )

    existing_written = _find_existing_claim_assertions_v2(
        ledger=ledger,
        pred_id=pred_id,
        e_ref=e_ref,
        rest_terms=rest_terms,
        key_tuple_digest=candidate_set.key_tuple_digest,
    )
    if existing_written:
        _assert_duplicate_meta_compatible(ledger=ledger, written_assertions=existing_written, options=options)
        entity_ref = _entity_ref_for_duplicate(
            ledger=ledger,
            written_assertions=existing_written,
            fallback=e_ref,
        )
        return AcceptResult(
            materialize_id=computed_materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"duplicate": 1},
            entity_ref=entity_ref if candidate_set.candidate_kind == "entity" else None,
        )

    cand_key_digest = _compute_cand_key_digest(candidate_set.target, candidate_set.key_tuple_digest)
    write_meta = _build_base_write_meta(
        candidate_set=candidate_set,
        options=options,
        derived_rule_id=derived_rule_id,
        derived_rule_version=derived_rule_version,
        schema_digest_token=schema_digest_token,
        policy_digest_token=policy_digest_token,
        materialize_id=computed_materialize_id,
        cand_key_digest=cand_key_digest,
    )
    write_meta["materialize_kind"] = "fact"
    write_meta["subject_e_ref"] = e_ref

    asrt_id = set_field(
        ledger=ledger,
        pred_id=pred_id,
        e_ref=e_ref,
        rest_terms=rest_terms,
        meta=write_meta,
    )
    return AcceptResult(
        materialize_id=computed_materialize_id,
        run_id=candidate_set.run_id,
        accepted_count=1,
        skipped_count=0,
        written_assertions=[
            {
                "asrt_id": asrt_id,
                "pred_id": pred_id,
                "key_tuple_digest": candidate_set.key_tuple_digest,
            }
        ],
        skipped_reason_counts={},
    )


def _accept_entity_candidate_v2(
    *,
    ledger: Ledger,
    candidate_set: CandidateSet,
    payload: dict[str, Any],
    options: AcceptOptions,
    derived_rule_id: str,
    derived_rule_version: str,
    schema_digest_token: str | None = None,
    policy_digest_token: str | None = None,
    schema_ir: dict[str, Any] | None = None,
) -> AcceptResult:
    entity_type = payload.get("entity_type", candidate_set.target)
    if not isinstance(entity_type, str) or not entity_type:
        raise WriteProtocolError("ENTITY_TYPE_MISSING: entity candidate payload.entity_type must be non-empty string")
    identity_fields_raw = payload.get("identity_fields")
    if not isinstance(identity_fields_raw, list):
        raise WriteProtocolError("IDENTITY_FIELDS_INVALID: entity candidate payload.identity_fields must be list")
    identity_fields = [str(name) for name in identity_fields_raw if isinstance(name, str) and name]
    if not identity_fields:
        schema_identity = _schema_identity_fields(schema_ir=schema_ir, entity_type=entity_type)
        identity_fields = [name for name, _ in schema_identity]
    if not identity_fields:
        raise WriteProtocolError("IDENTITY_FIELDS_EMPTY: identity_fields must not be empty")

    resolved_identity_raw = payload.get("resolved_identity")
    if not isinstance(resolved_identity_raw, dict):
        raise WriteProtocolError("RESOLVED_IDENTITY_INVALID: payload.resolved_identity must be object")
    resolved_identity = dict(resolved_identity_raw)
    missing_identity_raw = payload.get("missing_identity_fields")
    if not isinstance(missing_identity_raw, list):
        raise WriteProtocolError("MISSING_IDENTITY_FIELDS_INVALID: payload.missing_identity_fields must be list")
    missing_identity_fields = {str(name) for name in missing_identity_raw if isinstance(name, str) and name}

    identity_types = payload.get("identity_types")
    identity_type_map: dict[str, str] = {}
    if isinstance(identity_types, dict):
        for name, tag in identity_types.items():
            if isinstance(name, str) and isinstance(tag, str):
                identity_type_map[name] = tag
    for name, tag in _schema_identity_fields(schema_ir=schema_ir, entity_type=entity_type):
        identity_type_map.setdefault(name, tag)
    for name in identity_fields:
        identity_type_map.setdefault(name, "string")

    override = options.identity_override
    if override is None:
        override = {}
    if not isinstance(override, dict):
        raise WriteProtocolError("IDENTITY_OVERRIDE_INVALID: identity_override must be object")

    unknown_override_keys = sorted([key for key in override.keys() if key not in set(identity_fields)])
    if unknown_override_keys:
        raise WriteProtocolError(
            f"IDENTITY_FIELD_UNKNOWN: identity_override contains unknown fields: {unknown_override_keys}"
        )
    conflict_keys = sorted([key for key in override.keys() if key in resolved_identity])
    if conflict_keys:
        raise WriteProtocolError(
            f"IDENTITY_FIELD_CONFLICT: identity_override cannot include resolved fields: {conflict_keys}"
        )
    non_missing_override = sorted([key for key in override.keys() if key not in missing_identity_fields])
    if non_missing_override:
        raise WriteProtocolError(
            f"IDENTITY_FIELD_CONFLICT: identity_override only accepts missing fields: {non_missing_override}"
        )

    merged_identity = dict(resolved_identity)
    merged_identity.update(override)
    missing_after = [field for field in identity_fields if field not in merged_identity]
    if missing_after:
        raise WriteProtocolError(f"IDENTITY_INCOMPLETE: missing identity fields: {missing_after}")

    identity_tuples = [
        (field, identity_type_map[field], merged_identity[field])
        for field in identity_fields
    ]
    entity_ref = encode_idref_v1(entity_type, identity_tuples)
    exists_pred_id = _entity_exists_pred_id(schema_ir=schema_ir, entity_type=entity_type)

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
                    "pred_id": exists_pred_id,
                    "key_tuple_digest": candidate_set.key_tuple_digest,
                }
            ],
            skipped_reason_counts={},
            entity_ref=entity_ref,
        )

    existing_written = _find_existing_claim_assertions_v2(
        ledger=ledger,
        pred_id=exists_pred_id,
        e_ref=entity_ref,
        rest_terms=[],
        key_tuple_digest=candidate_set.key_tuple_digest,
    )
    if existing_written:
        _assert_duplicate_meta_compatible(ledger=ledger, written_assertions=existing_written, options=options)
        return AcceptResult(
            materialize_id=computed_materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"duplicate": 1},
            entity_ref=entity_ref,
        )

    cand_key_digest = _compute_cand_key_digest(candidate_set.target, candidate_set.key_tuple_digest)
    write_meta = _build_base_write_meta(
        candidate_set=candidate_set,
        options=options,
        derived_rule_id=derived_rule_id,
        derived_rule_version=derived_rule_version,
        schema_digest_token=schema_digest_token,
        policy_digest_token=policy_digest_token,
        materialize_id=computed_materialize_id,
        cand_key_digest=cand_key_digest,
    )
    write_meta["materialize_kind"] = "entity"
    write_meta["entity_type"] = entity_type
    write_meta["entity_ref"] = entity_ref
    if override:
        write_meta["identity_override_digest"] = _digest_json(override)

    asrt_id = set_field(
        ledger=ledger,
        pred_id=exists_pred_id,
        e_ref=entity_ref,
        rest_terms=[],
        meta=write_meta,
    )
    return AcceptResult(
        materialize_id=computed_materialize_id,
        run_id=candidate_set.run_id,
        accepted_count=1,
        skipped_count=0,
        written_assertions=[
            {
                "asrt_id": asrt_id,
                "pred_id": exists_pred_id,
                "key_tuple_digest": candidate_set.key_tuple_digest,
            }
        ],
        skipped_reason_counts={},
        entity_ref=entity_ref,
    )


def _build_base_write_meta(
    *,
    candidate_set: CandidateSet,
    options: AcceptOptions,
    derived_rule_id: str,
    derived_rule_version: str,
    schema_digest_token: str | None,
    policy_digest_token: str | None,
    materialize_id: str,
    cand_key_digest: str,
) -> dict[str, Any]:
    accepted_at = now_epoch_nanos()
    write_meta: dict[str, Any] = {
        "source": "derivation.accept",
        "source_loc": f"{derived_rule_id}:{derived_rule_version}",
        "trace_id": candidate_set.run_id,
        "derived_rule_id": derived_rule_id,
        "derived_rule_version": derived_rule_version,
        "derivation_id": candidate_set.derivation_id,
        "derivation_version": candidate_set.derivation_version,
        "run_id": candidate_set.run_id,
        "materialize_id": materialize_id,
        "key_tuple_digest": candidate_set.key_tuple_digest,
        "cand_key_digest": cand_key_digest,
        "support_digest": candidate_set.support_digest,
        "support_kind": candidate_set.support_kind,
        "candidate_id": candidate_set.candidate_id,
        "candidate_key": candidate_set.candidate_key,
        "candidate_kind": candidate_set.candidate_kind,
        "accepted_at": accepted_at,
    }
    if isinstance(schema_digest_token, str) and schema_digest_token:
        write_meta["schema_digest"] = schema_digest_token
    if isinstance(policy_digest_token, str) and policy_digest_token:
        write_meta["policy_digest"] = policy_digest_token
    if options.approved_by is not None:
        write_meta["approved_by"] = options.approved_by
        write_meta["accepted_by"] = options.approved_by
        write_meta["accepted_by"] = options.approved_by
    if options.note is not None:
        write_meta["note"] = options.note
    return write_meta


def _resolve_fact_terms(
    *,
    ledger: Ledger,
    terms: list[Any],
    resolved_candidate_refs: dict[str, str] | None,
) -> tuple[str, list[tuple[str, Any]]]:
    if not terms:
        raise WriteProtocolError("INVALID_SUBJECT_SLOT: terms[0] must be subject entity term")
    subject = terms[0]
    subject_e_ref = _resolve_entity_term(
        ledger=ledger,
        term=subject,
        resolved_candidate_refs=resolved_candidate_refs,
    )
    rest_terms: list[tuple[str, Any]] = []
    for idx, term in enumerate(terms[1:], start=1):
        rest_terms.append(
            _resolve_non_subject_term(
                ledger=ledger,
                term=term,
                resolved_candidate_refs=resolved_candidate_refs,
                term_index=idx,
            )
        )
    return subject_e_ref, rest_terms


def _resolve_entity_term(
    *,
    ledger: Ledger,
    term: Any,
    resolved_candidate_refs: dict[str, str] | None,
) -> str:
    if isinstance(term, dict):
        kind = term.get("kind")
        if kind == "entity_ref":
            value = term.get("value")
            if isinstance(value, str) and value.startswith("idref_v1:"):
                return value
            raise WriteProtocolError("INVALID_SUBJECT_SLOT: entity_ref term value must be idref_v1 token")
        if kind == "candidate_ref":
            candidate_key = term.get("candidate_key")
            if not isinstance(candidate_key, str) or not candidate_key:
                raise WriteProtocolError("INVALID_SUBJECT_SLOT: candidate_ref term missing candidate_key")
            resolved = _resolve_candidate_key_to_entity_ref(
                ledger=ledger,
                candidate_key=candidate_key,
                resolved_candidate_refs=resolved_candidate_refs,
            )
            if resolved is None:
                raise WriteProtocolError(
                    f"UNRESOLVED_DEPENDENCY: candidate_ref not accepted: {candidate_key}"
                )
            return resolved
    raise WriteProtocolError("INVALID_SUBJECT_SLOT: terms[0] must be entity_ref or candidate_ref")


def _resolve_non_subject_term(
    *,
    ledger: Ledger,
    term: Any,
    resolved_candidate_refs: dict[str, str] | None,
    term_index: int,
) -> tuple[str, Any]:
    if isinstance(term, tuple) and len(term) == 2:
        return str(term[0]), term[1]
    if not isinstance(term, dict):
        raise WriteProtocolError(f"INVALID_TERM: terms[{term_index}] must be object")
    kind = term.get("kind")
    if kind == "literal":
        tag = term.get("tag")
        if not isinstance(tag, str) or not tag:
            raise WriteProtocolError(f"INVALID_TERM: terms[{term_index}].tag must be non-empty string")
        return tag, term.get("value")
    if kind == "entity_ref":
        value = term.get("value")
        if not isinstance(value, str) or not value.startswith("idref_v1:"):
            raise WriteProtocolError(
                f"INVALID_TERM: terms[{term_index}] entity_ref value must be idref_v1 token"
            )
        return "entity_ref", value
    if kind == "candidate_ref":
        candidate_key = term.get("candidate_key")
        if not isinstance(candidate_key, str) or not candidate_key:
            raise WriteProtocolError(f"INVALID_TERM: terms[{term_index}] candidate_ref missing candidate_key")
        resolved = _resolve_candidate_key_to_entity_ref(
            ledger=ledger,
            candidate_key=candidate_key,
            resolved_candidate_refs=resolved_candidate_refs,
        )
        if resolved is None:
            raise WriteProtocolError(
                f"UNRESOLVED_DEPENDENCY: candidate_ref not accepted: {candidate_key}"
            )
        return "entity_ref", resolved
    raise WriteProtocolError(f"INVALID_TERM: unsupported term kind at terms[{term_index}]")


def _resolve_candidate_key_to_entity_ref(
    *,
    ledger: Ledger,
    candidate_key: str,
    resolved_candidate_refs: dict[str, str] | None,
) -> str | None:
    if resolved_candidate_refs is not None:
        in_batch = resolved_candidate_refs.get(candidate_key)
        if isinstance(in_batch, str) and in_batch:
            return in_batch

    refs: set[str] = set()
    for row in ledger.find_meta(key="candidate_key", kind="str"):
        if row.value != candidate_key:
            continue
        if ledger.has_active_revocation(row.asrt_id):
            continue
        claim = ledger.get_claim(row.asrt_id)
        if claim is None:
            continue
        candidate_kind = _meta_value(ledger, row.asrt_id, "candidate_kind")
        materialize_kind = _meta_value(ledger, row.asrt_id, "materialize_kind")
        if candidate_kind != "entity" and materialize_kind not in {"entity", "record"}:
            continue
        entity_ref = _meta_value(ledger, row.asrt_id, "entity_ref")
        if isinstance(entity_ref, str) and entity_ref:
            refs.add(entity_ref)
        elif isinstance(claim.e_ref, str) and claim.e_ref.startswith("idref_v1:"):
            refs.add(claim.e_ref)
    if not refs:
        return None
    if len(refs) > 1:
        raise WriteProtocolError(
            f"CANDIDATE_REF_CONFLICT: candidate_key maps to multiple entity_ref values: {candidate_key}"
        )
    return next(iter(refs))


def _find_existing_claim_assertions_v2(
    *,
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],
    key_tuple_digest: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for claim in ledger.find_claims(pred_id=pred_id, e_ref=e_ref):
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        if claim.rest_terms != rest_terms:
            continue
        rows.append(
            {
                "asrt_id": claim.asrt_id,
                "pred_id": claim.pred_id,
                "key_tuple_digest": key_tuple_digest,
            }
        )
    rows.sort(key=lambda row: (row["pred_id"], row["asrt_id"]))
    return rows


def _entity_ref_for_duplicate(
    *,
    ledger: Ledger,
    written_assertions: list[dict[str, str]],
    fallback: str | None = None,
) -> str | None:
    for row in written_assertions:
        entity_ref = _meta_value(ledger, row["asrt_id"], "entity_ref")
        if isinstance(entity_ref, str) and entity_ref:
            return entity_ref
        claim = ledger.get_claim(row["asrt_id"])
        if claim is not None and isinstance(claim.e_ref, str) and claim.e_ref.startswith("idref_v1:"):
            return claim.e_ref
    return fallback


def _schema_identity_fields(
    *,
    schema_ir: dict[str, Any] | None,
    entity_type: str,
) -> list[tuple[str, str]]:
    if not isinstance(schema_ir, dict):
        return []
    entities = schema_ir.get("entities")
    if not isinstance(entities, list):
        return []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        if entity.get("entity_type") != entity_type:
            continue
        identity_fields = entity.get("identity_fields")
        if not isinstance(identity_fields, list):
            return []
        out: list[tuple[str, str]] = []
        for field in identity_fields:
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            tag = field.get("type_domain")
            if isinstance(name, str) and name and isinstance(tag, str) and tag:
                out.append((name, tag))
        return out
    return []


def _entity_exists_pred_id(
    *,
    schema_ir: dict[str, Any] | None,
    entity_type: str,
) -> str:
    default_pred_id = f"{entity_type}:exists"
    if not isinstance(schema_ir, dict):
        return default_pred_id
    predicates = schema_ir.get("predicates")
    if not isinstance(predicates, list):
        return default_pred_id
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        if pred.get("owner_type") != entity_type:
            continue
        if pred.get("is_record_exists") is not True and pred.get("is_entity_exists") is not True:
            continue
        pred_id = pred.get("pred_id")
        if isinstance(pred_id, str) and pred_id:
            return pred_id
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        pred_id = pred.get("pred_id")
        if pred_id == default_pred_id:
            return default_pred_id
    return default_pred_id


def _digest_json(value: Any) -> str:
    try:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise WriteProtocolError(f"IDENTITY_OVERRIDE_INVALID: identity_override must be JSON-serializable: {exc}") from exc
    return sha256_token(payload)


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
    stage_state = read_record_stage_status(
        ledger=ledger,
        record_e_ref=record_e_ref,
        materialize_id=materialize_id,
        path="$.accept.record.marker",
    )
    progress_before = _record_materialization_progress(
        ledger=ledger,
        existing_written=existing_written,
        expected_roles=roles,
        record_exists_pred_id=record_exists_pred_id,
    )

    if stage_state["status"] == RECORD_STAGE_ABORTED:
        return AcceptResult(
            materialize_id=materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"aborted": 1},
            diagnostics=[
                *stage_state["diag"],
                _diag_item(
                    code="RECORD_REJECT_ABORTED",
                    severity="error",
                    path="$.accept.record",
                    message="record accept is aborted and cannot be retried",
                    data={
                        "stage_before": stage_state["status"],
                        "stage_after": stage_state["status"],
                        "expected_digest": expected_record_digest,
                        "marker_digest": stage_state.get("digest"),
                        "missing_roles_count": progress_before["missing_roles_count"],
                        "extra_roles_count": progress_before["extra_roles_count"],
                    },
                )
            ],
        )

    if stage_state["status"] == "conflict":
        return AcceptResult(
            materialize_id=materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"conflict": 1},
            diagnostics=list(stage_state["diag"]),
        )

    if stage_state["status"] == RECORD_STAGE_COMMITTED:
        committed_digest = stage_state.get("digest")
        if committed_digest != expected_record_digest:
            _write_record_stage_marker(
                ledger=ledger,
                record_e_ref=record_e_ref,
                materialize_id=materialize_id,
                stage=RECORD_STAGE_ABORTED,
                record_digest=expected_record_digest,
                marker_meta=_record_stage_marker_meta(
                    write_meta_base={},
                    record_type=record_type,
                    materialize_id=materialize_id,
                    record_e_ref=record_e_ref,
                    key_tuple_digest=candidate_set.key_tuple_digest,
                    cand_key_digest=cand_key_digest,
                    record_digest=expected_record_digest,
                    roles_count_expected=len(roles),
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
                        code="RECORD_COMMITTED_DIGEST_CONFLICT",
                        severity="error",
                        path="$.accept.record",
                        message="committed record digest conflicts with candidate digest",
                        data={
                            "diag_source": "action",
                            "stage_before": stage_state["status"],
                            "stage_after": RECORD_STAGE_ABORTED,
                            "expected_digest": committed_digest,
                            "attempted_digest": expected_record_digest,
                        },
                    ),
                    _diag_item(
                        code="RECORD_MARKER_CONFLICT_COMMITTED_AND_ABORTED",
                        severity="error",
                        path="$.accept.record.marker",
                        message="record enters marker conflict state (committed and aborted markers)",
                        data={
                            "diag_source": "action",
                            "reason": "committed_and_aborted",
                            "committed_digest": committed_digest,
                            "attempted_digest": expected_record_digest,
                        },
                    ),
                ],
            )
        if not progress_before["is_complete"] or progress_before["actual_digest"] != expected_record_digest:
            _write_record_stage_marker(
                ledger=ledger,
                record_e_ref=record_e_ref,
                materialize_id=materialize_id,
                stage=RECORD_STAGE_ABORTED,
                record_digest=expected_record_digest,
                marker_meta=_record_stage_marker_meta(
                    write_meta_base={},
                    record_type=record_type,
                    materialize_id=materialize_id,
                    record_e_ref=record_e_ref,
                    key_tuple_digest=candidate_set.key_tuple_digest,
                    cand_key_digest=cand_key_digest,
                    record_digest=expected_record_digest,
                    roles_count_expected=len(roles),
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
                            "stage_before": stage_state["status"],
                            "stage_after": RECORD_STAGE_ABORTED,
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
        "derivation_id": candidate_set.derivation_id,
        "derivation_version": candidate_set.derivation_version,
        "run_id": candidate_set.run_id,
        "materialize_id": materialize_id,
        "key_tuple_digest": candidate_set.key_tuple_digest,
        "cand_key_digest": cand_key_digest,
        "support_digest": candidate_set.support_digest,
        "support_kind": candidate_set.support_kind,
        "materialize_kind": "record",
        "candidate_id": candidate_set.candidate_id,
        "candidate_key": candidate_set.candidate_key,
        "candidate_kind": candidate_set.candidate_kind,
        "accepted_at": now_epoch_nanos(),
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
        roles_count_expected=len(roles),
    )
    _write_record_stage_marker(
        ledger=ledger,
        record_e_ref=record_e_ref,
        materialize_id=materialize_id,
        stage=RECORD_STAGE_BEGIN,
        record_digest=expected_record_digest,
        marker_meta=marker_meta,
    )

    if progress_before["extra_roles_count"] > 0:
        _write_record_stage_marker(
            ledger=ledger,
            record_e_ref=record_e_ref,
            materialize_id=materialize_id,
            stage=RECORD_STAGE_ABORTED,
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
                        "stage_before": stage_state["status"],
                        "stage_after": RECORD_STAGE_ABORTED,
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
        stage=RECORD_STAGE_ROLES_WRITTEN,
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
            stage=RECORD_STAGE_ABORTED,
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
                        "stage_before": stage_state["status"],
                        "stage_after": RECORD_STAGE_ABORTED,
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
        stage=RECORD_STAGE_COMMITTED,
        record_digest=expected_record_digest,
        marker_meta=marker_meta,
    )
    existing_written_after.sort(key=lambda row: (row["pred_id"], row["asrt_id"]))
    diagnostics: list[dict[str, Any]] = []
    if stage_state["status"] in {RECORD_STAGE_BEGIN, RECORD_STAGE_ROLES_WRITTEN} or progress_before["exists_missing"] or progress_before["missing_roles_count"] > 0:
        diagnostics.append(
            _diag_item(
                code="ACCEPT_RECORD_RECOVERED_PARTIAL",
                severity="warning",
                path="$.accept.record",
                message="record accept recovered and finalized a partial materialization",
                data={
                    "stage_before": stage_state["status"],
                    "stage_after": RECORD_STAGE_COMMITTED,
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
    roles_count_expected: int,
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
        "roles_count_expected": roles_count_expected,
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
    if stage not in RECORD_STAGE_VALUES:
        raise WriteProtocolError(f"unsupported record stage marker: {stage}")
    return set_field(
        ledger=ledger,
        pred_id=RECORD_STAGE_MARKER_PRED_ID,
        e_ref=record_e_ref,
        rest_terms=[
            ("string", materialize_id),
            ("string", stage),
            ("string", record_digest),
        ],
        meta=marker_meta,
    )


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
