from __future__ import annotations

"""
Compatibility shim for the legacy core.store.api module path.

Prefer importing Store and register_engine_evaluator from
``factpy_kernel.core.store.runtime`` or ``factpy_kernel.core.store``.
"""

from factpy_kernel.core.store.runtime import Store, register_engine_evaluator

__all__ = ["Store", "register_engine_evaluator"]
