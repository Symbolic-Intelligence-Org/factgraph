from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, TypeAlias

JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$")


class ProtocolShapeError(ValueError):
    """Raised when a protocol DTO violates shape-level invariants."""


def _require_non_empty_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProtocolShapeError(f"{field_name} must be non-empty string")
    return value


def _require_optional_non_empty_str(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_str(value, field_name=field_name)


def _require_bool(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ProtocolShapeError(f"{field_name} must be bool")
    return value


def _require_literal(value: Any, *, field_name: str, allowed: tuple[str, ...]) -> str:
    text = _require_non_empty_str(value, field_name=field_name)
    if text not in allowed:
        raise ProtocolShapeError(f"{field_name} must be one of {allowed}")
    return text


def _validate_json_value(value: Any, *, field_name: str) -> None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, list):
        for idx, item in enumerate(value):
            _validate_json_value(item, field_name=f"{field_name}[{idx}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _require_non_empty_str(key, field_name=f"{field_name}.<key>")
            _validate_json_value(item, field_name=f"{field_name}[{key!r}]")
        return
    raise ProtocolShapeError(f"{field_name} must be JSONValue")


def _validate_json_mapping(mapping: Any, *, field_name: str) -> dict[str, JSONValue]:
    if not isinstance(mapping, dict):
        raise ProtocolShapeError(f"{field_name} must be dict[str, JSONValue]")
    for key, value in mapping.items():
        _require_non_empty_str(key, field_name=f"{field_name}.<key>")
        _validate_json_value(value, field_name=f"{field_name}[{key!r}]")
    return dict(mapping)


def _validate_path(path: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(path, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[str, ...]")
    for idx, segment in enumerate(path):
        _require_non_empty_str(segment, field_name=f"{field_name}[{idx}]")
    return path


def _validate_tuple_items(value: Any, *, field_name: str, item_type: type[Any]) -> tuple[Any, ...]:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[{item_type.__name__}, ...]")
    for idx, item in enumerate(value):
        if not isinstance(item, item_type):
            raise ProtocolShapeError(f"{field_name}[{idx}] must be {item_type.__name__}")
    return value


@dataclass(frozen=True)
class ErrorDTO:
    code: str
    message: str
    path: tuple[str, ...] = ()
    details: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = _require_non_empty_str(self.code, field_name="code")
        if _CODE_RE.fullmatch(code) is None:
            raise ProtocolShapeError("code must be SCREAMING_SNAKE_CASE")
        _require_non_empty_str(self.message, field_name="message")
        _validate_path(self.path, field_name="path")
        object.__setattr__(self, "details", _validate_json_mapping(self.details, field_name="details"))


@dataclass(frozen=True)
class WarningDTO:
    code: str
    message: str
    path: tuple[str, ...] = ()
    details: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = _require_non_empty_str(self.code, field_name="code")
        if _CODE_RE.fullmatch(code) is None:
            raise ProtocolShapeError("code must be SCREAMING_SNAKE_CASE")
        _require_non_empty_str(self.message, field_name="message")
        _validate_path(self.path, field_name="path")
        object.__setattr__(self, "details", _validate_json_mapping(self.details, field_name="details"))


__all__ = [
    "ErrorDTO",
    "JSONValue",
    "ProtocolShapeError",
    "WarningDTO",
]

