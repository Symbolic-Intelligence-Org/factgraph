"""Immutable product read views for sealed evaluation runs.

The protocol DTOs deliberately optimize for integrity validation and replay.
This module is the small, read-only presentation adapter above those DTOs.  It
does not evaluate, replay, resolve a source, or turn a V1 run into a V2 run.
In particular, a V1 run is labelled as such and every field that only a future
V2 carrier could have captured is explicit about being ``not_captured``.

``RowViewV2`` can mint *its own* explicit :class:`ExplainTargetV1`; there is no
"first row" convenience and no live ``close()`` compatibility shim here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, TypeAlias

from .protocol.common import ProtocolShapeError
from .protocol.evaluation_run_v1 import EvaluationRunSideV1, EvaluationRunV1, ExplainTargetV1
from .protocol.evaluation_run_v2 import EvaluationRunSideV2 as ProtocolEvaluationRunSideV2
from .protocol.evaluation_run_v2 import EvaluationRunV2, assert_evaluation_run_v2_current
from .protocol.goal_plan_v1 import GoalResultRowV1, GoalTechnicalAssessmentV1

ProductRunSourceProtocolV2: TypeAlias = Literal["evaluation_run_v1", "evaluation_run_v2"]
ProductRunSideV2: TypeAlias = Literal["baseline", "effective", "candidate_effective"]
CaptureStateV2: TypeAlias = Literal["captured", "not_captured", "not_applicable"]


class ProductViewErrorV2(ValueError):
    """A typed rejection while opening a sealed run as a product read view."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CaptureStateViewV2:
    """One explicit product-data capture boundary.

    The state is intentionally a value rather than an omitted optional field:
    consumers must distinguish a field that was not captured from one that is
    applicable and captured by a later protocol version.
    """

    state: CaptureStateV2
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.state not in {"captured", "not_captured", "not_applicable"}:
            raise ProductViewErrorV2(
                "capture state is unsupported", code="PRODUCT_VIEW_V2_CAPTURE_STATE_INVALID"
            )
        if self.reason_code is not None and (
            not isinstance(self.reason_code, str) or not self.reason_code
        ):
            raise ProductViewErrorV2(
                "capture reason code must be non-empty when supplied",
                code="PRODUCT_VIEW_V2_CAPTURE_STATE_INVALID",
            )
        if self.state == "captured" and self.reason_code is not None:
            raise ProductViewErrorV2(
                "captured state cannot carry an unavailable reason",
                code="PRODUCT_VIEW_V2_CAPTURE_STATE_INVALID",
            )


@dataclass(frozen=True)
class ResultValueViewV2:
    """One typed selected value, preserving the sealed protocol value."""

    alias: str
    tag: str
    value: str | int | bool
    value_digest: str

    def __repr__(self) -> str:
        return (
            "ResultValueViewV2("
            f"alias={self.alias!r}, tag={self.tag!r}, value=<redacted>, "
            f"value_digest={self.value_digest!r})"
        )


@dataclass(frozen=True, repr=False)
class EvaluationRunV2ExplainTarget:
    """One explicit V2 row observation selected for product Explain.

    This is intentionally distinct from :class:`ExplainTargetV1`.  A V2 run
    carries engine observations rather than V1 Explain anchors, so adapting it
    to a V1 target would make an unsupported detached-proof promise.  The
    target is bound to its exact sealed run, world side, engine frame and row
    observation identity; the V2 Explain adapter re-checks all four links.
    """

    run_digest: str
    side: ProductRunSideV2
    engine: str
    observation_digest: str
    source_protocol: Literal["evaluation_run_v2"] = field(default="evaluation_run_v2", init=False)

    def __post_init__(self) -> None:
        for name in ("run_digest", "observation_digest"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.startswith("sha256:"):
                raise ProductViewErrorV2(
                    f"{name} must name a sealed V2 digest",
                    code="PRODUCT_VIEW_V2_EXPLAIN_TARGET_INVALID",
                )
        if self.side not in {"baseline", "effective", "candidate_effective"}:
            raise ProductViewErrorV2(
                "V2 Explain target side is unsupported",
                code="PRODUCT_VIEW_V2_EXPLAIN_TARGET_INVALID",
            )
        if not isinstance(self.engine, str) or self.engine not in {
            "native",
            "souffle",
            "problog",
        }:
            raise ProductViewErrorV2(
                "V2 Explain target engine is unsupported",
                code="PRODUCT_VIEW_V2_EXPLAIN_TARGET_INVALID",
            )


@dataclass(frozen=True, repr=False)
class EvaluationRunV2RowView:
    """One exact V2 engine observation, without a fabricated truth claim."""

    run_digest: str
    side: ProductRunSideV2
    engine: str
    row_identity_digest: str
    observation_digest: str
    point_probability: str | None
    values: tuple[ResultValueViewV2, ...]

    def to_explain_target(self) -> EvaluationRunV2ExplainTarget:
        """Create the explicit Explain target for this exact observation.

        Returns:
            A run/side/engine/observation-pinned V2 Explain target.

        Notes:
            The target does not run Explain by itself and never chooses a
            different or implicit first row. Pass this row or the returned
            target to ``ProductEvaluationOutcomeV2.explain(...)``.
        """
        return EvaluationRunV2ExplainTarget(
            run_digest=self.run_digest,
            side=self.side,
            engine=self.engine,
            observation_digest=self.observation_digest,
        )

    def __repr__(self) -> str:
        return (
            "EvaluationRunV2RowView("
            f"side={self.side!r}, engine={self.engine!r}, "
            f"row_identity_digest={self.row_identity_digest!r}, "
            f"observation_digest={self.observation_digest!r}, "
            f"point_probability={self.point_probability!r}, values=<redacted>)"
        )


@dataclass(frozen=True)
class AssetDescriptorCaptureViewV2:
    """The only asset metadata carried by a sealed V2 run plan."""

    descriptor_capture: CaptureStateViewV2
    descriptor_digest: str | None
    binding_digest: str
    name: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioFactSemanticsViewV2:
    raw_kind: str
    point_probability: str
    semantics_digest: str


@dataclass(frozen=True)
class ScenarioProvenanceReferenceViewV2:
    """Safe, closed provenance reference copied from V2 world material."""

    source_ref: str
    locator: Mapping[str, object]
    origin_role: str
    content_digest: str | None
    admission_ref: str | None
    reference_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "locator", _freeze_public_mapping(self.locator))


@dataclass(frozen=True, repr=False)
class ScenarioFactViewV2:
    predicate_id: str
    witness_id: str
    values: tuple[tuple[str, str | int | bool], ...]
    origin: str
    fact_semantics: ScenarioFactSemanticsViewV2 | None
    provenance: tuple[ScenarioProvenanceReferenceViewV2, ...]
    note: str | None
    labels: tuple[str, ...]
    premise_ids: tuple[str, ...]
    scenario_operation_digests: tuple[str, ...]
    semantic_fact_digest: str
    evidence_fact_digest: str


@dataclass(frozen=True)
class ScenarioOperationMetadataViewV2:
    premise_id: str
    source_operation_digest: str
    member_value_digest: str | None
    fact_semantics: ScenarioFactSemanticsViewV2 | None
    provenance: tuple[ScenarioProvenanceReferenceViewV2, ...]
    note: str | None
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ScenarioOperationEvidenceViewV2:
    kind: str
    resolved_operation_digest: str
    metadata_bindings: tuple[ScenarioOperationMetadataViewV2, ...]
    masked_witness_ids: tuple[str, ...]
    synthetic_witness_ids: tuple[str, ...]
    operation_evidence_digest: str


@dataclass(frozen=True, repr=False)
class ScenarioWorldCaptureViewV2:
    """A fully captured V2 world, with semantic and provenance lanes apart."""

    side: ProductRunSideV2
    world_capture_digest: str
    semantic_world_digest: str
    resolution_evidence_digest: str
    world_digest: str
    schema_digest: str
    base_view_digest: str
    admissibility_digest: str
    facts: tuple[ScenarioFactViewV2, ...]
    operation_evidence: tuple[ScenarioOperationEvidenceViewV2, ...]


@dataclass(frozen=True)
class ScenarioCaptureViewV2:
    world_capture: CaptureStateViewV2
    provenance_capture: CaptureStateViewV2
    world: ScenarioWorldCaptureViewV2


@dataclass(frozen=True)
class ExecutionAttachmentViewV2:
    kind: str
    semantics_kind: str
    semantics_digest: str
    binding_digest: str
    attachment_digest: str
    rule_id: str | None
    rule_version: str | None
    rule_digest: str | None
    occurrence_alias: str | None
    structural_node_id: str | None


@dataclass(frozen=True)
class ExecutionProfileViewV2:
    kind: str
    name: str | None
    profile_digest: str
    compiler_digest: str
    semantic_model: str
    semantics_digest: str
    probability_materialization_model: str | None
    engine_pins: tuple[tuple[str, str, str], ...]
    resource_policy: tuple[int, int | None]
    capture_policy: tuple[str, int]
    attachments: tuple[ExecutionAttachmentViewV2, ...]


@dataclass(frozen=True)
class ChoiceSelectionKeyViewV2:
    """One captured, direct semantic address used to key a choice world."""

    occurrence_alias: str
    port_name: str


@dataclass(frozen=True)
class ChoiceArmViewV2:
    """One captured categorical arm; this does not claim it was selected."""

    arm_id: str
    probability: str
    condition_node_id: str


@dataclass(frozen=True)
class ChoiceTopologyViewV2:
    """The sealed authored shape of one V2-only exclusive choice.

    The topology comes from the run's validated replay-program capture, never
    from a live product Policy or from an engine proof.  In particular, arms
    are business structure and weights, not an inferred selection trace.
    """

    choice_id: str
    node_id: str
    topology_digest: str
    skeleton_node_id: str
    selection_key: tuple[ChoiceSelectionKeyViewV2, ...]
    arms: tuple[ChoiceArmViewV2, ...]


@dataclass(frozen=True)
class ChoiceCaptureViewV2:
    """V2 choice activation plus, when captured, its sealed authored shape."""

    attachment_capture: CaptureStateViewV2
    authored_topology: CaptureStateViewV2
    structural_node_ids: tuple[str, ...] = ()
    topology: ChoiceTopologyViewV2 | None = None


@dataclass(frozen=True)
class ProbabilityMaterializationEntryViewV2:
    """One declared Scenario probability and its actual ProbLog projection.

    ``declared_point_probability`` remains the V2 semantic input.  The
    float64 fields record the deliberately explicit legacy-engine boundary;
    consumers must not infer that the engine's row probability is an exact
    Decimal evaluation of the declared value.
    """

    fact_evidence_digest: str
    declared_point_probability: str
    float64_hex: str
    float64_text: str
    problog_text: str | None
    action: str
    entry_digest: str


@dataclass(frozen=True)
class ProbabilityMaterializationViewV2:
    """The sealed probability projection applied to one successful frame."""

    model: str
    materialization_digest: str
    entries: tuple[ProbabilityMaterializationEntryViewV2, ...]


@dataclass(frozen=True)
class FunctionPortViewV2:
    name: str
    tag: str
    mode: str
    predicate_id: str


@dataclass(frozen=True)
class FunctionInputBindingViewV2:
    port_name: str
    source_occurrence_alias: str
    source_port_name: str


@dataclass(frozen=True, repr=False)
class FunctionCallViewV2:
    call_digest: str
    call_key: str
    inputs: tuple[ResultValueViewV2, ...]
    output: ResultValueViewV2

    def __repr__(self) -> str:
        return (
            "FunctionCallViewV2("
            f"call_digest={self.call_digest!r}, call_key=<opaque>, "
            f"input_count={len(self.inputs)}, output=<redacted>)"
        )


@dataclass(frozen=True)
class FunctionAssetViewV2:
    descriptor_capture: CaptureStateViewV2
    descriptor_digest: str
    binding_digest: str
    name: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, repr=False)
class FunctionOccurrenceViewV2:
    occurrence_alias: str
    function_id: str
    function_version: str | None
    function_digest: str
    signature_digest: str
    implementation_digest: str
    relation_predicate_id: str
    topology_digest: str
    ports: tuple[FunctionPortViewV2, ...]
    input_bindings: tuple[FunctionInputBindingViewV2, ...]
    calls: tuple[FunctionCallViewV2, ...]
    asset: FunctionAssetViewV2
    lifecycle: Literal["run_local_materialization"] = "run_local_materialization"
    callable_capture: Literal["not_captured"] = "not_captured"

    def __repr__(self) -> str:
        return (
            "FunctionOccurrenceViewV2("
            f"occurrence_alias={self.occurrence_alias!r}, function_id={self.function_id!r}, "
            f"function_digest={self.function_digest!r}, call_count={len(self.calls)}, "
            "callable_capture='not_captured')"
        )


@dataclass(frozen=True)
class FunctionCaptureViewV2:
    definition_capture: CaptureStateViewV2
    materialization_capture: CaptureStateViewV2
    occurrences: tuple[FunctionOccurrenceViewV2, ...] = ()


@dataclass(frozen=True, repr=False)
class EvaluationRunV2ResultView:
    """Read-only presentation of one sealed V2 world side.

    V2 intentionally exposes per-engine observations instead of the V1
    ``GoalResultV1`` result-mode/completeness/summary model.  In particular,
    a point probability is an observation, not a Boolean conclusion or an
    absence proof.
    """

    source_protocol: Literal["evaluation_run_v2"]
    run_digest: str
    side: ProductRunSideV2
    plan_digest: str
    query_digest: str
    target: TargetViewV2
    engine: str
    engine_status: str
    diagnostic_code: str
    rows: tuple[EvaluationRunV2RowView, ...]
    profile: ExecutionProfileViewV2
    probability_materialization: ProbabilityMaterializationViewV2 | None
    asset: AssetDescriptorCaptureViewV2
    scenario: ScenarioCaptureViewV2
    choice: ChoiceCaptureViewV2
    functions: FunctionCaptureViewV2
    expectation_support: str
    summary_capture: CaptureStateViewV2 = field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_GOAL_RESULT_SUMMARY_NOT_DEFINED"
        )
    )

    def row(self, observation_digest: str) -> EvaluationRunV2RowView:
        for row in self.rows:
            if row.observation_digest == observation_digest:
                return row
        raise ProductViewErrorV2(
            "V2 row observation does not belong to this result view",
            code="PRODUCT_VIEW_V2_ROW_TARGET_INVALID",
        )

    def __repr__(self) -> str:
        return (
            "EvaluationRunV2ResultView("
            f"run_digest={self.run_digest!r}, side={self.side!r}, engine={self.engine!r}, "
            f"engine_status={self.engine_status!r}, row_count={len(self.rows)})"
        )


@dataclass(frozen=True, repr=False)
class TargetViewV2:
    """The exact logical target selected by one sealed side."""

    kind: str
    target_id: str
    target_version: str | None
    target_digest: str

    def __repr__(self) -> str:
        return (
            "TargetViewV2("
            f"kind={self.kind!r}, target_id={self.target_id!r}, "
            f"target_version={self.target_version!r}, target_digest={self.target_digest!r})"
        )


@dataclass(frozen=True, repr=False)
class RowViewV2:
    """One exact selected row and its plan-bound Explain anchor.

    ``to_explain_target`` is deliberately the only Explain affordance on a
    row.  It returns a detached explicit target and cannot act like legacy
    ``EvaluateRow.close()`` or silently choose an unrequested row.
    """

    side: ProductRunSideV2
    semantic_row_digest: str
    anchor_digest: str
    values: tuple[ResultValueViewV2, ...]

    def to_explain_target(self) -> ExplainTargetV1:
        """Create a V1 row Explain target from this exact row anchor.

        Returns:
            A side- and row-anchor-bound ``ExplainTargetV1``.

        Notes:
            This compatibility view never chooses another row and does not
            behave like legacy ``EvaluateRow.close()``.
        """
        return ExplainTargetV1(self.side, "row", self.anchor_digest)

    def __repr__(self) -> str:
        return (
            "RowViewV2("
            f"side={self.side!r}, semantic_row_digest={self.semantic_row_digest!r}, "
            f"anchor_digest={self.anchor_digest!r}, values=<redacted>)"
        )


@dataclass(frozen=True, repr=False)
class SummaryViewV2:
    """An exact result-summary target without a fabricated proof claim."""

    side: ProductRunSideV2
    anchor_digest: str
    result_mode: str
    completeness: str
    row_count: int
    exists_value: str | None
    count_value: int | None
    negative_proof: Literal["not_claimed"] = "not_claimed"

    def to_explain_target(self) -> ExplainTargetV1:
        """Create a V1 summary Explain target without a negative-proof claim.

        Returns:
            A side- and summary-anchor-bound ``ExplainTargetV1``.

        Notes:
            A zero-row summary remains descriptive and never fabricates a
            failed EvidenceGraph or logical falsehood proof.
        """
        return ExplainTargetV1(self.side, "summary", self.anchor_digest)

    def __repr__(self) -> str:
        return (
            "SummaryViewV2("
            f"side={self.side!r}, anchor_digest={self.anchor_digest!r}, "
            f"result_mode={self.result_mode!r}, completeness={self.completeness!r}, "
            f"row_count={self.row_count}, negative_proof='not_claimed')"
        )


@dataclass(frozen=True)
class ExpectationViewV2:
    """One declared expectation's result-local technical outcome."""

    expectation_id: str
    expectation_digest: str
    kind: str
    status: str
    matched_semantic_row_digests: tuple[str, ...]
    diagnostic_code: str


@dataclass(frozen=True)
class ExecutionViewV2:
    """Presentation-safe execution information already sealed by V1."""

    profile_kind: str
    profile_digest: str
    compiler_digest: str
    config_digest: str | None
    engine_frames: tuple[tuple[str, str, str], ...]
    assessment: GoalTechnicalAssessmentV1 = field(repr=False, compare=False)
    semantic_model: CaptureStateViewV2 = field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_SEMANTIC_MODEL_NOT_CAPTURED_BY_V1"
        )
    )
    profile_attachments: CaptureStateViewV2 = field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_PROFILE_ATTACHMENTS_NOT_CAPTURED_BY_V1"
        )
    )

    def __repr__(self) -> str:
        return (
            "ExecutionViewV2("
            f"profile_kind={self.profile_kind!r}, profile_digest={self.profile_digest!r}, "
            f"engine_frames={self.engine_frames!r}, semantic_model={self.semantic_model.state!r}, "
            f"profile_attachments={self.profile_attachments.state!r})"
        )


@dataclass(frozen=True, repr=False)
class ResultViewV2:
    """Product-facing, immutable view of exactly one V1 run side.

    The V1 source protocol remains visible to callers.  The fields under
    ``v2_*`` are compatibility capture markers, not guesses reconstructed from
    an older run.
    """

    source_protocol: ProductRunSourceProtocolV2
    run_digest: str
    side: ProductRunSideV2
    plan_digest: str
    query_digest: str
    target: TargetViewV2
    result_mode: str
    completeness: str
    rows: tuple[RowViewV2, ...]
    summary: SummaryViewV2
    expectations: tuple[ExpectationViewV2, ...]
    execution: ExecutionViewV2
    v2_asset_descriptor: CaptureStateViewV2 = field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_ASSET_DESCRIPTOR_NOT_CAPTURED_BY_V1"
        )
    )
    v2_scenario_metadata: CaptureStateViewV2 = field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_SCENARIO_METADATA_NOT_CAPTURED_BY_V1"
        )
    )
    v2_provenance: CaptureStateViewV2 = field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_PROVENANCE_NOT_CAPTURED_BY_V1"
        )
    )
    v2_probability_observation: CaptureStateViewV2 = field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_PROBABILITY_OBSERVATION_NOT_CAPTURED_BY_V1"
        )
    )
    v2_choice_topology: CaptureStateViewV2 = field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_CHOICE_TOPOLOGY_NOT_CAPTURED_BY_V1"
        )
    )
    comparison: CaptureStateViewV2 = field(
        default_factory=lambda: CaptureStateViewV2("not_applicable")
    )

    def row(self, anchor_digest: str) -> RowViewV2:
        """Return one row only when the caller names its explicit anchor."""

        for row in self.rows:
            if row.anchor_digest == anchor_digest:
                return row
        raise ProductViewErrorV2(
            "row anchor does not belong to this result view",
            code="PRODUCT_VIEW_V2_ROW_TARGET_INVALID",
        )

    def __repr__(self) -> str:
        return (
            "ResultViewV2("
            f"source_protocol={self.source_protocol!r}, run_digest={self.run_digest!r}, "
            f"side={self.side!r}, target={self.target!r}, result_mode={self.result_mode!r}, "
            f"completeness={self.completeness!r}, row_count={len(self.rows)})"
        )


def result_view_v2_from_run(
    run: EvaluationRunV1,
    *,
    side: ProductRunSideV2,
) -> ResultViewV2:
    """Open one named sealed V1 side as an immutable product read view.

    This adapter deliberately accepts only the already sealed V1 run.  It does
    not accept a Store, relation, callback, or current schema and therefore
    cannot silently re-evaluate the Query while constructing a presentation.
    """

    _validate_run_v1(run)
    selected_side = _run_side_v1(run, side)
    plan = run.candidate_plan if side == "candidate_effective" else run.plan
    if plan is None:  # defensive: _run_side_v1 already rejects this state.
        raise ProductViewErrorV2(
            "candidate side has no independent plan", code="PRODUCT_VIEW_V2_SIDE_INVALID"
        )
    result = selected_side.canonical_result
    assert result.summary_anchor is not None
    selection_order = tuple(item.alias for item in plan.selections)
    rows = tuple(
        _row_view_v2(row, side=side, selection_order=selection_order) for row in result.rows
    )
    expectations = tuple(
        ExpectationViewV2(
            expectation_id=outcome.expectation_id,
            expectation_digest=outcome.expectation_digest,
            kind=outcome.kind,
            status=outcome.status,
            matched_semantic_row_digests=outcome.matched_semantic_row_digests,
            diagnostic_code=outcome.diagnostic_code,
        )
        for outcome in result.expectation_outcomes
    )
    execution = ExecutionViewV2(
        profile_kind=run.execution_profile.kind,
        profile_digest=run.execution_profile.profile_digest,
        compiler_digest=run.execution_profile.compiler_digest,
        config_digest=run.execution_profile.config_digest,
        engine_frames=tuple(
            (frame.engine, frame.status, frame.diagnostic_code)
            for frame in selected_side.engine_results
        ),
        assessment=selected_side.assessment,
    )
    return ResultViewV2(
        source_protocol="evaluation_run_v1",
        run_digest=run.run_digest,
        side=side,
        plan_digest=plan.plan_digest,
        query_digest=plan.query_digest,
        target=TargetViewV2(
            kind=plan.target.kind,
            target_id=plan.target.target_id,
            target_version=plan.target.target_version,
            target_digest=plan.target.target_digest,
        ),
        result_mode=result.result_mode,
        completeness=result.completeness,
        rows=rows,
        summary=SummaryViewV2(
            side=side,
            anchor_digest=result.summary_anchor.summary_anchor_digest,
            result_mode=result.result_mode,
            completeness=result.completeness,
            row_count=len(rows),
            exists_value=result.exists_value,
            count_value=result.count_value,
        ),
        expectations=expectations,
        execution=execution,
        comparison=(
            CaptureStateViewV2("not_captured", "V2_COMPARISON_DATA_NOT_CAPTURED_BY_V1")
            if run.candidate_plan is not None
            else CaptureStateViewV2("not_applicable")
        ),
    )


def result_view_v2_from_evaluation_run_v2(
    run: EvaluationRunV2,
    *,
    side: ProductRunSideV2,
) -> EvaluationRunV2ResultView:
    """Open one named sealed ``EvaluationRunV2`` side as product data.

    Unlike :func:`result_view_v2_from_run`, this adapter never projects a V2
    engine observation into V1's canonical-result or Explain-anchor shapes.
    A V2 row retains its identity digest, observation digest, and exact-point
    probability (when the selected engine provides one).
    """

    _validate_run_v2(run)
    selected_side = _run_side_v2(run, side)
    plan = run.candidate_plan if side == "candidate_effective" else run.primary_plan
    if plan is None:  # defensive after _run_side_v2 validation.
        raise ProductViewErrorV2(
            "candidate V2 side has no independently sealed plan",
            code="PRODUCT_VIEW_V2_SIDE_INVALID",
        )
    succeeded = tuple(frame for frame in selected_side.engine_frames if frame.status == "succeeded")
    if run.profile.kind == "portable_deterministic_v2":
        selected_frames = tuple(frame for frame in succeeded if frame.engine == "native")
    else:
        selected_frames = succeeded
    if len(selected_frames) != 1:
        raise ProductViewErrorV2(
            "sealed V2 side does not identify one canonical successful engine frame",
            code="PRODUCT_VIEW_V2_ENGINE_FRAME_INVALID",
        )
    frame = selected_frames[0]
    rows = tuple(
        EvaluationRunV2RowView(
            run_digest=run.run_digest,
            side=side,
            engine=frame.engine,
            row_identity_digest=observation.row_identity_digest,
            observation_digest=observation.observation_digest,
            point_probability=observation.point_probability,
            values=tuple(
                ResultValueViewV2(
                    alias=alias,
                    tag=value.tag,
                    value=value.value,
                    value_digest=value.value_digest,
                )
                for alias, value in observation.values
            ),
        )
        for observation in frame.observations
    )
    return EvaluationRunV2ResultView(
        source_protocol="evaluation_run_v2",
        run_digest=run.run_digest,
        side=side,
        plan_digest=plan.plan_digest,
        query_digest=plan.query_digest,
        target=TargetViewV2(
            kind=plan.target.target_kind,
            target_id=plan.target.target_id,
            target_version=plan.target.target_version,
            target_digest=plan.target.target_digest,
        ),
        engine=frame.engine,
        engine_status=frame.status,
        diagnostic_code=frame.diagnostic_code,
        rows=rows,
        profile=_execution_profile_view_v2(run),
        probability_materialization=_probability_materialization_view_v2(
            frame.probability_materialization
        ),
        asset=_asset_descriptor_capture_view_v2(plan),
        scenario=_scenario_capture_view_v2(run, side=side),
        choice=_choice_capture_view_v2(run, side=side),
        functions=_function_capture_view_v2(run, side=side),
        expectation_support=selected_side.expectation_support,
    )


def _asset_descriptor_capture_view_v2(plan: object) -> AssetDescriptorCaptureViewV2:
    # The sealed protocol has already verified the exact descriptor shape and
    # digest.  Decode it only to make its *already captured* user-facing
    # fields available; never resolve a current asset or registry entry.
    descriptor_bytes = getattr(plan, "asset_descriptor_bytes", None)
    descriptor_digest = getattr(plan, "asset_descriptor_digest", None)
    binding_digest = getattr(plan, "asset_binding_digest", None)
    if not isinstance(binding_digest, str):  # pragma: no cover - protocol guard
        raise ProductViewErrorV2(
            "V2 plan asset binding is malformed", code="PRODUCT_VIEW_V2_RUN_INVALID"
        )
    if descriptor_bytes is None:
        return AssetDescriptorCaptureViewV2(
            descriptor_capture=CaptureStateViewV2(
                "not_captured", "V2_ASSET_DESCRIPTOR_ABSENT_FROM_RUN_PLAN"
            ),
            descriptor_digest=None,
            binding_digest=binding_digest,
        )
    try:
        descriptor = json.loads(descriptor_bytes.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise ProductViewErrorV2(
            "sealed V2 asset descriptor cannot be decoded",
            code="PRODUCT_VIEW_V2_RUN_INVALID",
        ) from exc
    if not isinstance(descriptor, dict):  # pragma: no cover - protocol guard
        raise ProductViewErrorV2(
            "sealed V2 asset descriptor is malformed", code="PRODUCT_VIEW_V2_RUN_INVALID"
        )
    tags = descriptor.get("tags")
    if not isinstance(tags, list):  # pragma: no cover - protocol guard
        raise ProductViewErrorV2(
            "sealed V2 asset descriptor tags are malformed",
            code="PRODUCT_VIEW_V2_RUN_INVALID",
        )
    return AssetDescriptorCaptureViewV2(
        descriptor_capture=CaptureStateViewV2("captured"),
        descriptor_digest=descriptor_digest,
        binding_digest=binding_digest,
        name=descriptor.get("name"),
        description=descriptor.get("description"),
        tags=tuple(tags),
    )


def _scenario_capture_view_v2(
    run: EvaluationRunV2,
    *,
    side: ProductRunSideV2,
) -> ScenarioCaptureViewV2:
    replay_world = run.replay_payload.world(side)
    world = replay_world.world
    return ScenarioCaptureViewV2(
        world_capture=CaptureStateViewV2("captured"),
        provenance_capture=CaptureStateViewV2("captured"),
        world=ScenarioWorldCaptureViewV2(
            side=side,
            world_capture_digest=replay_world.world_capture_digest,
            semantic_world_digest=world.semantic_world_digest,
            resolution_evidence_digest=world.resolution_evidence_digest,
            world_digest=world.world_digest,
            schema_digest=world.schema_digest,
            base_view_digest=world.base_view_digest,
            admissibility_digest=world.admissibility_digest,
            facts=tuple(_scenario_fact_view_v2(fact) for fact in world.facts),
            operation_evidence=tuple(
                _scenario_operation_evidence_view_v2(item) for item in world.operation_evidence
            ),
        ),
    )


def _scenario_fact_view_v2(fact: object) -> ScenarioFactViewV2:
    semantics = fact.fact_semantics
    display = fact.display
    return ScenarioFactViewV2(
        predicate_id=fact.predicate_id,
        witness_id=fact.witness_id,
        values=tuple((value.tag, value.value) for value in fact.values),
        origin=fact.origin,
        fact_semantics=_scenario_fact_semantics_view_v2(semantics),
        provenance=tuple(
            _scenario_provenance_reference_view_v2(item) for item in fact.provenance
        ),
        note=display.note,
        labels=display.labels,
        premise_ids=fact.premise_ids,
        scenario_operation_digests=fact.scenario_operation_digests,
        semantic_fact_digest=fact.semantic_fact_digest,
        evidence_fact_digest=fact.evidence_fact_digest,
    )


def _scenario_operation_evidence_view_v2(item: object) -> ScenarioOperationEvidenceViewV2:
    return ScenarioOperationEvidenceViewV2(
        kind=item.kind,
        resolved_operation_digest=item.resolved_operation_digest,
        metadata_bindings=tuple(
            _scenario_operation_metadata_view_v2(binding)
            for binding in item.metadata_bindings
        ),
        masked_witness_ids=item.masked_witness_ids,
        synthetic_witness_ids=item.synthetic_witness_ids,
        operation_evidence_digest=item.operation_evidence_digest,
    )


def _scenario_operation_metadata_view_v2(item: object) -> ScenarioOperationMetadataViewV2:
    meta = item.meta
    return ScenarioOperationMetadataViewV2(
        premise_id=item.premise_id,
        source_operation_digest=item.source_operation_digest,
        member_value_digest=item.member_value_digest,
        fact_semantics=_scenario_fact_semantics_view_v2(meta.fact_semantics),
        provenance=tuple(
            _scenario_provenance_reference_view_v2(reference) for reference in meta.provenance
        ),
        note=meta.display.note,
        labels=meta.display.labels,
    )


def _scenario_fact_semantics_view_v2(value: object) -> ScenarioFactSemanticsViewV2 | None:
    if value is None:
        return None
    return ScenarioFactSemanticsViewV2(
        raw_kind=value.raw_kind,
        point_probability=value.point_probability,
        semantics_digest=value.semantics_digest,
    )


def _scenario_provenance_reference_view_v2(
    value: object,
) -> ScenarioProvenanceReferenceViewV2:
    locator = value.locator
    return ScenarioProvenanceReferenceViewV2(
        source_ref=value.source_ref,
        locator=locator.to_wire(),
        origin_role=value.origin_role,
        content_digest=value.content_digest,
        admission_ref=value.admission_ref,
        reference_digest=value.reference_digest,
    )


def _execution_profile_view_v2(run: EvaluationRunV2) -> ExecutionProfileViewV2:
    profile = run.profile
    return ExecutionProfileViewV2(
        kind=profile.kind,
        name=profile.name,
        profile_digest=profile.profile_digest,
        compiler_digest=profile.compiler_digest,
        semantic_model=profile.semantics.model,
        semantics_digest=profile.semantics.semantics_digest,
        probability_materialization_model=getattr(profile.semantics, "materialization", None),
        engine_pins=tuple(
            (item.engine, item.engine_version, item.adapter_version) for item in profile.engines
        ),
        resource_policy=(profile.resources.max_rows, profile.resources.timeout_ms),
        capture_policy=(profile.capture.mode, profile.capture.max_capture_bytes),
        attachments=tuple(
            ExecutionAttachmentViewV2(
                kind=item.kind,
                semantics_kind=item.semantics.kind,
                semantics_digest=item.semantics.semantics_digest,
                binding_digest=item.binding_digest,
                attachment_digest=item.attachment_digest,
                rule_id=item.rule_id,
                rule_version=item.rule_version,
                rule_digest=item.rule_digest,
                occurrence_alias=item.occurrence_alias,
                structural_node_id=item.structural_node_id,
            )
            for item in profile.attachments
        ),
    )


def _probability_materialization_view_v2(
    value: object,
) -> ProbabilityMaterializationViewV2 | None:
    """Copy the already-validated engine projection into presentation data."""

    if value is None:
        return None
    return ProbabilityMaterializationViewV2(
        model=value.model,
        materialization_digest=value.materialization_digest,
        entries=tuple(
            ProbabilityMaterializationEntryViewV2(
                fact_evidence_digest=item.fact_evidence_digest,
                declared_point_probability=item.declared_point_probability,
                float64_hex=item.float64_hex,
                float64_text=item.float64_text,
                problog_text=item.problog_text,
                action=item.action,
                entry_digest=item.entry_digest,
            )
            for item in value.entries
        ),
    )


def _choice_capture_view_v2(
    run: EvaluationRunV2,
    *,
    side: ProductRunSideV2,
) -> ChoiceCaptureViewV2:
    plan = run.candidate_plan if side == "candidate_effective" else run.primary_plan
    if plan is None:  # defensive: caller already validated the named side.
        raise ProductViewErrorV2(
            "candidate V2 side has no choice-capture plan",
            code="PRODUCT_VIEW_V2_SIDE_INVALID",
        )
    structural_node_ids = tuple(
        attachment.structural_node_id
        for attachment in run.profile.attachments
        if (
            attachment.target.pin_digest == plan.target.pin_digest
            and attachment.kind == "choice"
            and attachment.structural_node_id is not None
        )
    )
    try:
        # This runner-owned helper recursively revalidates the run and fully
        # decodes the sealed replay program before returning a detached,
        # canonical topology.  Do not parse ``compiled_program_bytes`` here:
        # presentation has no authority to reconstruct a lowering relation.
        from .goal_plan_v2_runtime import choice_capture_from_evaluation_run_v2

        topology = choice_capture_from_evaluation_run_v2(
            run,
            side="candidate" if side == "candidate_effective" else "primary",
        )
    except Exception as exc:
        raise ProductViewErrorV2(
            "sealed V2 choice capture could not be validated",
            code="PRODUCT_VIEW_V2_CHOICE_CAPTURE_INVALID",
        ) from exc
    if topology is None:
        if structural_node_ids:
            raise ProductViewErrorV2(
                "V2 choice activation has no sealed authored topology",
                code="PRODUCT_VIEW_V2_CHOICE_CAPTURE_MISSING",
            )
        return ChoiceCaptureViewV2(
            attachment_capture=CaptureStateViewV2("not_applicable"),
            authored_topology=CaptureStateViewV2("not_applicable"),
        )
    if structural_node_ids != (topology.node_id,):
        raise ProductViewErrorV2(
            "V2 choice activation does not match its sealed topology",
            code="PRODUCT_VIEW_V2_CHOICE_CAPTURE_MISMATCH",
        )
    return ChoiceCaptureViewV2(
        attachment_capture=CaptureStateViewV2("captured"),
        authored_topology=CaptureStateViewV2("captured"),
        structural_node_ids=structural_node_ids,
        topology=ChoiceTopologyViewV2(
            choice_id=topology.choice_id,
            node_id=topology.node_id,
            topology_digest=topology.topology_digest,
            skeleton_node_id=topology.skeleton_node_id,
            selection_key=tuple(
                ChoiceSelectionKeyViewV2(item.occurrence_alias, item.port_name)
                for item in topology.selection_key
            ),
            arms=tuple(
                ChoiceArmViewV2(
                    arm_id=item.arm_id,
                    probability=item.probability,
                    condition_node_id=item.condition_node_id,
                )
                for item in topology.arms
            ),
        ),
    )


def _function_capture_view_v2(
    run: EvaluationRunV2,
    *,
    side: ProductRunSideV2,
) -> FunctionCaptureViewV2:
    selected_side = _run_side_v2(run, side)
    if not selected_side.function_materializations:
        return FunctionCaptureViewV2(
            definition_capture=CaptureStateViewV2("not_applicable"),
            materialization_capture=CaptureStateViewV2("not_applicable"),
        )
    try:
        from .goal_plan_v2_runtime import function_capture_from_evaluation_run_v2

        definitions = function_capture_from_evaluation_run_v2(
            run,
            side="candidate" if side == "candidate_effective" else "primary",
        )
    except Exception as exc:
        raise ProductViewErrorV2(
            "sealed V2 Function capture could not be validated",
            code="PRODUCT_VIEW_V2_FUNCTION_CAPTURE_INVALID",
        ) from exc
    materializations = {
        item.occurrence_alias: item for item in selected_side.function_materializations
    }
    if not definitions:
        raise ProductViewErrorV2(
            "Function materialization has no sealed definition",
            code="PRODUCT_VIEW_V2_FUNCTION_CAPTURE_MISMATCH",
        )
    if set(materializations) != {item.occurrence_alias for item in definitions}:
        raise ProductViewErrorV2(
            "Function definitions do not exactly cover side materializations",
            code="PRODUCT_VIEW_V2_FUNCTION_CAPTURE_MISMATCH",
        )
    occurrences: list[FunctionOccurrenceViewV2] = []
    for definition in definitions:
        materialization = materializations[definition.occurrence_alias]
        if (
            materialization.function_digest != definition.function_digest
            or materialization.signature_digest != definition.signature_digest
            or materialization.implementation_digest != definition.implementation_digest
            or materialization.relation_predicate_id != definition.relation_predicate_id
            or materialization.ports
            != tuple((name, tag, mode) for name, tag, mode, _predicate in definition.ports)
        ):
            raise ProductViewErrorV2(
                "Function materialization pins do not match its definition",
                code="PRODUCT_VIEW_V2_FUNCTION_CAPTURE_MISMATCH",
            )
        try:
            asset_meta = json.loads(definition.asset_meta_json)
        except json.JSONDecodeError as exc:  # pragma: no cover - runner validated.
            raise ProductViewErrorV2(
                "Function asset descriptor is malformed",
                code="PRODUCT_VIEW_V2_FUNCTION_CAPTURE_INVALID",
            ) from exc
        if asset_meta.get("state") == "absent":
            asset = FunctionAssetViewV2(
                descriptor_capture=CaptureStateViewV2(
                    "not_captured", "V2_FUNCTION_ASSET_DESCRIPTOR_ABSENT"
                ),
                descriptor_digest=definition.asset_descriptor_digest,
                binding_digest=definition.asset_binding_digest,
            )
        else:
            asset = FunctionAssetViewV2(
                descriptor_capture=CaptureStateViewV2("captured"),
                descriptor_digest=definition.asset_descriptor_digest,
                binding_digest=definition.asset_binding_digest,
                name=asset_meta.get("name"),
                description=asset_meta.get("description"),
                tags=tuple(asset_meta.get("tags", ())),
            )
        calls = tuple(
            FunctionCallViewV2(
                call_digest=call.call_digest,
                call_key=call.call_key,
                inputs=tuple(
                    ResultValueViewV2(
                        alias=name,
                        tag=value.tag,
                        value=value.value,
                        value_digest=value.value_digest,
                    )
                    for name, value in call.inputs
                ),
                output=ResultValueViewV2(
                    alias=call.output[0],
                    tag=call.output[1].tag,
                    value=call.output[1].value,
                    value_digest=call.output[1].value_digest,
                ),
            )
            for call in materialization.calls
        )
        occurrences.append(
            FunctionOccurrenceViewV2(
                occurrence_alias=definition.occurrence_alias,
                function_id=definition.function_id,
                function_version=definition.function_version,
                function_digest=definition.function_digest,
                signature_digest=definition.signature_digest,
                implementation_digest=definition.implementation_digest,
                relation_predicate_id=definition.relation_predicate_id,
                topology_digest=definition.topology_digest,
                ports=tuple(FunctionPortViewV2(*item) for item in definition.ports),
                input_bindings=tuple(
                    FunctionInputBindingViewV2(*item) for item in definition.input_bindings
                ),
                calls=calls,
                asset=asset,
            )
        )
    return FunctionCaptureViewV2(
        definition_capture=CaptureStateViewV2("captured"),
        materialization_capture=CaptureStateViewV2("captured"),
        occurrences=tuple(occurrences),
    )


def _row_view_v2(
    row: GoalResultRowV1,
    *,
    side: ProductRunSideV2,
    selection_order: tuple[str, ...],
) -> RowViewV2:
    if row.anchor is None:
        raise ProductViewErrorV2(
            "sealed V1 result row lacks an Explain anchor",
            code="PRODUCT_VIEW_V2_ROW_ANCHOR_MISSING",
        )
    values = dict(row.values)
    if set(values) != set(selection_order):
        raise ProductViewErrorV2(
            "result row does not match sealed selection shape",
            code="PRODUCT_VIEW_V2_ROW_SHAPE_INVALID",
        )
    return RowViewV2(
        side=side,
        semantic_row_digest=row.semantic_row_digest,
        anchor_digest=row.anchor.anchor_digest,
        values=tuple(
            ResultValueViewV2(
                alias=alias,
                tag=values[alias].tag,
                value=values[alias].value,
                value_digest=values[alias].value_digest,
            )
            for alias in selection_order
        ),
    )


def _run_side_v1(run: EvaluationRunV1, side: ProductRunSideV2) -> EvaluationRunSideV1:
    if side == "baseline":
        return run.baseline
    if side == "effective":
        return run.effective
    if side == "candidate_effective" and run.candidate_effective is not None:
        return run.candidate_effective
    raise ProductViewErrorV2("requested run side is absent", code="PRODUCT_VIEW_V2_SIDE_INVALID")


def _run_side_v2(run: EvaluationRunV2, side: ProductRunSideV2) -> ProtocolEvaluationRunSideV2:
    if side == "baseline":
        return run.baseline
    if side == "effective":
        return run.effective
    if side == "candidate_effective" and run.candidate_effective is not None:
        return run.candidate_effective
    raise ProductViewErrorV2("requested V2 run side is absent", code="PRODUCT_VIEW_V2_SIDE_INVALID")


def _validate_run_v1(run: object) -> EvaluationRunV1:
    if not isinstance(run, EvaluationRunV1):
        raise ProductViewErrorV2(
            "product V2 views require a sealed EvaluationRunV1",
            code="PRODUCT_VIEW_V2_RUN_INVALID",
        )
    try:
        EvaluationRunV1.__post_init__(run)
    except ProtocolShapeError as exc:
        raise ProductViewErrorV2(
            "sealed run failed integrity validation", code="PRODUCT_VIEW_V2_RUN_INVALID"
        ) from exc
    return run


def _validate_run_v2(run: object) -> EvaluationRunV2:
    if not isinstance(run, EvaluationRunV2):
        raise ProductViewErrorV2(
            "product V2 result views require a sealed EvaluationRunV2",
            code="PRODUCT_VIEW_V2_RUN_INVALID",
        )
    try:
        assert_evaluation_run_v2_current(run)
    except ProtocolShapeError as exc:
        raise ProductViewErrorV2(
            "sealed V2 run failed integrity validation", code="PRODUCT_VIEW_V2_RUN_INVALID"
        ) from exc
    return run


def _freeze_public_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Freeze the small closed locator wire used by provenance references."""

    if not isinstance(value, Mapping):  # pragma: no cover - protocol guard
        raise ProductViewErrorV2(
            "V2 provenance locator is malformed", code="PRODUCT_VIEW_V2_RUN_INVALID"
        )
    frozen: dict[str, object] = {}
    for key, item in value.items():
        if isinstance(item, list):
            frozen[key] = tuple(item)
        else:
            frozen[key] = item
    return MappingProxyType(frozen)


__all__ = [
    "AssetDescriptorCaptureViewV2",
    "CaptureStateV2",
    "CaptureStateViewV2",
    "ChoiceArmViewV2",
    "ChoiceCaptureViewV2",
    "ChoiceSelectionKeyViewV2",
    "ChoiceTopologyViewV2",
    "EvaluationRunV2ExplainTarget",
    "EvaluationRunV2ResultView",
    "EvaluationRunV2RowView",
    "ExecutionViewV2",
    "ExecutionAttachmentViewV2",
    "ExecutionProfileViewV2",
    "FunctionAssetViewV2",
    "FunctionCallViewV2",
    "FunctionCaptureViewV2",
    "FunctionInputBindingViewV2",
    "FunctionOccurrenceViewV2",
    "FunctionPortViewV2",
    "ExpectationViewV2",
    "ProductRunSideV2",
    "ProductRunSourceProtocolV2",
    "ProductViewErrorV2",
    "ProbabilityMaterializationEntryViewV2",
    "ProbabilityMaterializationViewV2",
    "ResultValueViewV2",
    "ResultViewV2",
    "RowViewV2",
    "SummaryViewV2",
    "TargetViewV2",
    "ScenarioCaptureViewV2",
    "ScenarioFactSemanticsViewV2",
    "ScenarioFactViewV2",
    "ScenarioOperationEvidenceViewV2",
    "ScenarioOperationMetadataViewV2",
    "ScenarioProvenanceReferenceViewV2",
    "ScenarioWorldCaptureViewV2",
    "result_view_v2_from_evaluation_run_v2",
    "result_view_v2_from_run",
]
