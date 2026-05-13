"""SDK shell for G5 ProofFrame Diff capability.

Implements the ``SDKStore.diff_proof_frames`` facade method per the
archived G5 blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g5-round-events-proofframe-diff.md``
§5.

Public surface contract per blueprint §5 locks:

- Method:      ``SDKStore.diff_proof_frames(...)`` (instance method;
               not a free function in ``factpy.sdk.__all__`` — see
               §5.7 lock and G1 + G4 + G2 + G3 precedent).
- Signature:   ``diff_proof_frames(round_a_id, round_b_id,
               round_a_events, round_b_events, *, warnings=(),
               include_unchanged=False)`` per §5.3 lock; raw
               ``tuple[RoundEvent, ...]`` × 2 mirroring
               ``factpy.audit.proof_frame_diff.build_proof_frame_diff(...)``
               1:1. SDK shell does no IO; users load events via
               ``factpy.audit.load_audit_package`` or hold them from
               a fresh recorder.
- Return:      ``ProofFrameDiff`` (raw application-canonical DTO from
               ``factpy.audit.proof_frame_diff``; documented passthrough
               per §5.4 lock; not re-exported from
               ``factpy.sdk.__all__``).
- Errors:      Non-SDK exceptions crossing the SDK boundary remap to
               ``SDKStoreError(...) from exc`` per §5.8 lock with
               8 capability-specific paths
               (``$.diff_proof_frames.round_a_id`` /
               ``$.diff_proof_frames.round_b_id`` /
               ``$.diff_proof_frames.round_a_events`` /
               ``$.diff_proof_frames.round_b_events`` /
               ``$.diff_proof_frames.warnings`` /
               ``$.diff_proof_frames.include_unchanged`` /
               ``$.diff_proof_frames.request`` / base
               ``$.diff_proof_frames``). The 6 input paths use inline
               pre-validation; ``.request`` catches
               ``ProofFrameDiffError`` from the runtime; the base
               path is a defensive ``Exception`` wrap. No
               ``ProtocolShapeError`` path (no intermediate request
               DTO), no ``.dependencies`` path (no derivation
               lowering / rule registry), no ``CapabilityHelperError``
               path (diff is pure ``factpy.audit``, not a
               ``factpy.application.capability_helpers`` builder).
- Sibling:     ``sdk_diff_proof_frames`` does NOT call any sibling SDK
               shell (``sdk_check`` / ``sdk_diagnose`` / ``sdk_why_not``
               / ``sdk_fact_overlay_check`` / ``sdk_proof_frame_recheck``
               / ``sdk_rule_disable`` / ``sdk_rule_literal_replace`` /
               ``sdk_rule_add_condition``). It owns its own dispatch
               and never extracts ``RoundEvent`` tuples from any other
               SDK call's return value.

Cross-cutting precedent layer rule (encoded in §6 invariants):
``RoundEvent``, ``WarningDTO``, and ``ProofFrameDiff`` cross the SDK
boundary as raw frozen DTOs because they are "frozen canonical DTO
above ``factpy.core`` using ``factpy.application.protocol``
vocabulary". Substrate IR (``factpy.core.*``) remains excluded.
"""

from __future__ import annotations

from typing import Any

from factpy.application.protocol.common import WarningDTO
from factpy.audit.proof_frame_diff import (
    ProofFrameDiff,
    ProofFrameDiffError,
    build_proof_frame_diff,
)
from factpy.audit.round_events import RoundEvent

from ..errors import SDKStoreError


def sdk_diff_proof_frames(
    sdk: Any,
    round_a_id: Any,
    round_b_id: Any,
    round_a_events: Any,
    round_b_events: Any,
    *,
    warnings: Any = (),
    include_unchanged: bool = False,
) -> ProofFrameDiff:
    """Diff two rounds' proof-frame events.

    Returns the application ``ProofFrameDiff`` DTO directly. The SDK
    shell is pure (no IO; no Store / registry / engine arg), mirroring
    ``factpy.audit.proof_frame_diff.build_proof_frame_diff(...)`` 1:1.
    """

    del sdk  # SDK shell is pure; sdk handle reserved for future symmetry

    if not isinstance(round_a_id, str) or not round_a_id:
        raise SDKStoreError(
            "round_a_id must be non-empty str",
            path="$.diff_proof_frames.round_a_id",
        )
    if not isinstance(round_b_id, str) or not round_b_id:
        raise SDKStoreError(
            "round_b_id must be non-empty str",
            path="$.diff_proof_frames.round_b_id",
        )

    if not isinstance(round_a_events, tuple) or not all(
        isinstance(event, RoundEvent) for event in round_a_events
    ):
        raise SDKStoreError(
            "round_a_events must be tuple[RoundEvent, ...]",
            path="$.diff_proof_frames.round_a_events",
        )
    if not isinstance(round_b_events, tuple) or not all(
        isinstance(event, RoundEvent) for event in round_b_events
    ):
        raise SDKStoreError(
            "round_b_events must be tuple[RoundEvent, ...]",
            path="$.diff_proof_frames.round_b_events",
        )

    if not isinstance(warnings, tuple) or not all(
        isinstance(warning, WarningDTO) for warning in warnings
    ):
        raise SDKStoreError(
            "warnings must be tuple[WarningDTO, ...]",
            path="$.diff_proof_frames.warnings",
        )

    if not isinstance(include_unchanged, bool):
        raise SDKStoreError(
            "include_unchanged must be bool",
            path="$.diff_proof_frames.include_unchanged",
        )

    try:
        return build_proof_frame_diff(
            round_a_id=round_a_id,
            round_b_id=round_b_id,
            round_a_events=round_a_events,
            round_b_events=round_b_events,
            warnings=warnings,
            include_unchanged=include_unchanged,
        )
    except ProofFrameDiffError as exc:
        raise SDKStoreError(
            f"invalid diff_proof_frames request: {exc}",
            path="$.diff_proof_frames.request",
        ) from exc
    except Exception as exc:
        raise SDKStoreError(
            f"diff_proof_frames runtime failed: {exc}",
            path="$.diff_proof_frames",
        ) from exc


__all__ = [
    "sdk_diff_proof_frames",
]
