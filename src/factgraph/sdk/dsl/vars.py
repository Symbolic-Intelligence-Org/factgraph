from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SDKDSLError
from .expr import LogicVar


@dataclass
class _VarFactory:
    def __call__(self, *names: str) -> tuple[LogicVar, ...]:
        if not names:
            raise SDKDSLError("vars() with factory mode requires explicit names, e.g. V('p', 'c')")
        return _build_named_vars(names)

    def __iter__(self):
        raise SDKDSLError(
            "with vars() as (...) is not supported by runtime SDK v1 due Python runtime limits; "
            "use with vars('p','c') as (p,c) or with vars() as V: p,c = V('p','c')"
        )


class _VarsContext:
    def __init__(self, *names: str) -> None:
        self._names = names

    def __enter__(self) -> Any:
        if not self._names:
            return _VarFactory()
        return _build_named_vars(self._names)

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _build_named_vars(names: tuple[str, ...] | list[str]) -> tuple[LogicVar, ...]:
    out: list[LogicVar] = []
    seen: set[str] = set()
    for raw in names:
        if not isinstance(raw, str) or not raw:
            raise SDKDSLError("vars(...) names must be non-empty strings")
        if raw in seen:
            raise SDKDSLError(f"duplicate vars(...) name: {raw}")
        seen.add(raw)
        out.append(LogicVar(label=raw))
    return tuple(out)


def vars(*names: str) -> _VarsContext:
    """Create logic variables for rule, inference, and query bodies.

    Use as a context manager: `with vars("u", "tag") as (u, tag): ...`.
    Calling `vars()` with no names returns a factory inside the context, so
    `with vars() as V: u, tag = V("u", "tag")` is also supported.
    """

    return _VarsContext(*names)
