"""ProbLog adapter package."""

from factgraph.adapters.problog.accept import persist_problog_annotations
from factgraph.adapters.problog.engine_eval import evaluate_problog
from factgraph.adapters.problog.problog_engine import ProbLogEngineError, run_problog
from factgraph.adapters.problog.problog_export import ProbLogExportError, export_problog
from factgraph.adapters.problog.problog_import import ProbLogImportError, parse_problog_output
from factgraph.adapters.problog.rule_ext import (
    ProbLogRuleExt,
    ProbLogWeightedChoiceArm,
    ProbLogWeightedChoiceBranch,
    ProbLogWeightedChoiceError,
    ProbLogWeightedChoiceExt,
)
from factgraph.core.store.runtime import register_engine_evaluator

register_engine_evaluator(evaluate_problog, "problog")

__all__ = [
    "ProbLogEngineError",
    "ProbLogExportError",
    "ProbLogImportError",
    "ProbLogRuleExt",
    "ProbLogWeightedChoiceArm",
    "ProbLogWeightedChoiceBranch",
    "ProbLogWeightedChoiceError",
    "ProbLogWeightedChoiceExt",
    "evaluate_problog",
    "export_problog",
    "parse_problog_output",
    "persist_problog_annotations",
    "run_problog",
]
