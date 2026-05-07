"""Check capability helper builders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from kernel.core.store._support import BindingItems

from kernel.application.protocol import (
    CheckRequest,
    CompiledDerivationPlan,
)

from .errors import (
    CapabilityHelperError,
    OriginPackageError,
)


def build_check_request(
    plan: CompiledDerivationPlan,
    binding: Mapping[str, Any] | BindingItems,
    *,
    engine: str = "native",
) -> CheckRequest:
    """Build a CheckRequest from application-canonical inputs."""

    _reject_sdk_origin(plan, path="plan")
    _reject_sdk_origin(binding, path="binding")
    _reject_sdk_origin(engine, path="engine")

    if not isinstance(plan, CompiledDerivationPlan):
        raise CapabilityHelperError("plan must be CompiledDerivationPlan")

    return CheckRequest(
        plan=plan,
        binding=_normalize_helper_binding(binding),
        engine=engine,  # type: ignore[arg-type]
    )


def _normalize_helper_binding(binding: Mapping[str, Any] | BindingItems) -> BindingItems:
    if isinstance(binding, Mapping):
        items: list[tuple[str, Any]] = []
        for key, value in binding.items():
            if not isinstance(key, str) or not key:
                raise CapabilityHelperError("binding keys must be non-empty str")
            items.append((key, value))
        items.sort(key=lambda item: item[0])
        return tuple(items)

    if isinstance(binding, tuple):
        normalized: list[tuple[str, Any]] = []
        previous_key: str | None = None
        seen: set[str] = set()
        for index, item in enumerate(binding):
            if not isinstance(item, tuple) or len(item) != 2:
                raise CapabilityHelperError(f"binding[{index}] must be tuple[str, Any]")
            key, value = item
            if not isinstance(key, str) or not key:
                raise CapabilityHelperError(f"binding[{index}][0] must be non-empty str")
            if key in seen:
                raise CapabilityHelperError("binding must not contain duplicate keys")
            if previous_key is not None and key < previous_key:
                raise CapabilityHelperError("BindingItems must be sorted by key")
            seen.add(key)
            previous_key = key
            normalized.append((key, value))
        return tuple(normalized)

    raise CapabilityHelperError("binding must be Mapping[str, Any] or BindingItems")


def _reject_sdk_origin(value: Any, *, path: str) -> None:
    module_parts = type(value).__module__.split(".")
    if len(module_parts) >= 2 and module_parts[:2] == ["kernel", "sdk"]:
        raise OriginPackageError(f"{path} must be application canonical type, not SDK object")

    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_sdk_origin(key, path=f"{path}.key")
            _reject_sdk_origin(item, path=f"{path}[{key!r}]")
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_sdk_origin(item, path=f"{path}[{index}]")


__all__ = [
    "build_check_request",
]
