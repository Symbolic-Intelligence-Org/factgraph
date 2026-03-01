from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    contract_version: int = 2
    predicate_count: int = 0
    active_claim_count: int = 0
    selected_claim_count: int = 0
    selected_by_pred: dict[str, int] = field(default_factory=dict)
    dropped_by_policy_count: int = 0


def _project_view_facts_impl(
    ledger: Ledger,
    schema_ir: dict,
    *,
    temporal_view: str = "active",
    audit: ProjectorAudit | None = None,
) -> dict[str, list[tuple[Any, ...]]]:
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    if not isinstance(schema_ir, dict):
        raise ViewProjectionError("schema_ir must be dict")
    if temporal_view not in {"active", "current"}:
        raise ViewProjectionError("temporal_view must be 'active' or 'current'")

    predicates = schema_ir.get("predicates")
    if not isinstance(predicates, list):
        raise ViewProjectionError("schema_ir.predicates must be list")

    output: dict[str, list[tuple[Any, ...]]] = {}
    if audit is not None:
        audit.predicate_count = len([pred for pred in predicates if isinstance(pred, dict)])

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
        ]
        if audit is not None:
            audit.active_claim_count += len(active_claims)

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
            if audit is not None:
                audit.dropped_by_policy_count += max(0, len(active_claims) - len(selected_claims))
        elif cardinality == "multi":
            selected_claims = active_claims
        elif cardinality == "temporal":
            if temporal_view == "active":
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
        if audit is not None:
            audit.selected_claim_count += len(selected_claims)
            if selected_claims:
                audit.selected_by_pred[pred_id] = audit.selected_by_pred.get(pred_id, 0) + len(selected_claims)

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
    temporal_view: str = "active",
) -> dict[str, list[tuple[Any, ...]]]:
    return _project_view_facts_impl(
        ledger,
        schema_ir,
        temporal_view=temporal_view,
        audit=None,
    )


def project_view_facts_with_audit(
    ledger: Ledger,
    schema_ir: dict,
    *,
    temporal_view: str = "active",
) -> tuple[dict[str, list[tuple[Any, ...]]], ProjectorAudit]:
    audit = ProjectorAudit()
    facts = _project_view_facts_impl(
        ledger,
        schema_ir,
        temporal_view=temporal_view,
        audit=audit,
    )
    return facts, audit
