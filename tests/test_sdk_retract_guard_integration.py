"""Slice 2 Step 3 — SDK shell retract guard integration tests.

Verifies `SDKStore.retract(asrt_id)` wrap with `check_retract_allowed`
per ADR-IC §4.1 + Slice 2 blueprint §8 Step 3 + §5.3.

NEW test file per Slice 2 SF7. Tests cover end-to-end through the SDK
shell `fg.retract` API:
- Identity Claim asrt → SDKStoreError with INV-7c wording + code
- :exists Claim asrt → SDKStoreError with existence-claim transitional
  guard wording + code
- Field Claim asrt → passes through (succeeds via retract_by_asrt)
- Unknown asrt → passes through (downstream ASSERTION_NOT_FOUND)

Uses Form I schema (Slice 1 baseline carries forward).
"""
import pytest

from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class RetractGuardUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()


def _make_user_fg_with_one_user():
    """Create a FactGraph with one materialized User entity + one Field write.

    Returns (fg, e_ref, name_asrt_id).
    """
    fg = FactGraph.create(schema_classes=[RetractGuardUser])
    e_ref = fg.entities.ref(RetractGuardUser, user_id="alice", tenant_id="acme")
    name_asrt_id = fg.fields.set(RetractGuardUser.name, e_ref, "Alice")
    return fg, e_ref, name_asrt_id


def _find_identity_asrt_id(fg, pred_id: str, e_ref: str) -> str:
    """Find the first asrt_id matching a pred_id + e_ref in the ledger."""
    claims = fg._store.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
    assert claims, f"no Claim found for pred_id={pred_id!r} e_ref={e_ref!r}"
    return claims[0].asrt_id


def test_field_claim_retract_succeeds():
    """Field Claim retract → succeeds (unprotected pass-through)."""
    fg, e_ref, name_asrt_id = _make_user_fg_with_one_user()
    revoker_id = fg.assertions.retract(name_asrt_id)
    # retract_by_asrt returns the revoker assertion id (str) on success
    assert isinstance(revoker_id, str)
    assert revoker_id != name_asrt_id  # revoker is a NEW assertion


def test_identity_claim_retract_raises_inv_7c():
    """Identity Claim retract → SDKStoreError with INV-7c wording + code."""
    fg, e_ref, _ = _make_user_fg_with_one_user()
    identity_asrt_id = _find_identity_asrt_id(fg, "retract_guard_user:user_id", e_ref)

    with pytest.raises(SDKStoreError) as exc_info:
        fg.assertions.retract(identity_asrt_id)

    err = exc_info.value
    assert err.code == "INV_7C_IDENTITY_PROTECTED"
    # Wording must include the key identifiers per ADR-IC §4.1
    msg = str(err)
    assert "INV-7c" in msg
    assert "fg.entities.create" in msg
    assert "fg.entities.delete" in msg
    assert "INV-7a" in msg  # references Identity immutability invariant
    assert "ADR-IC §4.1" in msg


def test_exists_claim_retract_raises_transitional_guard():
    """`<EntityType>:exists` Claim retract → SDKStoreError with transitional guard wording + code."""
    fg, e_ref, _ = _make_user_fg_with_one_user()
    exists_asrt_id = _find_identity_asrt_id(fg, "RetractGuardUser:exists", e_ref)

    with pytest.raises(SDKStoreError) as exc_info:
        fg.assertions.retract(exists_asrt_id)

    err = exc_info.value
    assert err.code == "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
    msg = str(err)
    assert ":exists Claim" in msg
    assert "transitional" in msg
    assert "fg.entities.delete" in msg
    assert "ADR-IC §4.4" in msg
    # Must NOT pretend this is INV-7c protection
    assert "INV-7c" not in msg


def test_unknown_asrt_passes_through():
    """Unknown asrt → pass-through to retract_by_asrt → downstream raises ASSERTION_NOT_FOUND."""
    fg, _, _ = _make_user_fg_with_one_user()

    with pytest.raises(SDKStoreError) as exc_info:
        fg.assertions.retract("asrt-unknown-id")

    err = exc_info.value
    # Code from downstream retract_by_asrt WriteProtocolError mapping, NOT the guard
    assert err.code == "ASSERTION_NOT_FOUND"
    # Must NOT be a guard-classified error
    assert err.code not in {"INV_7C_IDENTITY_PROTECTED", "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"}


def test_identity_and_exists_produce_distinguishable_sdk_errors():
    """Identity vs :exists raise SDKStoreError with DIFFERENT codes + messages.

    Per ADR-IC §8 acceptance: caller can distinguish between the two
    guard violations.
    """
    fg, e_ref, _ = _make_user_fg_with_one_user()
    identity_asrt_id = _find_identity_asrt_id(fg, "retract_guard_user:user_id", e_ref)
    exists_asrt_id = _find_identity_asrt_id(fg, "RetractGuardUser:exists", e_ref)

    with pytest.raises(SDKStoreError) as id_exc:
        fg.assertions.retract(identity_asrt_id)
    with pytest.raises(SDKStoreError) as ex_exc:
        fg.assertions.retract(exists_asrt_id)

    # Distinct codes
    assert id_exc.value.code == "INV_7C_IDENTITY_PROTECTED"
    assert ex_exc.value.code == "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
    assert id_exc.value.code != ex_exc.value.code

    # Distinct wording markers
    assert "INV-7c" in str(id_exc.value)
    assert "INV-7c" not in str(ex_exc.value)
    assert "transitional" in str(ex_exc.value)
    assert "transitional" not in str(id_exc.value)


def test_tenant_id_identity_also_protected():
    """All identity_pred_ids members (not just primary) → INV-7c.

    Per Slice 1 SF2 + ADR-IC §4.3.1 Form I all-Identity-is-anchor: every
    Identity field's Claim must be INV-7c protected, not just one
    "primary" field.
    """
    fg, e_ref, _ = _make_user_fg_with_one_user()
    tenant_asrt_id = _find_identity_asrt_id(fg, "retract_guard_user:tenant_id", e_ref)

    with pytest.raises(SDKStoreError) as exc_info:
        fg.assertions.retract(tenant_asrt_id)
    assert exc_info.value.code == "INV_7C_IDENTITY_PROTECTED"


def test_retract_guard_runs_before_retract_by_asrt():
    """Guard check executes BEFORE retract_by_asrt — Identity Claim is NOT mutated.

    Per blueprint §5.3: `check_retract_allowed` must be called BEFORE
    `retract_by_asrt`. Verify by:
    1. Identifying the Identity Claim asrt_id.
    2. Attempting retract — must raise INV-7c.
    3. Verifying the Identity Claim is still active in the ledger
       (no revoker assertion was created).
    """
    fg, e_ref, _ = _make_user_fg_with_one_user()
    identity_asrt_id = _find_identity_asrt_id(fg, "retract_guard_user:user_id", e_ref)

    # Count active Claims for the Identity pred + e_ref before retract attempt
    claims_before = fg._store.ledger.find_claims(pred_id="retract_guard_user:user_id", e_ref=e_ref)
    assert len(claims_before) == 1

    with pytest.raises(SDKStoreError):
        fg.assertions.retract(identity_asrt_id)

    # After failed retract, the original Identity Claim must still be in the
    # ledger AND no revoker assertion was emitted.
    claims_after = fg._store.ledger.find_claims(pred_id="retract_guard_user:user_id", e_ref=e_ref)
    assert len(claims_after) == 1
    assert claims_after[0].asrt_id == identity_asrt_id
