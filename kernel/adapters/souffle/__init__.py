"""Souffle adapter package."""

from kernel.adapters.souffle.engine_eval import evaluate_store_engine
from kernel.core.store.runtime import register_engine_evaluator

# Register on import for Store.evaluate(mode="souffle").
register_engine_evaluator(evaluate_store_engine, "souffle")
