"""ProbLog adapter package."""

from kernel.adapters.problog.accept import persist_problog_annotations
from kernel.adapters.problog.engine_eval import evaluate_problog
from kernel.adapters.problog.problog_engine import ProbLogEngineError, run_problog
from kernel.adapters.problog.problog_export import ProbLogExportError, export_problog
from kernel.adapters.problog.problog_import import ProbLogImportError, parse_problog_output
from kernel.adapters.problog.rule_ext import ProbLogRuleExt
from kernel.core.store.runtime import register_engine_evaluator

register_engine_evaluator(evaluate_problog, "problog")

__all__ = [
    "ProbLogEngineError",
    "ProbLogExportError",
    "ProbLogImportError",
    "ProbLogRuleExt",
    "evaluate_problog",
    "export_problog",
    "parse_problog_output",
    "persist_problog_annotations",
    "run_problog",
]
