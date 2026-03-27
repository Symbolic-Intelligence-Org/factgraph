"""ProbLog adapter package."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from factpy_kernel.adapters.problog.accept import persist_problog_annotations
from factpy_kernel.adapters.problog.problog_engine import ProbLogEngineError, run_problog
from factpy_kernel.adapters.problog.problog_export import ProbLogExportError, export_problog
from factpy_kernel.adapters.problog.problog_import import ProbLogImportError, parse_problog_output
from factpy_kernel.adapters.souffle.where_compile import extract_where_variables
from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store import builders as store_builders
from factpy_kernel.core.store.runtime import register_engine_evaluator


def evaluate_problog(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: list[Any],
    where: list[Any],
    head: dict[str, Any] | None = None,
    body_confidences: list[float] | None = None,
) -> list[CandidateSet]:
    where_variables = extract_where_variables(where)

    if isinstance(head, dict) and head.get("callee_kind") == "entity_type":
        entity_spec = store_builders.entity_spec_from_head(
            store,
            entity_type=target_pred_id,
            head=head,
        )
        missing_vars = [
            value
            for value in entity_spec["head_vars"]
            if isinstance(value, str) and value.startswith("$") and value not in where_variables
        ]
        if missing_vars:
            raise WhereValidationError(f"head entity vars reference unbound where variables: {missing_vars}")
    else:
        schema_pred = store_builders.find_schema_pred(store, target_pred_id)
        if schema_pred is None:
            raise WhereValidationError(f"target predicate not found: {target_pred_id}")
        arg_specs = schema_pred.get("arg_specs")
        if not isinstance(arg_specs, list) or not arg_specs:
            raise WhereValidationError("target predicate arg_specs must be non-empty list")
        if not isinstance(head_vars, list) or len(head_vars) != len(arg_specs):
            raise WhereValidationError("head_vars length must match target arg_specs")
        missing_vars = [
            value
            for value in head_vars
            if isinstance(value, str) and value.startswith("$") and value not in where_variables
        ]
        if missing_vars:
            raise WhereValidationError(f"head_vars reference unbound where variables: {missing_vars}")

    rule_spec = {
        "derivation_id": derivation_id,
        "version": version,
        "target_pred_id": target_pred_id,
        "head_vars": list(head_vars),
        "where": where,
        "head": head,
        "body_confidences": body_confidences,
        "query_vars": where_variables,
        "query_pred": "answer",
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        pl_path = Path(tmpdir) / "query.pl"
        export_problog(store, rule_spec, pl_path)
        raw_output = run_problog(pl_path)

    parse_spec = dict(rule_spec)
    parse_spec["store"] = store
    candidates = parse_problog_output(raw_output, parse_spec, store.ledger)
    _remember_pending_probability_annotations(store, candidates)
    return candidates


def _remember_pending_probability_annotations(
    store: Any,
    candidates: list[CandidateSet],
) -> None:
    if not isinstance(candidates, list) or not candidates:
        return
    if not hasattr(store, "_problog_pending_annotations"):
        store._problog_pending_annotations = {}
    pending_by_run = store._problog_pending_annotations
    if not isinstance(pending_by_run, dict):
        return

    for candidate in candidates:
        if not isinstance(candidate, CandidateSet):
            continue
        if candidate.candidate_kind != "fact":
            continue
        if candidate.confidence is None:
            continue
        run_pending = pending_by_run.setdefault(candidate.run_id, {})
        if not isinstance(run_pending, dict):
            continue
        run_pending[candidate.candidate_id] = [
            {
                "namespace": "problog",
                "category": "semantic",
                "key": "probability",
                "kind": "float",
                "value": float(candidate.confidence),
                "origin": "derived",
                "derivation": candidate.derivation_id,
            }
        ]


# Register on import for Store.evaluate(mode="problog").
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
