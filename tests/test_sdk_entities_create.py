"""Slice 3a Step 2 — `fg.entities.create` eager emission acceptance tests.

Per blueprint §8 Step 2 + §5.3 + §7.2 + SF3 + SF4 + ADR-IC §4.2(emission
contract — application 层 derive)+ ADR-IC §4.2.1(complete identity bundle)+
ADR-API §4.1.2(entities namespace migration mapping)。

Test scope:
- **Eager emission**:`create` 立即 emit N Identity Claims in ledger Active
  set(per SF4 — eager,not lazy)。
- **Shadow store populate**:`create` populates `_identity_values_by_e_ref`
  via shipped `SDKStore.ref` path(per SF4 legacy compat coexist)。
- **Duplicate reject**:second `create` 同 identity 抛
  `EntityAlreadyExistsError(code="ENTITY_ALREADY_EXISTS")`(per blueprint
  §13.1 + §5.3)。
- **Identity bundle completeness**:missing identity field 抛
  `SDKStoreError`(per ADR-IC §4.2.1 emission input contract)。
- **Coexistence with lazy path**:shipped `fg.ref + fg.set` 仍工作 after
  `create`(per SF4 — Slice 3a NOT remove shadow store)。
- **Application layer planner used**(per SF3 INV-6):SDK manager 只归一化,
  application path 才是源头 — test that `EntityCreateCommand` shape is
  acceptable + planner returns expected plan structure。
- **Layer 1 排他 enforcement**:non-Entity-class first arg rejected with
  ADR-API §4.1.1 layer pointer(reuses Step 1 helper)。

NEW test file per Slice 3a SF7 + Step 2.6 acceptance。
"""
from __future__ import annotations

from collections import Counter

import pytest

from factgraph._sdk_errors import EntityAlreadyExistsError
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


# ---------- public SDK surface export check(P2 amend 2026-05-30)----------


def test_entity_already_exists_error_exported_from_sdk_top_level():
    """`EntityAlreadyExistsError` must be importable from `factgraph.sdk`
    top-level alongside other public SDK errors(`SDKStoreError` /
    `EntityNotFoundError` / `CardinalityError` etc.)。

    `fg.entities.create` is a public API,so the typed duplicate-create
    error must be on the same public export surface for user code to
    catch it without reaching into `factgraph._sdk_errors` internal module。
    """
    from factgraph.sdk import (  # type: ignore[attr-defined]
        EntityAlreadyExistsError as PublicEntityAlreadyExistsError,
    )
    from factgraph.sdk import SDKStoreError as PublicSDKStoreError

    # Same class object across import paths(no shadowing duplication)
    assert PublicEntityAlreadyExistsError is EntityAlreadyExistsError
    # Subclass relationship preserved on the public re-export path
    assert issubclass(PublicEntityAlreadyExistsError, PublicSDKStoreError)


def test_entity_already_exists_error_listed_in_sdk_all():
    """`__all__` of `factgraph.sdk` must list `EntityAlreadyExistsError`
    so wildcard imports + IDE / type-checker tooling pick it up。"""
    import factgraph.sdk as sdk_pkg

    assert "EntityAlreadyExistsError" in sdk_pkg.__all__


class CreateUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()


PRED_USER_ID = "create_user:user_id"
PRED_TENANT_ID = "create_user:tenant_id"
PRED_NAME = "create_user:name"
# :exists is co-emitted atomically with the Identity Claims (ADR-IC §4.4 —
# the existence-claim is now a real rule-matchable EDB fact, not transitional).
PRED_EXISTS = "CreateUser:exists"


def _make_fg():
    return FactGraph.create(schema_classes=[CreateUser])


def _claim_counts(fg: FactGraph, e_ref: str) -> Counter:
    return Counter(c.pred_id for c in fg._store.ledger.find_claims(e_ref=e_ref))


# ---------- eager emission contract(SF4 + ADR-IC §4.2)----------


def test_create_eager_emits_n_identity_atomic():
    """`fg.entities.create` 立即 emit N Identity Claims —
    NOT lazy(对比 shipped `fg.ref + fg.set` first Field write 才 materialize)。"""
    fg = _make_fg()

    # Before create: 0 claims for this e_ref
    e_ref_pre = fg.entities.ref(CreateUser, user_id="probe", tenant_id="acme")
    assert _claim_counts(fg, e_ref_pre) == Counter()

    # Create eager — should immediately emit Identity Claims.
    e_ref = fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")
    counts = _claim_counts(fg, e_ref)
    # No Field Claim yet (create only emits Identity + :exists; Field requires fg.set)
    assert counts == Counter({
        PRED_USER_ID: 1,
        PRED_TENANT_ID: 1,
        PRED_EXISTS: 1,
    })


def test_create_returns_deterministic_e_ref():
    """`fg.entities.create` returns the same e_ref as `fg.entities.ref` /
    `fg.ref` for the same identity bundle(deterministic typed constructor)。"""
    fg = _make_fg()
    e_ref_create = fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")

    fg2 = _make_fg()
    e_ref_ref = fg2.entities.ref(CreateUser, user_id="alice", tenant_id="acme")
    assert e_ref_create == e_ref_ref

    fg3 = _make_fg()
    e_ref_ref_again = fg3.entities.ref(CreateUser, user_id="alice", tenant_id="acme")
    assert e_ref_create == e_ref_ref_again


def test_create_identity_bundle_carries_correct_values():
    """Each emitted Identity Claim carries the correct value from kwargs。"""
    fg = _make_fg()
    e_ref = fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")

    user_id_claims = fg._store.ledger.find_claims(pred_id=PRED_USER_ID, e_ref=e_ref)
    tenant_id_claims = fg._store.ledger.find_claims(pred_id=PRED_TENANT_ID, e_ref=e_ref)

    assert len(user_id_claims) == 1
    assert user_id_claims[0].rest_terms == [("string", "alice")]
    assert len(tenant_id_claims) == 1
    assert tenant_id_claims[0].rest_terms == [("string", "acme")]


def test_create_meta_kwarg_propagates_to_claim_meta():
    """`meta=` kwarg flows through `command_meta` into emitted Claim meta。"""
    fg = _make_fg()
    e_ref = fg.entities.create(
        CreateUser,
        user_id="alice",
        tenant_id="acme",
        meta={"source": "step2_test"},
    )
    # All emitted claims should carry the source meta
    claims = fg._store.ledger.find_claims(e_ref=e_ref)
    assert len(claims) == 3  # 2 Identity + 1 :exists
    for claim in claims:
        meta_rows = fg._store.ledger.find_meta(asrt_id=claim.asrt_id)
        meta_map = {row.key: row.value for row in meta_rows}
        assert meta_map.get("source") == "step2_test", (
            f"missing source meta on claim {claim.asrt_id} ({claim.pred_id})"
        )


# ---------- shadow store populate(SF4)----------


def test_create_populates_shadow_store():
    """`fg.entities.create` populates `_identity_values_by_e_ref` for legacy
    compat with `fg.set` / `fg.add` Layer 2 fields API per ADR-IC §4.2.3。"""
    fg = _make_fg()
    e_ref = fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")
    assert e_ref in fg._identity_values_by_e_ref
    assert fg._identity_values_by_e_ref[e_ref] == {
        "user_id": "alice",
        "tenant_id": "acme",
    }


def test_create_then_shipped_fg_set_works():
    """After eager `create`,shipped `fg.set` writes Field Claim through the
    coexisting shadow-store path — Slice 3a does NOT remove shadow store
    (per SF4 + ADR-IC §4.2.4 Step 2+ direction)。"""
    fg = _make_fg()
    e_ref = fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")
    asrt_id = fg.fields.set(CreateUser.name, e_ref, "Alice")
    assert isinstance(asrt_id, str)

    counts = _claim_counts(fg, e_ref)
    # Identity (2) + :exists unchanged + 1 Field Claim added
    assert counts == Counter({
        PRED_USER_ID: 1,
        PRED_TENANT_ID: 1,
        PRED_EXISTS: 1,
        PRED_NAME: 1,
    })


# ---------- duplicate reject(blueprint §13.1 + §5.3)----------


def test_create_duplicate_raises_entity_already_exists():
    """Second `create` 同 identity bundle 抛 EntityAlreadyExistsError。"""
    fg = _make_fg()
    e_ref_first = fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")

    with pytest.raises(EntityAlreadyExistsError) as exc_info:
        fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")

    err = exc_info.value
    assert err.code == "ENTITY_ALREADY_EXISTS"
    assert err.entity_type == "CreateUser"
    assert err.identity_kwargs == {"user_id": "alice", "tenant_id": "acme"}
    assert err.e_ref == e_ref_first


def test_create_duplicate_error_message_references_delete_path():
    """Per ADR-IC §4.1:error message must guide user to delete+create path
    if they intend to change the identity bundle。"""
    fg = _make_fg()
    fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")

    with pytest.raises(EntityAlreadyExistsError) as exc_info:
        fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")
    msg = str(exc_info.value)
    assert "fg.entities.delete" in msg
    assert "fg.fields.set" in msg or "fg.fields.add" in msg


def test_create_duplicate_after_lazy_materialization_also_rejects():
    """If entity materialized via lazy path(`fg.ref + fg.set`),subsequent
    `fg.entities.create` should still reject — entity exists per ledger view。"""
    fg = _make_fg()
    e_ref = fg.entities.ref(CreateUser, user_id="alice", tenant_id="acme")
    fg.fields.set(CreateUser.name, e_ref, "Alice")  # lazy materialization

    with pytest.raises(EntityAlreadyExistsError) as exc_info:
        fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")
    assert exc_info.value.code == "ENTITY_ALREADY_EXISTS"


# ---------- identity bundle completeness(ADR-IC §4.2.1)----------


def test_create_missing_identity_field_raises():
    """ADR-IC §4.2.1 emission input contract:**complete** identity bundle
    required;missing field rejected。"""
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.create(CreateUser, user_id="only_one")  # missing tenant_id
    assert "missing identity field" in str(exc_info.value)
    assert "tenant_id" in str(exc_info.value)


def test_create_no_identity_kwargs_raises():
    fg = _make_fg()
    with pytest.raises(SDKStoreError):
        fg.entities.create(CreateUser)


# ---------- coexistence with lazy materialization path(SF4)----------


def test_lazy_path_still_works_after_create_of_different_entity():
    """Lazy `fg.ref + fg.set` continues to work after some entities were
    created eagerly via `fg.entities.create` — both paths coexist。"""
    fg = _make_fg()
    # Entity A: eager create
    e_a = fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")
    # Entity B: lazy ref + set
    e_b = fg.entities.ref(CreateUser, user_id="bob", tenant_id="acme")
    fg.fields.set(CreateUser.name, e_b, "Bob")

    counts_a = _claim_counts(fg, e_a)
    counts_b = _claim_counts(fg, e_b)
    # A: 2 Identity + :exists (no Field)
    assert counts_a == Counter({PRED_USER_ID: 1, PRED_TENANT_ID: 1, PRED_EXISTS: 1})
    # B: 2 Identity + :exists + 1 Field
    assert counts_b == Counter({PRED_USER_ID: 1, PRED_TENANT_ID: 1, PRED_EXISTS: 1, PRED_NAME: 1})


# ---------- application layer planner(SF3 INV-6)----------


def test_application_planner_can_be_invoked_directly():
    """Application-layer `plan_create_command` + `apply_create_plan` are
    public functions(per SF3 — SDK manager is only a thin shell around
    application path)。Direct invocation works for tooling / advanced use。"""
    from factgraph.application import apply_create_plan, plan_create_command
    from factgraph.application.protocol import EntityCreateCommand, EntitySelector

    fg = _make_fg()
    command = EntityCreateCommand(
        target=EntitySelector(
            entity_type="CreateUser",
            identity={"user_id": "alice", "tenant_id": "acme"},
        ),
        command_meta={},
    )
    plan = plan_create_command(
        command,
        store=fg._store,
        index=fg._application_schema_index,
    )
    assert plan.can_apply
    assert plan.errors == ()
    # 2 Identity set ops + the co-emitted :exists (record_exists) op.
    assert [op.op for op in plan.planned_ops] == ["set", "set", "record_exists"]

    result = apply_create_plan(
        plan,
        store=fg._store,
        index=fg._application_schema_index,
    )
    assert result.errors == ()
    assert len(result.applied) == 3
    assert all(applied.status == "applied" for applied in result.applied)


def test_application_planner_rejects_duplicate_via_can_apply_false():
    """Planner returns `can_apply=False` with ErrorDTO when entity exists —
    no exception leaks across application/SDK boundary。"""
    from factgraph.application import plan_create_command
    from factgraph.application.protocol import EntityCreateCommand, EntitySelector

    fg = _make_fg()
    fg.entities.create(CreateUser, user_id="alice", tenant_id="acme")

    command = EntityCreateCommand(
        target=EntitySelector(
            entity_type="CreateUser",
            identity={"user_id": "alice", "tenant_id": "acme"},
        ),
        command_meta={},
    )
    plan = plan_create_command(
        command,
        store=fg._store,
        index=fg._application_schema_index,
    )
    assert plan.can_apply is False
    assert len(plan.errors) == 1
    assert plan.errors[0].code == "ENTITY_ALREADY_EXISTS"


# ---------- Layer 1 排他 enforcement(reuses Step 1 helper)----------


def test_create_rejects_string_arg():
    """Layer 1 排他 per ADR-API §4.1.1:non-Entity-class first arg rejected。"""
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.create("idref_v1:something", user_id="alice")
    msg = str(exc_info.value)
    assert "fg.entities.create" in msg
    assert "Layer 1" in msg
    assert "ADR-API §4.1.1" in msg


def test_create_rejects_field_descriptor():
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.create(CreateUser.name, user_id="alice")
    msg = str(exc_info.value)
    assert "fg.entities.create" in msg
    assert "Field descriptor" in msg
    assert "ADR-API §4.1.1" in msg
