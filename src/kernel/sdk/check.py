"""SDK shell for Q1 Check capability.

Phase 1 of G1 (per blueprint
``docs/blueprints/active/2026-05-08_l-direction-g1-check-diagnose.md`` §8)
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
               ``kernel.sdk.__all__``).
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

from .dsl import Derivation
from .errors import SDKStoreError
from .store import _compiled_derivation_plan_to_application


def sdk_check(
    sdk: Any,
    derivation: Any,
    binding: Mapping[str, Any],
    *,
    engine: str = "native",
    registry: Any = None,
) -> CheckResult:
    """Run Check for a single SDK ``Derivation`` and binding mapping."""

    _validate_derivation(derivation)
    binding_dict = _validate_binding(binding)

    compiled_plans = sdk._compile_derivation_input(derivation)
    if len(compiled_plans) != 1:
        raise SDKStoreError(
            "check derivation must compile to exactly one plan",
            path="$.check.derivation",
        )

    plan = _compiled_derivation_plan_to_application(
        compiled_plans[0],
        mode=engine,
        explicit_engine_ext=getattr(derivation, "engine_ext", None),
        engine_options=None,
    )
    resolved_registry = sdk._resolve_runtime_registry(derivation, explicit_registry=registry)

    try:
        request = build_check_request(plan, binding_dict, engine=engine)
    except CapabilityHelperError as exc:
        raise SDKStoreError(f"invalid check input: {exc}", path="$.check") from exc

    return check_derivation_binding(request, store=sdk._store, registry=resolved_registry)


def _validate_derivation(derivation: Any) -> None:
    if not isinstance(derivation, Derivation):
        raise SDKStoreError("derivation must be SDK Derivation", path="$.check.derivation")


def _validate_binding(binding: Any) -> dict[str, Any]:
    if not isinstance(binding, Mapping):
        raise SDKStoreError("binding must be Mapping[str, Any]", path="$.check.binding")

    out: dict[str, Any] = {}
    for key, value in binding.items():
        if not isinstance(key, str) or not key.startswith("$") or len(key) == 1:
            raise SDKStoreError(
                "binding keys must be $-prefixed variable names",
                path="$.check.binding",
            )
        out[key] = value
    return out


__all__ = [
    "sdk_check",
]
