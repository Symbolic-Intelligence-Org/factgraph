"""ProofFrame capability helper builders."""

from __future__ import annotations

from factgraph.application.protocol import (
    FactOverlay,
    ProofFrameRecheckRequest,
)
from factgraph.core.store._support import ProofReceipt

from ._binding import _reject_sdk_origin
from .errors import CapabilityHelperError


def build_proof_frame_recheck_request(
    support: ProofReceipt,
    *,
    overlay: FactOverlay | None = None,
) -> ProofFrameRecheckRequest:
    """Build a ProofFrameRecheckRequest from application-canonical inputs."""

    overlay_value = FactOverlay() if overlay is None else overlay

    _reject_sdk_origin(support, path="support")
    _reject_sdk_origin(overlay_value, path="overlay")

    if not isinstance(support, ProofReceipt):
        raise CapabilityHelperError("support must be ProofReceipt")
    if not isinstance(overlay_value, FactOverlay):
        raise CapabilityHelperError("overlay must be FactOverlay or None")

    return ProofFrameRecheckRequest(
        support_artifact=support,
        overlay=overlay_value,
    )


__all__ = [
    "build_proof_frame_recheck_request",
]
