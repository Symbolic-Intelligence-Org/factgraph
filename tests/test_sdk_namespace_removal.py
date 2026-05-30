"""Slice 3a Step 7 — read/write namespace + flat shortcut removal tests."""
from __future__ import annotations

import pytest

from factgraph._sdk_errors import EntityNotFoundError
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class NamespaceUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


def _make_fg():
    return FactGraph.create(schema_classes=[NamespaceUser])


def _make_created_fg():
    fg = _make_fg()
    e_ref = fg.entities.create(NamespaceUser, user_id="alice", tenant_id="acme")
    return fg, e_ref


def test_fg_read_and_write_namespaces_are_removed():
    fg = _make_fg()

    with pytest.raises(AttributeError):
        getattr(fg, "read")
    with pytest.raises(AttributeError):
        getattr(fg, "write")


@pytest.mark.parametrize(
    "shortcut",
    ["set", "add", "retract", "edit", "get", "ref", "find", "match"],
)
def test_flat_top_level_shortcuts_are_removed(shortcut: str):
    fg = _make_fg()

    with pytest.raises(AttributeError):
        getattr(fg, shortcut)


def test_entities_edit_replaces_flat_edit_entrypoint():
    fg, e_ref = _make_created_fg()
    fg.fields.set(NamespaceUser.name, e_ref, "Alice")

    editor = fg.entities.edit(NamespaceUser, user_id="alice", tenant_id="acme")
    editor.name.set("Alicia")
    editor.tags.add("vip")
    editor.commit()

    snap = fg.entities.get(NamespaceUser, user_id="alice", tenant_id="acme")
    assert snap is not None
    assert snap.name == "Alicia"
    assert snap.tags == ("vip",)


def test_entities_edit_rejects_unmaterialized_entity():
    fg = _make_fg()
    fg.entities.ref(NamespaceUser, user_id="ghost", tenant_id="acme")

    with pytest.raises(EntityNotFoundError):
        fg.entities.edit(NamespaceUser, user_id="ghost", tenant_id="acme")


def test_entities_fields_assertions_replace_removed_shortcuts():
    fg, e_ref = _make_created_fg()

    name_asrt = fg.fields.set(NamespaceUser.name, e_ref, "Alice")
    tag_asrt = fg.fields.add(NamespaceUser.tags, e_ref, "vip")

    assert fg.entities.get(NamespaceUser, user_id="alice", tenant_id="acme").name == "Alice"
    assert [row.name for row in fg.entities.where(NamespaceUser, name="Alice")] == ["Alice"]
    assert fg.fields.get(NamespaceUser.tags, e_ref) == ("vip",)
    assert fg.assertions.by_id(name_asrt).asrt_id == name_asrt

    fg.assertions.retract(tag_asrt)
    assert fg.fields.get(NamespaceUser.tags, e_ref) == ()


def test_fields_set_still_rejects_identity_descriptor_after_flat_removal():
    fg, e_ref = _make_created_fg()

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.set(NamespaceUser.user_id, e_ref, "alice")

    msg = str(exc_info.value)
    assert "INV-7c" in msg
    assert "fg.entities.delete" in msg
