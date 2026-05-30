"""Slice 2 Step 4 — Application ingest path retract guard tests (P1 #2 fix).

Verifies `application/ingest_runtime.py:_apply_retract` wrap per ADR-IC §4.1 +
Slice 2 blueprint §8 Step 4 + §5.4.

NEW test file per Slice 2 SF7. Tests cover the application ingest path:
- Identity Claim asrt → ErrorDTO(code="INV_7C_IDENTITY_PROTECTED", ...)
  with code propagated directly (NOT wrapped in INGEST_RETRACT_FAILED)
- :exists Claim asrt → ErrorDTO(code="EXISTENCE_CLAIM_TRANSITIONAL_GUARD", ...)
- Field Claim asrt → passes through (succeeds via retract_by_asrt)
- Unknown asrt → INGEST_RETRACT_FAILED (existing downstream behavior)

Critical P1 #2 lock: `_apply_retract` signature must accept `index: SchemaIndex`
parameter; `_apply_item` chain pass-through verified by integration through
`apply_ingest_request`.
"""
import pytest

from factgraph.application.ingest_runtime import apply_ingest_request
from factgraph.application.protocol import (
    IngestRequest,
    IngestRetractItem,
)
from factgraph.sdk import Entity, FactGraph, Field, Identity


class IngestGuardUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()


def _make_fg_with_one_user():
    """Create FactGraph + materialized user + Field write.

    Returns (fg, e_ref, name_asrt_id).
    """
    fg = FactGraph.create(schema_classes=[IngestGuardUser])
    e_ref = fg.entities.ref(IngestGuardUser, user_id="alice", tenant_id="acme")
    name_asrt_id = fg.fields.set(IngestGuardUser.name, e_ref, "Alice")
    return fg, e_ref, name_asrt_id


def _find_asrt_id(fg, pred_id: str, e_ref: str) -> str:
    """Find the first asrt_id matching pred_id + e_ref in the ledger."""
    claims = fg._store.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
    assert claims, f"no Claim found for pred_id={pred_id!r} e_ref={e_ref!r}"
    return claims[0].asrt_id


def _retract_request(asrt_id: str, *, idx: int = 0) -> IngestRequest:
    """Build an IngestRequest with one IngestRetractItem."""
    return IngestRequest(
        items=(IngestRetractItem(assertion_id=asrt_id),),
        collect_mode="collect",
    )


def _run_ingest(fg, request: IngestRequest):
    """Invoke apply_ingest_request with fg's store + schema index."""
    return apply_ingest_request(
        request,
        store=fg._store,
        index=fg._application_schema_index,
    )


# ---------- Identity classification ----------


def test_ingest_identity_claim_retract_emits_inv_7c_error_dto():
    """Identity Claim ingest retract → ErrorDTO(code=INV_7C_IDENTITY_PROTECTED).

    P1 #2 + reviewer Step 4 lock: code propagates directly, NOT wrapped in
    INGEST_RETRACT_FAILED.
    """
    fg, e_ref, _ = _make_fg_with_one_user()
    identity_asrt_id = _find_asrt_id(fg, "ingest_guard_user:user_id", e_ref)

    result = _run_ingest(fg, _retract_request(identity_asrt_id))

    assert len(result.errors) == 1
    err = result.errors[0]
    assert err.code == "INV_7C_IDENTITY_PROTECTED"
    assert err.code != "INGEST_RETRACT_FAILED"  # MUST NOT be wrapped
    assert err.path == ("items", "0")
    assert "INV-7c" in err.message
    assert "ADR-IC §4.1" in err.message
    assert err.details["classification"] == "identity"
    assert err.details["assertion_id"] == identity_asrt_id
    # No assertions written
    assert result.written_assertion_ids == ()


def test_ingest_tenant_id_identity_also_protected():
    """All Identity members (not just primary) trigger INV-7c per Slice 1 SF2."""
    fg, e_ref, _ = _make_fg_with_one_user()
    tenant_asrt_id = _find_asrt_id(fg, "ingest_guard_user:tenant_id", e_ref)

    result = _run_ingest(fg, _retract_request(tenant_asrt_id))
    assert len(result.errors) == 1
    assert result.errors[0].code == "INV_7C_IDENTITY_PROTECTED"


# ---------- :exists classification ----------


def test_ingest_exists_claim_retract_emits_transitional_guard_error_dto():
    """:exists Claim ingest retract → ErrorDTO(code=EXISTENCE_CLAIM_TRANSITIONAL_GUARD).

    P1 #2 + reviewer Step 4 lock: code propagates directly, NOT wrapped.
    SF10: error message must NOT contain "INV-7c".
    """
    fg, e_ref, _ = _make_fg_with_one_user()
    exists_asrt_id = _find_asrt_id(fg, "IngestGuardUser:exists", e_ref)

    result = _run_ingest(fg, _retract_request(exists_asrt_id))

    assert len(result.errors) == 1
    err = result.errors[0]
    assert err.code == "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
    assert err.code != "INGEST_RETRACT_FAILED"
    assert ":exists Claim" in err.message
    assert "transitional" in err.message
    assert "ADR-IC §4.4" in err.message
    assert "INV-7c" not in err.message  # SF10 explicit
    assert err.details["classification"] == "exists"
    assert err.details["assertion_id"] == exists_asrt_id


# ---------- pass-through cases ----------


def test_ingest_field_claim_retract_passes_through():
    """Field Claim ingest retract → succeeds via retract_by_asrt (no guard)."""
    fg, _, name_asrt_id = _make_fg_with_one_user()

    result = _run_ingest(fg, _retract_request(name_asrt_id))

    # No errors; revoker assertion id returned
    assert result.errors == ()
    assert len(result.written_assertion_ids) == 1
    revoker_id = result.written_assertion_ids[0]
    assert isinstance(revoker_id, str)
    assert revoker_id != name_asrt_id  # revoker is a NEW assertion


def test_ingest_unknown_asrt_uses_existing_ingest_retract_failed_code():
    """Unknown asrt → INGEST_RETRACT_FAILED (existing downstream behavior preserved).

    Pass-through path: guard does not classify (returns "unprotected"), then
    retract_by_asrt fails with WriteProtocolError which the existing exception
    handler wraps with code INGEST_RETRACT_FAILED.
    """
    fg, _, _ = _make_fg_with_one_user()

    result = _run_ingest(fg, _retract_request("asrt-does-not-exist"))

    assert len(result.errors) == 1
    err = result.errors[0]
    assert err.code == "INGEST_RETRACT_FAILED"
    # Must NOT be classified as guard error
    assert err.code not in {"INV_7C_IDENTITY_PROTECTED", "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"}


# ---------- code distinction ----------


def test_ingest_identity_and_exists_distinguishable_codes():
    """Identity vs :exists produce distinct codes in same ingest batch."""
    fg, e_ref, _ = _make_fg_with_one_user()
    identity_asrt_id = _find_asrt_id(fg, "ingest_guard_user:user_id", e_ref)
    exists_asrt_id = _find_asrt_id(fg, "IngestGuardUser:exists", e_ref)

    request = IngestRequest(
        items=(
            IngestRetractItem(assertion_id=identity_asrt_id),
            IngestRetractItem(assertion_id=exists_asrt_id),
        ),
        collect_mode="collect",
    )
    result = _run_ingest(fg, request)

    assert len(result.errors) == 2
    codes = {err.code for err in result.errors}
    assert codes == {"INV_7C_IDENTITY_PROTECTED", "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"}


# ---------- guard runs before retract_by_asrt ----------


def test_ingest_guard_runs_before_retract_by_asrt():
    """Guard runs BEFORE retract_by_asrt — Identity Claim still active after failure."""
    fg, e_ref, _ = _make_fg_with_one_user()
    identity_asrt_id = _find_asrt_id(fg, "ingest_guard_user:user_id", e_ref)

    claims_before = fg._store.ledger.find_claims(
        pred_id="ingest_guard_user:user_id", e_ref=e_ref
    )
    assert len(claims_before) == 1

    result = _run_ingest(fg, _retract_request(identity_asrt_id))
    assert result.errors[0].code == "INV_7C_IDENTITY_PROTECTED"

    claims_after = fg._store.ledger.find_claims(
        pred_id="ingest_guard_user:user_id", e_ref=e_ref
    )
    assert len(claims_after) == 1
    assert claims_after[0].asrt_id == identity_asrt_id


# ---------- collect mode preserves batch ----------


def test_ingest_failed_retract_does_not_abort_collect_batch():
    """Failed retract item in collect mode does NOT abort batch.

    Verify: Identity retract fails but Field retract in same batch succeeds.
    """
    fg, e_ref, name_asrt_id = _make_fg_with_one_user()
    identity_asrt_id = _find_asrt_id(fg, "ingest_guard_user:user_id", e_ref)

    request = IngestRequest(
        items=(
            IngestRetractItem(assertion_id=identity_asrt_id),  # will fail
            IngestRetractItem(assertion_id=name_asrt_id),       # will succeed
        ),
        collect_mode="collect",
    )
    result = _run_ingest(fg, request)

    # 1 error (identity) + 1 written assertion (field retract revoker)
    assert len(result.errors) == 1
    assert result.errors[0].code == "INV_7C_IDENTITY_PROTECTED"
    assert len(result.written_assertion_ids) == 1
