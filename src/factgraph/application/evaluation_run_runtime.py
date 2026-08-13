from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from factgraph.core.protocol.digests import sha256_token

from .evaluation_query_runtime import (
    CompiledEvaluationQueryV0,
    ResolvedEvaluationQueryNavigationSelectionV0,
    _assert_compiled_evaluation_query_current,
)
from .policy_runtime import CompiledPolicyV0, _assert_compiled_policy_current
from .protocol.evaluate_result import EvaluateResult, canonical_bytes_for_evaluate
from .protocol.evaluation_run import (
    EvaluationRunAnchorV0, EvaluationRunBindingV0, EvaluationRunExecutionProfileV0,
    EvaluationRunNavigationSelectionV0, EvaluationRunRowAnchorV0,
    EvaluationRunRulePinV0, EvaluationRunSelectionV0, EvaluationRunSummaryAnchorV0,
    EvaluationRunTargetV0, _plain, _token,
)


NATIVE_WHERE_SEMANTICS_VERSION = "native_where_v1"
EVALUATION_QUERY_PROJECTION_ADAPTER_VERSION = "evaluation_query_projection_v0"


def build_evaluation_run_anchor_v0(
    compiled_query: CompiledEvaluationQueryV0,
    result: EvaluateResult,
    *,
    source_target: EvaluationRunTargetV0 | None = None,
) -> EvaluationRunAnchorV0:
    """Capture an identity-only live Run anchor; this is not replay material."""
    _assert_compiled_evaluation_query_current(compiled_query)
    if not isinstance(result, EvaluateResult) or result.run_anchor is not None:
        raise ValueError("EvaluationRun anchor requires one unanchored EvaluateResult")
    policy = compiled_query.compiled_policy
    target = source_target or build_evaluation_run_target_v0(
        compiled_policy=policy,
        schema_digest=compiled_query.schema_digest,
        original_target_kind="policy",
        target_id=policy.policy_id,
        target_version=policy.policy_version,
    )
    _assert_anchor_target_matches_query(target, compiled_query)
    bindings = tuple(EvaluationRunBindingV0(
        item.address, item.value_type, item.value_digest,
    ) for item in compiled_query.bindings)
    selections = tuple(
        EvaluationRunNavigationSelectionV0(
            item.alias,
            item.navigation,
            item.value_type,
            item.field_predicate_id,
        )
        if isinstance(item, ResolvedEvaluationQueryNavigationSelectionV0)
        else EvaluationRunSelectionV0(item.alias, item.address, item.value_type)
        for item in compiled_query.selections
    )
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


def build_evaluation_run_target_v0(
    *,
    compiled_policy: CompiledPolicyV0,
    schema_digest: str,
    original_target_kind: Literal["rule", "policy"],
    target_id: str,
    target_version: str | None,
) -> EvaluationRunTargetV0:
    """Seal one source target against an exact normalized compiled Policy.

    This accepts only application runtime values. It is deliberately separate
    from the F3 compiled Query so that target origin never changes Query
    lowering or its digest.
    """

    if not isinstance(compiled_policy, CompiledPolicyV0):
        raise ValueError("compiled_policy must be trusted CompiledPolicyV0")
    _assert_compiled_policy_current(compiled_policy)
    if original_target_kind not in {"rule", "policy"}:
        raise ValueError("original_target_kind must be rule or policy")
    if not isinstance(target_id, str) or not target_id:
        raise ValueError("target_id must be non-empty string")
    if target_version is not None and (not isinstance(target_version, str) or not target_version):
        raise ValueError("target_version must be non-empty string or None")
    if original_target_kind == "policy" and (
        target_id, target_version
    ) != (compiled_policy.policy_id, compiled_policy.policy_version):
        raise ValueError("direct Policy source identity must match compiled Policy")
    if original_target_kind == "rule" and (
        compiled_policy.policy_id != f"__factgraph_rule_lift__:{target_id}"
        or compiled_policy.policy_version != target_version
    ):
        raise ValueError("Rule source identity does not match normalized Policy")
    rule_pins = tuple(EvaluationRunRulePinV0(
        pin.occurrence_alias, pin.rule_id, pin.rule_version,
        pin.rule_content_digest, pin.semantic_contract_digest,
    ) for pin in compiled_policy.rule_pins)
    normalization_kind = "rule_lift_v0" if original_target_kind == "rule" else "policy_direct_v0"
    target_values = (
        original_target_kind, normalization_kind, target_id, target_version,
        compiled_policy.policy_id, compiled_policy.policy_version,
        compiled_policy.policy_digest, compiled_policy.address_space_digest,
        schema_digest, compiled_policy.policy_structure, compiled_policy.lineage,
        rule_pins,
    )
    return EvaluationRunTargetV0(
        original_target_kind=original_target_kind,
        normalization_kind=normalization_kind,
        target_id=target_id,
        target_version=target_version,
        normalized_policy_id=compiled_policy.policy_id,
        normalized_policy_version=compiled_policy.policy_version,
        policy_digest=compiled_policy.policy_digest,
        address_space_digest=compiled_policy.address_space_digest,
        schema_digest=schema_digest,
        policy_structure=compiled_policy.policy_structure,
        policy_lineage=compiled_policy.lineage,
        rule_pins=rule_pins,
        target_digest=_token("evaluation_run_target_v0", _plain(target_values)),
    )


def _assert_anchor_target_matches_query(
    target: EvaluationRunTargetV0,
    compiled_query: CompiledEvaluationQueryV0,
) -> None:
    if not isinstance(target, EvaluationRunTargetV0):
        raise ValueError("EvaluationRun source target is invalid")
    # This is an internal runtime seam. Re-run the DTO seal before comparing
    # it with the Query so direct callers cannot attach a mutated target.
    EvaluationRunTargetV0.__post_init__(target)
    policy = compiled_query.compiled_policy
    expected_pins = tuple(EvaluationRunRulePinV0(
        pin.occurrence_alias, pin.rule_id, pin.rule_version,
        pin.rule_content_digest, pin.semantic_contract_digest,
    ) for pin in policy.rule_pins)
    if (
        target.policy_digest != policy.policy_digest
        or target.address_space_digest != policy.address_space_digest
        or target.schema_digest != compiled_query.schema_digest
        or target.normalized_policy_id != policy.policy_id
        or target.normalized_policy_version != policy.policy_version
        or target.policy_structure != policy.policy_structure
        or target.policy_lineage != policy.lineage
        or target.rule_pins != expected_pins
    ):
        raise ValueError("EvaluationRun source target does not match compiled Query")


def _certainty(value: object) -> object:
    if value is None:
        return None
    return {"lo": getattr(value, "lo"), "hi": getattr(value, "hi"), "kind": getattr(value, "kind")}


__all__ = ["build_evaluation_run_anchor_v0", "build_evaluation_run_target_v0"]
