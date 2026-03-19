from __future__ import annotations

from typing import Any

from factpy_kernel.core.rules.ruleref_substrate import evaluate_native_where
from factpy_kernel.core.store._support import (
    _DEGRADED_SUPPORT_KINDS,
    BindingSupportCapture,
    compute_support_digest,
)
from factpy_kernel.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
)
from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store import builders
from factpy_kernel.core.store.types import (
    BodyConfidencesIR,
    EngineEvaluatorFn,
    EvaluateMode,
    HeadSpecIR,
    HeadVarsIR,
    WhereIR,
)
from factpy_kernel.core.view.projector import project_view_facts, project_view_facts_with_witness


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
    registry: Any | None = None,
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
            candidates = engine_evaluate(**engine_kwargs)
            _remember_candidate_support_backrefs(store, candidates)
            return candidates
        if mode != "native":
            raise ValueError("mode must be one of: native, souffle, problog")

        entity_spec = builders.entity_spec_from_head(
            store,
            entity_type=target_pred_id,
            head=head,
        )
        captures = _evaluate_where_over_view_with_support(
            store,
            where,
            root_result_kind="entity",
            registry=registry,
        )
        if not captures:
            return []
        candidates = builders.entity_candidates_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            entity_spec=entity_spec,
            rows=captures,
        )
        _remember_candidate_support_backrefs(store, candidates)
        return candidates

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
        candidates = engine_evaluate(**engine_kwargs)
        _remember_candidate_support_backrefs(store, candidates)
        return candidates
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

    captures = _evaluate_where_over_view_with_support(
        store,
        where,
        root_result_kind="fact",
        registry=registry,
    )
    if not captures:
        return []

    candidates = builders.candidates_from_bindings(
        store,
        derivation_id=derivation_id,
        version=version,
        target_pred_id=target_pred_id,
        arg_specs=arg_specs,
        head_vars=head_vars,
        schema_pred=schema_pred,
        rows=captures,
    )
    _remember_candidate_support_backrefs(store, candidates)
    return candidates


def _evaluate_where_over_view(
    store: Any,
    where: WhereIR,
    *,
    registry: Any | None = None,
    witness_facts: dict[str, list[Any]] | None = None,
) -> Any:
    view_facts = project_view_facts(
        store.ledger,
        store.schema_ir,
    )
    return evaluate_native_where(
        view_facts,
        where,
        registry=registry,
        witness_facts=witness_facts,
        remember_support_artifact=store._remember_support_artifact if witness_facts is not None else None,
    )


def _evaluate_where_over_view_with_support(
    store: Any,
    where: WhereIR,
    *,
    root_result_kind: str,
    registry: Any | None = None,
) -> list[BindingSupportCapture]:
    witness_facts = project_view_facts_with_witness(
        store.ledger,
        store.schema_ir,
    )
    evaluation = _evaluate_where_over_view(
        store,
        where,
        registry=registry,
        witness_facts=witness_facts,
    )
    bindings = evaluation.bindings
    if not bindings:
        return []

    captures: list[BindingSupportCapture] = []
    for binding in bindings:
        rule_ref_edges = derive_rule_ref_edges_for_binding(
            where=where,
            binding=binding,
            rule_ref_resolutions=evaluation.rule_ref_resolutions,
        )
        artifact = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind=root_result_kind,
            rule_ref_edges=rule_ref_edges,
        )
        support_digest = compute_support_digest(artifact)
        store._remember_support_artifact(support_digest, artifact)
        captures.append(
            BindingSupportCapture(
                binding_items=artifact.binding_items,
                support_digest=support_digest,
                support_kind=artifact.kind,
            )
        )
    captures.sort(key=lambda row: (row.binding_items, row.support_digest, row.support_kind))
    return captures

def _remember_candidate_support_backrefs(
    store: Any,
    candidates: list[CandidateSet],
) -> None:
    if not candidates:
        return

    for candidate in candidates:
        support_kind = candidate.support_kind
        support_digest = candidate.support_digest
        if support_kind in _DEGRADED_SUPPORT_KINDS:
            store._remember_candidate_support(candidate.candidate_id, support_digest, support_kind)
            continue
        if support_kind != "native_binding_v1":
            continue
        if not isinstance(support_digest, str) or not support_digest.startswith("sha256:"):
            continue
        if support_digest == f"sha256:{'0' * 64}":
            continue
        store._remember_candidate_support(candidate.candidate_id, support_digest, support_kind)
