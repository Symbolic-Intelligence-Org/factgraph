"""Slice 3a Step 8 — unified AssertionView acceptance tests."""
from __future__ import annotations

import warnings

import pytest

from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class ViewUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


def _make_materialized_snapshot():
    fg = FactGraph.create(schema_classes=[ViewUser])
    e_ref = fg.entities.create(ViewUser, user_id="alice", tenant_id="acme")
    name_asrt = fg.fields.set(
        ViewUser.name,
        e_ref,
        "Alice",
        meta={"source": "seed", "version": "name-v1"},
    )
    tag_asrt = fg.fields.add(
        ViewUser.tags,
        e_ref,
        "vip",
        meta={"source": "tagger", "version": "tag-v1"},
    )
    snap = fg.entities.get(ViewUser, user_id="alice", tenant_id="acme")
    assert snap is not None
    return fg, e_ref, snap, name_asrt, tag_asrt


def test_snapshot_assertions_and_field_views_share_assertion_view_type():
    _fg, _e_ref, snap, _name_asrt, _tag_asrt = _make_materialized_snapshot()

    assert type(snap.assertions).__name__ == "AssertionView"
    assert type(snap.field("name")).__name__ == "AssertionView"
    assert type(snap.assertions.field(ViewUser.name)).__name__ == "AssertionView"
    assert snap.assertions.is_entity_scope is True
    assert snap.field("name").is_entity_scope is False
    assert snap.assertions.name is snap.assertions.field("name")
    assert snap.assertions.field(ViewUser.name) is snap.field("name")


def test_assertion_view_active_and_all_aggregate_entity_scope_records():
    _fg, _e_ref, snap, name_asrt, tag_asrt = _make_materialized_snapshot()

    assert {record.asrt_id for record in snap.assertions.active} == {name_asrt, tag_asrt}
    assert {record.asrt_id for record in snap.assertions.all}.issuperset({name_asrt, tag_asrt})
    assert [record.asrt_id for record in snap.field("name").active] == [name_asrt]
    assert [record.asrt_id for record in snap.field("tags").active] == [tag_asrt]


def test_assertion_view_all_keeps_revoked_history_records():
    fg, _e_ref, _snap, name_asrt, _tag_asrt = _make_materialized_snapshot()

    fg.assertions.retract(name_asrt)
    snap = fg.entities.get(ViewUser, user_id="alice", tenant_id="acme")
    assert snap is not None

    assert snap.field("name").active == ()
    revoked = snap.field("name").all.by_id(name_asrt).one()
    assert revoked.is_active is False
    assert snap.assertions.all.by_id(name_asrt).one().is_active is False


def test_assertion_view_history_alias_defaults_to_no_warning(monkeypatch):
    _fg, _e_ref, snap, name_asrt, _tag_asrt = _make_materialized_snapshot()
    monkeypatch.delenv("FACTGRAPH_WARN_DEPRECATED", raising=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        history = snap.field("name").history

    assert caught == []
    assert [record.asrt_id for record in history] == [name_asrt]


def test_assertion_view_history_alias_warns_when_env_enabled(monkeypatch):
    _fg, _e_ref, snap, name_asrt, _tag_asrt = _make_materialized_snapshot()
    monkeypatch.setenv("FACTGRAPH_WARN_DEPRECATED", "1")

    with pytest.warns(DeprecationWarning, match="AssertionView.history"):
        history = snap.field("name").history

    assert [record.asrt_id for record in history] == [name_asrt]


def test_assertion_view_where_uses_canonical_filters_and_rejects_flat_kwargs():
    _fg, e_ref, snap, _name_asrt, tag_asrt = _make_materialized_snapshot()

    records = snap.assertions.where(
        field=ViewUser.tags,
        e_ref=e_ref,
        value="vip",
        value_tag="string",
        _meta={"source": "tagger", "version": "tag-v1"},
    )

    assert [record.asrt_id for record in records] == [tag_asrt]
    with pytest.raises(TypeError):
        snap.assertions.where(source="tagger")  # type: ignore[call-arg]
    with pytest.raises(SDKStoreError):
        snap.assertions.where(_meta="tagger")


def test_assertion_view_is_pure_read_and_has_no_retract_method():
    fg, _e_ref, snap, name_asrt, _tag_asrt = _make_materialized_snapshot()

    assert not hasattr(snap.assertions, "retract")
    assert not hasattr(snap.field("name"), "retract")
    with pytest.raises(AttributeError):
        getattr(snap.assertions, "retract")
    fg.assertions.retract(name_asrt)
    assert fg._store.ledger.has_active_revocation(name_asrt)


def test_assertion_view_unknown_field_and_cross_entity_field_reject():
    _fg, _e_ref, snap, _name_asrt, _tag_asrt = _make_materialized_snapshot()

    class Other(Entity):
        other_id: str = Identity()
        name: str = Field()

    with pytest.raises(SDKStoreError, match="field not found"):
        snap.assertions.field("missing")
    with pytest.raises(SDKStoreError, match="Other.name"):
        snap.assertions.field(Other.name)
