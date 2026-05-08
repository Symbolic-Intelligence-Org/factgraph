"""SDK shell for Q4 Why-not Universe Diagnose capability.

Implements the ``SDKStore.why_not`` facade method per the archived G4 blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g4-why-not-frontier.md`` §5.

Public surface contract per blueprint §5 locks:

- Method:      ``SDKStore.why_not(...)`` (instance method; not a free function
               in ``kernel.sdk.__all__`` — see §5.4 lock language and G1 §5.4
               precedent).
- Signature:   ``why_not(derivation, candidates, *, engine="native",
               registry=None)`` (see §5.1 lock; ``derivation`` is SDK
               ``Derivation`` only, ``candidates`` mirrors A's
               ``build_why_not_candidate_universe(plan, candidates)`` row
               forms — ``Sequence[Mapping[str, Any] | Sequence[Any]]``).
- Return:      ``WhyNotUniverseResult`` (raw application protocol DTO;
               documented passthrough per §5.3 lock; not re-exported from
               ``kernel.sdk.__all__``).
- Errors:      All non-SDK exceptions crossing the SDK boundary remap to
               ``SDKStoreError(...) from exc`` per §5.6 lock with
               capability-specific paths (``$.why_not.derivation`` /
               ``$.why_not.dependencies`` / ``$.why_not.candidates`` /
               ``$.why_not.request`` / ``$.why_not``).
- Q1 Sibling:  ``sdk_why_not`` does NOT call the sibling Check or Diagnose
               SDK shells internally — Why-not owns its own dispatch and
               application-layer ``check_why_not_universe(...)`` handles
               per-row diagnose internally without re-entering the SDK
               shell layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from kernel.application.capability_helpers import (
    CapabilityHelperError,
    build_why_not_candidate_universe,
)
from kernel.application.protocol import ProtocolShapeError, WhyNotUniverseRequest, WhyNotUniverseResult
from kernel.application.why_not_runtime import WhyNotRuntimeError, check_why_not_universe
from kernel.core.rules.rule_ir import RuleCompileError

from ._validation import validate_derivation
from ..errors import SDKStoreError
from ..store import _compiled_derivation_plan_to_application


def sdk_why_not(
    sdk: Any,
    derivation: Any,
    candidates: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    engine: str = "native",
    registry: Any = None,
) -> WhyNotUniverseResult:
    """Run Why-not for a single SDK ``Derivation`` and explicit candidate universe.

    Returns the application ``WhyNotUniverseResult`` DTO directly. The SDK
    shell does not import Check / Diagnose SDK shells and does not wrap result
    rows or Frontier data.
    """

    validate_derivation(derivation, path="$.why_not.derivation")

    compiled_plans = sdk._compile_derivation_input(derivation)
    if len(compiled_plans) != 1:
        raise SDKStoreError(
            "why_not derivation must compile to exactly one plan",
            path="$.why_not.derivation",
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
            f"invalid why_not input: {exc}",
            path="$.why_not.derivation",
        ) from exc

    try:
        resolved_registry = sdk._resolve_runtime_registry(derivation, explicit_registry=registry)
    except RuleCompileError as exc:
        raise SDKStoreError(
            f"invalid why_not dependencies: {exc}",
            path="$.why_not.dependencies",
        ) from exc

    try:
        candidate_universe = build_why_not_candidate_universe(plan, candidates)
    except CapabilityHelperError as exc:
        raise SDKStoreError(
            f"invalid why_not candidates: {exc}",
            path="$.why_not.candidates",
        ) from exc

    try:
        request = WhyNotUniverseRequest(
            plan=plan,
            candidate_universe=candidate_universe,
            engine=engine,
        )
    except ProtocolShapeError as exc:
        raise SDKStoreError(
            f"invalid why_not request: {exc}",
            path="$.why_not.request",
        ) from exc

    try:
        return check_why_not_universe(request, store=sdk._store, registry=resolved_registry)
    except WhyNotRuntimeError as exc:
        raise SDKStoreError(f"why_not runtime failed: {exc}", path="$.why_not") from exc


__all__ = [
    "sdk_why_not",
]
