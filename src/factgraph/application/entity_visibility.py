from __future__ import annotations

from typing import Any

from factgraph.core.store import Store
from factgraph.core.store.ledger import Claim

from .schema_runtime import SchemaIndex, entity_info


def is_entity_identity_bundle_active(
    *,
    store: Store,
    schema_index: SchemaIndex,
    entity_type: str,
    e_ref: str,
    identity_values: dict[str, Any],
) -> bool:
    """Return True only when the complete Identity Claim bundle is active."""
    info = entity_info(schema_index, entity_type)
    for identity_field in info.identity_fields:
        if identity_field.name not in identity_values:
            return False
        pred_info = info.identity_predicates[identity_field.name]
        expected_terms = [(identity_field.type_domain, identity_values[identity_field.name])]
        claims = store.ledger.find_claims(pred_id=pred_info.pred_id, e_ref=e_ref)
        if not any(
            _claim_active_with_terms(
                store=store,
                claim=claim,
                expected_terms=expected_terms,
            )
            for claim in claims
        ):
            return False
    return True


def _claim_active_with_terms(
    *,
    store: Store,
    claim: Claim,
    expected_terms: list[tuple[str, Any]],
) -> bool:
    return (
        claim.rest_terms == expected_terms
        and not store.ledger.has_active_revocation(claim.asrt_id)
    )
