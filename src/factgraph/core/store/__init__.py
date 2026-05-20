"""Store facade and append-only ledger primitives."""

from typing import Any

__all__ = [
    "AssertionInput",
    "AssertionRecord",
    "CommitResult",
    "Database",
    "DatabaseError",
    "DatabaseValue",
    "DuplicateAssertionError",
    "Ledger",
    "MetaEntry",
    "Store",
    "register_engine_evaluator",
]


def __getattr__(name: str) -> Any:
    if name == "Ledger":
        from factgraph.core.store.ledger import Ledger

        return Ledger
    if name in {
        "AssertionInput",
        "AssertionRecord",
        "CommitResult",
        "Database",
        "DatabaseError",
        "DatabaseValue",
        "DuplicateAssertionError",
        "MetaEntry",
    }:
        from factgraph.core.store import database

        return getattr(database, name)
    if name in {"Store", "register_engine_evaluator"}:
        from factgraph.core.store.runtime import Store, register_engine_evaluator

        return {"Store": Store, "register_engine_evaluator": register_engine_evaluator}[name]
    raise AttributeError(name)
