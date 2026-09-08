"""Slice 3a Step 3 — `fg.entities.delete` whole-entity revoke acceptance tests.

Per blueprint §8 Step 3 + §5.4 + §7.2 + SF2 (discriminated signature) + SF3
(P1 amend — path-bound guard-bypass NOT metadata signal) + ADR-IC §4.1
强制点 3 (整批撤销 唯一合法路径)。

Test scope:
- **PF-S2 discriminated signature**:Form A `delete(e_ref: str)` + Form B
  `delete(EntityCls, **identity)`;tuple selector rejected with PF-S2 wording。
- **Atomic whole-entity revoke**:all Active Claims under e_ref(Identity +
  Field,and legacy `:exists` when present)revoked atomically;Active count → 0。
- **Path-bound guard-bypass(SF3 P1 amend — STRUCTURAL invariants)**:
  - generic `_apply_op(PlannedOpDTO(op="retract", asrt=identity))` still
    raises `INV_7C_IDENTITY_PROTECTED` — generic dispatcher 不可 bypass
  - `_apply_entity_delete_retract` 不出现在 `_apply_op` body — grep + import
    audit invariant 防 future drift
  - `fg.entities.delete(Identity Claim)` works via path-bound private executor
- **Recreate after delete**:fully revoked entity can be re-created with same
  identity bundle(per ADR-IC §4.1 INV-7a — `delete + create` 是 identity
  bundle 修改的唯一合法路径)。
- **Layer 1 排他 enforcement**:non-Entity non-str first arg rejected。

NEW test file per Slice 3a SF7 + Step 3.6 acceptance。
"""
from __future__ import annotations

import inspect
from collections import Counter

import pytest

from factgraph._sdk_errors import EntityNotFoundError
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class DelUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()
    status: str = Field()


PRED_USER_ID = "del_user:user_id"
PRED_TENANT_ID = "del_user:tenant_id"
PRED_EXISTS = "DelUser:exists"
PRED_NAME = "del_user:name"
PRED_STATUS = "del_user:status"


def _make_fg():
    return FactGraph.create(schema_classes=[DelUser])


def _make_materialized_fg():
    fg = _make_fg()
    e_ref = fg.entities.create(DelUser, user_id="alice", tenant_id="acme")
    fg.fields.set(DelUser.name, e_ref, "Alice")
    fg.fields.set(DelUser.status, e_ref, "active")
    return fg, e_ref


def _active_claim_counts(fg: FactGraph, e_ref: str) -> Counter:
    return Counter(
        c.pred_id
        for c in fg._store.ledger.find_claims(e_ref=e_ref)
        if not fg._store.ledger.has_active_revocation(c.asrt_id)
    )


def _write_legacy_exists_claim(fg: FactGraph, e_ref: str) -> str:
    from factgraph.application import apply_write_plan
    from factgraph.application.protocol import (
        EntityRef,
        EntitySelector,
        EntityWriteCommand,
        EntityWritePlan,
        PlannedOpDTO,
    )

    identity = dict(fg._identity_values_by_e_ref[e_ref])
    target = EntityRef(entity_type="DelUser", identity=identity, encoded_ref=e_ref)
    plan = EntityWritePlan(
        command=EntityWriteCommand(
            target=EntitySelector(entity_type="DelUser", identity=identity, encoded_ref=e_ref),
        ),
        resolved_target=target,
        planned_ops=(PlannedOpDTO(op="record_exists", target=target),),
        can_apply=True,
    )
    result = apply_write_plan(
        plan,
        store=fg._store,
        index=fg._application_schema_index,
        database=fg._database_for_application_write("legacy exists test fixture"),
    )
    assert result.errors == ()
    assert result.applied[0].assertion_id is not None
    return result.applied[0].assertion_id


# ---------- Form A: delete(e_ref: str)----------


def test_delete_form_a_revokes_all_active_claims():
    """`delete(e_ref: str)` revokes all Active Claims under that e_ref atomically。"""
    fg, e_ref = _make_materialized_fg()
    # Pre: 4 Active Claims (2 Identity + 2 Field); :exists is virtual.
    assert _active_claim_counts(fg, e_ref) == Counter({
        PRED_USER_ID: 1,
        PRED_TENANT_ID: 1,
        PRED_NAME: 1,
        PRED_STATUS: 1,
    })

    revoked = fg.entities.delete(e_ref)
    assert revoked == 4
    # Post: 0 Active Claims
    assert _active_claim_counts(fg, e_ref) == Counter()


def test_delete_form_a_revokes_legacy_exists_claim_when_present():
    fg, e_ref = _make_materialized_fg()
    exists_asrt = _write_legacy_exists_claim(fg, e_ref)

    assert _active_claim_counts(fg, e_ref)[PRED_EXISTS] == 1
    revoked = fg.entities.delete(e_ref)

    assert revoked == 5
    assert fg._store.ledger.has_active_revocation(exists_asrt)
    assert _active_claim_counts(fg, e_ref) == Counter()


def test_delete_form_a_does_not_remove_ledger_history():
    """Delete is revoke-by-append per ADR-IC INV-11/12/13 — original Claims
    remain in ledger history with active revocations recorded。"""
    fg, e_ref = _make_materialized_fg()
    pre_count = len(fg._store.ledger.find_claims(e_ref=e_ref))
    fg.entities.delete(e_ref)
    post_count = len(fg._store.ledger.find_claims(e_ref=e_ref))
    # Same count(history preserved);revocations added separately
    assert post_count == pre_count
    # All claims now revoked
    for claim in fg._store.ledger.find_claims(e_ref=e_ref):
        assert fg._store.ledger.has_active_revocation(claim.asrt_id)


def test_delete_form_a_rejects_unmanaged_e_ref():
    fg = _make_fg()
    fake_e_ref = "idref_v1:DelUser:fakehash0000000000"
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.delete(fake_e_ref)
    assert exc_info.value.code == "UNRESOLVABLE_E_REF"


def test_delete_form_a_rejects_identity_kwargs():
    """Form A is e_ref-only;extra identity kwargs are reserved for Form B。"""
    fg, e_ref = _make_materialized_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.delete(e_ref, user_id="alice")  # mixed forms forbidden
    msg = str(exc_info.value)
    assert "Form A" in msg or "e_ref" in msg


# ---------- Form B: delete(EntityCls, **identity)----------


def test_delete_form_b_revokes_all_active_claims():
    fg, e_ref = _make_materialized_fg()
    revoked = fg.entities.delete(DelUser, user_id="alice", tenant_id="acme")
    assert revoked == 4  # 2 Identity + 2 Field
    assert _active_claim_counts(fg, e_ref) == Counter()


def test_delete_form_a_and_form_b_equivalent():
    fg_a, e_a = _make_materialized_fg()
    fg_b, e_b = _make_materialized_fg()
    n_a = fg_a.entities.delete(e_a)
    n_b = fg_b.entities.delete(DelUser, user_id="alice", tenant_id="acme")
    assert n_a == n_b


def test_delete_form_b_rejects_missing_identity_field():
    fg, _ = _make_materialized_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.delete(DelUser, user_id="only_one")  # missing tenant_id
    assert "missing identity field" in str(exc_info.value)


# ---------- tuple selector forbidden(PF-S2)----------


def test_delete_rejects_tuple_selector():
    """Per PF-S2 lock:tuple selector explicitly forbidden — error message
    must guide user to Form A or Form B。"""
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.delete((DelUser, {"user_id": "alice"}))
    msg = str(exc_info.value)
    assert "requires e_ref string OR EntityClass + full identity bundle" in msg
    assert "ADR-API §4.1.2" in msg


def test_delete_rejects_list_selector():
    fg = _make_fg()
    with pytest.raises(SDKStoreError):
        fg.entities.delete([DelUser, "alice", "acme"])


def test_delete_rejects_int():
    fg = _make_fg()
    with pytest.raises(SDKStoreError):
        fg.entities.delete(42)


# ---------- ENTITY_NOT_FOUND when target not visible ----------


def test_delete_form_b_raises_entity_not_found_when_not_materialized():
    fg = _make_fg()
    # Only ref (no create or set), entity not visible
    fg.entities.ref(DelUser, user_id="ghost", tenant_id="acme")
    with pytest.raises(EntityNotFoundError) as exc_info:
        fg.entities.delete(DelUser, user_id="ghost", tenant_id="acme")
    assert exc_info.value.code == "ENTITY_NOT_FOUND"


def test_delete_form_a_raises_entity_not_found_when_only_ref():
    fg = _make_fg()
    e_ref = fg.entities.ref(DelUser, user_id="ghost", tenant_id="acme")
    with pytest.raises(EntityNotFoundError) as exc_info:
        fg.entities.delete(e_ref)
    assert exc_info.value.code == "ENTITY_NOT_FOUND"


# ---------- Recreate after delete(ADR-IC §4.1 — delete + create is legal)----------


def test_recreate_with_same_identity_after_delete_succeeds():
    """Per ADR-IC §4.1 INV-7a:`fg.entities.delete(e_ref) + fg.entities.create(EC, **id)`
    is the **唯一合法** identity bundle modification path。 After delete,recreate
    must succeed with the same identity bundle(no stale `EntityAlreadyExistsError`)。"""
    fg, e_ref = _make_materialized_fg()
    fg.entities.delete(e_ref)

    e_ref_recreated = fg.entities.create(DelUser, user_id="alice", tenant_id="acme")
    # Deterministic e_ref: idref_v1 is content-derived, so same identity → same e_ref
    assert e_ref_recreated == e_ref
    # New Identity Claims; Entity visibility is virtual.
    active_after = _active_claim_counts(fg, e_ref_recreated)
    assert active_after == Counter({
        PRED_USER_ID: 1,
        PRED_TENANT_ID: 1,
    })


# ---------- SF3 P1 amend: path-bound guard-bypass STRUCTURAL invariants ----------


def test_generic_apply_op_still_blocks_identity_retract_per_inv_7c():
    """**Critical structural invariant** per SF3 P1 amend(2026-05-30):
    generic `_apply_op` retract branch **always** enforces
    `check_retract_allowed`。 Identity Claim retract via generic dispatcher
    raises `INV_7C_IDENTITY_PROTECTED` — Step 3 path-bound bypass does NOT
    weaken Slice 2 三层 enforcement。"""
    from factgraph.application.entity_write import EntityWriteError, _apply_op
    from factgraph.application.protocol import (
        EntityRef,
        FieldPath,
        PlannedOpDTO,
    )

    fg, e_ref = _make_materialized_fg()
    identity_claims = fg._store.ledger.find_claims(pred_id=PRED_USER_ID, e_ref=e_ref)
    assert len(identity_claims) == 1
    identity_asrt = identity_claims[0].asrt_id

    target = EntityRef(
        entity_type="DelUser",
        identity={"user_id": "alice", "tenant_id": "acme"},
        encoded_ref=e_ref,
    )
    op = PlannedOpDTO(
        op="retract",
        target=target,
        field=FieldPath(entity_type="DelUser", field_name="user_id"),
        assertion_id=identity_asrt,
    )

    with pytest.raises(EntityWriteError) as exc_info:
        _apply_op(op, store=fg._store, index=fg._application_schema_index)
    assert exc_info.value.code == "INV_7C_IDENTITY_PROTECTED"
    # Identity Claim NOT actually revoked
    assert not fg._store.ledger.has_active_revocation(identity_asrt)


def test_generic_apply_op_still_blocks_exists_retract_per_transitional_guard():
    """generic `_apply_op` retract branch also enforces existence-claim
    transitional guard on `:exists` Claim retract — Step 3 bypass is
    path-bound,not metadata-driven, so `:exists` is protected from
    generic-dispatcher callers。"""
    from factgraph.application.entity_write import EntityWriteError, _apply_op
    from factgraph.application.protocol import (
        EntityRef,
        FieldPath,
        PlannedOpDTO,
    )

    fg, e_ref = _make_materialized_fg()
    exists_asrt = _write_legacy_exists_claim(fg, e_ref)

    target = EntityRef(
        entity_type="DelUser",
        identity={"user_id": "alice", "tenant_id": "acme"},
        encoded_ref=e_ref,
    )
    op = PlannedOpDTO(
        op="retract",
        target=target,
        field=FieldPath(entity_type="DelUser", field_name="exists"),
        assertion_id=exists_asrt,
    )

    with pytest.raises(EntityWriteError) as exc_info:
        _apply_op(op, store=fg._store, index=fg._application_schema_index)
    assert exc_info.value.code == "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"


def test_apply_entity_delete_retract_not_referenced_in_apply_op_source():
    """**Future-drift protection**:`_apply_entity_delete_retract` private
    helper must NEVER appear inside `_apply_op` body。 The path-binding is
    a structural guarantee — verified here by source-level grep against the
    `_apply_op` function source。 If a future commit accidentally wires the
    private helper into the generic dispatcher,this test fails first。"""
    from factgraph.application.entity_write import _apply_op

    source = inspect.getsource(_apply_op)
    assert "_apply_entity_delete_retract" not in source, (
        "_apply_entity_delete_retract must NOT be called from _apply_op "
        "per SF3 P1 amend (path-bound guard-bypass, not metadata signal). "
        "If you intentionally changed this, audit the SF3 lock + Decision Note #3 "
        "in the historical API-namespace design record "
        "before re-running."
    )


def test_apply_entity_delete_retract_excluded_from_module_all():
    """`_apply_entity_delete_retract` must NOT be in `application.entity_write.__all__`
    — the private helper is intentionally NOT a documented re-export per SF3
    P1 amend(importing it from outside the application layer is an explicit
    bypass that must be auditable via grep)。"""
    from factgraph.application import entity_write

    assert "_apply_entity_delete_retract" not in entity_write.__all__


def test_path_bound_delete_actually_revokes_identity_claims():
    """`fg.entities.delete` successfully revokes Identity Claims through the
    path-bound private executor — proves the bypass works for the legitimate
    delete path while remaining blocked for generic dispatcher callers
    (see test_generic_apply_op_still_blocks_identity_retract_per_inv_7c)。"""
    fg, e_ref = _make_materialized_fg()
    identity_claims = fg._store.ledger.find_claims(pred_id=PRED_USER_ID, e_ref=e_ref)
    identity_asrt = identity_claims[0].asrt_id

    fg.entities.delete(e_ref)

    # Identity Claim revoked through path-bound path
    assert fg._store.ledger.has_active_revocation(identity_asrt)


def test_path_bound_delete_revokes_legacy_exists_claims_when_present():
    fg, e_ref = _make_materialized_fg()
    exists_asrt = _write_legacy_exists_claim(fg, e_ref)

    fg.entities.delete(e_ref)

    assert fg._store.ledger.has_active_revocation(exists_asrt)


# ---------- application layer planner direct invocation(SF3 INV-6)----------


def test_application_delete_planner_direct_invocation():
    """Application layer `plan_delete_command` + `apply_delete_plan` are
    public functions(per SF3 — SDK manager is a thin shell)。 Direct
    invocation works for advanced tooling。"""
    from factgraph.application import apply_delete_plan, plan_delete_command
    from factgraph.application.protocol import (
        EntityDeleteCommand,
        EntitySelector,
    )

    fg, e_ref = _make_materialized_fg()
    command = EntityDeleteCommand(
        target=EntitySelector(
            entity_type="DelUser",
            identity={"user_id": "alice", "tenant_id": "acme"},
            encoded_ref=e_ref,
        ),
        command_meta={},
    )
    plan = plan_delete_command(
        command,
        store=fg._store,
        index=fg._application_schema_index,
    )
    assert plan.can_apply
    # 4 retract ops: 2 Identity + 2 Field
    assert len(plan.planned_retracts) == 4

    result = apply_delete_plan(
        plan,
        store=fg._store,
        index=fg._application_schema_index,
    )
    assert result.errors == ()
    assert len(result.applied) == 4
    assert all(applied.status == "applied" for applied in result.applied)


def test_entity_delete_command_rejects_missing_encoded_ref():
    """`EntityDeleteCommand` protocol shape requires non-None encoded_ref
    so the planner can directly enumerate Active Claims。"""
    from factgraph.application.protocol import (
        EntityDeleteCommand,
        EntitySelector,
    )
    from factgraph.application.protocol.common import ProtocolShapeError

    with pytest.raises(ProtocolShapeError) as exc_info:
        EntityDeleteCommand(
            target=EntitySelector(
                entity_type="DelUser",
                identity={"user_id": "alice", "tenant_id": "acme"},
                # no encoded_ref
            ),
            command_meta={},
        )
    assert "encoded_ref" in str(exc_info.value)


# ---------- Layer 1 排他 enforcement(reuses Step 1 helper)----------


def test_delete_rejects_field_descriptor():
    """Layer 1 排他:Field descriptor is Layer 2 nav key,not Layer 1。"""
    fg = _make_fg()
    with pytest.raises(SDKStoreError) as exc_info:
        fg.entities.delete(DelUser.name, user_id="alice")
    msg = str(exc_info.value)
    # The first positional is a Field instance — falls into the "neither e_ref
    # string nor Entity subclass" branch with the PF-S2 wording。
    assert "requires e_ref string OR EntityClass" in msg


# ---------- multiple delete idempotency(noop after first revoke)----------


def test_delete_already_deleted_raises_entity_not_found():
    """After delete,entity is no longer visible → second delete raises
    ENTITY_NOT_FOUND(consistent with `fg.entities.delete` semantics)。"""
    fg, e_ref = _make_materialized_fg()
    fg.entities.delete(e_ref)
    with pytest.raises(EntityNotFoundError) as exc_info:
        fg.entities.delete(e_ref)
    assert exc_info.value.code == "ENTITY_NOT_FOUND"
