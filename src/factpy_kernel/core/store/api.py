from __future__ import annotations

"""
Compatibility shim for the legacy core.store.api module path.

Prefer importing Store and register_engine_evaluator from
``factpy_kernel.core.store.runtime`` or ``factpy_kernel.core.store``.
"""

from typing import Any

from factpy_kernel.core.store.runtime import Store, register_engine_evaluator

__all__ = ["Store", "register_engine_evaluator"]


def __getattr__(name: str) -> Any:
    if name == "_ENGINE_EVALUATOR":
        from factpy_kernel.core.store import runtime as _runtime

        return _runtime._ENGINE_EVALUATOR
    raise AttributeError(name)
