from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factgraph.core.policy.active import is_active
from factgraph.core.policy.chosen import (
    PolicyNonDeterminismError,
    compute_chosen_for_predicate,
)
from factgraph.core.store._support import ProjectedFact
from factgraph.core.store.types import ReadPolicy
from factgraph.core.store.ledger import Claim, Ledger
from factgraph.core.view.confidence import aggregate_confidence


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
    audit: ProjectorAudit | None = None,
) -> dict[str, list[tuple[Any, ...]]]:
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    if not isinstance(schema_ir, dict):
        raise ViewProjectionError("schema_ir must be dict")
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

        cardinality = schema_pred.get("cardinality", "single")
        active_claims = [
            claim
            for claim in ledger.find_claims(pred_id=pred_id)
            if is_active(ledger, claim.asrt_id)
        ]
        if audit is not None:
            audit.active_claim_count += len(active_claims)

        selected_claims: list[Claim]
        if cardinality == "single":
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
) -> dict[str, list[tuple[Any, ...]]]:
    return _project_view_facts_impl(
        ledger,
        schema_ir,
        audit=None,
    )


def project_view_facts_with_witness(
    ledger: Ledger,
    schema_ir: dict,
) -> dict[str, list[ProjectedFact]]:
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    if not isinstance(schema_ir, dict):
        raise ViewProjectionError("schema_ir must be dict")
    predicates = schema_ir.get("predicates")
    if not isinstance(predicates, list):
        raise ViewProjectionError("schema_ir.predicates must be list")

    output: dict[str, list[ProjectedFact]] = {}
    for schema_pred in predicates:
        if not isinstance(schema_pred, dict):
            raise ViewProjectionError("schema predicate must be dict")
        pred_id = schema_pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            raise ViewProjectionError("predicate pred_id must be non-empty string")

        selected_claims = _select_view_claims(ledger, schema_pred)
        projected = [
            ProjectedFact(
                asrt_id=claim.asrt_id,
                fact_tuple=build_args_for_claim(ledger, claim),
            )
            for claim in selected_claims
        ]
        output[pred_id] = sorted(projected, key=lambda row: tuple(str(part) for part in row.fact_tuple))

    return output


def project_view_facts_with_audit(
    ledger: Ledger,
    schema_ir: dict,
) -> tuple[dict[str, list[tuple[Any, ...]]], ProjectorAudit]:
    audit = ProjectorAudit()
    facts = _project_view_facts_impl(
        ledger,
        schema_ir,
        audit=audit,
    )
    return facts, audit


def _select_view_claims(
    ledger: Ledger,
    schema_pred: dict[str, Any],
) -> list[Claim]:
    pred_id = schema_pred.get("pred_id")
    if not isinstance(pred_id, str) or not pred_id:
        raise ViewProjectionError("predicate pred_id must be non-empty string")

    cardinality = schema_pred.get("cardinality", "single")
    active_claims = [
        claim
        for claim in ledger.find_claims(pred_id=pred_id)
        if is_active(ledger, claim.asrt_id)
    ]

    if cardinality == "single":
        try:
            chosen_map = compute_chosen_for_predicate(ledger, schema_pred)
        except PolicyNonDeterminismError as exc:
            raise ViewProjectionError(str(exc)) from exc
        chosen_ids = set(chosen_map.values())
        return [
            claim for claim in active_claims if claim.asrt_id in chosen_ids
        ]
    if cardinality == "multi":
        return active_claims
    raise ViewProjectionError(f"unsupported cardinality: {cardinality}")


def project_display_facts(
    ledger: Ledger,
    policy: ReadPolicy,
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    if not isinstance(policy, ReadPolicy):
        raise TypeError("policy must be ReadPolicy")

    grouped: dict[tuple[str, tuple[Any, ...]], list[dict[str, Any]]] = {}
    for claim in ledger.claims:
        if policy.respect_revocations and not is_active(ledger, claim.asrt_id):
            continue

        fact = build_args_for_claim(ledger, claim)
        meta_rows = ledger.find_meta(asrt_id=claim.asrt_id)
        meta_raw: dict[str, Any] = {row.key: row.value for row in meta_rows}
        grouped.setdefault((claim.pred_id, fact), []).append(
            {
                "asrt_id": claim.asrt_id,
                "source": meta_raw.get("source"),
                "confidence": meta_raw.get("confidence"),
            }
        )

    output: dict[str, list[dict[str, Any]]] = {}
    for (pred_id, fact), rows in grouped.items():
        confidence = aggregate_confidence(
            rows,
            strategy=policy.confidence_strategy,
            prefer_source=policy.prefer_source,
        )
        output.setdefault(pred_id, []).append(
            {
                "fact": fact,
                "confidence": confidence,
                "count": len(rows),
            }
        )

    for pred_id in output:
        output[pred_id].sort(key=lambda item: tuple(str(part) for part in item["fact"]))
    return output
