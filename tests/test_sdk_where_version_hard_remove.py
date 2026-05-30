"""Slice 3a Step 9 — version(v) and flat where kwargs hard removal."""
from __future__ import annotations

import pytest

from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class WhereUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


def _make_snapshot():
    fg = FactGraph.create(schema_classes=[WhereUser])
    e_ref = fg.entities.create(WhereUser, user_id="alice", tenant_id="acme")
    name_v1 = fg.fields.set(
        WhereUser.name,
        e_ref,
        "Alice",
        meta={"source": "seed", "trace_id": "trace-name-1", "version": "name-v1"},
    )
    name_v2 = fg.fields.set(
        WhereUser.name,
        e_ref,
        "Alicia",
        meta={"source": "correction", "trace_id": "trace-name-2", "version": "name-v2"},
    )
    tag_asrt = fg.fields.add(
        WhereUser.tags,
        e_ref,
        "vip",
        meta={"source": "tagger", "trace_id": "trace-tag-1", "version": "tag-v1"},
    )
    snap = fg.entities.get(WhereUser, user_id="alice", tenant_id="acme")
    assert snap is not None
    return fg, e_ref, snap, {"name_v1": name_v1, "name_v2": name_v2, "tag": tag_asrt}


def test_assertion_record_set_version_method_is_hard_removed():
    _fg, _e_ref, snap, _ids = _make_snapshot()

    assert not hasattr(snap.field("name").active, "version")
    assert not hasattr(snap.field("name").all, "version")
    with pytest.raises(AttributeError):
        getattr(snap.field("name").active, "version")


def test_assertion_view_version_method_is_hard_removed():
    _fg, _e_ref, snap, _ids = _make_snapshot()

    assert not hasattr(snap.field("name"), "version")
    assert not hasattr(snap.assertions, "version")
    with pytest.raises(AttributeError):
        getattr(snap.field("name"), "version")


@pytest.mark.parametrize("kwarg", ["source", "trace_id", "version", "meta"])
def test_assertion_record_set_where_rejects_flat_metadata_kwargs_by_signature(kwarg: str):
    _fg, _e_ref, snap, _ids = _make_snapshot()

    with pytest.raises(TypeError):
        snap.field("tags").active.where(**{kwarg: "seed"})  # type: ignore[arg-type]


def test_assertion_record_set_where_filters_value_tag_and_meta():
    _fg, _e_ref, snap, ids = _make_snapshot()

    tag_records = snap.field("tags").active.where(
        value="vip",
        value_tag="string",
        _meta={"source": "tagger", "trace_id": "trace-tag-1", "version": "tag-v1"},
    )

    assert [record.asrt_id for record in tag_records] == [ids["tag"]]


def test_assertion_record_set_where_meta_version_replaces_version_method():
    _fg, _e_ref, snap, ids = _make_snapshot()

    records = snap.field("name").all.where(_meta={"version": "name-v1"})

    assert [record.asrt_id for record in records] == [ids["name_v1"]]
    assert records.one().value == "Alice"


def test_assertion_record_set_where_distinguishes_omitted_meta_from_empty_meta():
    _fg, _e_ref, snap, _ids = _make_snapshot()

    assert snap.field("tags").active.where() == snap.field("tags").active
    assert snap.field("tags").active.where(_meta={}) == snap.field("tags").active


def test_assertion_record_set_where_rejects_non_dict_meta_and_non_string_value_tag():
    _fg, _e_ref, snap, _ids = _make_snapshot()

    with pytest.raises(SDKStoreError, match="_meta"):
        snap.field("tags").active.where(_meta="tagger")
    with pytest.raises(SDKStoreError, match="value_tag"):
        snap.field("tags").active.where(value_tag=123)


def test_assertion_view_where_meta_version_uses_same_canonical_path():
    _fg, e_ref, snap, ids = _make_snapshot()

    records = snap.assertions.where(
        field=WhereUser.name,
        e_ref=e_ref,
        value="Alice",
        value_tag="string",
        _meta={"version": "name-v1"},
    )

    assert [record.asrt_id for record in records] == [ids["name_v1"]]
