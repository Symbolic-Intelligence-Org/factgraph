"""SDK shell for Q1 Check capability.

Phase 1 of G1 (per blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g1-check-diagnose.md`` §8)
implements the ``SDKStore.check`` facade method.

Public surface contract per blueprint §5 locks:

- Method:      ``SDKStore.check(...)`` (instance method; not a free function in
               ``kernel.sdk.__all__`` — see §5.4 lock).
- Signature:   ``check(derivation, binding, *, engine="native", registry=None)``
               (see §5.7 lock; ``derivation`` is SDK ``Derivation`` only,
               ``binding`` is ``Mapping[str, Any]`` with ``$``-prefixed
               variable-name string keys; both validated in Phase 1).
- Return:      ``CheckResult`` (raw application protocol DTO; documented
               passthrough per §5.2 lock; not re-exported from
               ``kernel.sdk.__all__``). For ergonomic evidence traversal,
               advanced callers can wrap ``result.evidence_envelope`` data
               with ``kernel.application.walker.SupportArtifactView`` from
               outside the SDK boundary.
- Errors:      ``CapabilityHelperError`` and ``OriginPackageError`` from
               ``kernel.application.capability_helpers`` are caught and
               re-raised as ``SDKStoreError`` with ``__cause__`` chaining
               (per §5.3 lock; exact ``code`` / ``path`` filled in Phase 1).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.application.capability_helpers import (
    CapabilityHelperError,
    build_check_request,
)
from kernel.application.derivation_check_runtime import check_derivation_binding
from kernel.application.protocol import CheckResult

from ._validation import resolve_runtime_registry, validate_binding, validate_derivation
from ..errors import SDKStoreError
from ..store import _compiled_derivation_plan_to_application


def sdk_check(
    sdk: Any,
    derivation: Any,
    binding: Mapping[str, Any],
    *,
    engine: str = "native",
    registry: Any = None,
) -> CheckResult:
    """Run Check for a single SDK ``Derivation`` and binding mapping.

    Returns the application ``CheckResult`` DTO directly. The SDK shell does
    not import walker views; callers that need ergonomic evidence traversal
    can opt into ``kernel.application.walker`` themselves.
    """

    validate_derivation(derivation, path="$.check.derivation")
    binding_dict = validate_binding(binding, path="$.check.binding")

    compiled_plans = sdk._compile_derivation_input(derivation)
    if len(compiled_plans) != 1:
        raise SDKStoreError(
            "check derivation must compile to exactly one plan",
            path="$.check.derivation",
        )

    try:
        plan = _compiled_derivation_plan_to_application(
            compiled_plans[0],
            mode=engine,
            engine_options=None,
        )
    except ValueError as exc:
        raise SDKStoreError(
            f"invalid check input: {exc}",
            path="$.check.derivation",
        ) from exc
    resolved_registry = resolve_runtime_registry(
        sdk,
        derivation,
        explicit_registry=registry,
        path="$.check.dependencies",
    )

    try:
        request = build_check_request(plan, binding_dict, engine=engine)
    except CapabilityHelperError as exc:
        raise SDKStoreError(f"invalid check input: {exc}", path="$.check") from exc

    return check_derivation_binding(request, store=sdk._store, registry=resolved_registry)


__all__ = [
    "sdk_check",
]
