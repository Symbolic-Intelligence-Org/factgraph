"""Runtime handlers for library specs (backend-specific executables)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from symir.errors import SchemaError
from symir.rules.library import Library, LibrarySpec


Handler = Callable[[list[str]], str]


@dataclass(frozen=True)
class RuntimeKey:
    name: str
    arity: int
    kind: str
    backend: str


class LibraryRuntime:
    """Runtime registry aligned with LibrarySpec definitions."""

    def __init__(self, library: Library) -> None:
        self.library = library
        self._handlers: dict[RuntimeKey, Handler] = {}

    def register(self, name: str, arity: int, kind: str, backend: str, handler: Handler) -> None:
        spec = self.library.get(name, arity, kind)
        if spec is None:
            raise SchemaError(f"LibraryRuntime register failed: missing spec {name}/{arity} ({kind}).")
        key = RuntimeKey(name=name, arity=arity, kind=kind, backend=backend)
        if key in self._handlers:
            raise SchemaError(f"LibraryRuntime handler already registered: {name}/{arity} ({kind}) @ {backend}")
        self._handlers[key] = handler

    def get(self, name: str, arity: int, kind: str, backend: str) -> Optional[Handler]:
        return self._handlers.get(RuntimeKey(name=name, arity=arity, kind=kind, backend=backend))
