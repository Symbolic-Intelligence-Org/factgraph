"""ProbLog engine evaluator for ``Store.evaluate(mode="problog")``."""

from __future__ import annotations

import copy
from dataclasses import replace
import tempfile
from pathlib import Path
from typing import Any

from factpy_kernel.adapters.problog.problog_engine import run_problog
from factpy_kernel.adapters.problog.problog_export import export_problog
from factpy_kernel.adapters.problog.problog_import import parse_problog_output
from factpy_kernel.adapters.problog.provenance import parse_problog_trace, problog_trace_to_dict
from factpy_kernel.adapters.problog.rule_ext import resolve_problog_engine_ext
from factpy_kernel.adapters.souffle.where_compile import extract_where_variables
from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store import builders as store_builders
from factpy_kernel.core.store._support import (
    PROBLOG_PROVENANCE_KIND,
    ProvenanceEnvelope,
    compute_provenance_digest,
)
from factpy_kernel.core.store.types import EngineExtBase


def evaluate_problog(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: list[Any],
    where: list[Any],
    mode: str = "problog",
    head: dict[str, Any] | None = None,
    engine_ext: EngineExtBase | None = None,
    engine_options: dict[str, Any] | None = None,
) -> list[CandidateSet]:
    """Evaluate a derivation through the ProbLog adapter."""
    del mode
    resolved_engine_ext = resolve_problog_engine_ext(
        where=where,
        engine_ext=engine_ext,
    )

    timeout = resolve_problog_timeout(engine_options)
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
        "engine_ext": resolved_engine_ext,
        "query_vars": where_variables,
        "query_pred": "answer",
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        pl_path = Path(tmpdir) / "query.pl"
        export_problog(store, rule_spec, pl_path)
        raw_output = run_problog(pl_path, timeout=timeout, trace=True)

    parse_spec = dict(rule_spec)
    parse_spec["store"] = store
    candidates = parse_problog_output(raw_output, parse_spec, store.ledger)
    candidates = _attach_problog_provenance(store, candidates, raw_output)
    _remember_pending_probability_annotations(store, candidates)
    return candidates


def resolve_problog_timeout(engine_options: dict[str, Any] | None) -> int:
    """Normalize shared ``engine_options`` into ProbLog CLI timeout seconds."""
    default_timeout = 30
    if engine_options is None:
        return default_timeout
    if not isinstance(engine_options, dict):
        raise ValueError(
            f"ProbLog engine_options must be dict[str, Any] or None, got {type(engine_options).__name__}"
        )

    supported_keys = {"timeout"}
    unknown_keys = sorted(str(key) for key in engine_options if key not in supported_keys)
    if unknown_keys:
        supported = ", ".join(sorted(supported_keys))
        unknown = ", ".join(unknown_keys)
        raise ValueError(f"Unsupported ProbLog engine_options: {unknown}. Supported keys: {supported}")

    timeout = engine_options.get("timeout", default_timeout)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise ValueError("ProbLog engine_options.timeout must be a positive int")
    return timeout


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


def _attach_problog_provenance(
    store: Any,
    candidates: list[CandidateSet],
    raw_output: str,
) -> list[CandidateSet]:
    if not candidates or not isinstance(raw_output, str):
        return candidates

    trace = parse_problog_trace(raw_output)
    if not trace.events:
        return candidates
    trace_dict = problog_trace_to_dict(trace)

    attached: list[CandidateSet] = []
    for candidate in candidates:
        envelope = ProvenanceEnvelope(
            candidate_id=candidate.candidate_id,
            engine="problog",
            payload_type="proof_trace",
            payload=copy.deepcopy(trace_dict),
        )
        support_digest = compute_provenance_digest(envelope)
        store._remember_provenance_envelope(support_digest, envelope)
        attached.append(
            replace(
                candidate,
                support_digest=support_digest,
                support_kind=PROBLOG_PROVENANCE_KIND,
            )
        )
    return attached


__all__ = [
    "evaluate_problog",
    "resolve_problog_timeout",
]
