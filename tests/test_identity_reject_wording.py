"""Slice 2 Step 6 — Identity reject error wording acceptance tests.

Verifies updated error messages + codes per ADR-IC §4.1 wording for:
- `sdk/facade.py:IdentityEditor.set/add/retract` (SDK shell Layer 2 reject)
- `application/entity_write.py:plan_write_command` is_identity_field check
  (application source-of-truth Layer 2 reject)

NEW test file per Slice 2 SF7. Per blueprint §5.7 + SF12:
- Wording must include: INV-7c, INV-7a, fg.entities.delete, fg.entities.create,
  ADR-IC §4.1
- Code must be INV_7C_IDENTITY_PROTECTED (consistent with Layer 3 retract guard)

NOTE on test paths:
- IdentityEditor tests require a *materialized* entity (Form I anchors must
  exist) — fixture calls fg.set on a Field first to trigger materialization.
- plan_write_command tests call the planner directly with an EntityWriteCommand
  carrying an Identity-targeted FieldMutation. (SDK fg.set rejects Identity
  descriptors at the shell parameter validation layer before they reach the
  application planner; the planner's is_identity_field check is defense in
  depth for any path that constructs an EntityWriteCommand directly.)
"""
import pytest

from factgraph.application import plan_write_command
from factgraph.application.protocol import (
    EntitySelector,
    EntityWriteCommand,
    FieldMutation,
    FieldPath,
)
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class IdentityRejectUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()


def _make_materialized_fg():
    """Create FactGraph + materialized user (Identity Claims exist in ledger).

    Returns (fg, e_ref).
    """
    fg = FactGraph.create(schema_classes=[IdentityRejectUser])
    e_ref = fg.entities.ref(IdentityRejectUser, user_id="alice", tenant_id="acme")
    # Materialize entity by writing a Field — emits the Identity bundle; the
    # entity-domain row is projected virtually from that bundle.
    fg.fields.set(IdentityRejectUser.name, e_ref, "Alice")
    return fg, e_ref


def _make_fg_with_editor():
    """Create FactGraph + materialized user + open EntityEditor.

    Returns (fg, editor).
    """
    fg, _ = _make_materialized_fg()
    editor = fg.entities.edit(IdentityRejectUser, user_id="alice", tenant_id="acme")
    return fg, editor


def _identity_write_command(field_name: str, value: str) -> EntityWriteCommand:
    """Build an EntityWriteCommand targeting an Identity field on IdentityRejectUser."""
    return EntityWriteCommand(
        target=EntitySelector(
            entity_type="IdentityRejectUser",
            identity={"user_id": "alice", "tenant_id": "acme"},
        ),
        mutations=(
            FieldMutation(
                op="set",
                field=FieldPath(entity_type="IdentityRejectUser", field_name=field_name),
                value=value,
            ),
        ),
        create_if_missing=True,
        include_dependencies=True,
    )


# ---------- IdentityEditor wording (SDK shell Layer 2) ----------


def test_identity_editor_set_raises_inv_7c_with_full_wording():
    """IdentityEditor.set raises SDKStoreError with INV-7c wording markers."""
    _, editor = _make_fg_with_editor()
    with pytest.raises(SDKStoreError) as exc_info:
        editor.user_id.set("bob")
    err = exc_info.value
    msg = str(err)
    # Per ADR-IC §4.1 wording markers
    assert "INV-7c" in msg
    assert "INV-7a" in msg  # references Identity immutable anchor invariant
    assert "fg.entities.delete" in msg
    assert "fg.entities.create" in msg
    assert "ADR-IC §4.1" in msg
    # Stale wording must be gone
    assert "open a new editor with different identity" not in msg
    # Identity field name must appear
    assert "user_id" in msg


def test_identity_editor_set_has_inv_7c_code():
    """IdentityEditor.set raises SDKStoreError with code=INV_7C_IDENTITY_PROTECTED."""
    _, editor = _make_fg_with_editor()
    with pytest.raises(SDKStoreError) as exc_info:
        editor.user_id.set("bob")
    assert exc_info.value.code == "INV_7C_IDENTITY_PROTECTED"


def test_identity_editor_add_and_retract_share_inv_7c_wording():
    """IdentityEditor.add and .retract delegate to .set — share wording + code."""
    _, editor = _make_fg_with_editor()
    for method in (editor.user_id.add, editor.user_id.retract):
        with pytest.raises(SDKStoreError) as exc_info:
            method("bob")
        err = exc_info.value
        assert err.code == "INV_7C_IDENTITY_PROTECTED"
        assert "INV-7c" in str(err)
        assert "ADR-IC §4.1" in str(err)


def test_identity_editor_tenant_id_also_rejected_with_wording():
    """Non-primary Identity fields (Form I all-Identity-is-anchor per SF2) rejected."""
    _, editor = _make_fg_with_editor()
    with pytest.raises(SDKStoreError) as exc_info:
        editor.tenant_id.set("other_tenant")
    err = exc_info.value
    assert err.code == "INV_7C_IDENTITY_PROTECTED"
    assert "tenant_id" in str(err)
    assert "INV-7c" in str(err)


# ---------- plan_write_command wording (application source-of-truth Layer 2) ----------


def test_plan_write_command_identity_mutation_raises_inv_7c():
    """plan_write_command(EntityWriteCommand with Identity FieldMutation) → INV-7c errors.

    Exercises the application-layer is_identity_field check at line 187 of
    entity_write.py (per Slice 1 Step 1 baseline; Step 6 updates wording).
    Calls the planner directly — bypasses SDK shell parameter validation that
    already rejects Identity descriptors at fg.set entry.
    """
    fg, _ = _make_materialized_fg()
    command = _identity_write_command(field_name="user_id", value="bob")

    plan = plan_write_command(
        command,
        store=fg._store,
        index=fg._application_schema_index,
    )
    # Planner returns a can_apply=False plan with errors (does NOT raise) — Step 6
    # only changes wording + code, not the surface contract.
    assert plan.can_apply is False
    assert len(plan.errors) == 1
    err = plan.errors[0]
    msg = err.message
    assert "INV-7c" in msg
    assert "INV-7a" in msg
    assert "fg.entities.delete" in msg
    assert "fg.entities.create" in msg
    assert "ADR-IC §4.1" in msg
    # Identity field path must appear
    assert "IdentityRejectUser" in msg
    assert "user_id" in msg


def test_plan_write_command_identity_mutation_has_inv_7c_code():
    """plan_write_command Identity reject → ErrorDTO code=INV_7C_IDENTITY_PROTECTED."""
    fg, _ = _make_materialized_fg()
    command = _identity_write_command(field_name="user_id", value="bob")

    plan = plan_write_command(
        command,
        store=fg._store,
        index=fg._application_schema_index,
    )
    assert plan.can_apply is False
    assert plan.errors[0].code == "INV_7C_IDENTITY_PROTECTED"


def test_plan_write_command_stale_code_replaced():
    """Verify the stale IDENTITY_FIELD_MUTATION_NOT_SUPPORTED code is no longer used."""
    fg, _ = _make_materialized_fg()
    command = _identity_write_command(field_name="user_id", value="bob")

    plan = plan_write_command(
        command,
        store=fg._store,
        index=fg._application_schema_index,
    )
    assert plan.can_apply is False
    assert plan.errors[0].code != "IDENTITY_FIELD_MUTATION_NOT_SUPPORTED"


# ---------- consistency across Layer 2 + Layer 3 ----------


def test_layer_2_and_layer_3_share_inv_7c_code():
    """Layer 2 (Identity field write) and Layer 3 (Identity Claim asrt retract)
    both surface code=INV_7C_IDENTITY_PROTECTED — single source of truth for
    caller branching per ADR-IC §4.1.
    """
    fg, e_ref = _make_materialized_fg()

    # Layer 2: plan_write_command on Identity field
    command = _identity_write_command(field_name="user_id", value="bob")
    plan = plan_write_command(
        command,
        store=fg._store,
        index=fg._application_schema_index,
    )
    assert plan.can_apply is False
    l2_code = plan.errors[0].code

    # Layer 3: fg.retract on Identity Claim asrt
    claims = fg._store.ledger.find_claims(
        pred_id="identity_reject_user:user_id", e_ref=e_ref
    )
    assert claims, "Identity Claim should exist after materialization"
    identity_asrt_id = claims[0].asrt_id
    with pytest.raises(SDKStoreError) as l3_exc:
        fg.assertions.retract(identity_asrt_id)

    # Same code propagates through both layers
    assert l2_code == l3_exc.value.code == "INV_7C_IDENTITY_PROTECTED"
