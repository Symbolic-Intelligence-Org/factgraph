from __future__ import annotations

from typing import Any

from factpy_kernel.core.rules.ruleref_types import NativeRuleRefResolution
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store._support import (
    NonFactStep,
    PredWitness,
    RuleRefEdge,
    SupportArtifact,
    make_non_fact_step_key,
    make_pred_atom_key,
    normalize_asrt_ids,
    normalize_binding_items,
    normalize_detail_items,
)


def build_support_artifact_for_binding(
    *,
    where: list[Any],
    binding: dict[str, Any],
    witness_facts: dict[str, list[Any]],
    root_result_kind: str,
    rule_ref_edges: tuple[RuleRefEdge, ...] = (),
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
        rule_refs=tuple(sorted({edge.rule_ref_id for edge in rule_ref_edges})),
        rule_ref_edges=tuple(
            sorted(
                rule_ref_edges,
                key=lambda edge: (
                    edge.ruleref_atom_key,
                    edge.rule_ref_id,
                    edge.rule_ref_version,
                    edge.child_support_digest or "",
                ),
            )
        ),
    )


def derive_rule_ref_edges_for_binding(
    *,
    where: list[Any],
    binding: dict[str, Any],
    rule_ref_resolutions: tuple[NativeRuleRefResolution, ...],
) -> tuple[RuleRefEdge, ...]:
    resolution_by_key = {row.ruleref_atom_key: row for row in rule_ref_resolutions}
    edges: list[RuleRefEdge] = []
    for branch_index, branch in enumerate(_normalize_where_branches(where)):
        for atom_index, atom in enumerate(branch):
            if not isinstance(atom, tuple) or not atom or atom[0] != "ruleref":
                continue
            ruleref_atom_key = make_non_fact_step_key(branch_index, atom_index, "ruleref")
            resolution = resolution_by_key.get(ruleref_atom_key)
            if resolution is None:
                raise WhereValidationError(f"missing rule_ref_resolution for {ruleref_atom_key}")
            grounded = _ground_ruleref_terms(atom[3], binding)
            if grounded is None:
                continue
            matches = [row for row in resolution.row_supports if row.row_terms == grounded]
            if not matches:
                continue
            if len(matches) > 1:
                raise WhereValidationError(f"multiple row_support matches for {ruleref_atom_key}")
            row_support = matches[0]
            edges.append(
                RuleRefEdge(
                    ruleref_atom_key=ruleref_atom_key,
                    rule_ref_id=resolution.rule_ref_id,
                    rule_ref_version=resolution.rule_ref_version,
                    child_support_digest=row_support.child_support_digest,
                    unresolved_reason=row_support.unresolved_reason,
                )
            )
    return tuple(
        sorted(
            edges,
            key=lambda edge: (
                edge.ruleref_atom_key,
                edge.rule_ref_id,
                edge.rule_ref_version,
                edge.child_support_digest or "",
            ),
        )
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


def _normalize_where_branches(where: list[Any]) -> list[list[tuple[Any, ...]]]:
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


def _ground_ruleref_terms(terms: Any, binding: dict[str, Any]) -> tuple[Any, ...] | None:
    if not isinstance(terms, list):
        raise WhereValidationError("ruleref atom terms must be list")
    grounded: list[Any] = []
    for term in terms:
        if isinstance(term, str) and term.startswith("$"):
            if term not in binding:
                return None
            grounded.append(binding[term])
            continue
        grounded.append(term)
    return tuple(grounded)


def _validate_root_result_kind(value: str) -> str:
    if value not in {"fact", "entity", "row"}:
        raise WhereValidationError("root_result_kind must be 'fact', 'entity', or 'row'")
    return value


__all__ = [
    "build_support_artifact_for_binding",
    "derive_rule_ref_edges_for_binding",
]
