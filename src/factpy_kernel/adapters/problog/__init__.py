"""ProbLog adapter package."""

from factpy_kernel.adapters.problog.accept import persist_problog_annotations
from factpy_kernel.adapters.problog.engine_eval import evaluate_problog
from factpy_kernel.adapters.problog.problog_engine import ProbLogEngineError, run_problog
from factpy_kernel.adapters.problog.problog_export import ProbLogExportError, export_problog
from factpy_kernel.adapters.problog.problog_import import ProbLogImportError, parse_problog_output
from factpy_kernel.core.store.runtime import register_engine_evaluator

register_engine_evaluator(evaluate_problog, "problog")

__all__ = [
    "ProbLogEngineError",
    "ProbLogExportError",
    "ProbLogImportError",
    "evaluate_problog",
    "export_problog",
    "parse_problog_output",
    "persist_problog_annotations",
    "run_problog",
]
