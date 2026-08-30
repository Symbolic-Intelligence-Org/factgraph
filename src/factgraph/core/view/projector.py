from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from factgraph.core.policy.active import is_active
from factgraph.core.policy.chosen import (
    PolicyNonDeterminismError,
    compute_chosen_for_predicate,
)
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.store._support import ProjectedFact
from factgraph.core.store.ledger import Claim, Ledger


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

    virtual_exists = _virtual_entity_exists_rows(ledger, schema_ir)
    output: dict[str, list[tuple[Any, ...]]] = {}
    if audit is not None:
        audit.predicate_count = len([pred for pred in predicates if isinstance(pred, dict)])

    for schema_pred in predicates:
        if not isinstance(schema_pred, dict):
            raise ViewProjectionError("schema predicate must be dict")
        pred_id = schema_pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            raise ViewProjectionError("predicate pred_id must be non-empty string")

        if bool(schema_pred.get("is_entity_exists", False)):
            facts = [fact for fact, _support in virtual_exists.get(pred_id, ())]
            output[pred_id] = sorted(facts, key=canonical_fact_sort_key)
            if audit is not None and facts:
                audit.selected_claim_count += len(facts)
                audit.selected_by_pred[pred_id] = len(facts)
            continue

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
        output[pred_id] = sorted(facts, key=canonical_fact_sort_key)

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


def canonical_fact_sort_key(fact: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(str(part) for part in fact)


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

    virtual_exists = _virtual_entity_exists_rows(ledger, schema_ir)
    output: dict[str, list[ProjectedFact]] = {}
    for schema_pred in predicates:
        if not isinstance(schema_pred, dict):
            raise ViewProjectionError("schema predicate must be dict")
        pred_id = schema_pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            raise ViewProjectionError("predicate pred_id must be non-empty string")

        if bool(schema_pred.get("is_entity_exists", False)):
            projected = [
                ProjectedFact(
                    asrt_id=_virtual_exists_witness_id(
                        pred_id=pred_id,
                        e_ref=fact[0],
                        support_asrt_ids=support,
                    ),
                    fact_tuple=fact,
                )
                for fact, support in virtual_exists.get(pred_id, ())
            ]
            output[pred_id] = sorted(
                projected,
                key=lambda row: canonical_fact_sort_key(row.fact_tuple),
            )
            continue

        selected_claims = _select_view_claims(ledger, schema_pred)
        projected = [
            ProjectedFact(
                asrt_id=claim.asrt_id,
                fact_tuple=build_args_for_claim(ledger, claim),
            )
            for claim in selected_claims
        ]
        output[pred_id] = sorted(projected, key=lambda row: canonical_fact_sort_key(row.fact_tuple))

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


def _virtual_entity_exists_rows(
    ledger: Ledger,
    schema_ir: dict[str, Any],
) -> dict[str, list[tuple[tuple[Any, ...], tuple[str, ...]]]]:
    """Project Entity-domain rows from complete chosen Identity bundles.

    Persisted ``<EntityType>:exists`` Claims are deliberately not consulted.
    The returned support inventory contains every Identity assertion required
    by the bundle and is committed into the deterministic virtual witness id.
    """

    predicates = schema_ir.get("predicates")
    entities = schema_ir.get("entities", [])
    if not isinstance(predicates, list):
        raise ViewProjectionError("schema_ir.predicates must be list")
    if not isinstance(entities, list):
        raise ViewProjectionError("schema_ir.entities must be list when provided")

    predicates_by_owner_field: dict[tuple[str, str], dict[str, Any]] = {}
    exists_by_owner: dict[str, str] = {}
    for predicate in predicates:
        if not isinstance(predicate, dict):
            raise ViewProjectionError("schema predicate must be dict")
        owner = predicate.get("owner_type")
        pred_id = predicate.get("pred_id")
        if not isinstance(owner, str) or not isinstance(pred_id, str):
            continue
        if bool(predicate.get("is_entity_exists", False)):
            exists_by_owner[owner] = pred_id
        if bool(predicate.get("is_identity_field", False)):
            field_name = predicate.get("py_field_name")
            if isinstance(field_name, str) and field_name:
                predicates_by_owner_field[(owner, field_name)] = predicate

    output: dict[str, list[tuple[tuple[Any, ...], tuple[str, ...]]]] = {
        pred_id: [] for pred_id in exists_by_owner.values()
    }
    for entity in entities:
        if not isinstance(entity, dict):
            raise ViewProjectionError("schema entity must be dict")
        entity_type = entity.get("entity_type")
        identity_fields = entity.get("identity_fields")
        if not isinstance(entity_type, str) or not isinstance(identity_fields, list):
            raise ViewProjectionError("schema entity identity is invalid")
        exists_pred_id = exists_by_owner.get(entity_type)
        if exists_pred_id is None:
            continue

        selected_by_field: list[
            tuple[str, str, dict[str, tuple[Any, str]]]
        ] = []
        for identity_field in identity_fields:
            if not isinstance(identity_field, dict):
                raise ViewProjectionError("identity field must be dict")
            field_name = identity_field.get("name")
            type_domain = identity_field.get("type_domain")
            if not isinstance(field_name, str) or not isinstance(type_domain, str):
                raise ViewProjectionError("identity field name/domain is invalid")
            predicate = predicates_by_owner_field.get((entity_type, field_name))
            if predicate is None:
                raise ViewProjectionError(
                    f"missing identity predicate for {entity_type}.{field_name}"
                )
            values: dict[str, tuple[Any, str]] = {}
            for claim in _select_view_claims(ledger, predicate):
                fact = build_args_for_claim(ledger, claim)
                if len(fact) != 2:
                    raise ViewProjectionError(
                        f"identity predicate {predicate['pred_id']} must be binary"
                    )
                values[claim.e_ref] = (fact[1], claim.asrt_id)
            selected_by_field.append((field_name, type_domain, values))

        candidates: set[str] = set()
        for _field_name, _type_domain, values in selected_by_field:
            candidates = set(values) if not candidates else candidates & set(values)

        rows: list[tuple[tuple[Any, ...], tuple[str, ...]]] = []
        for e_ref in sorted(candidates, key=lambda item: item.encode("utf-8")):
            identity = [
                (field_name, type_domain, values[e_ref][0])
                for field_name, type_domain, values in selected_by_field
            ]
            try:
                expected_ref = encode_idref_v1(entity_type, identity)
            except (TypeError, ValueError):
                continue
            if expected_ref != e_ref:
                continue
            supports = tuple(
                sorted(
                    (values[e_ref][1] for _name, _domain, values in selected_by_field),
                    key=lambda item: item.encode("utf-8"),
                )
            )
            rows.append(((e_ref,), supports))
        output[exists_pred_id] = rows
    return output


def _virtual_exists_witness_id(
    *,
    pred_id: str,
    e_ref: str,
    support_asrt_ids: tuple[str, ...],
) -> str:
    payload = "\x00".join(
        ("factgraph.virtual-entity-exists.v1", pred_id, e_ref, *support_asrt_ids)
    ).encode("utf-8")
    return "virtual-entity-exists:v1:" + hashlib.sha256(payload).hexdigest()
