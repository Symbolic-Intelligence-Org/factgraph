"""Shared binding normalization for capability helper builders."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any

from factpy.core.store._support import BindingItems

from .errors import (
    CapabilityHelperError,
    OriginPackageError,
)


def _normalize_helper_binding(binding: Mapping[str, Any] | BindingItems) -> BindingItems:
    if isinstance(binding, Mapping):
        items: list[tuple[str, Any]] = []
        for key, value in binding.items():
            _reject_sdk_origin(key, path="binding.key")
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
            _reject_sdk_origin(key, path=f"binding[{index}][0]")
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


def _reject_sdk_origin(value: Any, *, path: str, seen: set[int] | None = None) -> None:
    module_name = getattr(value, "__module__", "") if isinstance(value, type) else type(value).__module__
    module_parts = module_name.split(".")
    if len(module_parts) >= 2 and module_parts[:2] == ["kernel", "sdk"]:
        raise OriginPackageError(f"{path} must be application canonical type, not SDK object")

    should_walk = (
        (dataclasses.is_dataclass(value) and not isinstance(value, type))
        or isinstance(value, (Mapping, Sequence))
    )
    if not should_walk or isinstance(value, (str, bytes, bytearray)):
        return

    seen = seen if seen is not None else set()
    marker = id(value)
    if marker in seen:
        raise CapabilityHelperError("binding value is recursive (self-referential structure)")
    seen.add(marker)
    try:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            for field in dataclasses.fields(value):
                _reject_sdk_origin(
                    getattr(value, field.name),
                    path=f"{path}.{field.name}",
                    seen=seen,
                )
            return

        if isinstance(value, Mapping):
            for key, item in value.items():
                _reject_sdk_origin(key, path=f"{path}.key", seen=seen)
                _reject_sdk_origin(item, path=f"{path}[{key!r}]", seen=seen)
            return

        for index, item in enumerate(value):
            _reject_sdk_origin(item, path=f"{path}[{index}]", seen=seen)
    finally:
        seen.remove(marker)


__all__ = [
    "_normalize_helper_binding",
    "_reject_sdk_origin",
]
