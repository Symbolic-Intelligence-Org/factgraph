"""SDK shell for Batch 4 ProofFrame Recheck capability.

Implements the ``SDKStore.recheck_proof_frame`` facade method per the
scoped G2 blueprint
``docs/blueprints/active/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md``
§5.

Public surface contract per blueprint §5 locks:

- Method:      ``SDKStore.recheck_proof_frame(...)`` (instance method;
               not a free function in ``kernel.sdk.__all__`` — see §5.7
               lock and G1 + G4 + Fact Overlay precedent).
- Signature:   ``recheck_proof_frame(support_artifact, overlay)`` (see
               §5.2 lock; ``support_artifact`` is a raw
               ``SupportArtifact`` from a prior Check, ``overlay`` is a
               raw ``EvaluationOverlay``). No derivation lowering, no
               registry resolution, no engine argument — ProofFrame
               Recheck operates on already-captured support, not on a
               derivation plan.
- Return:      ``ProofFrameRecheckResult`` (raw application protocol
               DTO; documented passthrough per §5.4 lock; not
               re-exported from ``kernel.sdk.__all__``).
- Errors:      Non-SDK exceptions crossing the SDK boundary remap to
               ``SDKStoreError(...) from exc`` per §5.8 lock with
               capability-specific paths
               (``$.recheck_proof_frame.support_artifact`` /
               ``$.recheck_proof_frame.overlay`` /
               ``$.recheck_proof_frame.request`` /
               ``$.recheck_proof_frame``). The runtime
               ``recheck_proof_frame(...)`` returns
               ``ProofFrameRecheckResult`` for unsupported support
               kinds, rule-ref edges, and rule actions (no exception);
               that result is passed through unchanged. The runtime
               exception remap is defensive — current source has no
               raise paths, but §5.8 covers the contract.
- Batch-4 Sibling: ``sdk_proof_frame_recheck`` does NOT call any sibling
               SDK shell (``sdk_check`` / ``sdk_diagnose`` /
               ``sdk_why_not`` / ``sdk_fact_overlay_check``). It owns
               its own dispatch; in particular it never extracts
               ``SupportArtifact`` from a ``CheckResult.engine_payload``
               (which is a ``SupportArtifact | ProvenanceEnvelope``
               union per G2 §5.2 falsifier F2).

Validators ``_validate_support_artifact`` / ``_validate_overlay`` are
intentionally local to this module (per user guidance at G2 Phase 2
kickoff). Extraction to ``shells/_validation.py`` deferred until G3 or
G5 also need them.
"""

from __future__ import annotations

from typing import Any

from kernel.application.protocol import (
    EvaluationOverlay,
    ProofFrameRecheckRequest,
    ProofFrameRecheckResult,
    ProtocolShapeError,
)
from kernel.application.proofframe_runtime import recheck_proof_frame
from kernel.core.store._support import SupportArtifact

from ..errors import SDKStoreError


def _validate_support_artifact(value: Any) -> None:
    if not isinstance(value, SupportArtifact):
        raise SDKStoreError(
            "support_artifact must be SupportArtifact",
            path="$.recheck_proof_frame.support_artifact",
        )


def _validate_overlay(value: Any) -> None:
    if not isinstance(value, EvaluationOverlay):
        raise SDKStoreError(
            "overlay must be EvaluationOverlay",
            path="$.recheck_proof_frame.overlay",
        )


def sdk_proof_frame_recheck(
    sdk: Any,
    support_artifact: Any,
    overlay: Any,
) -> ProofFrameRecheckResult:
    """Recheck a previously captured support frame under a fact-side overlay.

    Returns the application ``ProofFrameRecheckResult`` DTO directly. The
    SDK shell does not import sibling SDK shells; the runtime handles
    unsupported support kinds / rule-ref edges / rule actions by
    returning result DTOs (no exceptions raised today, but §5.8 wraps
    defensively for forward-compat).
    """

    _validate_support_artifact(support_artifact)
    _validate_overlay(overlay)

    try:
        request = ProofFrameRecheckRequest(
            support_artifact=support_artifact,
            overlay=overlay,
        )
    except ProtocolShapeError as exc:
        raise SDKStoreError(
            f"invalid recheck_proof_frame request: {exc}",
            path="$.recheck_proof_frame.request",
        ) from exc

    try:
        return recheck_proof_frame(request, store=sdk._store)
    except Exception as exc:
        raise SDKStoreError(
            f"recheck_proof_frame runtime failed: {exc}",
            path="$.recheck_proof_frame",
        ) from exc


__all__ = [
    "sdk_proof_frame_recheck",
]
