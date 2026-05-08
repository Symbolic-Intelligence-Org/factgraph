"""ProofFrame capability helper builders."""

from __future__ import annotations

from kernel.core.store._support import SupportArtifact

from kernel.application.protocol import (
    EvaluationOverlay,
    ProofFrameRecheckRequest,
)

from ._binding import _reject_sdk_origin
from .errors import CapabilityHelperError


def build_proof_frame_recheck_request(
    support: SupportArtifact,
    *,
    overlay: EvaluationOverlay | None = None,
) -> ProofFrameRecheckRequest:
    """Build a ProofFrameRecheckRequest from application-canonical inputs."""

    overlay_value = EvaluationOverlay() if overlay is None else overlay

    _reject_sdk_origin(support, path="support")
    _reject_sdk_origin(overlay_value, path="overlay")

    if not isinstance(support, SupportArtifact):
        raise CapabilityHelperError("support must be SupportArtifact")
    if not isinstance(overlay_value, EvaluationOverlay):
        raise CapabilityHelperError("overlay must be EvaluationOverlay or None")

    return ProofFrameRecheckRequest(
        support_artifact=support,
        overlay=overlay_value,
    )


__all__ = [
    "build_proof_frame_recheck_request",
]
