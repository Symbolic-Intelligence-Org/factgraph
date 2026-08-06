"""Slice 2 Step 5 — Application entity_write path retract guard tests.

Verifies `application/entity_write.py:_apply_op` retract branch wrap per
ADR-IC §4.1 + Slice 2 blueprint §8 Step 5 + §5.5.

NEW test file per Slice 2 SF7. Tests cover the application entity_write
retract path through `_apply_op` directly with PlannedOpDTO(op="retract"):
- Identity Claim asrt → EntityWriteError(code=INV_7C_IDENTITY_PROTECTED)
  with code propagated directly (NOT swallowed)
- :exists Claim asrt → EntityWriteError(code=EXISTENCE_CLAIM_TRANSITIONAL_GUARD)
- Field Claim asrt → passes through (succeeds via retract_by_asrt)
- Unknown asrt → passes through (downstream WriteProtocolError surfaces)

Per Slice 1 Step 11 baseline: `_apply_op` already takes `index: SchemaIndex`
parameter — Step 5 reuses it (no new parameter).
"""
import pytest

from factgraph.application.entity_write import EntityWriteError, _apply_op
from factgraph.application.protocol import EntityRef, FieldPath, PlannedOpDTO
from factgraph.core.evidence.write_protocol import set_field
from factgraph.sdk import Entity, FactGraph, Field, Identity


class EntityWriteGuardUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()


def _make_fg_with_one_user():
    """Create FactGraph + materialized user + Field write.

    Returns (fg, e_ref, name_asrt_id, identity_kwargs).
    """
    fg = FactGraph.create(schema_classes=[EntityWriteGuardUser])
    identity_kwargs = {"user_id": "alice", "tenant_id": "acme"}
    e_ref = fg.entities.ref(EntityWriteGuardUser, **identity_kwargs)
    name_asrt_id = fg.fields.set(EntityWriteGuardUser.name, e_ref, "Alice")
    return fg, e_ref, name_asrt_id, identity_kwargs


def _find_asrt_id(fg, pred_id: str, e_ref: str) -> str:
    """Find the first asrt_id matching pred_id + e_ref in the ledger."""
    claims = fg._store.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
    assert claims, f"no Claim found for pred_id={pred_id!r} e_ref={e_ref!r}"
    return claims[0].asrt_id


def _write_legacy_exists_claim(fg, e_ref: str) -> str:
    """Write a legacy `<EntityType>:exists` Claim fixture explicitly."""
    return set_field(fg._store.ledger, "EntityWriteGuardUser:exists", e_ref, [])


def _retract_op(asrt_id: str, *, identity_kwargs: dict, e_ref: str) -> PlannedOpDTO:
    """Build a PlannedOpDTO for a retract op against a known asrt_id.

    Per protocol shape: retract requires target (EntityRef) + field (FieldPath)
    + assertion_id. Note: `_apply_op` retract branch only uses op.assertion_id
    and op.meta — op.field is a protocol-shape requirement, not consumed by
    the retract path itself. Any valid field of the entity works for fixture
    purposes.
    """
    target = EntityRef(
        entity_type="EntityWriteGuardUser",
        identity=identity_kwargs,
        encoded_ref=e_ref,
    )
    field_path = FieldPath(entity_type="EntityWriteGuardUser", field_name="name")
    return PlannedOpDTO(
        op="retract",
        target=target,
        field=field_path,
        assertion_id=asrt_id,
    )


def _apply_retract_op(fg, op: PlannedOpDTO):
    """Invoke _apply_op directly with fg's store + schema index."""
    return _apply_op(op, store=fg._store, index=fg._application_schema_index)


# ---------- Identity classification ----------


def test_entity_write_identity_retract_raises_inv_7c_entity_write_error():
    """Identity Claim retract → EntityWriteError(code=INV_7C_IDENTITY_PROTECTED).

    Code propagated directly per reviewer Step 5 lock.
    """
    fg, e_ref, _, identity_kwargs = _make_fg_with_one_user()
    identity_asrt_id = _find_asrt_id(fg, "entity_write_guard_user:user_id", e_ref)
    op = _retract_op(identity_asrt_id, identity_kwargs=identity_kwargs, e_ref=e_ref)

    with pytest.raises(EntityWriteError) as exc_info:
        _apply_retract_op(fg, op)

    err = exc_info.value
    assert err.code == "INV_7C_IDENTITY_PROTECTED"
    assert "INV-7c" in str(err)
    assert "ADR-IC §4.1" in str(err)
    assert err.details["classification"] == "identity"
    assert err.details["assertion_id"] == identity_asrt_id
    assert err.path == ("planned_ops", "assertion_id")


def test_entity_write_tenant_id_identity_also_protected():
    """All Identity members (not just primary) trigger INV-7c per Slice 1 SF2."""
    fg, e_ref, _, identity_kwargs = _make_fg_with_one_user()
    tenant_asrt_id = _find_asrt_id(fg, "entity_write_guard_user:tenant_id", e_ref)
    op = _retract_op(tenant_asrt_id, identity_kwargs=identity_kwargs, e_ref=e_ref)

    with pytest.raises(EntityWriteError) as exc_info:
        _apply_retract_op(fg, op)
    assert exc_info.value.code == "INV_7C_IDENTITY_PROTECTED"


# ---------- :exists classification ----------


def test_entity_write_exists_retract_raises_transitional_guard():
    """Legacy :exists Claim retract → EntityWriteError(code=EXISTENCE_CLAIM_TRANSITIONAL_GUARD).

    Code propagated directly per reviewer Step 5 lock.
    SF10: message must NOT contain "INV-7c".
    """
    fg, e_ref, _, identity_kwargs = _make_fg_with_one_user()
    exists_asrt_id = _write_legacy_exists_claim(fg, e_ref)
    op = _retract_op(exists_asrt_id, identity_kwargs=identity_kwargs, e_ref=e_ref)

    with pytest.raises(EntityWriteError) as exc_info:
        _apply_retract_op(fg, op)

    err = exc_info.value
    assert err.code == "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
    msg = str(err)
    assert ":exists Claim" in msg
    assert "transitional" in msg
    assert "ADR-IC §4.4" in msg
    assert "INV-7c" not in msg  # SF10 explicit
    assert err.details["classification"] == "exists"


# ---------- pass-through cases ----------


def test_entity_write_field_retract_passes_through():
    """Field Claim retract → succeeds via retract_by_asrt (unprotected pass-through)."""
    fg, e_ref, name_asrt_id, identity_kwargs = _make_fg_with_one_user()
    op = _retract_op(name_asrt_id, identity_kwargs=identity_kwargs, e_ref=e_ref)

    # No raise — returns revoker assertion id
    revoker_id = _apply_retract_op(fg, op)
    assert isinstance(revoker_id, str)
    assert revoker_id != name_asrt_id  # revoker is a NEW assertion


def test_entity_write_unknown_asrt_surfaces_downstream_error():
    """Unknown asrt → guard returns 'unprotected', downstream retract_by_asrt surfaces error.

    Pass-through path: guard does not classify (returns 'unprotected'), then
    retract_by_asrt raises its own error (WriteProtocolError, not caught here
    so surfaces to caller — different from ingest path which wraps it).
    """
    fg, e_ref, _, identity_kwargs = _make_fg_with_one_user()
    op = _retract_op("asrt-does-not-exist", identity_kwargs=identity_kwargs, e_ref=e_ref)

    # entity_write _apply_op does NOT wrap WriteProtocolError; it surfaces.
    # The key acceptance is that it's NOT a RetractGuardError / EntityWriteError
    # from the guard layer — i.e., the guard correctly returns 'unprotected'.
    from factgraph.core.evidence.write_protocol import WriteProtocolError

    with pytest.raises(WriteProtocolError) as exc_info:
        _apply_retract_op(fg, op)
    # Must NOT be guard-classified
    msg = str(exc_info.value)
    assert "INV-7c" not in msg
    assert "INV_7C_IDENTITY_PROTECTED" not in msg
    assert "EXISTENCE_CLAIM_TRANSITIONAL_GUARD" not in msg


# ---------- distinguishable codes ----------


def test_entity_write_identity_and_exists_distinguishable_codes():
    """Identity vs legacy :exists produce DIFFERENT EntityWriteError codes."""
    fg, e_ref, _, identity_kwargs = _make_fg_with_one_user()
    identity_asrt_id = _find_asrt_id(fg, "entity_write_guard_user:user_id", e_ref)
    exists_asrt_id = _write_legacy_exists_claim(fg, e_ref)

    identity_op = _retract_op(identity_asrt_id, identity_kwargs=identity_kwargs, e_ref=e_ref)
    exists_op = _retract_op(exists_asrt_id, identity_kwargs=identity_kwargs, e_ref=e_ref)

    with pytest.raises(EntityWriteError) as id_exc:
        _apply_retract_op(fg, identity_op)
    with pytest.raises(EntityWriteError) as ex_exc:
        _apply_retract_op(fg, exists_op)

    assert id_exc.value.code == "INV_7C_IDENTITY_PROTECTED"
    assert ex_exc.value.code == "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
    assert id_exc.value.code != ex_exc.value.code


# ---------- guard runs before retract_by_asrt ----------


def test_entity_write_guard_runs_before_retract_by_asrt():
    """Guard runs BEFORE retract_by_asrt — Identity Claim still active after failure."""
    fg, e_ref, _, identity_kwargs = _make_fg_with_one_user()
    identity_asrt_id = _find_asrt_id(fg, "entity_write_guard_user:user_id", e_ref)
    op = _retract_op(identity_asrt_id, identity_kwargs=identity_kwargs, e_ref=e_ref)

    claims_before = fg._store.ledger.find_claims(
        pred_id="entity_write_guard_user:user_id", e_ref=e_ref
    )
    assert len(claims_before) == 1

    with pytest.raises(EntityWriteError):
        _apply_retract_op(fg, op)

    claims_after = fg._store.ledger.find_claims(
        pred_id="entity_write_guard_user:user_id", e_ref=e_ref
    )
    assert len(claims_after) == 1
    assert claims_after[0].asrt_id == identity_asrt_id


def test_entity_write_system_retract_raises_inv_12_entity_write_error():
    """The application-layer system classification rejects before another write."""
    fg, e_ref, name_asrt_id, identity_kwargs = _make_fg_with_one_user()
    first_revoke = _apply_retract_op(
        fg,
        _retract_op(name_asrt_id, identity_kwargs=identity_kwargs, e_ref=e_ref),
    )
    before_revokes = tuple(fg._store.ledger.revokes)
    op = _retract_op(first_revoke, identity_kwargs=identity_kwargs, e_ref=e_ref)

    with pytest.raises(EntityWriteError) as exc_info:
        _apply_retract_op(fg, op)

    error = exc_info.value
    assert error.code == "INV_12_SYSTEM_REVOKE_FORBIDDEN"
    assert error.details["classification"] == "system"
    assert error.details["assertion_id"] == first_revoke
    assert "revoke-of-revoke is forbidden" in str(error)
    assert tuple(fg._store.ledger.revokes) == before_revokes


# ---------- EntityWriteError code preserved ----------


def test_entity_write_error_code_propagates_not_swallowed():
    """EntityWriteError.code must be the guard code, not generic ENTITY_WRITE_FAILED.

    Per reviewer Step 5 lock: code propagated directly.
    """
    fg, e_ref, _, identity_kwargs = _make_fg_with_one_user()
    identity_asrt_id = _find_asrt_id(fg, "entity_write_guard_user:user_id", e_ref)
    op = _retract_op(identity_asrt_id, identity_kwargs=identity_kwargs, e_ref=e_ref)

    with pytest.raises(EntityWriteError) as exc_info:
        _apply_retract_op(fg, op)

    # Code is the guard code, NOT a generic wrapped code
    assert exc_info.value.code == "INV_7C_IDENTITY_PROTECTED"
    assert exc_info.value.code != "ENTITY_WRITE_FAILED"
