"""
Compatibility shim for the legacy core.store.api module path.

Prefer importing Store and register_engine_evaluator from
``factgraph.core.store.runtime`` or ``factgraph.core.store``.
"""

from __future__ import annotations

from factgraph.core.store.runtime import Store, register_engine_evaluator

__all__ = ["Store", "register_engine_evaluator"]
