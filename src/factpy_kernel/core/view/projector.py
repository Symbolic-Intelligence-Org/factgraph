from __future__ import annotations

from typing import Any

from factpy_kernel.core.derivation.accept import (
    _RECORD_STAGE_ABORTED,
    _RECORD_STAGE_COMMITTED,
    _RECORD_STAGE_MARKER_PRED_ID,
)
from factpy_kernel.core.policy.active import is_active
from factpy_kernel.core.policy.chosen import (
    PolicyNonDeterminismError,
    choose_one,
    compute_chosen_for_predicate,
    group_key_for_claim,
)
from factpy_kernel.core.store.ledger import Claim, Ledger


class ViewProjectionError(Exception):
    pass


def _meta_str(ledger: Ledger, asrt_id: str, key: str) -> str | None:
    for row in ledger.find_meta(asrt_id=asrt_id, key=key):
        if isinstance(row.value, str):
            return row.value
    return None


def _parse_record_stage_marker(claim: Claim) -> tuple[str, str, str] | None:
    if claim.pred_id != _RECORD_STAGE_MARKER_PRED_ID:
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
    return materialize_id, stage, record_digest


def _build_record_commit_index(ledger: Ledger) -> dict[tuple[str, str], dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for claim in ledger.find_claims(pred_id=_RECORD_STAGE_MARKER_PRED_ID):
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        parsed = _parse_record_stage_marker(claim)
        if parsed is None:
            continue
        materialize_id, stage, record_digest = parsed
        key = (claim.e_ref, materialize_id)
        entry = by_key.setdefault(key, {"committed_digests": set(), "aborted_digests": set()})
        if stage == _RECORD_STAGE_COMMITTED:
            entry["committed_digests"].add(record_digest)
        elif stage == _RECORD_STAGE_ABORTED:
            entry["aborted_digests"].add(record_digest)
    return by_key


def _build_visible_record_claim_ids(ledger: Ledger) -> set[str]:
    commit_index = _build_record_commit_index(ledger)
    groups: dict[tuple[str, str], list[Claim]] = {}
    legacy_visible: set[str] = set()

    for claim in ledger.find_claims():
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        if _meta_str(ledger, claim.asrt_id, "materialize_kind") != "record":
            continue
        materialize_id = _meta_str(ledger, claim.asrt_id, "materialize_id")
        if not isinstance(materialize_id, str) or not materialize_id:
            continue
        record_digest = _meta_str(ledger, claim.asrt_id, "record_digest")
        if not isinstance(record_digest, str) or not record_digest:
            # Backward-compatibility for pre-staging records.
            legacy_visible.add(claim.asrt_id)
            continue
        groups.setdefault((claim.e_ref, materialize_id), []).append(claim)

    visible: set[str] = set(legacy_visible)
    for key, claims in groups.items():
        marker = commit_index.get(key)
        if not isinstance(marker, dict):
            continue
        if marker.get("aborted_digests"):
            continue
        committed_digests = marker.get("committed_digests")
        if not isinstance(committed_digests, set) or not committed_digests:
            continue
        committed_digest = sorted(str(d) for d in committed_digests)[0]
        # Require record exists row to be present before exposing any role rows.
        has_exists = False
        for claim in claims:
            claim_digest = _meta_str(ledger, claim.asrt_id, "record_digest")
            if claim_digest != committed_digest:
                continue
            if claim.rest_terms == []:
                has_exists = True
                break
        if not has_exists:
            continue
        for claim in claims:
            if _meta_str(ledger, claim.asrt_id, "record_digest") == committed_digest:
                visible.add(claim.asrt_id)
    return visible


def build_args_for_claim(ledger: Ledger, claim: Claim) -> tuple[Any, ...]:
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    if not isinstance(claim, Claim):
        raise TypeError("claim must be Claim")

    rows = ledger.find_claim_args(asrt_id=claim.asrt_id)
    if not rows:
        if claim.rest_terms:
            raise ViewProjectionError(f"missing claim_arg rows for asrt_id={claim.asrt_id}")
        return (claim.e_ref,)

    sorted_rows = sorted(rows, key=lambda row: row.idx)
    if len(sorted_rows) != len(claim.rest_terms):
        raise ViewProjectionError(
            f"claim_arg count mismatch for asrt_id={claim.asrt_id}"
        )

    for expected_idx, row in enumerate(sorted_rows):
        if row.idx != expected_idx:
            raise ViewProjectionError(
                f"claim_arg idx must be contiguous for asrt_id={claim.asrt_id}"
            )

    return (claim.e_ref, *[row.val_atom for row in sorted_rows])


def project_view_facts(
    ledger: Ledger,
    schema_ir: dict,
    *,
    temporal_view: str = "record",
) -> dict[str, list[tuple[Any, ...]]]:
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    if not isinstance(schema_ir, dict):
        raise ViewProjectionError("schema_ir must be dict")
    if temporal_view not in {"record", "current"}:
        raise ViewProjectionError("temporal_view must be 'record' or 'current'")

    predicates = schema_ir.get("predicates")
    if not isinstance(predicates, list):
        raise ViewProjectionError("schema_ir.predicates must be list")

    output: dict[str, list[tuple[Any, ...]]] = {}
    visible_record_claim_ids = _build_visible_record_claim_ids(ledger)

    for schema_pred in predicates:
        if not isinstance(schema_pred, dict):
            raise ViewProjectionError("schema predicate must be dict")
        pred_id = schema_pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            raise ViewProjectionError("predicate pred_id must be non-empty string")

        cardinality = schema_pred.get("cardinality", "functional")
        active_claims = [
            claim
            for claim in ledger.find_claims(pred_id=pred_id)
            if is_active(ledger, claim.asrt_id)
            and (
                _meta_str(ledger, claim.asrt_id, "materialize_kind") != "record"
                or claim.asrt_id in visible_record_claim_ids
            )
        ]

        selected_claims: list[Claim]
        if cardinality == "functional":
            try:
                chosen_map = compute_chosen_for_predicate(ledger, schema_pred)
            except PolicyNonDeterminismError as exc:
                raise ViewProjectionError(str(exc)) from exc
            chosen_ids = set(chosen_map.values())
            selected_claims = [
                claim for claim in active_claims if claim.asrt_id in chosen_ids
            ]
        elif cardinality == "multi":
            selected_claims = active_claims
        elif cardinality == "temporal":
            if temporal_view == "record":
                selected_claims = active_claims
            else:
                try:
                    groups: dict[tuple[Any, ...], list[Claim]] = {}
                    for claim in active_claims:
                        group_key = group_key_for_claim(schema_pred, claim, ledger=ledger)
                        groups.setdefault(group_key, []).append(claim)
                    selected_claims = []
                    for claims in groups.values():
                        chosen_asrt_id = choose_one(ledger, [claim.asrt_id for claim in claims])
                        for claim in claims:
                            if claim.asrt_id == chosen_asrt_id:
                                selected_claims.append(claim)
                                break
                except PolicyNonDeterminismError as exc:
                    raise ViewProjectionError(str(exc)) from exc
        else:
            raise ViewProjectionError(f"unsupported cardinality: {cardinality}")

        facts = [build_args_for_claim(ledger, claim) for claim in selected_claims]
        output[pred_id] = sorted(facts, key=lambda fact: tuple(str(part) for part in fact))

    return output
