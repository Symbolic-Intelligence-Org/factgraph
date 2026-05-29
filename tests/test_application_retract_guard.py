"""Slice 2 Step 2 — Application retract guard acceptance tests.

Verifies `application/retract_guard.py` per ADR-IC §4.1 + Slice 2 blueprint
§8 Step 2.

NEW test file per Slice 2 SF7. Tests cover the 4 classifications:
- identity → INV_7C_IDENTITY_PROTECTED raise
- exists   → EXISTENCE_CLAIM_TRANSITIONAL_GUARD raise
- Field Claim (unprotected) → pass-through (no raise)
- Unknown asrt (unprotected) → pass-through (no raise)
"""
import pytest

from factgraph.application.retract_guard import (
    RetractGuardError,
    check_retract_allowed,
    classify_retract_target,
)
from factgraph.application.schema_runtime import build_schema_index
from factgraph.authoring.schema_compile import compile_authoring_schema_v1
from factgraph.core.store.ledger import Claim


class _StubLedger:
    """Minimal Ledger stub exposing only `get_claim(asrt_id)`.

    Per P1 #1 amend, the retract guard uses ONLY this existing API.
    Avoids spinning up a real sqlite-backed Ledger for unit tests of
    pure schema-aware classification.
    """

    def __init__(self, claims_by_asrt_id: dict[str, str]) -> None:
        # asrt_id -> pred_id mapping
        self._claims = {
            asrt_id: Claim(asrt_id=asrt_id, pred_id=pred_id, e_ref="stub", rest_terms=[])
            for asrt_id, pred_id in claims_by_asrt_id.items()
        }

    def get_claim(self, asrt_id: str):
        return self._claims.get(asrt_id)


def _build_form_i_index():
    """Form I schema fixture with 2 identity fields + 1 field + 1 exists.

    Identity pred_ids: user:user_id, user:tenant_id
    Exists pred_id:    User:exists
    Field pred_id:     user:name
    """
    authoring = {
        "entities": [
            {
                "entity_type": "User",
                "identity_fields": [
                    {"name": "user_id", "type_domain": "string"},
                    {"name": "tenant_id", "type_domain": "string"},
                ],
                "fields": [
                    {"__kind__": "field", "py_name": "name", "type_domain": "string", "cardinality": "single"},
                ],
            },
        ]
    }
    return build_schema_index(compile_authoring_schema_v1(authoring))


# ---------- classify_retract_target ----------


def test_classify_identity_claim_returns_identity():
    """asrt_id pointing to Identity Claim → 'identity' classification."""
    idx = _build_form_i_index()
    ledger = _StubLedger({"asrt-1": "user:user_id"})
    assert classify_retract_target("asrt-1", ledger=ledger, schema_index=idx) == "identity"


def test_classify_exists_claim_returns_exists():
    """asrt_id pointing to <EntityType>:exists Claim → 'exists' classification."""
    idx = _build_form_i_index()
    ledger = _StubLedger({"asrt-2": "User:exists"})
    assert classify_retract_target("asrt-2", ledger=ledger, schema_index=idx) == "exists"


def test_classify_field_claim_returns_unprotected():
    """asrt_id pointing to Field Claim → 'unprotected' classification (P1 #1 naming)."""
    idx = _build_form_i_index()
    ledger = _StubLedger({"asrt-3": "user:name"})
    assert classify_retract_target("asrt-3", ledger=ledger, schema_index=idx) == "unprotected"


def test_classify_unknown_asrt_returns_unprotected():
    """Unknown asrt (Ledger returns None) → 'unprotected' pass-through (P1 #1)."""
    idx = _build_form_i_index()
    ledger = _StubLedger({})  # empty — unknown asrt
    assert classify_retract_target("asrt-unknown", ledger=ledger, schema_index=idx) == "unprotected"


# ---------- check_retract_allowed ----------


def test_check_identity_raises_inv_7c():
    """Identity Claim retract → RetractGuardError(code=INV_7C_IDENTITY_PROTECTED)."""
    idx = _build_form_i_index()
    ledger = _StubLedger({"asrt-1": "user:tenant_id"})
    with pytest.raises(RetractGuardError) as exc_info:
        check_retract_allowed("asrt-1", ledger=ledger, schema_index=idx)
    err = exc_info.value
    assert err.code == "INV_7C_IDENTITY_PROTECTED"
    assert err.classification == "identity"
    assert err.asrt_id == "asrt-1"
    assert err.pred_id == "user:tenant_id"


def test_check_exists_raises_transitional_guard():
    """<EntityType>:exists Claim retract → RetractGuardError(code=EXISTENCE_CLAIM_TRANSITIONAL_GUARD)."""
    idx = _build_form_i_index()
    ledger = _StubLedger({"asrt-2": "User:exists"})
    with pytest.raises(RetractGuardError) as exc_info:
        check_retract_allowed("asrt-2", ledger=ledger, schema_index=idx)
    err = exc_info.value
    assert err.code == "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
    assert err.classification == "exists"
    assert err.asrt_id == "asrt-2"
    assert err.pred_id == "User:exists"


def test_check_field_passes_through():
    """Field Claim retract → no raise (unprotected pass-through)."""
    idx = _build_form_i_index()
    ledger = _StubLedger({"asrt-3": "user:name"})
    # No raise — should return None
    result = check_retract_allowed("asrt-3", ledger=ledger, schema_index=idx)
    assert result is None


def test_check_unknown_asrt_passes_through():
    """Unknown asrt → no raise (unprotected pass-through; downstream handles)."""
    idx = _build_form_i_index()
    ledger = _StubLedger({})  # empty
    # No raise — should return None; downstream retract_by_asrt produces error
    result = check_retract_allowed("asrt-unknown", ledger=ledger, schema_index=idx)
    assert result is None


# ---------- error code distinction (per ADR-IC §8 acceptance) ----------


def test_identity_and_exists_produce_distinguishable_codes():
    """Identity vs exists produce DIFFERENT codes (caller can branch)."""
    idx = _build_form_i_index()
    ledger = _StubLedger(
        {"asrt-id": "user:user_id", "asrt-ex": "User:exists"}
    )

    with pytest.raises(RetractGuardError) as id_exc:
        check_retract_allowed("asrt-id", ledger=ledger, schema_index=idx)
    with pytest.raises(RetractGuardError) as ex_exc:
        check_retract_allowed("asrt-ex", ledger=ledger, schema_index=idx)

    assert id_exc.value.code != ex_exc.value.code
    assert id_exc.value.code == "INV_7C_IDENTITY_PROTECTED"
    assert ex_exc.value.code == "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
    assert id_exc.value.classification == "identity"
    assert ex_exc.value.classification == "exists"


# ---------- RetractGuardError does NOT inherit SDK exception ----------


def test_retract_guard_error_does_not_inherit_sdk_error():
    """RetractGuardError MUST NOT inherit from any SDK-layer exception
    per Slice 2 SF2 three-layer enforcement model.

    SDK shell mapping to SDKStoreError is the consumer's responsibility,
    not the application-layer guard's.
    """
    # Verify by inspecting the MRO — no factgraph.sdk error in chain
    mro_names = [cls.__name__ for cls in RetractGuardError.__mro__]
    assert "SDKStoreError" not in mro_names
    assert "SDKValueError" not in mro_names
    assert "EntityNotFoundError" not in mro_names
    # Confirm it's a plain Exception subclass
    assert issubclass(RetractGuardError, Exception)


# ---------- Q-PR1 carve-out: only uses existing Ledger.get_claim API ----------


def test_helper_only_uses_existing_ledger_get_claim_api():
    """Per P1 #1: retract_guard MUST only use existing Ledger.get_claim API.

    The _StubLedger above exposes ONLY get_claim — if the helper called
    any other Ledger method, this test would fail with AttributeError.
    All tests above passing confirms the helper is purely get_claim-based.
    """
    idx = _build_form_i_index()
    ledger = _StubLedger({"asrt-1": "user:user_id"})
    # Helper must complete without touching other Ledger methods
    with pytest.raises(RetractGuardError):
        check_retract_allowed("asrt-1", ledger=ledger, schema_index=idx)
    classify_retract_target("asrt-1", ledger=ledger, schema_index=idx)
    # If we reach here, the helper used only get_claim ✓
