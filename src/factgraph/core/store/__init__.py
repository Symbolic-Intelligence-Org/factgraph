"""Store facade and append-only ledger primitives."""

from typing import Any

__all__ = [
    "AssertionInput",
    "AssertionRecord",
    "CommitResult",
    "Database",
    "DatabaseError",
    "DatabaseValue",
    "DatabaseWorkspacePaths",
    "DuplicateAssertionError",
    "Ledger",
    "MetaEntry",
    "Store",
    "register_engine_evaluator",
    "resolve_database_workspace_paths",
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
        "DatabaseWorkspacePaths",
        "DuplicateAssertionError",
        "MetaEntry",
        "resolve_database_workspace_paths",
    }:
        from factgraph.core.store import database

        return getattr(database, name)
    if name in {"Store", "register_engine_evaluator"}:
        from factgraph.core.store.runtime import Store, register_engine_evaluator

        return {"Store": Store, "register_engine_evaluator": register_engine_evaluator}[name]
    raise AttributeError(name)
