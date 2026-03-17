from __future__ import annotations

from typing import Any

from factpy_kernel.core.store._support import (
    BindingSupportCapture,
    NonFactStep,
    PredWitness,
    SupportArtifact,
    compute_support_digest,
    make_non_fact_step_key,
    make_pred_atom_key,
    normalize_asrt_ids,
    normalize_binding_items,
    normalize_detail_items,
)
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
        captures = _evaluate_where_over_view_with_support(
            store,
            where,
            root_result_kind="entity",
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

    captures = _evaluate_where_over_view_with_support(
        store,
        where,
        root_result_kind="fact",
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
) -> list[dict[str, Any]]:
    view_facts = project_view_facts(
        store.ledger,
        store.schema_ir,
    )
    return evaluate_where(view_facts, where)


def _evaluate_where_over_view_with_support(
    store: Any,
    where: WhereIR,
    *,
    root_result_kind: str,
) -> list[BindingSupportCapture]:
    bindings = _evaluate_where_over_view(store, where)
    if not bindings:
        return []

    # Native support capture currently projects the ledger twice:
    # once for the existing pure-value evaluate path, and once for witness facts.
    # This keeps evaluate_where(...) untouched in the first iteration; projection
    # dedup/merging can be optimized later once the support carrier shape is stable.
    witness_facts = project_view_facts_with_witness(
        store.ledger,
        store.schema_ir,
    )
    captures: list[BindingSupportCapture] = []
    for binding in bindings:
        artifact = _build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind=root_result_kind,
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

    # Only candidates backed by real native support should enter the backref index.
    # Compatibility rows still using support_kind="none" should not produce explain handles.
    for candidate in candidates:
        if candidate.support_kind != "native_binding_v1":
            continue
        support_digest = candidate.support_digest
        if not isinstance(support_digest, str) or not support_digest.startswith("sha256:"):
            continue
        if support_digest == f"sha256:{'0' * 64}":
            continue
        store._remember_candidate_support(candidate.candidate_id, support_digest)


def _build_support_artifact_for_binding(
    *,
    where: WhereIR,
    binding: dict[str, Any],
    witness_facts: dict[str, list[Any]],
    root_result_kind: str,
) -> SupportArtifact:
    pred_witnesses: list[PredWitness] = []
    non_fact_steps: list[NonFactStep] = []

    branches = _normalize_where_branches(where)
    for branch_index, branch in enumerate(branches):
        for atom_index, atom in enumerate(branch):
            if not isinstance(atom, tuple) or not atom:
                raise WhereValidationError("invalid atom structure")
            kind = atom[0]
            if kind == "pred":
                # For OR-of-AND, this first iteration traverses every branch and
                # may therefore emit empty witness sets for branches that did not
                # actually produce the final binding. This preserves deterministic
                # structure now; branch-winning explain narrowing can be added later.
                pred_witnesses.append(
                    _build_pred_witness(
                        branch_index=branch_index,
                        atom_index=atom_index,
                        atom=atom,
                        binding=binding,
                        witness_facts=witness_facts,
                    )
                )
                continue
            non_fact_steps.append(
                _build_non_fact_step(
                    branch_index=branch_index,
                    atom_index=atom_index,
                    atom=atom,
                    binding=binding,
                )
            )

    return SupportArtifact(
        kind="native_binding_v1",
        root_result_kind=_validate_root_result_kind(root_result_kind),
        binding_items=normalize_binding_items(binding),
        pred_witnesses=tuple(sorted(pred_witnesses, key=lambda row: row.pred_atom_key)),
        non_fact_steps=tuple(
            sorted(non_fact_steps, key=lambda row: (row.step_key, row.kind, row.status, row.details))
        ),
        rule_refs=(),
    )


def _build_pred_witness(
    *,
    branch_index: int,
    atom_index: int,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    witness_facts: dict[str, list[Any]],
) -> PredWitness:
    _, pred_id, terms = atom
    if not isinstance(pred_id, str) or not pred_id:
        raise WhereValidationError("pred atom pred_id must be non-empty string")
    if not isinstance(terms, list):
        raise WhereValidationError("pred atom terms must be list")

    grounded_terms = tuple(_resolve_binding_term(term, binding) for term in terms)
    matches: list[str] = []
    for projected in witness_facts.get(pred_id, []):
        if tuple(projected.fact_tuple) == grounded_terms:
            matches.append(projected.asrt_id)

    return PredWitness(
        pred_atom_key=make_pred_atom_key(branch_index, atom_index, pred_id),
        asrt_ids=normalize_asrt_ids(matches),
    )


def _build_non_fact_step(
    *,
    branch_index: int,
    atom_index: int,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
) -> NonFactStep:
    kind = atom[0]
    status = "satisfied"
    details = normalize_detail_items(
        {
            "atom_repr": repr(atom),
            "binding": [[key, value] for key, value in normalize_binding_items(binding)],
        }
    )

    if kind == "not":
        status = "no_match"

    return NonFactStep(
        step_key=make_non_fact_step_key(branch_index, atom_index, str(kind)),
        kind=str(kind),
        status=status,
        details=details,
    )


def _normalize_where_branches(where: WhereIR) -> list[list[tuple[Any, ...]]]:
    if not isinstance(where, list) or not where:
        raise WhereValidationError("where must be non-empty list")
    if all(isinstance(item, tuple) for item in where):
        return [list(where)]
    if all(isinstance(item, list) for item in where):
        out: list[list[tuple[Any, ...]]] = []
        for branch in where:
            if not isinstance(branch, list) or not all(isinstance(atom, tuple) for atom in branch):
                raise WhereValidationError("where OR branch must contain atom tuples")
            out.append(list(branch))
        return out
    raise WhereValidationError("where must be one-level AND or two-level OR-of-AND")


def _resolve_binding_term(term: Any, binding: dict[str, Any]) -> Any:
    if isinstance(term, str) and term.startswith("$"):
        if term not in binding:
            raise WhereValidationError(f"unbound variable in support capture: {term}")
        return binding[term]
    return term


def _validate_root_result_kind(value: str) -> str:
    if value not in {"fact", "entity"}:
        raise WhereValidationError("root_result_kind must be 'fact' or 'entity'")
    return value
