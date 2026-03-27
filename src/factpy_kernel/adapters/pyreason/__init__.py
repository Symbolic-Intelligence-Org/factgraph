"""PyReason adapter package."""

from factpy_kernel.adapters.pyreason.engine_eval import pyreason_engine_eval
from factpy_kernel.core.store.runtime import register_engine_evaluator

register_engine_evaluator(pyreason_engine_eval, "pyreason")
