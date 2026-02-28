"""Store facade and append-only ledger primitives."""

from typing import Any

__all__ = [
    "Ledger",
    "Store",
    "register_engine_evaluator",
]


def __getattr__(name: str) -> Any:
    if name == "Ledger":
        from factpy_kernel.core.store.ledger import Ledger

        return Ledger
    if name in {"Store", "register_engine_evaluator"}:
        from factpy_kernel.core.store.runtime import Store, register_engine_evaluator

        return {"Store": Store, "register_engine_evaluator": register_engine_evaluator}[name]
    raise AttributeError(name)
