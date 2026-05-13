"""PyReason adapter package."""

from kernel.adapters.pyreason.engine_eval import pyreason_engine_eval
from kernel.core.store.runtime import register_engine_evaluator

register_engine_evaluator(pyreason_engine_eval, "pyreason")
