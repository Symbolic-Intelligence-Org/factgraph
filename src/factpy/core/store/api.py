"""
Compatibility shim for the legacy core.store.api module path.

Prefer importing Store and register_engine_evaluator from
``factpy.core.store.runtime`` or ``factpy.core.store``.
"""

from __future__ import annotations

from factpy.core.store.runtime import Store, register_engine_evaluator

__all__ = ["Store", "register_engine_evaluator"]
