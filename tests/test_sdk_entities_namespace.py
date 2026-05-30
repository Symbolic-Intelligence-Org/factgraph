"""Slice 3a Step 1 — `fg.entities.*` Layer 1 namespace acceptance tests.

Per blueprint §8 Step 1 + ADR-API §4.1(Q10 三层 namespace rename + 排他 navigation key):

- 4 base methods(`get` / `where` / `match` / `ref`)behavior equivalent to shipped
  `fg.read.*` / flat shortcuts(Step 1 coexists,no shipped deletion until Step 7)
- Layer 1 排他 enforcement(per ADR-API §4.1.1):non-Entity-subclass first arg
  raises `SDKStoreError` with layer-specific error message含 ADR-API §4.1.1 pointer
- `where` canonical signature(per ADR-API §4.4):flat `source=` / `trace_id=` /
  `version=` / `meta=` kwargs rejected,`_meta=` dict required for meta filters
- `ref` populates shadow store(per ADR-IC §4.2.3 + Slice 2 Step 7 legacy compat)

NEW test file per Slice 3a SF7 / Step 1.3 acceptance。
"""
from __future__ import annotations

import pytest

from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class EntitiesNsUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()
    status: str = Field()


def _make_fg():
    return FactGraph.create(schema_classes=[EntitiesNsUser])


def _make_materialized_fg():
    """Create FactGraph + materialize one entity for read-side tests."""
    fg = _make_fg()
    e_ref = fg.ref(EntitiesNsUser, user_id="alice", tenant_id="acme")
    fg.set(EntitiesNsUser.name, e_ref, "Alice")
    fg.set(EntitiesNsUser.status, e_ref, "active")
    return fg, e_ref


# ---------- property accessor + coexistence ----------


def test_fg_entities_returns_entities_manager():
    fg = _make_fg()
    assert type(fg.entities).__name__ == "_SDKEntitiesManager"


def test_fg_entities_namespace_is_read_only():
    """Per shipped manager convention(FrozenSnapshotError on attribute write)."""
    from factgraph._sdk_errors import FrozenSnapshotError

    fg = _make_fg()
    with pytest.raises(FrozenSnapshotError):
        fg.entities.spam = 42


def test_fg_entities_coexists_with_shipped_fg_read():
    """Step 1 does NOT delete fg.read.* — namespace coexistence verified."""
    fg = _make_fg()
    assert type(fg.read).__name__ == "_SDKReadManager"
    assert type(fg.entities).__name__ == "_SDKEntitiesManager"


def test_fg_entities_coexists_with_shipped_flat_shortcuts():
    """Step 1 does NOT delete flat fg.ref / fg.get / fg.set / etc."""
    fg = _make_fg()
    # flat fg.ref still works
    e_ref_flat = fg.ref(EntitiesNsUser, user_id="u1", tenant_id="t1")
    assert isinstance(e_ref_flat, str) and e_ref_flat.startswith("idref_v1:")
    # fg.entities.ref also works
    e_ref_ns = fg.entities.ref(EntitiesNsUser, user_id="u2", tenant_id="t1")
    assert isinstance(e_ref_ns, str) and e_ref_ns.startswith("idref_v1:")


# ---------- fg.entities.get ----------


def test_entities_get_returns_snapshot_when_entity_visible():
    fg, _ = _make_materialized_fg()
    snap = fg.entities.get(EntitiesNsUser, user_id="alice", tenant_id="acme")
    assert snap is not None
    assert snap.user_id == "alice"
    assert snap.name == "Alice"


def test_entities_get_returns_none_when_entity_not_visible():
    fg = _make_fg()
    snap = fg.entities.get(EntitiesNsUser, user_id="ghost", tenant_id="acme")
    assert snap is None


def test_entities_get_behavior_equivalent_to_fg_read_get():
    fg, _ = _make_materialized_fg()
    via_entities = fg.entities.get(EntitiesNsUser, user_id="alice", tenant_id="acme")
    via_read = fg.read.get(EntitiesNsUser, user_id="alice", tenant_id="acme")
    via_flat = fg.get(EntitiesNsUser, user_id="alice", tenant_id="acme")
    assert via_entities.user_id == via_read.user_id == via_flat.user_id
    assert via_entities.name == via_read.name == via_flat.name


# ---------- fg.entities.where ----------


def test_entities_where_with_field_filters():
    fg, _ = _make_materialized_fg()
    # Add a second entity to test filtering
    e2 = fg.ref(EntitiesNsUser, user_id="bob", tenant_id="acme")
    fg.set(EntitiesNsUser.name, e2, "Bob")
    fg.set(EntitiesNsUser.status, e2, "active")

    # Filter by name="Alice" — only alice should match(Field filtering shipped path)
    results_alice = list(fg.entities.where(EntitiesNsUser, name="Alice"))
    assert len(results_alice) == 1
    assert results_alice[0].name == "Alice"

    # Filter by status="active" — both should match
    results_active = list(fg.entities.where(EntitiesNsUser, status="active"))
    assert len(results_active) == 2


def test_entities_where_behavior_equivalent_to_fg_read_find():
    fg, _ = _make_materialized_fg()
    via_entities = list(fg.entities.where(EntitiesNsUser, status="active"))
    via_read_find = list(fg.read.find(EntitiesNsUser, status="active"))
    assert len(via_entities) == len(via_read_find)


def test_entities_where_rejects_flat_source_kwarg():
    """ADR-API §4.4:`where` does NOT accept flat meta kwargs;use _meta= dict."""
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.where(EntitiesNsUser, source="seed")
    assert "source=" in str(exc_info.value)
    assert "_meta" in str(exc_info.value)
    assert "ADR-API §4.4" in str(exc_info.value)


def test_entities_where_rejects_flat_trace_id_kwarg():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.where(EntitiesNsUser, trace_id="t-001")
    assert "trace_id=" in str(exc_info.value)


def test_entities_where_rejects_flat_version_kwarg():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.where(EntitiesNsUser, version="v1")
    assert "version=" in str(exc_info.value)


def test_entities_where_rejects_flat_meta_kwarg():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.where(EntitiesNsUser, meta={"x": "y"})
    assert "meta=" in str(exc_info.value)


def test_entities_where_accepts_empty_meta_dict():
    """Empty _meta dict is accepted as canonical signature(no meta filter applied)."""
    fg, _ = _make_materialized_fg()
    # Empty _meta dict — Step 1 accepts without filtering(equivalent to no _meta)
    results = list(fg.entities.where(EntitiesNsUser, _meta={}))
    # Same result as omitting _meta entirely
    results_no_meta = list(fg.entities.where(EntitiesNsUser))
    assert len(results) == len(results_no_meta)


def test_entities_where_accepts_none_meta():
    """_meta=None is the default and is accepted."""
    fg, _ = _make_materialized_fg()
    results = list(fg.entities.where(EntitiesNsUser, _meta=None))
    assert isinstance(results, list)


def test_entities_where_meta_filtering_deferred_to_step8():
    """Per blueprint Step 1 scope:non-empty _meta raises until Step 8 lands
    AssertionView meta-filter projection。Surfacing explicitly is safer than
    silently ignoring user input。"""
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.where(EntitiesNsUser, _meta={"source": "seed"})
    assert "meta filtering not yet implemented" in str(exc_info.value)
    assert "Step 8" in str(exc_info.value)


def test_entities_where_meta_must_be_dict():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.where(EntitiesNsUser, _meta="not_a_dict")
    assert "_meta" in str(exc_info.value)
    assert "dict" in str(exc_info.value)


# ---------- fg.entities.match ----------


def test_entities_match_behavior_equivalent_to_fg_read_match_on_invalid_template():
    """When template is None, fg.entities.match and fg.read.match should
    both produce the same error path(delegation-equivalence)。Full template
    matching is exercised by shipped Slice 1+2 tests — Step 1 verifies the
    namespace delegation,not the underlying matcher。"""
    fg = _make_fg()
    error_entities = None
    error_read = None
    try:
        list(fg.entities.match(EntitiesNsUser, None))
    except Exception as e:
        error_entities = type(e).__name__
    try:
        list(fg.read.match(EntitiesNsUser, None))
    except Exception as e:
        error_read = type(e).__name__
    # Both paths raise the same kind of error(delegation equivalence)。
    assert error_entities == error_read
    assert error_entities is not None  # both paths reject None


# ---------- fg.entities.ref ----------


def test_entities_ref_returns_deterministic_e_ref():
    fg = _make_fg()
    e1 = fg.entities.ref(EntitiesNsUser, user_id="alice", tenant_id="acme")
    e2 = fg.entities.ref(EntitiesNsUser, user_id="alice", tenant_id="acme")
    assert e1 == e2
    assert e1.startswith("idref_v1:EntitiesNsUser:")


def test_entities_ref_populates_shadow_store():
    """fg.entities.ref must populate the shadow store same as flat fg.ref
    (per ADR-IC §4.2.3 legacy compat path)."""
    fg = _make_fg()
    e_ref = fg.entities.ref(EntitiesNsUser, user_id="alice", tenant_id="acme")
    assert e_ref in fg._identity_values_by_e_ref
    assert fg._identity_values_by_e_ref[e_ref] == {"user_id": "alice", "tenant_id": "acme"}


def test_entities_ref_equivalent_to_flat_fg_ref():
    fg = _make_fg()
    e_ref_ns = fg.entities.ref(EntitiesNsUser, user_id="alice", tenant_id="acme")
    fg2 = _make_fg()
    e_ref_flat = fg2.ref(EntitiesNsUser, user_id="alice", tenant_id="acme")
    assert e_ref_ns == e_ref_flat


def test_entities_ref_then_fg_fields_set_via_shipped_path():
    """fg.entities.ref + shipped fg.set works(Step 5 will ship fg.fields.set)."""
    fg = _make_fg()
    e_ref = fg.entities.ref(EntitiesNsUser, user_id="alice", tenant_id="acme")
    asrt_id = fg.set(EntitiesNsUser.name, e_ref, "Alice")
    assert isinstance(asrt_id, str)


# ---------- Layer 1 排他 enforcement(per ADR-API §4.1.1)----------


def test_entities_get_rejects_string_arg():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.get("idref_v1:something")
    msg = str(exc_info.value)
    assert "fg.entities.get" in msg
    assert "Layer 1" in msg
    assert "fg.assertions.by_id" in msg
    assert "ADR-API §4.1.1" in msg


def test_entities_get_rejects_field_descriptor():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.get(EntitiesNsUser.name)
    msg = str(exc_info.value)
    assert "fg.entities.get" in msg
    assert "Layer 1" in msg
    assert "Field descriptor" in msg
    assert "fg.fields.*" in msg
    assert "ADR-API §4.1.1" in msg


def test_entities_where_rejects_non_entity_class():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.where("not_a_class")
    assert "fg.entities.where" in str(exc_info.value)
    assert "Layer 1" in str(exc_info.value)


def test_entities_match_rejects_non_entity_class():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.match("not_a_class", None)
    assert "fg.entities.match" in str(exc_info.value)
    assert "Layer 1" in str(exc_info.value)


def test_entities_ref_rejects_non_entity_class():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.ref("not_a_class", user_id="alice")
    assert "fg.entities.ref" in str(exc_info.value)
    assert "Layer 1" in str(exc_info.value)


def test_entities_rejection_includes_adr_pointer():
    """Each rejection error message must include ADR-API §4.1.1 pointer
    so user can navigate to the rejection rationale。"""
    fg = _make_fg()
    for method, args in [
        ("get", ("asrt_id_string",)),
        ("where", ("not_a_class",)),
        ("match", ("not_a_class", None)),
        ("ref", ("not_a_class",)),
    ]:
        with pytest.raises(SDKStoreError) as exc_info:
            getattr(fg.entities, method)(*args)
        assert "ADR-API §4.1.1" in str(exc_info.value), f"missing ADR pointer on {method}"
