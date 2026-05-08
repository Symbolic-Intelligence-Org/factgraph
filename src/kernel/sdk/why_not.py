"""SDK shell for Q4 Why-not Universe Diagnose capability.

Phase 0 of G4 (per blueprint
``docs/blueprints/active/2026-05-08_l-direction-g4-why-not-frontier.md`` §8)
adds the module skeleton + delegation hook with the locked signature.
Phase 1 fills in the real lowering, request construction, dispatch, and
``SDKStoreError`` remap.

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

from kernel.application.protocol import WhyNotUniverseResult


def sdk_why_not(
    sdk: Any,
    derivation: Any,
    candidates: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    engine: str = "native",
    registry: Any = None,
) -> WhyNotUniverseResult:
    """Run Why-not for a single SDK ``Derivation`` and explicit candidate universe.

    Phase 0 placeholder. Phase 1 implements the real path:

    1. ``validate_derivation(derivation, path="$.why_not.derivation")``
    2. lower derivation via G1 ``_compile_derivation_input(...)`` /
       ``_compiled_derivation_plan_to_application(...)`` chain
    3. resolve runtime registry (G1 B.1 pattern)
    4. ``build_why_not_candidate_universe(plan, candidates)`` (A helper)
    5. construct ``WhyNotUniverseRequest(...)``
    6. dispatch ``check_why_not_universe(request, store, registry)``
    7. return raw ``WhyNotUniverseResult``

    All non-SDK exceptions remap to ``SDKStoreError(...) from exc`` per
    §5.6 lock.
    """

    raise NotImplementedError(
        "G4 Phase 1 will implement sdk_why_not; current state is the "
        "Phase 0 skeleton."
    )


__all__ = [
    "sdk_why_not",
]
