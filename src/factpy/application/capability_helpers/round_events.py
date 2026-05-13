"""Round event capability helper builders."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from factpy.application.protocol import (
    CheckRequest,
    CheckResult,
    DiagnoseRequest,
    DiagnoseResult,
    FactOverlayCheckRequest,
    FactOverlayCheckResult,
    JSONValue,
    ProofFrameRecheckRequest,
    ProofFrameRecheckResult,
    WhyNotUniverseRequest,
    WhyNotUniverseResult,
)
from factpy.audit.round_events import (
    project_check_event_payload,
    project_diagnose_event_payload,
    project_fact_overlay_event_payload,
    project_proof_frame_event_payload,
    project_why_not_event_payload,
)

from ._binding import _reject_sdk_origin
from .errors import CapabilityHelperError

_Projector = Callable[[Any, Any], dict[str, JSONValue]]
_DispatchEntry = tuple[type[Any], type[Any], _Projector]

_DISPATCH: dict[str, _DispatchEntry] = {
    "check_result": (CheckRequest, CheckResult, project_check_event_payload),
    "diagnose_result": (DiagnoseRequest, DiagnoseResult, project_diagnose_event_payload),
    "fact_overlay_result": (
        FactOverlayCheckRequest,
        FactOverlayCheckResult,
        project_fact_overlay_event_payload,
    ),
    "why_not_result": (
        WhyNotUniverseRequest,
        WhyNotUniverseResult,
        project_why_not_event_payload,
    ),
    "proof_frame_result": (
        ProofFrameRecheckRequest,
        ProofFrameRecheckResult,
        project_proof_frame_event_payload,
    ),
}


def build_round_event_payload(
    *,
    kind: str,
    request: Any,
    result: Any,
) -> dict[str, JSONValue]:
    """Build a capability result payload for ``kernel.audit.round_events``."""

    _reject_sdk_origin(request, path="request")
    _reject_sdk_origin(result, path="result")

    if not isinstance(kind, str) or not kind:
        raise CapabilityHelperError("kind must be non-empty string")
    if kind not in _DISPATCH:
        raise CapabilityHelperError(
            f"unknown kind: {kind!r}; supported kinds: {sorted(_DISPATCH)!r}"
        )

    request_type, result_type, projector = _DISPATCH[kind]
    if not isinstance(request, request_type):
        raise CapabilityHelperError(
            f"kind {kind!r} expects request: "
            f"{request_type.__name__}, got {type(request).__name__}"
        )
    if not isinstance(result, result_type):
        raise CapabilityHelperError(
            f"kind {kind!r} expects result: "
            f"{result_type.__name__}, got {type(result).__name__}"
        )

    return projector(request, result)


__all__ = [
    "build_round_event_payload",
]
