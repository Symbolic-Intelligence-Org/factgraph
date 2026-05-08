"""SDK shell for Q2 Diagnose capability — Phase 0 stub.

Phase 0 of G1 (per blueprint
``docs/blueprints/active/2026-05-08_l-direction-g1-check-diagnose.md`` §8)
ships only a delegation skeleton that raises ``NotImplementedError``. Real
end-to-end implementation lands in Phase 2.

Public surface contract per blueprint §5 locks (see ``check.py`` for full
context — Diagnose mirrors Check's surface conventions):

- Method:      ``SDKStore.diagnose(...)`` (instance method; not a free function
               in ``kernel.sdk.__all__`` — see §5.4 lock).
- Signature:   ``diagnose(derivation, binding, *, engine="native", registry=None)``
               (see §5.7 lock).
- Return:      ``DiagnoseResult`` (raw application protocol DTO; documented
               passthrough per §5.2 lock; not re-exported from
               ``kernel.sdk.__all__``).
- Q1 Sibling:  ``sdk_diagnose`` MUST NOT call ``sdk_check`` internally; the
               two SDK shells mirror the application-layer Q1 Sibling
               discipline (Diagnose owns its own dispatch).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def sdk_diagnose(
    sdk: Any,
    derivation: Any,
    binding: Mapping[str, Any],
    *,
    engine: str = "native",
    registry: Any = None,
) -> Any:
    """Phase 0 stub for ``SDKStore.diagnose``; raises ``NotImplementedError``.

    Real implementation lands in Phase 2 per blueprint §8.
    """
    raise NotImplementedError(
        "sdk_diagnose is a Phase 0 stub; real implementation lands in Phase 2 "
        "per docs/blueprints/active/2026-05-08_l-direction-g1-check-diagnose.md §8"
    )
