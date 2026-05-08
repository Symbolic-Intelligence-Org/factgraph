"""Shared input validators for SDK shell methods.

Currently used by ``kernel.sdk.check`` and ``kernel.sdk.diagnose`` (G1).
Forward-readable target for G4 (Why-not + Frontier) and later G2/G3/G5
shells: each shell passes its own capability-specific error path so the
resulting ``SDKStoreError`` carries the correct boundary identifier.

The module is private (``_validation``) and the functions are imported
locally by sibling shell modules — nothing here is part of
``kernel.sdk.__all__`` (per blueprint §5.2 / §5.4 / §6 narrow public API).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .dsl import Derivation
from .errors import SDKStoreError


def validate_derivation(derivation: Any, *, path: str) -> None:
    """Reject anything that is not an SDK ``Derivation`` instance.

    The ``path`` argument is the ``SDKStoreError.path`` boundary identifier
    that the calling shell wants attached, e.g. ``"$.check.derivation"`` or
    ``"$.diagnose.derivation"``. The error message text is shared across
    callers — only the path differs.
    """

    if not isinstance(derivation, Derivation):
        raise SDKStoreError("derivation must be SDK Derivation", path=path)


def validate_binding(binding: Any, *, path: str) -> dict[str, Any]:
    """Validate the SDK shell binding mapping and return a plain ``dict`` copy.

    Accepts any ``collections.abc.Mapping`` whose keys are ``$``-prefixed
    variable-name strings (length ≥ 2). Returns a fresh ``dict[str, Any]``
    so callers can pass it onward without retaining the original mapping
    reference.
    """

    if not isinstance(binding, Mapping):
        raise SDKStoreError("binding must be Mapping[str, Any]", path=path)

    out: dict[str, Any] = {}
    for key, value in binding.items():
        if not isinstance(key, str) or not key.startswith("$") or len(key) == 1:
            raise SDKStoreError(
                "binding keys must be $-prefixed variable names",
                path=path,
            )
        out[key] = value
    return out


__all__ = [
    "validate_binding",
    "validate_derivation",
]
