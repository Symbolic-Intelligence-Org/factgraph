"""Slice 5 Step 2 — `fg.entities.exists` acceptance tests.

Per blueprint §8 Step 2 + Q-EXISTS §4.3:

- `fg.entities.exists(EntityCls, **identity) -> bool` reads the complete
  active Identity Claim bundle for the requested entity coordinate.
- It returns True after eager `fg.entities.create`.
- It returns True after legacy lazy materialization via `fg.ref + fg.set`.
- It returns False for ref-only identities because `fg.ref` only populates the
  SDK shadow store and does not emit claims.
- It returns False after `fg.entities.delete` revokes the Identity Claim bundle.
- It ignores legacy `:exists` Claims unless matching Identity Claims are active.
- It preserves Layer 1 exclusive navigation-key enforcement.
"""
from __future__ import annotations

import pytest

from factgraph.application import entity_info
from factgraph.core.evidence.write_protocol import retract_by_asrt, set_field
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class ExistsUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()


PRED_EXISTS = "ExistsUser:exists"


def _make_fg():
    return FactGraph.create(schema_classes=[ExistsUser])


def _active_claim_count(fg: FactGraph, pred_id: str, e_ref: str) -> int:
    return sum(
        1
        for claim in fg._store.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
        if not fg._store.ledger.has_active_revocation(claim.asrt_id)
    )


def _active_exists_claim_count(fg: FactGraph, e_ref: str) -> int:
    return _active_claim_count(fg, PRED_EXISTS, e_ref)


def _active_identity_claim_counts(fg: FactGraph, e_ref: str) -> dict[str, int]:
    info = entity_info(fg._application_schema_index, "ExistsUser")
    return {
        field_name: _active_claim_count(fg, pred.pred_id, e_ref)
        for field_name, pred in info.identity_predicates.items()
    }


def _retract_identity_claim(fg: FactGraph, e_ref: str, field_name: str) -> None:
    info = entity_info(fg._application_schema_index, "ExistsUser")
    pred = info.identity_predicates[field_name]
    claims = fg._store.ledger.find_claims(pred_id=pred.pred_id, e_ref=e_ref)
    assert claims
    retract_by_asrt(fg._store.ledger, claims[0].asrt_id)


def test_entities_exists_true_after_create():
    fg = _make_fg()
    e_ref = fg.entities.create(ExistsUser, user_id="alice", tenant_id="acme")

    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is True
    assert _active_identity_claim_counts(fg, e_ref) == {"user_id": 1, "tenant_id": 1}


def test_entities_exists_true_after_lazy_first_write():
    fg = _make_fg()
    e_ref = fg.entities.ref(ExistsUser, user_id="alice", tenant_id="acme")
    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is False

    # Legacy lazy materialization path: first field write emits Identity Claims.
    fg.fields.set(ExistsUser.name, e_ref, "Alice")

    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is True
    assert _active_identity_claim_counts(fg, e_ref) == {"user_id": 1, "tenant_id": 1}


def test_entities_exists_false_for_ref_only_shadow_store_entry():
    fg = _make_fg()
    e_ref = fg.entities.ref(ExistsUser, user_id="alice", tenant_id="acme")

    assert e_ref in fg._identity_values_by_e_ref
    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is False
    assert _active_exists_claim_count(fg, e_ref) == 0


def test_entities_exists_false_for_never_seen_identity():
    fg = _make_fg()

    assert fg.entities.exists(ExistsUser, user_id="ghost", tenant_id="acme") is False


def test_entities_exists_false_after_delete_form_a():
    fg = _make_fg()
    e_ref = fg.entities.create(ExistsUser, user_id="alice", tenant_id="acme")
    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is True

    fg.entities.delete(e_ref)

    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is False
    assert _active_identity_claim_counts(fg, e_ref) == {"user_id": 0, "tenant_id": 0}


def test_entities_exists_false_after_delete_form_b():
    fg = _make_fg()
    e_ref = fg.entities.create(ExistsUser, user_id="alice", tenant_id="acme")
    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is True

    fg.entities.delete(ExistsUser, user_id="alice", tenant_id="acme")

    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is False
    assert _active_identity_claim_counts(fg, e_ref) == {"user_id": 0, "tenant_id": 0}


def test_entities_exists_false_for_incomplete_active_identity_bundle():
    fg = _make_fg()
    e_ref = fg.entities.create(ExistsUser, user_id="alice", tenant_id="acme")
    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is True

    _retract_identity_claim(fg, e_ref, "tenant_id")

    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is False
    assert _active_identity_claim_counts(fg, e_ref) == {"user_id": 1, "tenant_id": 0}


def test_entities_exists_false_for_exists_claim_without_identity_bundle():
    fg = _make_fg()
    e_ref = fg.entities.ref(ExistsUser, user_id="alice", tenant_id="acme")
    info = entity_info(fg._application_schema_index, "ExistsUser")

    set_field(fg._store.ledger, info.exists_predicate_id, e_ref, [])

    assert fg.entities.exists(ExistsUser, user_id="alice", tenant_id="acme") is False
    assert _active_exists_claim_count(fg, e_ref) == 1
    assert _active_identity_claim_counts(fg, e_ref) == {"user_id": 0, "tenant_id": 0}


def test_entities_exists_requires_complete_identity_bundle():
    fg = _make_fg()

    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.exists(ExistsUser, user_id="alice")

    assert "missing identity field: ExistsUser.tenant_id" in str(exc_info.value)


def test_entities_exists_rejects_non_entity_class_inputs():
    fg = _make_fg()

    with pytest.raises(SDKStoreError) as str_exc:
        fg.entities.exists("asrt_123")
    assert "fg.assertions.by_id" in str(str_exc.value)
    assert "ADR-API §4.1.1" in str(str_exc.value)

    with pytest.raises(SDKStoreError) as field_exc:
        fg.entities.exists(ExistsUser.name)
    assert "fg.fields.*" in str(field_exc.value)
    assert "ADR-API §4.1.1" in str(field_exc.value)
