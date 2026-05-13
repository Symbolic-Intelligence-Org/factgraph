"""SDK shell for Q1 Check capability.

Phase 1 of G1 (per blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g1-check-diagnose.md`` §8)
implements the ``SDKStore.check`` facade method.

Public surface contract per blueprint §5 locks:

- Method:      ``SDKStore.check(...)`` (instance method; not a free function in
               ``factpy.sdk.__all__`` — see §5.4 lock).
- Signature:   ``check(inference, binding, *, engine="native", registry=None)``
               (see §5.7 lock; ``inference`` is SDK ``Inference`` only,
               ``binding`` is ``Mapping[str, Any]`` with ``$``-prefixed
               variable-name string keys; both validated in Phase 1).
- Return:      ``CheckResult`` (raw application protocol DTO; documented
               passthrough per §5.2 lock; not re-exported from
               ``factpy.sdk.__all__``). For ergonomic evidence traversal,
               advanced callers can wrap ``result.evidence_envelope`` data
               with ``factpy.application.walker.SupportArtifactView`` from
               outside the SDK boundary.
- Errors:      ``CapabilityHelperError`` and ``OriginPackageError`` from
               ``factpy.application.capability_helpers`` are caught and
               re-raised as ``SDKStoreError`` with ``__cause__`` chaining
               (per §5.3 lock; exact ``code`` / ``path`` filled in Phase 1).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factpy.application.capability_helpers import (
    CapabilityHelperError,
    build_check_request,
)
from factpy.application.derivation_check_runtime import check_derivation_binding
from factpy.application.protocol import CheckResult

from ._validation import resolve_runtime_registry, validate_binding, validate_derivation
from ..errors import SDKStoreError
from ..store import _compiled_derivation_plan_to_application


def sdk_check(
    sdk: Any,
    inference: Any,
    binding: Mapping[str, Any],
    *,
    engine: str = "native",
    registry: Any = None,
) -> CheckResult:
    """Run Check for a single SDK ``Inference`` and binding mapping.

    Returns the application ``CheckResult`` DTO directly. The SDK shell does
    not import walker views; callers that need ergonomic evidence traversal
    can opt into ``factpy.application.walker`` themselves.
    """

    validate_derivation(inference, path="$.check.inference")
    binding_dict = validate_binding(binding, path="$.check.binding")

    compiled_plans = sdk._compile_derivation_input(inference)
    if len(compiled_plans) != 1:
        raise SDKStoreError(
            "check inference must compile to exactly one plan",
            path="$.check.inference",
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
            path="$.check.inference",
        ) from exc
    resolved_registry = resolve_runtime_registry(
        sdk,
        inference,
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
