from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from typing import Any

from factgraph.core.derivation.candidates import CandidateSet, extract_candidate_refs
from factgraph.core.evidence.write_protocol import (
    _SYSTEM_MANAGED_META_KEYS,
    WriteProtocolError,
    now_epoch_nanos,
    retract_by_asrt,
    set_field,
)
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.store.ledger import Ledger

_META_PRIMARY_KEYS = {
    "run_id",
    "ingested_at",
    "accepted_at",
    "trace_id",
    "candidate_id",
    "candidate_key",
    "cand_key_digest",
    "key_tuple_digest",
    "materialize_id",
}


@dataclass(frozen=True)
class AcceptOptions:
    approved_by: str | None = None
    note: str | None = None
    dry_run: bool = False
    identity_override: dict[str, Any] | None = None
    # Caller-supplied business/actor provenance attached to every written derived
    # assertion. Persisted as ordinary meta rows; never overwrites protocol/system
    # meta keys. Used by callers (e.g. an authenticated write boundary) to record
    # who triggered a derivation, in which tenant, under which request.
    actor_meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class AcceptResult:
    run_id: str
    accepted_count: int
    skipped_count: int
    written_assertions: list[dict[str, Any]]
    skipped_reason_counts: dict[str, int]
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    diagnostics_contract_version: int = 1
    entity_ref: str | None = None
    candidate_id: str | None = None
    candidate_key: str | None = None


@dataclass(frozen=True)
class AcceptRequest:
    candidate_set: CandidateSet
    identity_override: dict[str, Any] | None = None
    approved_by: str | None = None
    note: str | None = None
    actor_meta: dict[str, Any] | None = None


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
        if not _is_v2_entity_payload(payload):
            raise WriteProtocolError(
                "ENTITY_PAYLOAD_INVALID: entity candidate payload must contain entity_type/identity_fields/resolved_identity/missing_identity_fields"
            )
        return _attach_candidate_identity(
            _accept_entity_candidate_v2(
                ledger=ledger,
                candidate_set=candidate_set,
                payload=payload,
                options=options,
                derived_rule_id=derived_rule_id,
                derived_rule_version=derived_rule_version,
                schema_digest_token=schema_digest_token,
                policy_digest_token=policy_digest_token,
                schema_ir=schema_ir,
            ),
            candidate_set,
        )
    if candidate_set.candidate_kind == "fact":
        if not isinstance(payload.get("terms"), list):
            raise WriteProtocolError("FACT_PAYLOAD_INVALID: fact candidate payload.terms must be list")
        return _attach_candidate_identity(
            _accept_fact_candidate_v2(
                ledger=ledger,
                candidate_set=candidate_set,
                payload=payload,
                options=options,
                derived_rule_id=derived_rule_id,
                derived_rule_version=derived_rule_version,
                schema_digest_token=schema_digest_token,
                policy_digest_token=policy_digest_token,
                resolved_candidate_refs=resolved_candidate_refs,
            ),
            candidate_set,
        )
    raise WriteProtocolError("candidate_kind must be 'fact' or 'entity'")


def _attach_candidate_identity(result: AcceptResult, candidate_set: CandidateSet) -> AcceptResult:
    return replace(
        result,
        candidate_id=candidate_set.candidate_id,
        candidate_key=candidate_set.candidate_key,
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
            actor_meta=req.actor_meta,
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
        actor_meta = item.get("actor_meta")
        if actor_meta is not None and not isinstance(actor_meta, dict):
            raise WriteProtocolError(f"requests[{idx}].actor_meta must be object when provided")
        out.append(
            AcceptRequest(
                candidate_set=candidate_raw,
                identity_override=dict(identity_override) if isinstance(identity_override, dict) else None,
                approved_by=approved_by,
                note=note,
                actor_meta=dict(actor_meta) if isinstance(actor_meta, dict) else None,
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
    if options.dry_run:
        return AcceptResult(
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

    cand_key_digest = _compute_cand_key_digest(candidate_set.target, candidate_set.key_tuple_digest)
    write_meta = _build_base_write_meta(
        candidate_set=candidate_set,
        options=options,
        derived_rule_id=derived_rule_id,
        derived_rule_version=derived_rule_version,
        schema_digest_token=schema_digest_token,
        policy_digest_token=policy_digest_token,
        cand_key_digest=cand_key_digest,
    )
    write_meta["subject_e_ref"] = e_ref

    actor_meta_keys = frozenset(options.actor_meta or {})
    existing_written = _find_existing_claim_assertions_v2(
        ledger=ledger,
        pred_id=pred_id,
        e_ref=e_ref,
        rest_terms=rest_terms,
        key_tuple_digest=candidate_set.key_tuple_digest,
        business_meta=_filter_business_meta(write_meta, actor_meta_keys),
        actor_meta_keys=actor_meta_keys,
    )
    if existing_written:
        _assert_duplicate_meta_compatible(ledger=ledger, written_assertions=existing_written, options=options)
        entity_ref = _entity_ref_for_duplicate(
            ledger=ledger,
            written_assertions=existing_written,
            fallback=e_ref,
        )
        return AcceptResult(
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"duplicate": 1},
            entity_ref=entity_ref if candidate_set.candidate_kind == "entity" else None,
        )

    asrt_id = set_field(
        ledger=ledger,
        pred_id=pred_id,
        e_ref=e_ref,
        rest_terms=rest_terms,
        meta=write_meta,
    )
    return AcceptResult(
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

    if options.dry_run:
        return AcceptResult(
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

    cand_key_digest = _compute_cand_key_digest(candidate_set.target, candidate_set.key_tuple_digest)
    write_meta = _build_base_write_meta(
        candidate_set=candidate_set,
        options=options,
        derived_rule_id=derived_rule_id,
        derived_rule_version=derived_rule_version,
        schema_digest_token=schema_digest_token,
        policy_digest_token=policy_digest_token,
        cand_key_digest=cand_key_digest,
    )
    write_meta["entity_type"] = entity_type
    write_meta["entity_ref"] = entity_ref
    if override:
        write_meta["identity_override_digest"] = _digest_json(override)

    actor_meta_keys = frozenset(options.actor_meta or {})
    existing_written = _find_existing_claim_assertions_v2(
        ledger=ledger,
        pred_id=exists_pred_id,
        e_ref=entity_ref,
        rest_terms=[],
        key_tuple_digest=candidate_set.key_tuple_digest,
        business_meta=_filter_business_meta(write_meta, actor_meta_keys),
        actor_meta_keys=actor_meta_keys,
    )
    if existing_written:
        _assert_duplicate_meta_compatible(ledger=ledger, written_assertions=existing_written, options=options)
        return AcceptResult(
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"duplicate": 1},
            entity_ref=entity_ref,
        )

    asrt_id = set_field(
        ledger=ledger,
        pred_id=exists_pred_id,
        e_ref=entity_ref,
        rest_terms=[],
        meta=write_meta,
    )
    return AcceptResult(
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
    if options.note is not None:
        write_meta["note"] = options.note
    _merge_actor_meta(write_meta, options.actor_meta)
    return write_meta


# Meta keys the write protocol manages itself; actor meta must never carry them.
_ACTOR_META_FORBIDDEN = {"ingested_at", "ingest_key", "revoked_asrt_id"}


def _merge_actor_meta(write_meta: dict[str, Any], actor_meta: dict[str, Any] | None) -> None:
    """Merge caller actor/business meta into the derived-assertion write meta.

    Additive only: protocol/system keys already present win and are never
    overwritten, and the write-protocol-managed keys are rejected outright — so
    actor provenance can ride a derived fact without corrupting its semantic meta.
    """
    if not actor_meta:
        return
    for key, value in actor_meta.items():
        if not isinstance(key, str) or not key:
            raise WriteProtocolError("actor_meta keys must be non-empty strings")
        if key in _ACTOR_META_FORBIDDEN:
            raise WriteProtocolError(f"actor_meta[{key}] is reserved and write-protocol-managed")
        if key in write_meta:
            continue  # never overwrite protocol/derivation meta
        write_meta[key] = value


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
    for row in ledger.effective_meta_rows(key="candidate_key", kind="str"):
        if row.value != candidate_key:
            continue
        if ledger.has_active_revocation(row.asrt_id):
            continue
        claim = ledger.get_claim(row.asrt_id)
        if claim is None:
            continue
        candidate_kind = _meta_value(ledger, row.asrt_id, "candidate_kind")
        if candidate_kind != "entity":
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
    business_meta: dict[str, Any],
    actor_meta_keys: frozenset[str] = frozenset(),
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for claim in ledger.find_claims(pred_id=pred_id, e_ref=e_ref):
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        if claim.rest_terms != rest_terms:
            continue
        if _business_meta_for_duplicate(ledger, claim.asrt_id, actor_meta_keys) != business_meta:
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


def _business_meta_for_duplicate(
    ledger: Ledger, asrt_id: str, actor_meta_keys: frozenset[str] = frozenset()
) -> dict[str, Any]:
    meta = {row.key: row.value for row in ledger.effective_meta_rows(asrt_id=asrt_id)}
    return _filter_business_meta(meta, actor_meta_keys)


def _filter_business_meta(
    meta: dict[str, Any], actor_meta_keys: frozenset[str] = frozenset()
) -> dict[str, Any]:
    # Actor/annotation provenance is NEVER part of a claim's business identity:
    # excluding it (on both sides of the duplicate comparison) keeps derived facts
    # content-addressed/idempotent even when the actor or request varies per accept.
    exclude = _META_PRIMARY_KEYS | _SYSTEM_MANAGED_META_KEYS | set(actor_meta_keys)
    return {
        key: value
        for key, value in meta.items()
        if key not in exclude
    }


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
        for identity_field in identity_fields:
            if not isinstance(identity_field, dict):
                continue
            name = identity_field.get("name")
            tag = identity_field.get("type_domain")
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
        if pred.get("is_entity_exists") is not True:
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


def _compute_cand_key_digest(target: str, key_tuple_digest: str) -> str:
    parts = [
        b"factpy\x00cand_key_v1\x00",
        target.encode("utf-8"),
        b"\x00",
        key_tuple_digest.encode("utf-8"),
        b"\x00",
    ]
    return sha256_token(b"".join(parts))


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


def _meta_value(ledger: Ledger, asrt_id: str, key: str) -> str | None:
    for row in ledger.effective_meta_rows(asrt_id=asrt_id, key=key):
        if isinstance(row.value, str):
            return row.value
    return None
