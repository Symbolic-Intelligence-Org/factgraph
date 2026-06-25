"""Slice 2 Step 8 — Identity Claim emission contract acceptance tests.

Per blueprint §8 Step 8 + §7.9 + ADR-IC §4.2(emission contract):

- 8.1 fg.ref + first fg.set → atomic emit N Identity + 1 Field Claim.
- 8.2 EntityEditor.commit() Field write goes through plan_write_command
      (entity must already be materialized — fg.edit pre-validates entity visibility).
- 8.3 SDKBatchTx.commit() atomic emission contract (per ADR-IC §4.2).
- 8.4 Two field writes to same e_ref — Identity Claims emit ONLY ONCE
      (dedup per `_materialization_ops:materialized_refs`).
- 8.5 Lazy materialization through `_identity_values_by_e_ref` shadow store
      — shadow store has e_ref (via prior `fg.entities.ref(...)`) → first Field write
      auto-emits Identity Claims (shipped legacy compat path per
      ADR-IC §4.2.3).
- 8.6 e_ref NOT in shadow store (externally-constructed string) → fail-fast
      `UNRESOLVABLE_E_REF` per ADR-IC §4.2.1 emission input contract.

Per P1 #3 amend(2026-05-29): `fg.entities.create/delete` full-entity API
**NOT TESTED** here — recorded as Slice 3a ADR-API Q10 namespace migration
carry-forward.

Pred ID conventions (shipped, verified via probe):
- Identity / Field predicates: `<snake_owner_prefix>:<field_name>` e.g.
  `emission_user:user_id` for class `EmissionUser`.

NEW test file per Slice 2 SF7.
"""
from collections import Counter

import pytest

from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class EmissionUser(Entity):
    """Two Identity fields + single + multi Field — exercises bundle + dedup."""

    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


# Pred IDs derived from EmissionUser class name + Slice 1 shipped naming.
PRED_USER_ID = "emission_user:user_id"
PRED_TENANT_ID = "emission_user:tenant_id"
PRED_NAME = "emission_user:name"
PRED_EXISTS = "EmissionUser:exists"
PRED_TAGS = "emission_user:tags"


def _claim_counts(fg: FactGraph, e_ref: str) -> Counter:
    """Count Claims by pred_id for a given e_ref."""
    return Counter(c.pred_id for c in fg._store.ledger.find_claims(e_ref=e_ref))


def _rest_value(rest_terms: list) -> object:
    """Extract the single value from rest_terms (e.g. [('string', 'Alice')] → 'Alice')."""
    if not rest_terms:
        return None
    if len(rest_terms) == 1 and isinstance(rest_terms[0], tuple) and len(rest_terms[0]) == 2:
        return rest_terms[0][1]
    return rest_terms


# ---------- 8.1 fg.ref + first fg.set atomic emission ----------


def test_emission_8_1_fg_ref_plus_fg_set_atomic_emits_n_identity_field():
    """fg.ref + first fg.set → 3 Claims atomic (2 Identity + 1 Field)."""
    fg = FactGraph.create(schema_classes=[EmissionUser])
    e_ref = fg.entities.ref(EmissionUser, user_id="u1", tenant_id="t1")

    # Before first Field write: shadow store has e_ref, ledger has NO claims.
    assert _claim_counts(fg, e_ref) == Counter()
    assert e_ref in fg._identity_values_by_e_ref  # shadow store seen

    fg.fields.set(EmissionUser.name, e_ref, "Alice")

    # 4 Claims atomically emitted per Q-EXISTS §4.4:
    # 2 Identity Claims (user_id + tenant_id) + the co-emitted :exists + 1 Field (name).
    counts = _claim_counts(fg, e_ref)
    assert counts == Counter({
        PRED_USER_ID: 1,
        PRED_TENANT_ID: 1,
        PRED_EXISTS: 1,
        PRED_NAME: 1,
    })


def test_emission_8_1_identity_bundle_carries_complete_values():
    """Each Identity Claim carries the correct value from identity_kwargs (per SF8 bundle)."""
    fg = FactGraph.create(schema_classes=[EmissionUser])
    e_ref = fg.entities.ref(EmissionUser, user_id="u1", tenant_id="t1")
    fg.fields.set(EmissionUser.name, e_ref, "Alice")

    user_id_claim = fg._store.ledger.find_claims(pred_id=PRED_USER_ID, e_ref=e_ref)
    tenant_id_claim = fg._store.ledger.find_claims(pred_id=PRED_TENANT_ID, e_ref=e_ref)
    name_claim = fg._store.ledger.find_claims(pred_id=PRED_NAME, e_ref=e_ref)

    assert len(user_id_claim) == 1 and _rest_value(user_id_claim[0].rest_terms) == "u1"
    assert len(tenant_id_claim) == 1 and _rest_value(tenant_id_claim[0].rest_terms) == "t1"
    assert len(name_claim) == 1 and _rest_value(name_claim[0].rest_terms) == "Alice"


# ---------- 8.2 EntityEditor.commit() Field write through plan_write_command ----------


def test_emission_8_2_entity_editor_commit_routes_field_write_through_planner():
    """fg.edit + editor.field.set + editor.commit() goes through plan_write_command.

    NOTE: fg.entities.edit() requires entity already materialized (pre-validates entity visibility
    via sdk_get). So EntityEditor is NOT a materialization path; it's the
    edit-existing-entity path that shares the same plan_write_command write
    plumbing. Test verifies: after editor.commit(), a new Field Claim was
    appended (no extra Identity re-emission since target visible).
    """
    fg = FactGraph.create(schema_classes=[EmissionUser])
    e_ref = fg.entities.ref(EmissionUser, user_id="u1", tenant_id="t1")
    # Materialize via first fg.set.
    fg.fields.set(EmissionUser.name, e_ref, "Alice")
    counts_after_first = _claim_counts(fg, e_ref)
    assert counts_after_first[PRED_USER_ID] == 1
    assert counts_after_first[PRED_TENANT_ID] == 1
    assert counts_after_first[PRED_NAME] == 1

    # Edit existing entity, set a new Field value.
    editor = fg.entities.edit(EmissionUser, user_id="u1", tenant_id="t1")
    editor.name.set("Bob")
    editor.commit()

    counts_after_edit = _claim_counts(fg, e_ref)
    # Identity Claim counts UNCHANGED (no re-materialization).
    assert counts_after_edit[PRED_USER_ID] == 1
    assert counts_after_edit[PRED_TENANT_ID] == 1
    # name has 2 Claims now (original + editor write).
    assert counts_after_edit[PRED_NAME] == 2


def test_emission_8_2_entity_editor_rejects_unmaterialized_entity():
    """fg.edit pre-validates entity visibility — unmaterialized entity raises EntityNotFoundError.

    Confirms editor is NOT a materialization path (per ADR-IC §4.2.3 — the
    materialization route is fg.ref + fg.set / SDKBatchTx).
    """
    from factgraph._sdk_errors import EntityNotFoundError

    fg = FactGraph.create(schema_classes=[EmissionUser])
    fg.entities.ref(EmissionUser, user_id="u1", tenant_id="t1")  # shadow store, no ledger emit
    with pytest.raises(EntityNotFoundError):
        fg.entities.edit(EmissionUser, user_id="u1", tenant_id="t1")


# ---------- 8.3 SDKBatchTx.commit() atomic emission ----------


def test_emission_8_3_sdk_batch_tx_commit_atomic_emits_full_bundle():
    """fg.batch + tx.entity + handle.field.set + tx.commit() → atomic emission.

    Verifies per ADR-IC §4.2 atomic guarantee:
    full Identity bundle + Field Claims in single commit.
    """
    fg = FactGraph.create(schema_classes=[EmissionUser])
    tx = fg.batch()
    h = tx.entity(EmissionUser, user_id="u1", tenant_id="t1")
    h.name.set("Alice")

    # Before commit: no Claims emitted yet (staged in batch only).
    assert _claim_counts(fg, h.e_ref) == Counter()

    tx.commit()

    # After commit: full bundle atomically present in ledger.
    counts = _claim_counts(fg, h.e_ref)
    assert counts == Counter({
        PRED_USER_ID: 1,
        PRED_TENANT_ID: 1,
        PRED_NAME: 1,
    })


def test_emission_8_3_sdk_batch_tx_multi_entity_each_gets_full_bundle():
    """Multi-entity batch — each entity gets its own complete Identity bundle."""
    fg = FactGraph.create(schema_classes=[EmissionUser])
    tx = fg.batch()
    h_alice = tx.entity(EmissionUser, user_id="u1", tenant_id="t1")
    h_alice.name.set("Alice")
    h_bob = tx.entity(EmissionUser, user_id="u2", tenant_id="t1")
    h_bob.name.set("Bob")
    tx.commit()

    counts_alice = _claim_counts(fg, h_alice.e_ref)
    counts_bob = _claim_counts(fg, h_bob.e_ref)
    expected = Counter({PRED_USER_ID: 1, PRED_TENANT_ID: 1, PRED_NAME: 1})
    assert counts_alice == expected
    assert counts_bob == expected
    # Cross-entity: e_refs distinct, claims indexed separately.
    assert h_alice.e_ref != h_bob.e_ref


# ---------- 8.4 Dedup: two field writes to same e_ref → Identity emits ONCE ----------


def test_emission_8_4_two_field_writes_identity_emits_only_once():
    """fg.set + fg.add on same e_ref → Identity Claims emit only ONCE.

    Dedup verified at the materialized_refs level inside plan_write_command
    (per `_materialization_ops` shipped path) and at the target_visible check
    on the second call (entity now visible in active view → no re-materialization).
    """
    fg = FactGraph.create(schema_classes=[EmissionUser])
    e_ref = fg.entities.ref(EmissionUser, user_id="u1", tenant_id="t1")

    fg.fields.set(EmissionUser.name, e_ref, "Alice")
    counts_after_first = _claim_counts(fg, e_ref)
    assert counts_after_first[PRED_USER_ID] == 1
    assert counts_after_first[PRED_TENANT_ID] == 1
    assert counts_after_first[PRED_NAME] == 1

    fg.fields.add(EmissionUser.tags, e_ref, "active")

    counts_after_second = _claim_counts(fg, e_ref)
    # Identity counts UNCHANGED.
    assert counts_after_second[PRED_USER_ID] == 1
    assert counts_after_second[PRED_TENANT_ID] == 1
    # name unchanged + tags +1.
    assert counts_after_second[PRED_NAME] == 1
    assert counts_after_second[PRED_TAGS] == 1


def test_emission_8_4_batch_dedup_within_single_commit():
    """Within a single SDKBatchTx commit, multiple Field writes on one handle
    do NOT cause Identity bundle re-emission (materialized_refs dedup).
    """
    fg = FactGraph.create(schema_classes=[EmissionUser])
    tx = fg.batch()
    h = tx.entity(EmissionUser, user_id="u1", tenant_id="t1")
    h.name.set("Alice")
    h.tags.add("active")
    h.tags.add("verified")
    tx.commit()

    counts = _claim_counts(fg, h.e_ref)
    # Identity Claims exactly once despite 3 Field operations.
    assert counts[PRED_USER_ID] == 1
    assert counts[PRED_TENANT_ID] == 1
    # name single-cardinality (1 Claim), tags multi-cardinality (2 Claims).
    assert counts[PRED_NAME] == 1
    assert counts[PRED_TAGS] == 2


# ---------- 8.5 Lazy materialization through shadow store ----------


def test_emission_8_5_lazy_materialization_through_shadow_store():
    """fg.ref populates shadow store; first Field write lazy-materializes
    Identity Claims through `_materialization_ops` (per ADR-IC §4.2.3).
    """
    fg = FactGraph.create(schema_classes=[EmissionUser])

    # fg.ref populates shadow store only (no ledger emission).
    e_ref = fg.entities.ref(EmissionUser, user_id="u1", tenant_id="t1")
    assert e_ref in fg._identity_values_by_e_ref
    assert fg._identity_values_by_e_ref[e_ref] == {"user_id": "u1", "tenant_id": "t1"}
    # Ledger empty: shadow store DOES NOT emit Identity Claims at ref() time.
    assert len(fg._store.ledger.find_claims(e_ref=e_ref)) == 0

    # First Field write triggers lazy materialization (per _materialization_ops).
    fg.fields.set(EmissionUser.name, e_ref, "Alice")
    counts = _claim_counts(fg, e_ref)
    assert counts[PRED_USER_ID] == 1
    assert counts[PRED_TENANT_ID] == 1
    assert counts[PRED_NAME] == 1


# ---------- 8.6 Unseen e_ref → UNRESOLVABLE_E_REF fail-fast ----------


def test_emission_8_6_unseen_e_ref_target_fails_fast_with_unresolvable_code():
    """Externally-constructed e_ref (not from fg.ref) → fail-fast UNRESOLVABLE_E_REF.

    Per ADR-IC §4.2.1 emission input contract: Layer 2 fields API requires
    the e_ref to have been produced by `sdk.ref(...)` (shadow store seen).
    """
    fg = FactGraph.create(schema_classes=[EmissionUser])
    fake_e_ref = "idref_v1:EmissionUser:fakehash00000000"

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.set(EmissionUser.name, fake_e_ref, "Alice")
    err = exc_info.value
    assert err.code == "UNRESOLVABLE_E_REF"
    assert fake_e_ref in str(err)
    # Migration hint must mention the namespace ref entry to obtain managed e_ref.
    assert "fg.entities.ref" in str(err)


def test_emission_8_6_unseen_entity_ref_value_fails_fast():
    """Externally-constructed e_ref AS VALUE for entity_ref field → UNRESOLVABLE_E_REF.

    Per shadow store legacy comment (Step 7): the fail-fast also applies to
    the entity_ref value path in `_build_application_write_value`.
    """
    class EmissionPost(Entity):
        post_id: str = Identity()
        author: EmissionUser = Field()  # entity_ref field

    fg = FactGraph.create(schema_classes=[EmissionUser, EmissionPost])
    post_ref = fg.entities.ref(EmissionPost, post_id="p1")
    fake_author_ref = "idref_v1:EmissionUser:fakehash00000000"

    with pytest.raises(SDKStoreError) as exc_info:
        fg.fields.set(EmissionPost.author, post_ref, fake_author_ref)
    err = exc_info.value
    assert err.code == "UNRESOLVABLE_E_REF"
    assert fake_author_ref in str(err)


# ---------- 8.7 NOT TESTED — fg.entities.create / fg.entities.delete ----------
# Per blueprint Step 8.7 + P1 #3 amend(2026-05-29):
# Full-entity API paths `fg.entities.create(EntityCls, **identity_kwargs)` and
# `fg.entities.delete(e_ref)` are Slice 3a ADR-API Q10 namespace migration scope.
# Slice 2 error wording references these as user-migration guidance only;
# implementation/acceptance does NOT depend on the unshipped API.
# When Slice 3a lands, add an `fg.entities.delete` + new-identity-create
# whole-entity revoke acceptance test here.
