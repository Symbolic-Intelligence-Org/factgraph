"""Slice 3a Step 6 — `fg.assertions.*` Layer 3 namespace acceptance tests.

Per blueprint §8 Step 6 + §5.7 + §7.4:

- `_SDKAssertionsManager` is promoted to public `AssertionsManager`.
- `fg.assertions.retract(asrt_id)` owns the Slice 2 retract guard wrapper.
- legacy flat `fg.retract(asrt_id)` delegates to `fg.assertions.retract`
  until Step 7 removes the flat shortcut.
- `fg.assertions.where(...)` ships the canonical Layer 3 filter entry with
  `_meta` dict input and no flat source/trace_id/version kwargs.
- `fg.fields.retract/delete` delegate to `fg.assertions.retract`.
"""
from __future__ import annotations

import pytest

from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class AssertUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


PRED_USER_ID = "assert_user:user_id"
PRED_EXISTS = "AssertUser:exists"
PRED_NAME = "assert_user:name"
PRED_TAGS = "assert_user:tags"


def _make_fg():
    return FactGraph.create(schema_classes=[AssertUser])


def _make_materialized_fg():
    fg = _make_fg()
    e_ref = fg.entities.create(AssertUser, user_id="alice", tenant_id="acme")
    name_asrt = fg.fields.set(AssertUser.name, e_ref, "Alice", meta={"source": "seed", "version": "name-v1"})
    tag_asrt = fg.fields.add(AssertUser.tags, e_ref, "vip", meta={"source": "tagger", "version": "tag-v1"})
    return fg, e_ref, name_asrt, tag_asrt


def _active_claims(fg: FactGraph, *, pred_id: str, e_ref: str):
    return [
        claim
        for claim in fg._store.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
        if not fg._store.ledger.has_active_revocation(claim.asrt_id)
    ]


# ---------- namespace shape + read shortcuts ----------


def test_assertions_manager_public_class_name_and_read_only_namespace():
    fg = _make_fg()

    assert type(fg.assertions).__name__ == "AssertionsManager"
    with pytest.raises(Exception) as exc_info:
        fg.assertions.spam = 42
    assert "assertions namespace is read-only" in str(exc_info.value)


def test_assertions_active_and_all_are_properties_with_legacy_callable_compat():
    fg, _e_ref, name_asrt, tag_asrt = _make_materialized_fg()

    active_property = fg.assertions.active
    all_property = fg.assertions.all

    assert {record.asrt_id for record in active_property}.issuperset({name_asrt, tag_asrt})
    assert {record.asrt_id for record in active_property()} == {record.asrt_id for record in active_property}
    assert {record.asrt_id for record in all_property()}.issuperset({name_asrt, tag_asrt})


# ---------- canonical where ----------


def test_assertions_where_filters_active_records_by_field_e_ref_value_tag_and_meta():
    fg, e_ref, _name_asrt, tag_asrt = _make_materialized_fg()

    records = fg.assertions.where(
        field=AssertUser.tags,
        e_ref=e_ref,
        value="vip",
        value_tag="string",
        _meta={"source": "tagger", "version": "tag-v1"},
    )

    assert [record.asrt_id for record in records] == [tag_asrt]


def test_assertions_where_uses_active_view_not_history():
    fg, e_ref, name_asrt, _tag_asrt = _make_materialized_fg()

    fg.assertions.retract(name_asrt)

    records = fg.assertions.where(field=AssertUser.name, e_ref=e_ref, value="Alice")
    assert records == ()
    assert fg.assertions.all.by_id(name_asrt).one().is_active is False


def test_assertions_where_rejects_non_field_filter_and_non_dict_meta():
    fg, _e_ref, _name_asrt, _tag_asrt = _make_materialized_fg()

    with pytest.raises(SDKStoreError) as field_exc:
        fg.assertions.where(field="assert_user:name")
    assert "Field descriptor" in str(field_exc.value)
    assert "ADR-API §4.1.1" in str(field_exc.value)

    with pytest.raises(SDKStoreError) as meta_exc:
        fg.assertions.where(_meta="seed")
    assert "_meta" in str(meta_exc.value)


def test_assertions_where_rejects_flat_source_kwarg_by_signature():
    fg, _e_ref, _name_asrt, _tag_asrt = _make_materialized_fg()

    with pytest.raises(TypeError):
        fg.assertions.where(source="seed")  # type: ignore[call-arg]


# ---------- retract guard moved to assertions namespace ----------


def test_assertions_retract_field_claim_succeeds_and_flat_retract_delegates():
    fg, _e_ref, name_asrt, tag_asrt = _make_materialized_fg()

    revoker = fg.assertions.retract(name_asrt)
    flat_revoker = fg.retract(tag_asrt)

    assert isinstance(revoker, str) and revoker
    assert isinstance(flat_revoker, str) and flat_revoker
    assert fg._store.ledger.has_active_revocation(name_asrt)
    assert fg._store.ledger.has_active_revocation(tag_asrt)


def test_assertions_retract_unknown_asrt_preserves_assertion_not_found_code():
    fg = _make_fg()

    with pytest.raises(SDKStoreError) as exc_info:
        fg.assertions.retract("missing-asrt")

    assert exc_info.value.code == "ASSERTION_NOT_FOUND"


def test_assertions_retract_identity_claim_preserves_inv7c_guard():
    fg, e_ref, _name_asrt, _tag_asrt = _make_materialized_fg()
    identity_claim = _active_claims(fg, pred_id=PRED_USER_ID, e_ref=e_ref)[0]

    with pytest.raises(SDKStoreError) as exc_info:
        fg.assertions.retract(identity_claim.asrt_id)

    assert exc_info.value.code == "INV_7C_IDENTITY_PROTECTED"
    assert not fg._store.ledger.has_active_revocation(identity_claim.asrt_id)


def test_assertions_retract_exists_claim_preserves_transitional_guard():
    fg, e_ref, _name_asrt, _tag_asrt = _make_materialized_fg()
    exists_claim = _active_claims(fg, pred_id=PRED_EXISTS, e_ref=e_ref)[0]

    with pytest.raises(SDKStoreError) as exc_info:
        fg.assertions.retract(exists_claim.asrt_id)

    assert exc_info.value.code == "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
    assert "INV-7c" not in str(exc_info.value)
    assert not fg._store.ledger.has_active_revocation(exists_claim.asrt_id)


def test_assertions_retract_rejects_entity_navigation_key():
    fg = _make_fg()

    with pytest.raises(SDKStoreError) as exc_info:
        fg.assertions.retract(AssertUser, user_id="alice", tenant_id="acme")  # type: ignore[arg-type]

    msg = str(exc_info.value)
    assert "Layer 3" in msg
    assert "fg.entities.delete" in msg
    assert "ADR-API §4.1.1" in msg


def test_fields_retract_and_delete_delegate_to_assertions_retract():
    fg, e_ref, _name_asrt, _tag_asrt = _make_materialized_fg()
    red = fg.fields.add(AssertUser.tags, e_ref, "red")
    blue = fg.fields.add(AssertUser.tags, e_ref, "blue")

    fg.fields.retract(AssertUser.tags, e_ref, "red")
    count = fg.fields.delete(AssertUser.tags, e_ref)

    assert count == 2  # original vip + blue
    assert fg._store.ledger.has_active_revocation(red)
    assert fg._store.ledger.has_active_revocation(blue)

