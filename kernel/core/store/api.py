"""
Compatibility shim for the legacy core.store.api module path.

Prefer importing Store and register_engine_evaluator from
``kernel.core.store.runtime`` or ``kernel.core.store``.
"""

from __future__ import annotations

from kernel.core.store.runtime import Store, register_engine_evaluator

__all__ = ["Store", "register_engine_evaluator"]
