"""SDK shell for Batch 4 ProofFrame Recheck capability.

Implements the ``SDKStore.recheck_proof_frame`` facade method per the
archived G2 blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md``
§5.

Public surface contract per blueprint §5 locks:

- Method:      ``SDKStore.recheck_proof_frame(...)`` (instance method;
               not a free function in ``factgraph.sdk.__all__`` — see §5.7
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
               re-exported from ``factgraph.sdk.__all__``).
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

Both validators (``validate_support_artifact`` and
``validate_evaluation_overlay``) live in
``factgraph.sdk.shells._validation``. The overlay validator was extracted
during the G2 post-publish verification round 2026-05-08 (Fact Overlay
and ProofFrame Recheck share the same ``EvaluationOverlay`` boundary
check). The support-artifact validator was promoted from local at G3
Phase 0 hygiene 2026-05-08 — G3 rule-overlay shells also need it, which
fires the G2 §5.2 deferred extraction trigger ("until G3/G5 also need
them").
"""

from __future__ import annotations

from typing import Any

from factgraph.application.protocol import (
    ProofFrameRecheckRequest,
    ProofFrameRecheckResult,
    ProtocolShapeError,
)
from factgraph.application.proofframe_runtime import recheck_proof_frame

from ._validation import validate_evaluation_overlay, validate_support_artifact
from ..errors import SDKStoreError


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

    validate_support_artifact(
        support_artifact, path="$.recheck_proof_frame.support_artifact"
    )
    validate_evaluation_overlay(overlay, path="$.recheck_proof_frame.overlay")

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
