"""Slice 3a Step 5 — `fg.fields.*` Layer 2 namespace acceptance tests.

Per blueprint §8 Step 5 + §5.6 + §7.3 + ADR-API §4.1.1:

- `fg.fields.set/add` are the canonical Layer 2 write entries.
- `fg.fields.retract(Field, e_ref, value)` is value-oriented and delegates the
  selected assertion id to `fg.assertions.retract`.
- `fg.fields.delete(Field, e_ref)` clears all active claims for a field/e_ref
  pair with fail-fast first-error semantics.
- `fg.fields.get(Field, e_ref)` materializes current values from active claims.
- Layer 2 rejects assertion-id and Entity-class navigation keys.
- Identity fields routed through `retract/delete` still hit Slice 2 INV-7c
  guard through `fg.assertions.retract`.
"""
from __future__ import annotations

import pytest

from factgraph._sdk_errors import FrozenSnapshotError
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class FieldsUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


PRED_USER_ID = "fields_user:user_id"
PRED_NAME = "fields_user:name"
PRED_TAGS = "fields_user:tags"


def _make_fg():
    return FactGraph.create(schema_classes=[FieldsUser])


def _make_created_fg():
    fg = _make_fg()
    e_ref = fg.entities.create(FieldsUser, user_id="alice", tenant_id="acme")
    return fg, e_ref


def _active_claims(fg: FactGraph, *, pred_id: str, e_ref: str):
    return [
        claim
        for claim in fg._store.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
        if not fg._store.ledger.has_active_revocation(claim.asrt_id)
    ]


# ---------- namespace shape + Layer 2 exclusivity ----------


def test_fg_fields_returns_fields_manager():
    fg = _make_fg()

    assert type(fg.fields).__name__ == "_SDKFieldsManager"


def test_fg_fields_namespace_is_read_only():
    fg = _make_fg()

    with pytest.raises(FrozenSnapshotError):
        fg.fields.spam = 42


def test_fields_set_rejects_assertion_id_navigation_key():
    fg, e_ref = _make_created_fg()

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.set("asrt_123", e_ref, "Alice")

    msg = str(exc_info.value)
    assert "Layer 2" in msg
    assert "Field descriptor" in msg
    assert "fg.assertions" in msg
    assert "ADR-API §4.1.1" in msg


def test_fields_set_rejects_entity_class_navigation_key():
    fg, e_ref = _make_created_fg()

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.set(FieldsUser, e_ref, "Alice")

    msg = str(exc_info.value)
    assert "Layer 2" in msg
    assert "Field descriptor" in msg
    assert "fg.entities" in msg
    assert "ADR-API §4.1.1" in msg


# ---------- set/add + get ----------


def test_fields_set_delegates_to_shipped_set_and_get_single_value():
    fg, e_ref = _make_created_fg()

    asrt_id = fg.fields.set(FieldsUser.name, e_ref, "Alice")

    assert isinstance(asrt_id, str) and asrt_id
    assert fg.fields.get(FieldsUser.name, e_ref) == "Alice"
    assert fg.entities.get(FieldsUser, user_id="alice", tenant_id="acme").name == "Alice"


def test_fields_set_latest_single_value_wins_for_get():
    fg, e_ref = _make_created_fg()

    fg.fields.set(FieldsUser.name, e_ref, "Alice")
    fg.fields.set(FieldsUser.name, e_ref, "Alicia")

    assert fg.fields.get(FieldsUser.name, e_ref) == "Alicia"


def test_fields_add_delegates_to_shipped_add_and_get_multi_values():
    fg, e_ref = _make_created_fg()

    first = fg.fields.add(FieldsUser.tags, e_ref, "red")
    second = fg.fields.add(FieldsUser.tags, e_ref, "blue")

    assert isinstance(first, str) and isinstance(second, str)
    assert fg.fields.get(FieldsUser.tags, e_ref) == ("red", "blue")
    assert set(fg.entities.get(FieldsUser, user_id="alice", tenant_id="acme").tags) == {"red", "blue"}


def test_fields_get_returns_empty_shapes_when_no_active_field_claims():
    fg, e_ref = _make_created_fg()

    assert fg.fields.get(FieldsUser.name, e_ref) is None
    assert fg.fields.get(FieldsUser.tags, e_ref) == ()


# ---------- value-oriented retract ----------


def test_fields_retract_value_retracts_unique_active_matching_assertion():
    fg, e_ref = _make_created_fg()
    red_asrt = fg.fields.add(FieldsUser.tags, e_ref, "red")
    blue_asrt = fg.fields.add(FieldsUser.tags, e_ref, "blue")

    revoker = fg.fields.retract(FieldsUser.tags, e_ref, "red")

    assert isinstance(revoker, str) and revoker
    assert fg._store.ledger.has_active_revocation(red_asrt)
    assert not fg._store.ledger.has_active_revocation(blue_asrt)
    assert fg.fields.get(FieldsUser.tags, e_ref) == ("blue",)


def test_fields_retract_no_match_raises():
    fg, e_ref = _make_created_fg()
    fg.fields.add(FieldsUser.tags, e_ref, "blue")

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.retract(FieldsUser.tags, e_ref, "red")

    msg = str(exc_info.value)
    assert "no active assertion matching" in msg
    assert "FieldsUser.tags" in msg


def test_fields_retract_ambiguous_match_raises_with_assertions_hint():
    fg, e_ref = _make_created_fg()
    fg.fields.add(FieldsUser.tags, e_ref, "red", meta={"source": "a"})
    fg.fields.add(FieldsUser.tags, e_ref, "red", meta={"source": "b"})

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.retract(FieldsUser.tags, e_ref, "red")

    msg = str(exc_info.value)
    assert "ambiguous active assertions" in msg
    assert "fg.assertions.retract" in msg


# ---------- clear-all delete + fail-fast first-error semantics ----------


def test_fields_delete_clear_all_retracts_active_field_claims():
    fg, e_ref = _make_created_fg()
    red = fg.fields.add(FieldsUser.tags, e_ref, "red")
    blue = fg.fields.add(FieldsUser.tags, e_ref, "blue")

    count = fg.fields.delete(FieldsUser.tags, e_ref)

    assert count == 2
    assert fg._store.ledger.has_active_revocation(red)
    assert fg._store.ledger.has_active_revocation(blue)
    assert fg.fields.get(FieldsUser.tags, e_ref) == ()


def test_fields_delete_returns_zero_when_no_active_claims():
    fg, e_ref = _make_created_fg()

    assert fg.fields.delete(FieldsUser.tags, e_ref) == 0


def test_fields_delete_identity_field_fail_fast_preserves_inv7c_guard():
    fg, e_ref = _make_created_fg()
    identity_claim = _active_claims(fg, pred_id=PRED_USER_ID, e_ref=e_ref)[0]

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.delete(FieldsUser.user_id, e_ref)

    assert exc_info.value.code == "INV_7C_IDENTITY_PROTECTED"
    assert not fg._store.ledger.has_active_revocation(identity_claim.asrt_id)


def test_fields_retract_identity_field_preserves_inv7c_guard():
    fg, e_ref = _make_created_fg()
    identity_claim = _active_claims(fg, pred_id=PRED_USER_ID, e_ref=e_ref)[0]

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.retract(FieldsUser.user_id, e_ref, "alice")

    assert exc_info.value.code == "INV_7C_IDENTITY_PROTECTED"
    assert not fg._store.ledger.has_active_revocation(identity_claim.asrt_id)


def test_fields_set_identity_descriptor_rejected_before_write():
    fg, e_ref = _make_created_fg()

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.set(FieldsUser.user_id, e_ref, "bob")

    msg = str(exc_info.value)
    assert "Identity" in msg
    assert "INV-7c" in msg
