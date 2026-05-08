"""SDK shell for Q3 Fact Overlay Check capability.

Implements the ``SDKStore.check_fact_overlay`` facade method per the
scoped G2 blueprint
``docs/blueprints/active/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md``
§5.

Public surface contract per blueprint §5 locks:

- Method:      ``SDKStore.check_fact_overlay(...)`` (instance method; not
               a free function in ``kernel.sdk.__all__`` — see §5.7 lock
               and G1 + G4 precedent).
- Signature:   ``check_fact_overlay(derivation, binding, overlay, *,
               engine="native", registry=None)`` (see §5.1 lock;
               ``derivation`` is SDK ``Derivation`` only, ``binding`` is a
               ``$``-prefixed mapping validated through the shared SDK
               validators, and ``overlay`` is a raw ``EvaluationOverlay``
               protocol DTO).
- Return:      ``FactOverlayCheckResult`` (raw application protocol DTO;
               documented passthrough per §5.3 lock; not re-exported from
               ``kernel.sdk.__all__``).
- Errors:      Non-SDK exceptions crossing the SDK boundary remap to
               ``SDKStoreError(...) from exc`` per §5.8 lock with
               capability-specific paths (``$.check_fact_overlay.derivation``
               / ``$.check_fact_overlay.binding`` /
               ``$.check_fact_overlay.dependencies`` /
               ``$.check_fact_overlay.request``). The runtime
               ``check_fact_overlay_binding(...)`` returns a
               ``FactOverlayCheckResult`` (including ``invalid_request``
               status) rather than raising; that result is passed through
               unchanged per §5.8 lock.
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
from kernel.core.rules.rule_ir import RuleCompileError
from kernel.core.store._support import normalize_binding_items

from ._validation import validate_binding, validate_derivation
from ..errors import SDKStoreError
from ..store import _compiled_derivation_plan_to_application


def sdk_fact_overlay_check(
    sdk: Any,
    derivation: Any,
    binding: Mapping[str, Any],
    overlay: Any,
    *,
    engine: str = "native",
    registry: Any = None,
) -> FactOverlayCheckResult:
    """Run Fact Overlay Check for one SDK ``Derivation`` + binding + overlay.

    Returns the application ``FactOverlayCheckResult`` DTO directly. The
    SDK shell does not import sibling SDK shells; the runtime
    ``check_fact_overlay_binding(...)`` represents unsupported overlay /
    runtime conditions as ``invalid_request`` result DTOs and is passed
    through unchanged.
    """

    validate_derivation(derivation, path="$.check_fact_overlay.derivation")
    binding_dict = validate_binding(binding, path="$.check_fact_overlay.binding")

    compiled_plans = sdk._compile_derivation_input(derivation)
    if len(compiled_plans) != 1:
        raise SDKStoreError(
            "check_fact_overlay derivation must compile to exactly one plan",
            path="$.check_fact_overlay.derivation",
        )

    try:
        plan = _compiled_derivation_plan_to_application(
            compiled_plans[0],
            mode=engine,
            explicit_engine_ext=getattr(derivation, "engine_ext", None),
            engine_options=None,
        )
    except ValueError as exc:
        raise SDKStoreError(
            f"invalid check_fact_overlay input: {exc}",
            path="$.check_fact_overlay.derivation",
        ) from exc

    try:
        resolved_registry = sdk._resolve_runtime_registry(derivation, explicit_registry=registry)
    except RuleCompileError as exc:
        raise SDKStoreError(
            f"invalid check_fact_overlay dependencies: {exc}",
            path="$.check_fact_overlay.dependencies",
        ) from exc

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

    return check_fact_overlay_binding(request, store=sdk._store, registry=resolved_registry)


__all__ = [
    "sdk_fact_overlay_check",
]
