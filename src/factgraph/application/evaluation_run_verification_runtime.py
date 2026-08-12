from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from factgraph.core.protocol.digests import sha256_token
from factgraph.core.rules.ruleref_substrate import evaluate_native_where
from factgraph.core.rules.where_ast import (
    AggregateAtom,
    AndExpr,
    Atom,
    BuiltinAtom,
    CmpAtom,
    InAtom,
    NotAtom,
    OrExpr,
    PredAtom,
    Term,
    WhereExpr,
    parse_where_ir_to_ast,
)
from factgraph.core.rules.where_eval import WhereValidationError, _where_ast_gate_enabled
from factgraph.core.store._support import ProjectedFact, compute_support_digest
from factgraph.core.store._support_capture import (
    build_support_artifact_for_binding,
    find_winning_case_index,
)

from .evaluation_run_bundle_runtime import (
    _assert_evaluation_run_bundle_current,
    _canonical_storage_value,
    _validate_native_where_bytes,
)
from .evaluation_run_runtime import (
    EVALUATION_QUERY_PROJECTION_ADAPTER_VERSION,
    NATIVE_WHERE_SEMANTICS_VERSION,
)
from .protocol.common import ProtocolShapeError
from .protocol.evaluate_result import (
    canonical_bytes_for_evaluate,
    claim_digest_for,
    closed_head_digest_for_parts,
)
from .protocol.evaluation_run import _token
from .protocol.evaluation_run_bundle import EvaluationRunBundleV0
from .protocol.evaluation_run_verification import EvaluationRunVerificationV0


MAX_EVALUATION_RUN_VERIFICATION_WORK = 100_000
_BOOLEAN_CERTAINTY = ("0x3ff0000000000000", "0x3ff0000000000000", "boolean")
_BOOLEAN_CERTAINTY_DIGEST = sha256_token(
    canonical_bytes_for_evaluate(
        "evaluation_run_certainty_v0",
        {"lo": 1.0, "hi": 1.0, "kind": "boolean"},
    )
)


def verify_evaluation_run_bundle(
    bundle: EvaluationRunBundleV0,
) -> EvaluationRunVerificationV0:
    """Re-execute one decoded F4B1 bundle without consulting a Store."""
    where, relation, view = _materialize_evaluation_run_bundle_input(bundle)
    expected_semantics = tuple(
        sorted(row.semantic_anchor_digest for row in bundle.run_anchor.row_anchors)
    )
    expected_support = tuple(
        sorted(
            (anchor.semantic_anchor_digest, row.proof_receipt_digest)
            for anchor, row in zip(
                bundle.run_anchor.row_anchors,
                bundle.rows,
                strict=True,
            )
        )
    )
    expected_semantic_digest = _multiset_digest("semantic", expected_semantics)
    expected_support_digest = _multiset_digest("support", expected_support)
    compatibility, compatibility_reasons = _runtime_compatibility(bundle)
    gate = "enabled" if _where_ast_gate_enabled() else "disabled"
    gate_mismatch = gate != bundle.execution_contract.where_ast_gate
    if compatibility == "declared_mismatch" or gate_mismatch:
        reasons = [*compatibility_reasons]
        if gate_mismatch:
            reasons.append("WHERE_AST_GATE_MISMATCH")
        return _record(
            bundle,
            compatibility=compatibility,
            execution_status="not_run",
            semantic_comparison="not_compared",
            support_comparison="not_compared",
            expected_semantic_digest=expected_semantic_digest,
            expected_support_digest=expected_support_digest,
            observed=None,
            estimated_work=0,
            verdict="runtime_incompatible",
            reason_codes=reasons,
        )

    relation_counts = {relation.predicate_id: len(relation.facts) for relation in bundle.relations}
    estimated_work = _estimate_verification_work(where, relation_counts)
    if estimated_work > MAX_EVALUATION_RUN_VERIFICATION_WORK:
        return _record(
            bundle,
            compatibility=compatibility,
            execution_status="not_run",
            semantic_comparison="not_compared",
            support_comparison="not_compared",
            expected_semantic_digest=expected_semantic_digest,
            expected_support_digest=expected_support_digest,
            observed=None,
            estimated_work=estimated_work,
            verdict="resource_rejected",
            reason_codes=["WORK_LIMIT_EXCEEDED"],
        )

    try:
        observed_rows = _execute_isolated(bundle, where, relation, view)
    except (
        KeyError,
        OverflowError,
        ProtocolShapeError,
        TypeError,
        ValueError,
        WhereValidationError,
    ):
        return _record(
            bundle,
            compatibility=compatibility,
            execution_status="failed",
            semantic_comparison="not_compared",
            support_comparison="not_compared",
            expected_semantic_digest=expected_semantic_digest,
            expected_support_digest=expected_support_digest,
            observed=None,
            estimated_work=estimated_work,
            verdict="execution_failed",
            reason_codes=["NATIVE_EXECUTION_FAILED"],
        )

    observed_semantics = tuple(sorted(row[0] for row in observed_rows))
    observed_support = tuple(sorted(observed_rows))
    observed_semantic_digest = _multiset_digest("semantic", observed_semantics)
    observed_support_digest = _multiset_digest("support", observed_support)
    semantic_comparison = "match" if observed_semantics == expected_semantics else "mismatch"
    support_comparison = "match" if observed_support == expected_support else "mismatch"
    if semantic_comparison == "mismatch":
        verdict = "semantic_mismatch"
        reasons = ["SEMANTIC_MULTISET_MISMATCH"]
    elif support_comparison == "mismatch":
        verdict = "support_mismatch"
        reasons = ["SUPPORT_MULTISET_MISMATCH"]
    elif compatibility == "source_unpinned":
        verdict = "matched_unpinned_runtime"
        reasons = ["SOURCE_RUNTIME_UNPINNED"]
    else:
        verdict = "matched_declared_runtime"
        reasons = []
    return _record(
        bundle,
        compatibility=compatibility,
        execution_status="completed",
        semantic_comparison=semantic_comparison,
        support_comparison=support_comparison,
        expected_semantic_digest=expected_semantic_digest,
        expected_support_digest=expected_support_digest,
        observed=(len(observed_rows), observed_semantic_digest, observed_support_digest),
        estimated_work=estimated_work,
        verdict=verdict,
        reason_codes=reasons,
    )


def _execute_isolated(
    bundle: EvaluationRunBundleV0,
    where: list[Any],
    relation: dict[str, list[ProjectedFact]],
    view: dict[str, list[tuple[Any, ...]]],
) -> tuple[tuple[str, str], ...]:
    evaluation = evaluate_native_where(
        view,
        where,
        registry=None,
        witness_facts=relation,
    )
    selected: dict[tuple[tuple[str, str, object], ...], tuple[str, str]] = {}
    head_scope_digest = closed_head_digest_for_parts(
        bundle.run_anchor.projection_head_id,
        bundle.run_anchor.projection_head_content_digest,
    )
    for binding in evaluation.bindings:
        branch = find_winning_case_index(
            where=where,
            binding=binding,
            witness_facts=relation,
            rule_ref_resolutions=(),
        )
        receipt = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=relation,
            root_result_kind="fact",
            selected_case_index=branch,
        )
        values = tuple(
            (
                selection.alias,
                selection.value_type,
                _canonical_storage_value(selection.value_type, binding[var_name]),
            )
            for selection, var_name in zip(
                bundle.run_anchor.selections,
                bundle.native_plan.head_var_names,
                strict=True,
            )
        )
        displayed = {
            alias: (
                {"kind": "entity_ref", "value": value}
                if value_type == "entity_ref"
                else {"kind": "literal", "tag": value_type, "value": value}
            )
            for alias, value_type, value in values
        }
        claim_digest = claim_digest_for(
            "projection",
            bundle.run_anchor.projection_head_id,
            displayed,
        )
        binding_digest = sha256_token(
            canonical_bytes_for_evaluate("evaluation_run_bindings_v0", displayed)
        )
        semantic_digest = _token(
            "evaluation_run_row_anchor_v0",
            (
                bundle.query_digest,
                "projection",
                claim_digest,
                binding_digest,
                head_scope_digest,
                _BOOLEAN_CERTAINTY_DIGEST,
            ),
        )
        support_digest = compute_support_digest(receipt)
        existing = selected.get(values)
        row = (semantic_digest, support_digest)
        if existing is None or support_digest < existing[1]:
            selected[values] = row
    return tuple(sorted(selected.values()))


def _runtime_compatibility(
    bundle: EvaluationRunBundleV0,
) -> tuple[str, list[str]]:
    profile = bundle.run_anchor.execution_profile
    mismatches: list[str] = []
    if profile.engine != "native" or profile.engine != bundle.execution_contract.engine:
        mismatches.append("ENGINE_PROFILE_MISMATCH")
    if profile.config_digest is not None or bundle.execution_contract.config != "none":
        mismatches.append("CONFIG_PROFILE_MISMATCH")
    if profile.engine_version is not None and (
        profile.engine_version != NATIVE_WHERE_SEMANTICS_VERSION
    ):
        mismatches.append("ENGINE_VERSION_MISMATCH")
    if profile.adapter_version is not None and (
        profile.adapter_version != EVALUATION_QUERY_PROJECTION_ADAPTER_VERSION
    ):
        mismatches.append("ADAPTER_VERSION_MISMATCH")
    if mismatches:
        return "declared_mismatch", mismatches
    if profile.engine_version is None or profile.adapter_version is None:
        return "source_unpinned", []
    return "declared_match", []


def _materialize_evaluation_run_bundle_input(
    bundle: EvaluationRunBundleV0,
) -> tuple[list[Any], dict[str, list[ProjectedFact]], dict[str, list[tuple[Any, ...]]]]:
    """Validated detached input seam shared by verification and F4B3 playback."""
    _assert_evaluation_run_bundle_current(bundle)
    where = _validate_native_where_bytes(bundle.native_plan.where_bytes)
    relation = {
        item.predicate_id: [
            ProjectedFact(asrt_id, tuple(value.value for value in values))
            for asrt_id, values in item.facts
        ]
        for item in bundle.relations
    }
    view = {pred_id: [item.fact_tuple for item in facts] for pred_id, facts in relation.items()}
    return where, relation, view


def _estimate_verification_work(
    where: list[Any],
    relation_counts: Mapping[str, int],
) -> int:
    expression = parse_where_ir_to_ast(where)
    return _estimate_expression(expression, relation_counts)


def _estimate_expression(expression: WhereExpr, counts: Mapping[str, int]) -> int:
    if isinstance(expression, AndExpr):
        return _estimate_atoms(expression.atoms, counts)
    if isinstance(expression, OrExpr):
        total = 0
        for branch in expression.branches:
            total = _saturating_add(total, _estimate_atoms(branch.atoms, counts))
        return total
    raise ProtocolShapeError("verification work estimator encountered unknown expression")


def _estimate_atoms(atoms: Sequence[Atom], counts: Mapping[str, int]) -> int:
    work = 1
    for atom in atoms:
        work = _saturating_multiply(work, _atom_factor(atom, counts))
    return work


def _atom_factor(atom: Atom, counts: Mapping[str, int]) -> int:
    if isinstance(atom, PredAtom):
        return max(1, counts.get(atom.pred_id, 0)) * _term_factors(atom.terms, counts)
    if isinstance(atom, NotAtom):
        return max(1, _estimate_expression(atom.body, counts))
    if isinstance(atom, InAtom):
        return max(1, len(atom.values))
    if isinstance(atom, CmpAtom):
        return _term_factors((atom.lhs, atom.rhs), counts)
    if isinstance(atom, BuiltinAtom):
        return _term_factors(atom.args, counts)
    raise ProtocolShapeError("verification work estimator encountered unsupported atom")


def _term_factors(terms: Sequence[Term], counts: Mapping[str, int]) -> int:
    factor = 1
    for term in terms:
        if isinstance(term, AggregateAtom):
            factor = _saturating_multiply(
                factor,
                max(1, _estimate_atoms(term.filter, counts)),
            )
    return factor


def _saturating_add(left: int, right: int) -> int:
    return min(MAX_EVALUATION_RUN_VERIFICATION_WORK + 1, left + right)


def _saturating_multiply(left: int, right: int) -> int:
    if left == 0 or right == 0:
        return 0
    if left > MAX_EVALUATION_RUN_VERIFICATION_WORK // right:
        return MAX_EVALUATION_RUN_VERIFICATION_WORK + 1
    return min(MAX_EVALUATION_RUN_VERIFICATION_WORK + 1, left * right)


def _multiset_digest(kind: str, values: tuple[Any, ...]) -> str:
    return _token(f"evaluation_run_verification_{kind}_multiset_v0", values)


def _record(
    bundle: EvaluationRunBundleV0,
    *,
    compatibility: str,
    execution_status: str,
    semantic_comparison: str,
    support_comparison: str,
    expected_semantic_digest: str,
    expected_support_digest: str,
    observed: tuple[int, str, str] | None,
    estimated_work: int,
    verdict: str,
    reason_codes: Sequence[str],
) -> EvaluationRunVerificationV0:
    values = (
        bundle.bundle_digest,
        bundle.run_anchor.anchor_digest,
        "unverified",
        "isolated_native_semantic_and_support_v0",
        "native",
        NATIVE_WHERE_SEMANTICS_VERSION,
        EVALUATION_QUERY_PROJECTION_ADAPTER_VERSION,
        compatibility,
        execution_status,
        semantic_comparison,
        support_comparison,
        len(bundle.rows),
        None if observed is None else observed[0],
        expected_semantic_digest,
        None if observed is None else observed[1],
        expected_support_digest,
        None if observed is None else observed[2],
        estimated_work,
        MAX_EVALUATION_RUN_VERIFICATION_WORK,
        verdict,
        tuple(sorted(set(reason_codes))),
        "verification_record_not_source_run",
    )
    # The DTO validates the dynamically selected Literal states as one sealed tuple.
    return EvaluationRunVerificationV0(
        *values,  # type: ignore[arg-type]
        _token("evaluation_run_verification_v0", values),
    )


__all__ = ["verify_evaluation_run_bundle"]
