from __future__ import annotations

from datetime import date, datetime

from factgraph.core.protocol.digests import sha256_token

from .evaluation_query_runtime import CompiledEvaluationQueryV0, _assert_compiled_evaluation_query_current
from .protocol.evaluate_result import EvaluateResult, canonical_bytes_for_evaluate
from .protocol.evaluation_run import (
    EvaluationRunAnchorV0, EvaluationRunBindingV0, EvaluationRunExecutionProfileV0,
    EvaluationRunRowAnchorV0, EvaluationRunRulePinV0, EvaluationRunSelectionV0,
    EvaluationRunSummaryAnchorV0, EvaluationRunTargetV0, _plain, _token,
)


def build_evaluation_run_anchor_v0(
    compiled_query: CompiledEvaluationQueryV0,
    result: EvaluateResult,
) -> EvaluationRunAnchorV0:
    """Capture an identity-only live Run anchor; this is not replay material."""
    _assert_compiled_evaluation_query_current(compiled_query)
    if not isinstance(result, EvaluateResult) or result.run_anchor is not None:
        raise ValueError("EvaluationRun anchor requires one unanchored EvaluateResult")
    policy = compiled_query.compiled_policy
    rule_pins = tuple(EvaluationRunRulePinV0(
        pin.occurrence_alias, pin.rule_id, pin.rule_version,
        pin.rule_content_digest, pin.semantic_contract_digest,
    ) for pin in policy.rule_pins)
    target_values = (
        "policy", "policy_direct_v0", policy.policy_id, policy.policy_version,
        policy.policy_id, policy.policy_version, policy.policy_digest,
        policy.address_space_digest, compiled_query.schema_digest,
        policy.policy_structure, policy.lineage, rule_pins,
    )
    target_digest = _token("evaluation_run_target_v0", _plain(target_values))
    target = EvaluationRunTargetV0(
        original_target_kind="policy", normalization_kind="policy_direct_v0",
        target_id=policy.policy_id, target_version=policy.policy_version,
        normalized_policy_id=policy.policy_id,
        normalized_policy_version=policy.policy_version,
        policy_digest=policy.policy_digest,
        address_space_digest=policy.address_space_digest,
        schema_digest=compiled_query.schema_digest,
        policy_structure=policy.policy_structure, policy_lineage=policy.lineage,
        rule_pins=rule_pins, target_digest=target_digest,
    )
    bindings = tuple(EvaluationRunBindingV0(
        item.address, item.value_type, item.value_digest,
    ) for item in compiled_query.bindings)
    selections = tuple(EvaluationRunSelectionV0(
        item.alias, item.address, item.value_type,
    ) for item in compiled_query.selections)
    profile = EvaluationRunExecutionProfileV0(
        result.engine,
        result.engine_meta["engine_version"],
        result.engine_meta["adapter_version"],
        result.fingerprint.config_digest,
        "complete" if all(result.engine_meta[key] is not None for key in ("engine_version", "adapter_version")) else "incomplete",
    )
    row_values = tuple(
        (
            ordinal,
            row.row_id,
            compiled_query.query_digest,
            row.kind,
            row.digest,
            sha256_token(canonical_bytes_for_evaluate("evaluation_run_bindings_v0", row.bindings)),
            row.closed_head_digest,
            sha256_token(canonical_bytes_for_evaluate("evaluation_run_certainty_v0", _certainty(row.certainty))),
        )
        for ordinal, row in enumerate(result.rows)
    )
    row_anchors = tuple(EvaluationRunRowAnchorV0(
        ordinal=values[0], row_id=values[1], query_digest=values[2],
        claim_kind=values[3], claim_digest=values[4], bindings_digest=values[5],
        head_scope_digest=values[6], certainty_digest=values[7],
        semantic_anchor_digest=_token("evaluation_run_row_anchor_v0", values[2:]),
    ) for values in row_values)
    summary_values = (
        compiled_query.query_digest,
        len(row_anchors),
        tuple(sorted(item.semantic_anchor_digest for item in row_anchors)),
        "not_asserted", "unknown", "unspecified",
    )
    summary = EvaluationRunSummaryAnchorV0(
        query_digest=summary_values[0], row_count=summary_values[1],
        row_anchor_digests=summary_values[2], truth_interpretation="not_asserted",
        completeness="unknown", ordering="unspecified",
        summary_anchor_digest=_token("evaluation_run_summary_anchor_v0", summary_values),
    )
    evaluated_at = result.evaluated_at
    if isinstance(evaluated_at, (datetime, date)):
        evaluated_at = evaluated_at.isoformat()
    if not isinstance(evaluated_at, str) or not evaluated_at:
        raise ValueError("EvaluateResult.evaluated_at is not anchorable")
    anchor_values = (
        target, compiled_query.query_digest, bindings, selections, profile,
        result.head.id, result.head.content_digest,
        result.fingerprint.view_snapshot_digest, result.result_id,
        result.fingerprint.result_digest, result.fingerprint.run_id, evaluated_at,
        row_anchors, summary,
        "identity_only", "digest_only_live_guard", "not_available",
        "live_recomputable_while_current",
    )
    return EvaluationRunAnchorV0(
        target=target, query_digest=compiled_query.query_digest, bindings=bindings,
        selections=selections, execution_profile=profile,
        projection_head_id=result.head.id,
        projection_head_content_digest=result.head.content_digest,
        view_snapshot_digest=result.fingerprint.view_snapshot_digest,
        result_id=result.result_id, result_digest=result.fingerprint.result_digest,
        run_id=result.fingerprint.run_id, evaluated_at=evaluated_at,
        row_anchors=row_anchors, summary=summary, capture_level="identity_only",
        view_capture="digest_only_live_guard", replay_availability="not_available",
        explain_availability="live_recomputable_while_current",
        anchor_digest=_token("evaluation_run_anchor_v0", _plain(anchor_values)),
    )


def _certainty(value: object) -> object:
    if value is None:
        return None
    return {"lo": getattr(value, "lo"), "hi": getattr(value, "hi"), "kind": getattr(value, "kind")}


__all__ = ["build_evaluation_run_anchor_v0"]
