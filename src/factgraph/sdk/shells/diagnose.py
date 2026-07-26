"""SDK shell for Q2 Diagnose capability.

Phase 2 of G1 (per blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g1-check-diagnose.md`` §8)
implements the ``sdk_diagnose`` facade method.

Public surface contract per blueprint §5 locks:

- Method:      ``sdk_diagnose(...)`` (instance method; not a free function
               in ``factgraph.sdk.__all__`` — see §5.4 lock).
- Signature:   ``diagnose(inference, binding, *, engine="native", registry=None)``
               (see §5.7 lock; ``inference`` is SDK ``Inference`` only,
               ``binding`` is ``Mapping[str, Any]`` with ``$``-prefixed
               variable-name string keys).
- Return:      ``DiagnoseResult`` (raw application protocol DTO; documented
               passthrough per §5.2 lock; not re-exported from
               ``factgraph.sdk.__all__``). Advanced callers that need locator
               parsing can opt into application-layer helpers such as
               ``factgraph.application.walker.parse_condition_key`` when they have a
               compatible atom-key string.
- Errors:      ``CapabilityHelperError`` and ``OriginPackageError`` from
               ``factgraph.application.capability_helpers`` are caught and
               re-raised as ``SDKStoreError`` with ``__cause__`` chaining
               (per §5.3 lock).
- Q1 Sibling:  Diagnose owns its own dispatch and does NOT call the sibling
               Check SDK shell internally — mirrors the application-layer Q1
               Sibling discipline at
               ``factgraph.application.protocol.derivation_diagnose`` module
               docstring ("Diagnose owns its full dispatch and does NOT call
               ``check_derivation_binding(...)``").
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factgraph.application.capability_helpers import (
    CapabilityHelperError,
    build_diagnose_request,
)
from factgraph.application.diagnose_runtime import diagnose_derivation_binding
from factgraph.application.protocol import DiagnoseResult

from ._validation import resolve_derivation_plan, resolve_runtime_registry, validate_binding
from ..errors import SDKStoreError


def sdk_diagnose(
    sdk: Any,
    inference: Any,
    binding: Mapping[str, Any],
    *,
    head: Any = None,
    engine: str = "native",
    registry: Any = None,
) -> DiagnoseResult:
    """Run Diagnose for a single SDK ``Inference`` and binding mapping.

    Returns the application ``DiagnoseResult`` DTO directly. The SDK shell
    keeps Diagnose independent from Check and does not import walker helpers.

    ``head`` is only consulted for the ``Rule`` / ``RuleExpr`` form, where it
    names the conclusion the body supports. An ``Inference`` already carries
    its head, so the argument is ignored for it.
    """

    plan = resolve_derivation_plan(
        sdk,
        inference,
        head=head,
        engine=engine,
        path="$.diagnose.inference",
    )
    binding_dict = validate_binding(binding, path="$.diagnose.binding")

    resolved_registry = resolve_runtime_registry(
        sdk,
        inference,
        explicit_registry=registry,
        path="$.diagnose.dependencies",
    )

    try:
        request = build_diagnose_request(plan, binding_dict, engine=engine)
    except CapabilityHelperError as exc:
        raise SDKStoreError(f"invalid diagnose input: {exc}", path="$.diagnose") from exc

    return diagnose_derivation_binding(request, store=sdk._store, registry=resolved_registry)


__all__ = [
    "sdk_diagnose",
]
