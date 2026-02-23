"""Souffle adapter package."""

from factpy_kernel.adapters.souffle.engine_eval import evaluate_store_engine
from factpy_kernel.core.store.api import register_engine_evaluator

# Register on import so existing Store.evaluate(mode="engine") call sites keep working.
register_engine_evaluator(evaluate_store_engine)
