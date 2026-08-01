"""Application-layer retract guard for INV-7c + existence-claim transitional guard.

This is the SHARED retract validation surface per Slice 2 SF2 three-layer
enforcement model. It is called by:

- SDK shell fail-fast path: `sdk/store.py:SDKStore.retract`
- Application ingest path: `application/ingest_runtime.py:_apply_retract`
- Application entity_write path: `application/entity_write.py:_apply_op` retract branch

It is NOT called from:

- Protocol direct path (`core/evidence/write_protocol.py:retract_by_asrt`) —
  per ADR-FI §4.4.2 caller contract; protocol layer schema-agnostic per
  Q-PR1 carve-out
- Internal rollback path (`core/derivation/accept.py:401`) — internal
  derivation rollback, NOT user-facing; intentionally unguarded per
  Slice 2 §6.3 + SF11 classification

Per ADR-IC / ADR-SYS-B:
- `identity_pred_ids` membership → INV-7c immutable anchor protection (§4.3.1)
- `exists_pred_ids` membership → existence-claim transitional guard (§4.4.2)
  (NOT INV-7c; may retire when Step 2+ removes `:exists` co-emission per §4.4.4)
- `pred_id.startswith("__system__.")` → INV-12 part 2 no revoke-of-revoke

Slice 3b INV-15 note:
- Exact-id classification uses Ledger's private audit lookup so the guard can
  see system claims while ordinary Ledger reads remain filtered.
- Unknown asrt classification → "unprotected" pass-through; downstream
  `retract_by_asrt` produces appropriate error path
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from factgraph.application.schema_runtime import SchemaIndex
    from factgraph.core.store.ledger import Ledger


RetractClassification = Literal["identity", "exists", "system", "unprotected"]


def _claim_for_retract_guard(ledger: Ledger, asrt_id: str):
    claim = ledger.get_claim(asrt_id)
    if claim is not None:
        return claim
    audit_lookup = getattr(ledger, "_get_claim_including_system", None)
    return audit_lookup(asrt_id) if callable(audit_lookup) else None


class RetractGuardError(Exception):
    """Application-layer retract guard violation.

    Does NOT inherit from any SDK-layer exception. SDK shell and other
    consumers are responsible for mapping this to their layer-specific
    error types (per Slice 2 SF2 three-layer enforcement model).

    Attributes:
        code: Either "INV_7C_IDENTITY_PROTECTED" or
              "EXISTENCE_CLAIM_TRANSITIONAL_GUARD".
        asrt_id: The assertion id that was being retracted.
        pred_id: The pred_id of the protected Claim.
        classification: "identity", "exists", or "system".
    """

    def __init__(
        self,
        *,
        code: str,
        asrt_id: str,
        pred_id: str,
        classification: Literal["identity", "exists", "system"],
    ) -> None:
        super().__init__(
            f"retract not allowed for {classification} Claim "
            f"(asrt_id={asrt_id}, pred_id={pred_id}): code={code}"
        )
        self.code = code
        self.asrt_id = asrt_id
        self.pred_id = pred_id
        self.classification = classification


def classify_retract_target(
    asrt_id: str,
    *,
    ledger: Ledger,
    schema_index: SchemaIndex,
) -> RetractClassification:
    """Classify the retract target by examining the asrt_id's pred_id.

    Returns:
        "identity"    — Identity Claim, INV-7c protected per ADR-IC §4.3.1
        "exists"      — <EntityType>:exists Claim, existence-claim
                        transitional guard per ADR-IC §4.4.2 (NOT INV-7c)
        "system"      — system Claim, INV-12 part 2 protected
        "unprotected" — Field Claim, unknown asrt, or non-anchor pred
                        (downstream retract_by_asrt handles unknown asrt
                        error path; Field Claim retract is the default
                        Slice 2 allow)
    """
    claim = _claim_for_retract_guard(ledger, asrt_id)
    if claim is None:
        return "unprotected"
    pred_id = claim.pred_id
    if pred_id.startswith("__system__."):
        return "system"
    if pred_id in schema_index.identity_pred_ids:
        return "identity"
    if pred_id in schema_index.exists_pred_ids:
        return "exists"
    return "unprotected"


def check_retract_allowed(
    asrt_id: str,
    *,
    ledger: Ledger,
    schema_index: SchemaIndex,
) -> None:
    """Raise RetractGuardError if asrt_id targets a protected Claim.

    Single Ledger lookup (no double get_claim) — performs classification
    inline rather than calling classify_retract_target.

    SDK shell catches and maps to SDKStoreError per ADR-IC §4.1 error
    messages. Application paths catch and produce ErrorDTO with
    appropriate code.

    "unprotected" classification is pass-through (no raise) — downstream
    retract_by_asrt handles Field Claim retract and unknown asrt error
    paths.
    """
    claim = _claim_for_retract_guard(ledger, asrt_id)
    if claim is None:
        return  # unknown asrt — unprotected pass-through
    pred_id = claim.pred_id
    if pred_id.startswith("__system__."):
        raise RetractGuardError(
            code="INV_12_SYSTEM_REVOKE_FORBIDDEN",
            asrt_id=asrt_id,
            pred_id=pred_id,
            classification="system",
        )
    if pred_id in schema_index.identity_pred_ids:
        raise RetractGuardError(
            code="INV_7C_IDENTITY_PROTECTED",
            asrt_id=asrt_id,
            pred_id=pred_id,
            classification="identity",
        )
    if pred_id in schema_index.exists_pred_ids:
        raise RetractGuardError(
            code="EXISTENCE_CLAIM_TRANSITIONAL_GUARD",
            asrt_id=asrt_id,
            pred_id=pred_id,
            classification="exists",
        )
    # Field Claim or non-anchor pred — unprotected pass-through


__all__ = [
    "RetractClassification",
    "RetractGuardError",
    "classify_retract_target",
    "check_retract_allowed",
]
