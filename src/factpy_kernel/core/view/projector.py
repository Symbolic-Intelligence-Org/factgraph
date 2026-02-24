from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factpy_kernel.core.record_staging import (
    RECORD_STAGE_COMMITTED,
    RECORD_STAGE_MARKER_PRED_ID,
    meta_int,
    parse_record_stage_marker_claim,
    resolve_record_stage_status,
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


@dataclass
class ProjectorAudit:
    contract_version: int = 1
    legacy_record_total: int = 0
    legacy_record_by_pred: dict[str, int] = field(default_factory=dict)
    legacy_exists_without_roles_total: int = 0
    legacy_exists_without_roles_by_pred: dict[str, int] = field(default_factory=dict)
    marker_conflict_total: int = 0
    marker_conflict_by_reason: dict[str, int] = field(default_factory=dict)
    committed_hidden_count_mismatch_total: int = 0
    committed_hidden_count_mismatch_by_pred: dict[str, int] = field(default_factory=dict)


def _inc_counter(mapping: dict[str, int], key: str) -> None:
    mapping[key] = mapping.get(key, 0) + 1


def _meta_str(ledger: Ledger, asrt_id: str, key: str) -> str | None:
    for row in ledger.find_meta(asrt_id=asrt_id, key=key):
        if isinstance(row.value, str):
            return row.value
    return None


def _build_record_stage_index(ledger: Ledger) -> dict[tuple[str, str], dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for claim in ledger.find_claims(pred_id=RECORD_STAGE_MARKER_PRED_ID):
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        parsed = parse_record_stage_marker_claim(claim)
        if parsed is None:
            continue
        materialize_id, stage, record_digest = parsed
        key = (claim.e_ref, materialize_id)
        entry = by_key.setdefault(
            key,
            {
                "stage_digests": {},
                "roles_count_expected_values": set(),
            },
        )
        stage_digests = entry["stage_digests"]
        if not isinstance(stage_digests, dict):
            continue
        stage_digests.setdefault(stage, set()).add(record_digest)
        roles_count_expected = meta_int(ledger, claim.asrt_id, "roles_count_expected")
        if isinstance(roles_count_expected, int) and roles_count_expected >= 0:
            count_values = entry.get("roles_count_expected_values")
            if isinstance(count_values, set):
                count_values.add(roles_count_expected)
    return by_key


def _build_visible_record_claim_ids(
    ledger: Ledger,
    *,
    audit: ProjectorAudit | None = None,
) -> set[str]:
    stage_index = _build_record_stage_index(ledger)
    groups: dict[tuple[str, str], list[Claim]] = {}
    legacy_groups: dict[tuple[str, str], list[Claim]] = {}

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
            legacy_groups.setdefault((claim.e_ref, materialize_id), []).append(claim)
            continue
        groups.setdefault((claim.e_ref, materialize_id), []).append(claim)

    visible: set[str] = set()
    for claims in legacy_groups.values():
        for claim in claims:
            visible.add(claim.asrt_id)

    if audit is not None:
        for legacy_claims in legacy_groups.values():
            exists_claims = [claim for claim in legacy_claims if claim.rest_terms == []]
            if not exists_claims:
                continue
            exists_claim = sorted(exists_claims, key=lambda c: (c.pred_id, c.asrt_id))[0]
            roles_count_actual = sum(1 for claim in legacy_claims if claim.rest_terms != [])
            audit.legacy_record_total += 1
            _inc_counter(audit.legacy_record_by_pred, exists_claim.pred_id)
            if roles_count_actual == 0:
                audit.legacy_exists_without_roles_total += 1
                _inc_counter(audit.legacy_exists_without_roles_by_pred, exists_claim.pred_id)

    stage_state_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for key, marker_entry in stage_index.items():
        stage_digests = marker_entry.get("stage_digests")
        roles_count_expected_values = marker_entry.get("roles_count_expected_values")
        if not isinstance(stage_digests, dict):
            continue
        stage_state = resolve_record_stage_status(
            stage_digests=stage_digests,
            roles_count_expected_values=roles_count_expected_values if isinstance(roles_count_expected_values, set) else set(),
            path="$.view.record_staging",
        )
        stage_state_by_key[key] = stage_state
        if audit is not None and stage_state["status"] == "conflict":
            audit.marker_conflict_total += 1
            reason = stage_state.get("reason")
            _inc_counter(audit.marker_conflict_by_reason, str(reason) if isinstance(reason, str) and reason else "unknown")

    for key, claims in groups.items():
        stage_state = stage_state_by_key.get(key)
        if not isinstance(stage_state, dict):
            continue
        if stage_state["status"] != RECORD_STAGE_COMMITTED:
            continue
        committed_digest = stage_state.get("digest")
        if not isinstance(committed_digest, str) or not committed_digest:
            continue
        # Require record exists row to be present before exposing any role rows.
        has_exists = False
        exists_pred_id: str | None = None
        roles_count_actual = 0
        for claim in claims:
            claim_digest = _meta_str(ledger, claim.asrt_id, "record_digest")
            if claim_digest != committed_digest:
                continue
            if claim.rest_terms == []:
                has_exists = True
                if exists_pred_id is None:
                    exists_pred_id = claim.pred_id
                continue
            roles_count_actual += 1
        if not has_exists:
            continue
        if isinstance(stage_state.get("roles_count_expected"), int):
            if roles_count_actual != stage_state["roles_count_expected"]:
                if audit is not None and isinstance(exists_pred_id, str) and exists_pred_id:
                    audit.committed_hidden_count_mismatch_total += 1
                    _inc_counter(audit.committed_hidden_count_mismatch_by_pred, exists_pred_id)
                continue
        for claim in claims:
            if _meta_str(ledger, claim.asrt_id, "record_digest") == committed_digest:
                visible.add(claim.asrt_id)
    return visible


def _project_view_facts_impl(
    ledger: Ledger,
    schema_ir: dict,
    *,
    temporal_view: str = "record",
    audit: ProjectorAudit | None = None,
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
    visible_record_claim_ids = _build_visible_record_claim_ids(ledger, audit=audit)

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
    return _project_view_facts_impl(ledger, schema_ir, temporal_view=temporal_view, audit=None)


def project_view_facts_with_audit(
    ledger: Ledger,
    schema_ir: dict,
    *,
    temporal_view: str = "record",
) -> tuple[dict[str, list[tuple[Any, ...]]], ProjectorAudit]:
    audit = ProjectorAudit()
    facts = _project_view_facts_impl(ledger, schema_ir, temporal_view=temporal_view, audit=audit)
    return facts, audit
