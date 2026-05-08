"""SDK shell for Q1 Check capability — Phase 0 stub.

Phase 0 of G1 (per blueprint
``docs/blueprints/active/2026-05-08_l-direction-g1-check-diagnose.md`` §8)
ships only a delegation skeleton that raises ``NotImplementedError``. Real
end-to-end implementation lands in Phase 1.

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


def sdk_check(
    sdk: Any,
    derivation: Any,
    binding: Mapping[str, Any],
    *,
    engine: str = "native",
    registry: Any = None,
) -> Any:
    """Phase 0 stub for ``SDKStore.check``; raises ``NotImplementedError``.

    Real implementation lands in Phase 1 per blueprint §8.
    """
    raise NotImplementedError(
        "sdk_check is a Phase 0 stub; real implementation lands in Phase 1 "
        "per docs/blueprints/active/2026-05-08_l-direction-g1-check-diagnose.md §8"
    )
