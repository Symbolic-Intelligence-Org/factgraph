"""SDK shell for Q2 Diagnose capability.

Phase 2 of G1 (per blueprint
``docs/blueprints/active/2026-05-08_l-direction-g1-check-diagnose.md`` §8)
implements the ``SDKStore.diagnose`` facade method.

Public surface contract per blueprint §5 locks:

- Method:      ``SDKStore.diagnose(...)`` (instance method; not a free function
               in ``kernel.sdk.__all__`` — see §5.4 lock).
- Signature:   ``diagnose(derivation, binding, *, engine="native", registry=None)``
               (see §5.7 lock; ``derivation`` is SDK ``Derivation`` only,
               ``binding`` is ``Mapping[str, Any]`` with ``$``-prefixed
               variable-name string keys).
- Return:      ``DiagnoseResult`` (raw application protocol DTO; documented
               passthrough per §5.2 lock; not re-exported from
               ``kernel.sdk.__all__``). Advanced callers that need locator
               parsing can opt into application-layer helpers such as
               ``kernel.application.walker.parse_atom_key`` when they have a
               compatible atom-key string.
- Errors:      ``CapabilityHelperError`` and ``OriginPackageError`` from
               ``kernel.application.capability_helpers`` are caught and
               re-raised as ``SDKStoreError`` with ``__cause__`` chaining
               (per §5.3 lock).
- Q1 Sibling:  Diagnose owns its own dispatch and does NOT call the sibling
               Check SDK shell internally — mirrors the application-layer Q1
               Sibling discipline at
               ``kernel.application.protocol.derivation_diagnose`` module
               docstring ("Diagnose owns its full dispatch and does NOT call
               ``check_derivation_binding(...)``").
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.application.capability_helpers import (
    CapabilityHelperError,
    build_diagnose_request,
)
from kernel.application.diagnose_runtime import diagnose_derivation_binding
from kernel.application.protocol import DiagnoseResult

from .dsl import Derivation
from .errors import SDKStoreError
from .store import _compiled_derivation_plan_to_application


def sdk_diagnose(
    sdk: Any,
    derivation: Any,
    binding: Mapping[str, Any],
    *,
    engine: str = "native",
    registry: Any = None,
) -> DiagnoseResult:
    """Run Diagnose for a single SDK ``Derivation`` and binding mapping.

    Returns the application ``DiagnoseResult`` DTO directly. The SDK shell
    keeps Diagnose independent from Check and does not import walker helpers.
    """

    _validate_derivation(derivation)
    binding_dict = _validate_binding(binding)

    compiled_plans = sdk._compile_derivation_input(derivation)
    if len(compiled_plans) != 1:
        raise SDKStoreError(
            "diagnose derivation must compile to exactly one plan",
            path="$.diagnose.derivation",
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
            f"invalid diagnose input: {exc}",
            path="$.diagnose.derivation",
        ) from exc
    resolved_registry = sdk._resolve_runtime_registry(derivation, explicit_registry=registry)

    try:
        request = build_diagnose_request(plan, binding_dict, engine=engine)
    except CapabilityHelperError as exc:
        raise SDKStoreError(f"invalid diagnose input: {exc}", path="$.diagnose") from exc

    return diagnose_derivation_binding(request, store=sdk._store, registry=resolved_registry)


def _validate_derivation(derivation: Any) -> None:
    if not isinstance(derivation, Derivation):
        raise SDKStoreError("derivation must be SDK Derivation", path="$.diagnose.derivation")


def _validate_binding(binding: Any) -> dict[str, Any]:
    if not isinstance(binding, Mapping):
        raise SDKStoreError("binding must be Mapping[str, Any]", path="$.diagnose.binding")

    out: dict[str, Any] = {}
    for key, value in binding.items():
        if not isinstance(key, str) or not key.startswith("$") or len(key) == 1:
            raise SDKStoreError(
                "binding keys must be $-prefixed variable names",
                path="$.diagnose.binding",
            )
        out[key] = value
    return out


__all__ = [
    "sdk_diagnose",
]
