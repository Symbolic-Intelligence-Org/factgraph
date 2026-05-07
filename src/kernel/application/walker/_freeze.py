"""Recursive freezer helpers shared by walker implementations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import WalkerSnapshotError


def freeze_value(value: Any) -> Any:
    """Recursively freeze supported containers into hashable values."""

    return _freeze_value(value, seen=set())


def _freeze_value(value: Any, *, seen: set[int]) -> Any:
    value_id = id(value)
    if isinstance(value, Mapping):
        if value_id in seen:
            raise WalkerSnapshotError("value contains a recursive mapping")
        seen.add(value_id)
        try:
            return tuple(
                sorted(
                    (
                        (_freeze_value(key, seen=seen), _freeze_value(item_value, seen=seen))
                        for key, item_value in value.items()
                    ),
                    key=lambda item: repr(item[0]),
                )
            )
        finally:
            seen.remove(value_id)
    if isinstance(value, (list, tuple)):
        if value_id in seen:
            raise WalkerSnapshotError("value contains a recursive sequence")
        seen.add(value_id)
        try:
            return tuple(_freeze_value(item, seen=seen) for item in value)
        finally:
            seen.remove(value_id)
    if isinstance(value, (set, frozenset)):
        if value_id in seen:
            raise WalkerSnapshotError("value contains a recursive set")
        seen.add(value_id)
        try:
            return tuple(sorted((_freeze_value(item, seen=seen) for item in value), key=repr))
        finally:
            seen.remove(value_id)
    try:
        hash(value)
    except TypeError as exc:
        raise WalkerSnapshotError(f"value is not recursively freezable: {value!r}") from exc
    return value


__all__ = ["freeze_value"]
