from __future__ import annotations

from typing import Any

from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.rules.where_eval import WhereValidationError, evaluate_where
from factpy_kernel.core.store import builders
from factpy_kernel.core.store.types import (
    BodyConfidencesIR,
    EngineEvaluatorFn,
    EvaluateMode,
    HeadSpecIR,
    HeadVarsIR,
    WhereIR,
)
from factpy_kernel.core.view.projector import project_view_facts


def evaluate_store(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: HeadVarsIR,
    where: WhereIR,
    mode: EvaluateMode = "native",
    head: HeadSpecIR | None = None,
    body_confidences: BodyConfidencesIR = None,
    engine_evaluate: EngineEvaluatorFn,
) -> list[CandidateSet]:
    if mode == "python":
        raise ValueError("mode='python' is removed; use mode='native'")
    if mode == "engine":
        raise ValueError("mode='engine' is removed; use mode='souffle'")
    if mode not in {"native", "souffle", "problog"}:
        raise ValueError("mode must be one of: native, souffle, problog")

    if isinstance(head, dict) and head.get("callee_kind") == "entity_type":
        if mode in {"souffle", "problog"}:
            engine_kwargs = {
                "mode": mode,
                "derivation_id": derivation_id,
                "version": version,
                "target_pred_id": target_pred_id,
                "head_vars": head_vars,
                "where": where,
                "head": head,
            }
            if mode == "problog":
                engine_kwargs["body_confidences"] = body_confidences
            return engine_evaluate(**engine_kwargs)
        if mode != "native":
            raise ValueError("mode must be one of: native, souffle, problog")

        entity_spec = builders.entity_spec_from_head(
            store,
            entity_type=target_pred_id,
            head=head,
        )
        bindings = _evaluate_where_over_view(store, where)
        if not bindings:
            return []
        return builders.entity_candidates_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            entity_spec=entity_spec,
            bindings=bindings,
        )

    if mode in {"souffle", "problog"}:
        engine_kwargs = {
            "mode": mode,
            "derivation_id": derivation_id,
            "version": version,
            "target_pred_id": target_pred_id,
            "head_vars": head_vars,
            "where": where,
            "head": head,
        }
        if mode == "problog":
            engine_kwargs["body_confidences"] = body_confidences
        return engine_evaluate(**engine_kwargs)
    if mode != "native":
        raise ValueError("mode must be one of: native, souffle, problog")

    schema_pred = builders.find_schema_pred(store, target_pred_id)
    if schema_pred is None:
        raise WhereValidationError(f"target predicate not found: {target_pred_id}")

    arg_specs = schema_pred.get("arg_specs")
    if not isinstance(arg_specs, list) or not arg_specs:
        raise WhereValidationError("target predicate arg_specs must be non-empty list")

    if not isinstance(head_vars, list) or len(head_vars) != len(arg_specs):
        raise WhereValidationError("head_vars length must match target arg_specs")

    bindings = _evaluate_where_over_view(store, where)
    if not bindings:
        return []

    return builders.candidates_from_bindings(
        store,
        derivation_id=derivation_id,
        version=version,
        target_pred_id=target_pred_id,
        arg_specs=arg_specs,
        head_vars=head_vars,
        schema_pred=schema_pred,
        bindings=bindings,
    )


def _evaluate_where_over_view(
    store: Any,
    where: WhereIR,
) -> list[dict[str, Any]]:
    view_facts = project_view_facts(
        store.ledger,
        store.schema_ir,
    )
    return evaluate_where(view_facts, where)
