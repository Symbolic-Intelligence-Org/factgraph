"""SDK shell for Q3 Fact Overlay Check capability.

Implements the ``SDKStore.check_fact_overlay`` facade method per the
archived G2 blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md``
§5.

Public surface contract per blueprint §5 locks (with post-publish
verification round polish landed 2026-05-08):

- Method:      ``SDKStore.check_fact_overlay(...)`` (instance method; not
               a free function in ``kernel.sdk.__all__`` — see §5.7 lock
               and G1 + G4 precedent).
- Signature:   ``check_fact_overlay(inference, binding, overlay, *,
               engine="native", registry=None)`` (see §5.1 lock;
               ``inference`` is SDK ``Inference`` only, ``binding`` is a
               ``$``-prefixed mapping validated through the shared SDK
               validators, and ``overlay`` is a raw ``EvaluationOverlay``
               protocol DTO — the SDK rejects ``tuple[FactValueOverride,
               ...]`` form even though the application
               ``FactOverlayCheckRequest.overlay`` field would otherwise
               tolerate it).
- Return:      ``FactOverlayCheckResult`` (raw application protocol DTO;
               documented passthrough per §5.3 lock; not re-exported from
               ``kernel.sdk.__all__``).
- Errors:      Non-SDK exceptions crossing the SDK boundary remap to
               ``SDKStoreError(...) from exc`` per §5.8 lock with
               capability-specific paths (``$.check_fact_overlay.inference``
               / ``$.check_fact_overlay.binding`` /
               ``$.check_fact_overlay.overlay`` /
               ``$.check_fact_overlay.dependencies`` /
               ``$.check_fact_overlay.request`` / base
               ``$.check_fact_overlay`` for unexpected runtime). The
               runtime ``check_fact_overlay_binding(...)`` represents
               supported failure modes (``rule_actions``, empty overlay,
               ruleref / action errors, native phase failures) as
               ``FactOverlayCheckResult(status="invalid_request")`` and
               those results are passed through unchanged; only truly
               unexpected runtime exceptions reach the base-path remap.
- Q3 Sibling:  ``sdk_fact_overlay_check`` does NOT call any sibling SDK
               shell (``sdk_check`` / ``sdk_diagnose`` / ``sdk_why_not``
               / ``sdk_proof_frame_recheck``) — it owns its own dispatch
               and shares only the application-layer
               ``_derivation_match_helpers`` indirectly through
               ``check_fact_overlay_binding(...)``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.application.protocol import (
    FactOverlayCheckRequest,
    FactOverlayCheckResult,
    ProtocolShapeError,
)
from kernel.application.fact_overlay_runtime import check_fact_overlay_binding
from kernel.core.store._support import normalize_binding_items

from ._validation import (
    resolve_runtime_registry,
    validate_binding,
    validate_derivation,
    validate_evaluation_overlay,
)
from ..errors import SDKStoreError
from ..store import _compiled_derivation_plan_to_application


def sdk_fact_overlay_check(
    sdk: Any,
    inference: Any,
    binding: Mapping[str, Any],
    overlay: Any,
    *,
    engine: str = "native",
    registry: Any = None,
) -> FactOverlayCheckResult:
    """Run Fact Overlay Check for one SDK ``Inference`` + binding + overlay.

    Returns the application ``FactOverlayCheckResult`` DTO directly. The
    SDK shell does not import sibling SDK shells; the runtime
    ``check_fact_overlay_binding(...)`` represents unsupported overlay /
    runtime conditions as ``invalid_request`` result DTOs and is passed
    through unchanged.
    """

    validate_derivation(inference, path="$.check_fact_overlay.inference")
    binding_dict = validate_binding(binding, path="$.check_fact_overlay.binding")
    validate_evaluation_overlay(overlay, path="$.check_fact_overlay.overlay")

    compiled_plans = sdk._compile_derivation_input(inference)
    if len(compiled_plans) != 1:
        raise SDKStoreError(
            "check_fact_overlay inference must compile to exactly one plan",
            path="$.check_fact_overlay.inference",
        )

    try:
        plan = _compiled_derivation_plan_to_application(
            compiled_plans[0],
            mode=engine,
            engine_options=None,
        )
    except ValueError as exc:
        raise SDKStoreError(
            f"invalid check_fact_overlay input: {exc}",
            path="$.check_fact_overlay.inference",
        ) from exc

    resolved_registry = resolve_runtime_registry(
        sdk,
        inference,
        explicit_registry=registry,
        path="$.check_fact_overlay.dependencies",
    )

    binding_items = normalize_binding_items(binding_dict)

    try:
        request = FactOverlayCheckRequest(
            plan=plan,
            binding=binding_items,
            overlay=overlay,
            engine=engine,
        )
    except ProtocolShapeError as exc:
        raise SDKStoreError(
            f"invalid check_fact_overlay request: {exc}",
            path="$.check_fact_overlay.request",
        ) from exc

    try:
        return check_fact_overlay_binding(request, store=sdk._store, registry=resolved_registry)
    except Exception as exc:
        raise SDKStoreError(
            f"check_fact_overlay runtime failed: {exc}",
            path="$.check_fact_overlay",
        ) from exc


__all__ = [
    "sdk_fact_overlay_check",
]
