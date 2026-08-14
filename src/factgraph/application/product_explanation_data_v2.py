"""Structured, presentation-safe Explain data above sealed evaluation runs.

The public contract in this module is data first.  ``narrate`` and text
rendering are intentionally lossy, pure views over that data; Agent and UI
code must consume :class:`EvaluationExplanationDataV2`, not parse prose.

The V1 and V2 adapters retain their distinct source protocols.  Neither
reseals, reinterprets, or silently converts the other carrier: V2 engine
observations are not V1 Explain anchors, and a V2 ProbLog observation never
becomes a fabricated native ``EvidenceGraph``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field as dc_field
import math
from types import MappingProxyType
from typing import Any, Literal, TypeAlias

from .evaluation_run_v1_runtime import (
    EvaluationRunExplanationV1,
    EvaluationRunRuntimeErrorV1,
    compare_policy_variants_v1,
    diff_scenario_run_v1,
    explain_evaluation_run_v1,
)
from .explain.evidence_tree import (
    Aggregate,
    BoundVar,
    Builtin,
    Compare,
    Const,
    EvidenceAtom,
    EvidenceGraph,
    EvidencePolicyCondition,
    EvidenceRule,
    EvidenceTimeline,
    EvidenceTree,
    Fails,
    Fact,
    Holds,
    NotReached,
    Source,
)
from .product_result_views_v2 import (
    AssetDescriptorCaptureViewV2,
    CaptureStateViewV2,
    ChoiceCaptureViewV2,
    EvaluationRunV2ExplainTarget,
    EvaluationRunV2ResultView,
    EvaluationRunV2RowView,
    ExecutionProfileViewV2,
    ExecutionViewV2,
    ProductRunSideV2,
    ProductViewErrorV2,
    ProbabilityMaterializationViewV2,
    ResultViewV2,
    RowViewV2,
    ScenarioCaptureViewV2,
    result_view_v2_from_evaluation_run_v2,
    result_view_v2_from_run,
)
from .protocol.certainty import Certainty
from .protocol.evaluation_run_v1 import EvaluationRunV1, ExplainTargetV1
from .protocol.evaluation_run_v2 import EvaluationRunV2
from .protocol.goal_plan_v1 import GoalPlanV1
from .protocol.policy import (
    PolicyCompareStructureNodeV0,
    PolicyFieldNavigation,
    PolicyLiteral,
    PolicyStructureNodeV0,
)
from .protocol.scenario_v1 import ResolvedScenarioOperationV1
from .protocol.semantic_address import SemanticPortAddress


EvidenceSupportStateV2: TypeAlias = Literal[
    "native_detached_recomputed",
    "portable_native_inner_not_parity",
    "problog_trace_captured",
    "not_captured",
    "not_available",
    "unsupported",
]
ExplanationObservationV2: TypeAlias = Literal["positive_row_observed", "result_summary_observed"]
ExplanationConclusionV2: TypeAlias = Literal["holds", "not_claimed"]

_EVIDENCE_SUPPORT_STATES = frozenset(
    {
        "native_detached_recomputed",
        "portable_native_inner_not_parity",
        "problog_trace_captured",
        "not_captured",
        "not_available",
        "unsupported",
    }
)
_SOURCE_META_ALLOWLIST = frozenset(
    {
        "actual",
        "engine",
        "origin_refs",
        "predicate",
        "premise_ids",
        "role",
        "scenario_operation_digests",
        "source_kind",
    }
)
_GRAPH_META_ALLOWLIST = frozenset(
    {
        "evidence_scope",
        "native_explain_context_digest",
        "proof_parity",
        "provider_receipt_count",
        "query_digest",
        "run_digest",
        "world_capture_digest",
    }
)
_ORIGIN_ROLES = frozenset(
    {
        "scenario_hypothesis",
        "baseline_support",
        "agent_extraction",
        "operator_input",
        "imported_record",
    }
)
_MAX_SAFE_VALUE_DEPTH = 12
_MAX_SAFE_VALUE_ITEMS = 128


@dataclass(frozen=True, repr=False)
class OpaqueProvenanceDescriptorV2:
    """A safe structural display of an *explicitly supplied* source reference.

    This is intentionally not typed as ``ProvenanceRefV1``.  The adapter uses
    structural inspection so importing this product module cannot make an
    older installation depend on a future provenance protocol.  It accepts
    only the closed wire shape used by that protocol and has no source-content
    or source-authority semantics.
    """

    source_ref: str
    locator: Mapping[str, object]
    origin_role: str
    content_digest: str | None
    admission_ref: str | None
    reference_digest: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "locator", _freeze_mapping(self.locator))

    def __repr__(self) -> str:
        return (
            "OpaqueProvenanceDescriptorV2("
            f"source_ref={self.source_ref!r}, locator={dict(self.locator)!r}, "
            f"origin_role={self.origin_role!r}, content_digest={self.content_digest!r}, "
            f"admission_ref={self.admission_ref!r}, reference_digest={self.reference_digest!r})"
        )


@dataclass(frozen=True, repr=False)
class EvidenceSourceViewV2:
    """Sanitized support source, never a generic ``Source.meta`` passthrough."""

    ref: str
    field: str | None
    value: object = dc_field(repr=False)
    metadata: Mapping[str, object] = dc_field(default_factory=dict, repr=False)
    omitted_metadata_keys: tuple[str, ...] = ()
    opaque_provenance: OpaqueProvenanceDescriptorV2 | None = None
    provenance_capture: CaptureStateViewV2 = dc_field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_PROVENANCE_NOT_CAPTURED_BY_V1"
        )
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))
        object.__setattr__(self, "omitted_metadata_keys", tuple(sorted(self.omitted_metadata_keys)))

    def __repr__(self) -> str:
        return (
            "EvidenceSourceViewV2("
            f"ref={self.ref!r}, field={self.field!r}, value=<redacted>, "
            f"metadata_keys={tuple(self.metadata)!r}, "
            f"opaque_provenance={'present' if self.opaque_provenance else 'none'})"
        )


@dataclass(frozen=True, repr=False)
class EvidenceTermViewV2:
    kind: Literal["bound", "const"]
    value: object = dc_field(repr=False)
    variable_name: str | None = None
    bound_by: str | None = None

    def __repr__(self) -> str:
        return (
            "EvidenceTermViewV2("
            f"kind={self.kind!r}, value=<redacted>, variable_name={self.variable_name!r}, "
            f"bound_by={self.bound_by!r})"
        )


@dataclass(frozen=True)
class CertaintyViewV2:
    kind: str
    lo: float
    hi: float


@dataclass(frozen=True, repr=False)
class EvidenceAtomViewV2:
    atom_id: str
    form_kind: Literal["fact", "compare", "builtin", "aggregate"]
    form: Mapping[str, object] = dc_field(repr=False)
    status: Literal["holds", "fails", "not_reached"]
    repr_text: str | None
    negated: bool
    timestep: int | None
    certainty: CertaintyViewV2 | None
    support: tuple[EvidenceSourceViewV2, ...]
    blocked_by: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "form", _freeze_mapping(self.form))

    def __repr__(self) -> str:
        return (
            "EvidenceAtomViewV2("
            f"atom_id={self.atom_id!r}, form_kind={self.form_kind!r}, status={self.status!r}, "
            f"support_count={len(self.support)})"
        )


@dataclass(frozen=True, repr=False)
class EvidenceRuleViewV2:
    occurrence_alias: str
    rule_id: str
    role: str
    status: str
    repr_text: str | None
    ports: Mapping[str, object] = dc_field(repr=False)
    atoms: tuple[EvidenceAtomViewV2, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ports", _freeze_mapping(self.ports))

    def __repr__(self) -> str:
        return (
            "EvidenceRuleViewV2("
            f"occurrence_alias={self.occurrence_alias!r}, rule_id={self.rule_id!r}, "
            f"role={self.role!r}, status={self.status!r}, atom_count={len(self.atoms)})"
        )


@dataclass(frozen=True)
class EvidenceJoinViewV2:
    join_id: str
    status: str
    left_occurrence_alias: str
    left_port_name: str
    right_occurrence_alias: str
    right_port_name: str


@dataclass(frozen=True)
class EvidencePolicyConditionViewV2:
    policy_node_id: str
    condition_id: str
    role: str
    atom: EvidenceAtomViewV2


@dataclass(frozen=True, repr=False)
class EvidenceTreeViewV2:
    tree_id: str
    status: str
    rules: tuple[EvidenceRuleViewV2, ...]
    joins: tuple[EvidenceJoinViewV2, ...]
    certainty: CertaintyViewV2 | None
    metadata: Mapping[str, object] = dc_field(repr=False)
    policy_conditions: tuple[EvidencePolicyConditionViewV2, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, repr=False)
class EvidenceTimelineViewV2:
    timeline_id: str
    status: str
    certainty: CertaintyViewV2 | None
    event_count: int
    metadata: Mapping[str, object] = dc_field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


EvidencePathViewV2: TypeAlias = EvidenceTreeViewV2 | EvidenceTimelineViewV2


@dataclass(frozen=True, repr=False)
class EvidenceGraphViewV2:
    graph_id: str
    engine: str
    layout_hint: str
    subject_binding: Mapping[str, object] = dc_field(repr=False)
    paths: tuple[EvidencePathViewV2, ...] = ()
    certainty: CertaintyViewV2 | None = None
    metadata: Mapping[str, object] = dc_field(default_factory=dict, repr=False)
    omitted_metadata_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject_binding", _freeze_mapping(self.subject_binding))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))
        object.__setattr__(self, "omitted_metadata_keys", tuple(sorted(self.omitted_metadata_keys)))

    def __repr__(self) -> str:
        return (
            "EvidenceGraphViewV2("
            f"graph_id={self.graph_id!r}, engine={self.engine!r}, layout_hint={self.layout_hint!r}, "
            f"path_count={len(self.paths)}, omitted_metadata_keys={self.omitted_metadata_keys!r})"
        )


@dataclass(frozen=True, repr=False)
class EvidenceSupportViewV2:
    """Closed evidence-support state with no fake graph for unavailable proof."""

    state: EvidenceSupportStateV2
    reason_code: str | None = None
    graph: EvidenceGraphViewV2 | None = None
    proof_parity: Literal["not_claimed"] = "not_claimed"

    def __post_init__(self) -> None:
        if self.state not in _EVIDENCE_SUPPORT_STATES:
            raise ProductViewErrorV2(
                "evidence support state is unsupported",
                code="PRODUCT_EXPLAIN_V2_EVIDENCE_STATE_INVALID",
            )
        graph_states = {
            "native_detached_recomputed",
            "portable_native_inner_not_parity",
            "problog_trace_captured",
        }
        if self.state in graph_states:
            if not isinstance(self.graph, EvidenceGraphViewV2) or self.reason_code is not None:
                raise ProductViewErrorV2(
                    "available evidence support requires exactly one sanitized graph",
                    code="PRODUCT_EXPLAIN_V2_EVIDENCE_STATE_INVALID",
                )
        elif (
            self.graph is not None or not isinstance(self.reason_code, str) or not self.reason_code
        ):
            raise ProductViewErrorV2(
                "unavailable evidence support requires a reason and no graph",
                code="PRODUCT_EXPLAIN_V2_EVIDENCE_STATE_INVALID",
            )

    def __repr__(self) -> str:
        return (
            "EvidenceSupportViewV2("
            f"state={self.state!r}, reason_code={self.reason_code!r}, "
            f"graph={'present' if self.graph else 'none'}, proof_parity='not_claimed')"
        )


@dataclass(frozen=True)
class PolicyOperandViewV2:
    kind: Literal["address", "field_navigation", "literal"]
    occurrence_alias: str | None = None
    port_name: str | None = None
    entity_type: str | None = None
    field_name: str | None = None
    scalar_domain: str | None = None
    value: object | None = dc_field(default=None, repr=False)


@dataclass(frozen=True)
class PolicyTopologyNodeViewV2:
    node_id: str
    kind: str
    child_node_ids: tuple[str, ...]
    occurrence_alias: str | None = None
    operation: str | None = None
    left: PolicyOperandViewV2 | None = None
    right: PolicyOperandViewV2 | None = None


@dataclass(frozen=True)
class PolicyProjectionNodeViewV2:
    node_id: str
    kind: str
    state: str
    branch_states: tuple[tuple[str, str], ...]


@dataclass(frozen=True, repr=False)
class PolicyPresentationViewV2:
    topology_capture: CaptureStateViewV2
    structure_digest: str | None
    root_node_id: str | None
    topology: tuple[PolicyTopologyNodeViewV2, ...] = ()
    asset_descriptor: CaptureStateViewV2 = dc_field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_ASSET_DESCRIPTOR_NOT_CAPTURED_BY_V1"
        )
    )
    choice_topology: CaptureStateViewV2 = dc_field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_CHOICE_TOPOLOGY_NOT_CAPTURED_BY_V1"
        )
    )
    projection_capture: CaptureStateViewV2 = dc_field(
        default_factory=lambda: CaptureStateViewV2("not_captured", "POLICY_PROJECTION_NOT_CAPTURED")
    )
    root_state: str | None = None
    projection_nodes: tuple[PolicyProjectionNodeViewV2, ...] = ()


@dataclass(frozen=True, repr=False)
class ScenarioOperationViewV2:
    kind: str
    operation_digest: str
    premise_ids: tuple[str, ...]
    origin_refs: tuple[str, ...]
    masked_witness_ids: tuple[str, ...]
    synthetic_witness_ids: tuple[str, ...]
    predicate_id: str | None
    entity_ref: str | None
    values: tuple[tuple[str, str | int | bool], ...] = dc_field(repr=False)


@dataclass(frozen=True, repr=False)
class ScenarioPresentationViewV2:
    request_digest: str | None
    patch_capture: CaptureStateViewV2
    patch_application: str
    operations: tuple[ScenarioOperationViewV2, ...] = ()
    v2_semantic_metadata: CaptureStateViewV2 = dc_field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_SCENARIO_SEMANTICS_NOT_CAPTURED_BY_V1"
        )
    )
    v2_provenance: CaptureStateViewV2 = dc_field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_SCENARIO_PROVENANCE_NOT_CAPTURED_BY_V1"
        )
    )


@dataclass(frozen=True)
class ComparisonPresentationViewV2:
    policy_comparison: CaptureStateViewV2
    scenario_diff: CaptureStateViewV2
    result_relation: str | None = None
    authored_structure_relation: str | None = None
    scenario_result_relation: str | None = None
    scenario_input_difference_axes: tuple[str, ...] = ()
    causal_attribution: Literal["not_claimed"] = "not_claimed"


@dataclass(frozen=True)
class ExplanationIdentityViewV2:
    source_protocol: Literal["evaluation_run_v1"]
    run_digest: str
    target_digest: str
    side: ProductRunSideV2
    result_digest: str
    world_capture_digest: str
    semantic_world_digest: str


@dataclass(frozen=True)
class QueryDescriptorViewV2:
    target_kind: str
    target_id: str
    target_version: str | None
    target_digest: str
    query_digest: str
    selections: tuple[tuple[str, str], ...]
    scenario_request_digest: str | None
    binding_capture: CaptureStateViewV2 = dc_field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_QUERY_BINDINGS_NOT_CAPTURED_BY_V1"
        )
    )


@dataclass(frozen=True)
class OutcomePresentationViewV2:
    observation: ExplanationObservationV2
    logical_conclusion: ExplanationConclusionV2
    row: RowViewV2 | None
    summary_anchor_digest: str | None
    negative_proof: Literal["not_claimed"] = "not_claimed"


@dataclass(frozen=True)
class ExplainBoundaryViewV2:
    proof_parity: Literal["not_claimed"] = "not_claimed"
    negative_proof: Literal["not_claimed"] = "not_claimed"
    source_authority: Literal["not_claimed"] = "not_claimed"
    action_authorization: Literal["not_claimed"] = "not_claimed"
    renderer_contract: Literal["structured_data_first_no_prose_parsing"] = (
        "structured_data_first_no_prose_parsing"
    )


@dataclass(frozen=True, repr=False)
class EvaluationExplanationDataV2:
    """Machine-readable product Explain contract.

    It may be rendered, diffed, and consumed by product code, but it makes no
    source-authority, policy-approval, action-authorization, or negative-proof
    claim.  ``source_protocol`` prevents an older V1 source from looking like
    a newly captured V2 run.
    """

    identity: ExplanationIdentityViewV2
    query_descriptor: QueryDescriptorViewV2
    outcome: OutcomePresentationViewV2
    execution: ExecutionViewV2 = dc_field(repr=False)
    policy: PolicyPresentationViewV2 = dc_field(repr=False)
    scenario: ScenarioPresentationViewV2 = dc_field(repr=False)
    evidence: EvidenceSupportViewV2 = dc_field(repr=False)
    comparison: ComparisonPresentationViewV2 = dc_field(repr=False)
    boundaries: ExplainBoundaryViewV2 = dc_field(default_factory=ExplainBoundaryViewV2)

    @property
    def source_protocol(self) -> Literal["evaluation_run_v1"]:
        return self.identity.source_protocol

    def narrate(self) -> tuple[str, ...]:
        return narrate_evaluation_explanation_v2(self)

    def render_text(self) -> str:
        return render_evaluation_explanation_text_v2(self)

    def __repr__(self) -> str:
        return (
            "EvaluationExplanationDataV2("
            f"source_protocol={self.identity.source_protocol!r}, run_digest={self.identity.run_digest!r}, "
            f"target_digest={self.identity.target_digest!r}, side={self.identity.side!r}, "
            f"observation={self.outcome.observation!r}, evidence={self.evidence.state!r})"
        )


@dataclass(frozen=True)
class EvaluationRunV2ExplanationIdentityViewV2:
    """Identity for one explicit V2 engine-observation Explain request."""

    source_protocol: Literal["evaluation_run_v2"]
    run_digest: str
    side: ProductRunSideV2
    engine: str
    target_observation_digest: str
    row_identity_digest: str
    plan_digest: str
    world_capture_digest: str
    semantic_world_digest: str
    resolution_evidence_digest: str


@dataclass(frozen=True)
class EvaluationRunV2QueryDescriptorViewV2:
    target_kind: str
    target_id: str
    target_version: str | None
    target_digest: str
    query_digest: str
    observed_value_aliases: tuple[str, ...]
    selection_shape: CaptureStateViewV2 = dc_field(
        default_factory=lambda: CaptureStateViewV2(
            "not_captured", "V2_PLAN_DOES_NOT_CAPTURE_QUERY_SELECTION_SHAPE"
        )
    )


@dataclass(frozen=True)
class EvaluationRunV2OutcomePresentationViewV2:
    """A V2 engine observation with no invented Boolean or proof outcome."""

    observation: Literal["engine_row_observed"]
    row: EvaluationRunV2RowView
    point_probability: str | None
    logical_conclusion: Literal["not_claimed"] = "not_claimed"
    negative_proof: Literal["not_claimed"] = "not_claimed"


@dataclass(frozen=True, repr=False)
class EvaluationRunV2ExplanationDataV2:
    """Data-first Explain view for one explicit ``EvaluationRunV2`` row.

    It intentionally has a distinct type from :class:`EvaluationExplanationDataV2`.
    The latter has V1 result/summary and detached-native evidence semantics;
    this carrier represents a V2 engine observation plus captured world,
    provenance, asset and profile material.  ``evidence.graph`` is always
    absent for the currently supported V2 ProbLog path.
    """

    identity: EvaluationRunV2ExplanationIdentityViewV2
    query_descriptor: EvaluationRunV2QueryDescriptorViewV2
    outcome: EvaluationRunV2OutcomePresentationViewV2
    profile: ExecutionProfileViewV2 = dc_field(repr=False)
    probability_materialization: ProbabilityMaterializationViewV2 | None = dc_field(repr=False)
    asset: AssetDescriptorCaptureViewV2 = dc_field(repr=False)
    scenario: ScenarioCaptureViewV2 = dc_field(repr=False)
    choice: ChoiceCaptureViewV2 = dc_field(repr=False)
    evidence: EvidenceSupportViewV2 = dc_field(repr=False)
    boundaries: ExplainBoundaryViewV2 = dc_field(default_factory=ExplainBoundaryViewV2)

    @property
    def source_protocol(self) -> Literal["evaluation_run_v2"]:
        return self.identity.source_protocol

    def narrate(self) -> tuple[str, ...]:
        return narrate_evaluation_run_v2_explanation_v2(self)

    def render_text(self) -> str:
        return render_evaluation_run_v2_explanation_text_v2(self)

    def __repr__(self) -> str:
        return (
            "EvaluationRunV2ExplanationDataV2("
            f"run_digest={self.identity.run_digest!r}, side={self.identity.side!r}, "
            f"engine={self.identity.engine!r}, "
            f"target_observation_digest={self.identity.target_observation_digest!r}, "
            f"evidence={self.evidence.state!r})"
        )


def evaluation_explanation_data_v2_from_run(
    run: EvaluationRunV1,
    *,
    target: ExplainTargetV1,
) -> EvaluationExplanationDataV2:
    """Build product Explain data for one *explicit* V1 row or summary target.

    Opening the result view first validates the sealed run and validates that
    the named target belongs to it.  A native evidence reconstruction problem
    is represented as ``not_available`` rather than replaced by a speculative
    proof graph.  A malformed target/run is rejected.
    """

    if not isinstance(target, ExplainTargetV1):
        raise ProductViewErrorV2(
            "Explain requires an explicit ExplainTargetV1",
            code="PRODUCT_EXPLAIN_V2_TARGET_INVALID",
        )
    if target.side not in {"baseline", "effective", "candidate_effective"}:
        raise ProductViewErrorV2(
            "Explain target side is unsupported", code="PRODUCT_EXPLAIN_V2_TARGET_INVALID"
        )
    side = target.side
    view = result_view_v2_from_run(run, side=side)
    selected_row, is_summary = _validate_product_target(view, target)
    plan = run.candidate_plan if side == "candidate_effective" else run.plan
    if plan is None:  # defensive after result-view validation.
        raise ProductViewErrorV2(
            "candidate target has no sealed plan", code="PRODUCT_EXPLAIN_V2_TARGET_INVALID"
        )

    raw: EvaluationRunExplanationV1 | None
    unavailable_reason: str | None = None
    try:
        raw = explain_evaluation_run_v1(run, target=target)
    except EvaluationRunRuntimeErrorV1 as exc:
        # Target membership was checked above.  A detached evidence failure is
        # an availability state, never a reason to create a guessed graph.
        raw = None
        unavailable_reason = exc.code

    if raw is None:
        observation: ExplanationObservationV2 = (
            "result_summary_observed" if is_summary else "positive_row_observed"
        )
        conclusion: ExplanationConclusionV2 = "not_claimed" if is_summary else "holds"
        evidence = EvidenceSupportViewV2("not_available", unavailable_reason)
        policy = PolicyPresentationViewV2(
            topology_capture=CaptureStateViewV2(
                "not_captured", "POLICY_TOPOLOGY_UNAVAILABLE_WITH_EXPLAIN"
            ),
            structure_digest=None,
            root_node_id=None,
        )
        scenario = _scenario_presentation_v2(
            plan, operations=None, patch_capture="not_captured", patch_application="not_captured"
        )
        comparison = _comparison_presentation_v2(run)
        return _explanation_data_v2(
            run=run,
            target=target,
            plan=plan,
            view=view,
            row=selected_row,
            observation=observation,
            conclusion=conclusion,
            evidence=evidence,
            policy=policy,
            scenario=scenario,
            comparison=comparison,
        )

    evidence = _evidence_support_v2(raw, run=run)
    policy = _policy_presentation_v2(raw)
    scenario = _scenario_presentation_v2(
        plan,
        operations=raw.scenario_operations,
        patch_capture=raw.scenario_patch_capture,
        patch_application=raw.scenario_patch_application,
    )
    return _explanation_data_v2(
        run=run,
        target=target,
        plan=plan,
        view=view,
        row=selected_row,
        observation=raw.observation,
        conclusion=raw.logical_conclusion,
        evidence=evidence,
        policy=policy,
        scenario=scenario,
        comparison=_comparison_presentation_v2(run),
    )


def evaluation_explanation_data_v2_from_evaluation_run_v2(
    run: EvaluationRunV2,
    *,
    target: EvaluationRunV2ExplainTarget,
) -> EvaluationRunV2ExplanationDataV2:
    """Open one explicit V2 engine observation as presentation-safe Explain data.

    The V2 carrier does not expose an evidence-graph reconstruction contract.
    In particular, a successful ProbLog point observation is kept as an exact
    probability plus its captured world/provenance/semantics data and returns
    ``EvidenceSupportViewV2(state="not_available", graph=None)``.  This
    adapter never invokes a native evaluator, replays the run, or constructs a
    speculative proof graph.
    """

    if not isinstance(target, EvaluationRunV2ExplainTarget):
        raise ProductViewErrorV2(
            "V2 Explain requires an explicit EvaluationRunV2ExplainTarget",
            code="PRODUCT_EXPLAIN_V2_TARGET_INVALID",
        )
    view = result_view_v2_from_evaluation_run_v2(run, side=target.side)
    if target.run_digest != view.run_digest or target.engine != view.engine:
        raise ProductViewErrorV2(
            "V2 Explain target does not belong to this sealed run/engine frame",
            code="PRODUCT_EXPLAIN_V2_TARGET_INVALID",
        )
    try:
        row = view.row(target.observation_digest)
    except ProductViewErrorV2 as exc:
        raise ProductViewErrorV2(
            "V2 Explain target does not name an observation in this sealed result",
            code="PRODUCT_EXPLAIN_V2_TARGET_INVALID",
        ) from exc
    if target.side != row.side or target.engine != row.engine:
        raise ProductViewErrorV2(
            "V2 Explain target observation link is malformed",
            code="PRODUCT_EXPLAIN_V2_TARGET_INVALID",
        )
    evidence = _v2_observation_evidence_support(view)
    return EvaluationRunV2ExplanationDataV2(
        identity=EvaluationRunV2ExplanationIdentityViewV2(
            source_protocol="evaluation_run_v2",
            run_digest=view.run_digest,
            side=view.side,
            engine=view.engine,
            target_observation_digest=row.observation_digest,
            row_identity_digest=row.row_identity_digest,
            plan_digest=view.plan_digest,
            world_capture_digest=view.scenario.world.world_capture_digest,
            semantic_world_digest=view.scenario.world.semantic_world_digest,
            resolution_evidence_digest=view.scenario.world.resolution_evidence_digest,
        ),
        query_descriptor=EvaluationRunV2QueryDescriptorViewV2(
            target_kind=view.target.kind,
            target_id=view.target.target_id,
            target_version=view.target.target_version,
            target_digest=view.target.target_digest,
            query_digest=view.query_digest,
            observed_value_aliases=tuple(value.alias for value in row.values),
        ),
        outcome=EvaluationRunV2OutcomePresentationViewV2(
            observation="engine_row_observed",
            row=row,
            point_probability=row.point_probability,
        ),
        profile=view.profile,
        probability_materialization=view.probability_materialization,
        asset=view.asset,
        scenario=view.scenario,
        choice=view.choice,
        evidence=evidence,
    )


def _v2_observation_evidence_support(
    view: EvaluationRunV2ResultView,
) -> EvidenceSupportViewV2:
    """State the V2 proof boundary without creating a synthetic graph."""

    if view.engine == "problog":
        return EvidenceSupportViewV2("not_available", "PROBLOG_V2_EVIDENCE_GRAPH_NOT_CAPTURED")
    if view.engine == "native":
        return EvidenceSupportViewV2(
            "not_available", "NATIVE_V2_DETACHED_EVIDENCE_GRAPH_NOT_IMPLEMENTED"
        )
    return EvidenceSupportViewV2("unsupported", "V2_ENGINE_EVIDENCE_GRAPH_UNSUPPORTED")


def _explanation_data_v2(
    *,
    run: EvaluationRunV1,
    target: ExplainTargetV1,
    plan: GoalPlanV1,
    view: ResultViewV2,
    row: RowViewV2 | None,
    observation: ExplanationObservationV2,
    conclusion: ExplanationConclusionV2,
    evidence: EvidenceSupportViewV2,
    policy: PolicyPresentationViewV2,
    scenario: ScenarioPresentationViewV2,
    comparison: ComparisonPresentationViewV2,
) -> EvaluationExplanationDataV2:
    return EvaluationExplanationDataV2(
        identity=ExplanationIdentityViewV2(
            source_protocol="evaluation_run_v1",
            run_digest=run.run_digest,
            target_digest=target.target_digest,
            side=target.side,
            result_digest=(
                run.candidate_effective.canonical_result.result_digest
                if target.side == "candidate_effective" and run.candidate_effective is not None
                else (
                    run.baseline.canonical_result.result_digest
                    if target.side == "baseline"
                    else run.effective.canonical_result.result_digest
                )
            ),
            world_capture_digest=(
                run.candidate_effective.world_capture_digest
                if target.side == "candidate_effective" and run.candidate_effective is not None
                else (
                    run.baseline.world_capture_digest
                    if target.side == "baseline"
                    else run.effective.world_capture_digest
                )
            ),
            semantic_world_digest=run.replay_payload.world(
                "baseline" if target.side == "baseline" else "effective"
            ).semantic_world_digest,
        ),
        query_descriptor=QueryDescriptorViewV2(
            target_kind=plan.target.kind,
            target_id=plan.target.target_id,
            target_version=plan.target.target_version,
            target_digest=plan.target.target_digest,
            query_digest=plan.query_digest,
            selections=tuple((item.alias, item.value_tag) for item in plan.selections),
            scenario_request_digest=plan.scenario_request_digest,
        ),
        outcome=OutcomePresentationViewV2(
            observation=observation,
            logical_conclusion=conclusion,
            row=row,
            summary_anchor_digest=(view.summary.anchor_digest if row is None else None),
        ),
        execution=view.execution,
        policy=policy,
        scenario=scenario,
        evidence=evidence,
        comparison=comparison,
    )


def _validate_product_target(
    view: ResultViewV2, target: ExplainTargetV1
) -> tuple[RowViewV2 | None, bool]:
    if target.kind == "row":
        return view.row(target.anchor_digest), False
    if target.kind == "summary" and target.anchor_digest == view.summary.anchor_digest:
        return None, True
    raise ProductViewErrorV2(
        "Explain target does not belong to the named sealed result",
        code="PRODUCT_EXPLAIN_V2_TARGET_INVALID",
    )


def _evidence_support_v2(
    explanation: EvaluationRunExplanationV1,
    *,
    run: EvaluationRunV1,
) -> EvidenceSupportViewV2:
    if (
        explanation.engine_evidence != "native_detached_recomputed"
        or explanation.evidence_graph is None
    ):
        return EvidenceSupportViewV2("not_captured", "V1_ENGINE_EVIDENCE_NOT_CAPTURED")
    state: EvidenceSupportStateV2 = (
        "portable_native_inner_not_parity"
        if run.execution_profile.kind == "portable_deterministic_v1"
        else "native_detached_recomputed"
    )
    return EvidenceSupportViewV2(
        state=state, graph=evidence_graph_view_v2_from_graph(explanation.evidence_graph)
    )


def _policy_presentation_v2(explanation: EvaluationRunExplanationV1) -> PolicyPresentationViewV2:
    structure = explanation.policy_structure
    if structure is None:
        return PolicyPresentationViewV2(
            topology_capture=CaptureStateViewV2("not_captured", "POLICY_TOPOLOGY_NOT_CAPTURED"),
            structure_digest=None,
            root_node_id=None,
        )
    projection = explanation.policy_projection
    if projection is None:
        projection_capture = CaptureStateViewV2("not_captured", "POLICY_PROJECTION_NOT_CAPTURED")
        root_state = None
        projection_nodes: tuple[PolicyProjectionNodeViewV2, ...] = ()
    else:
        projection_capture = CaptureStateViewV2("captured")
        root_state = projection.evaluation.root_state
        projection_nodes = tuple(
            PolicyProjectionNodeViewV2(
                node_id=node.node_id,
                kind=node.kind,
                state=node.state,
                branch_states=tuple(
                    (branch.branch_id, branch.state) for branch in node.branch_states
                ),
            )
            for node in projection.evaluation.nodes
        )
    return PolicyPresentationViewV2(
        topology_capture=CaptureStateViewV2("captured"),
        structure_digest=structure.structure_digest,
        root_node_id=structure.root_node_id,
        topology=tuple(_policy_topology_node_v2(node) for node in structure.nodes),
        projection_capture=projection_capture,
        root_state=root_state,
        projection_nodes=projection_nodes,
    )


def _policy_topology_node_v2(
    node: PolicyStructureNodeV0 | PolicyCompareStructureNodeV0,
) -> PolicyTopologyNodeViewV2:
    if isinstance(node, PolicyStructureNodeV0):
        return PolicyTopologyNodeViewV2(
            node_id=node.node_id,
            kind=node.kind,
            child_node_ids=node.child_node_ids,
            occurrence_alias=node.occurrence_alias,
            left=None if node.left is None else _policy_operand_v2(node.left),
            right=None if node.right is None else _policy_operand_v2(node.right),
        )
    return PolicyTopologyNodeViewV2(
        node_id=node.node_id,
        kind="compare",
        child_node_ids=(),
        operation=node.op,
        left=_policy_operand_v2(node.left),
        right=_policy_operand_v2(node.right),
    )


def _policy_operand_v2(
    value: SemanticPortAddress | PolicyFieldNavigation | PolicyLiteral,
) -> PolicyOperandViewV2:
    if isinstance(value, SemanticPortAddress):
        return PolicyOperandViewV2(
            kind="address",
            occurrence_alias=value.occurrence_alias,
            port_name=value.port_name,
        )
    if isinstance(value, PolicyFieldNavigation):
        return PolicyOperandViewV2(
            kind="field_navigation",
            occurrence_alias=value.base.occurrence_alias,
            port_name=value.base.port_name,
            entity_type=value.field.entity_type,
            field_name=value.field.field_name,
        )
    return PolicyOperandViewV2(
        kind="literal", scalar_domain=value.scalar_domain, value=_safe_value(value.value)
    )


def _scenario_presentation_v2(
    plan: GoalPlanV1,
    *,
    operations: tuple[ResolvedScenarioOperationV1, ...] | None,
    patch_capture: str,
    patch_application: str,
) -> ScenarioPresentationViewV2:
    if operations is None:
        capture = CaptureStateViewV2("not_captured", "SCENARIO_PATCH_NOT_CAPTURED")
        operation_views: tuple[ScenarioOperationViewV2, ...] = ()
    else:
        capture = CaptureStateViewV2("captured")
        operation_views = tuple(_scenario_operation_v2(operation) for operation in operations)
    return ScenarioPresentationViewV2(
        request_digest=plan.scenario_request_digest,
        patch_capture=capture,
        patch_application=patch_application,
        operations=operation_views,
    )


def _scenario_operation_v2(operation: ResolvedScenarioOperationV1) -> ScenarioOperationViewV2:
    return ScenarioOperationViewV2(
        kind=operation.kind,
        operation_digest=operation.operation_digest,
        premise_ids=operation.premise_ids,
        origin_refs=operation.origin_refs,
        masked_witness_ids=operation.masked_witness_ids,
        synthetic_witness_ids=operation.synthetic_witness_ids,
        predicate_id=operation.predicate_id,
        entity_ref=operation.entity_ref,
        values=tuple((value.tag, value.value) for value in operation.values),
    )


def _comparison_presentation_v2(run: EvaluationRunV1) -> ComparisonPresentationViewV2:
    if run.candidate_plan is None:
        policy_capture = CaptureStateViewV2("not_applicable")
        result_relation = None
        authored_structure_relation = None
    else:
        try:
            comparison = compare_policy_variants_v1(run)
        except EvaluationRunRuntimeErrorV1 as exc:
            policy_capture = CaptureStateViewV2("not_captured", exc.code)
            result_relation = None
            authored_structure_relation = None
        else:
            policy_capture = CaptureStateViewV2("captured")
            result_relation = comparison.result_relation
            authored_structure_relation = comparison.authored_structure_relation
    if run.plan.scenario_request_digest is None:
        scenario_capture = CaptureStateViewV2("not_applicable")
        scenario_result_relation = None
        axes: tuple[str, ...] = ()
    else:
        try:
            scenario_diff = diff_scenario_run_v1(run)
        except EvaluationRunRuntimeErrorV1 as exc:
            scenario_capture = CaptureStateViewV2("not_captured", exc.code)
            scenario_result_relation = None
            axes = ()
        else:
            scenario_capture = CaptureStateViewV2("captured")
            scenario_result_relation = scenario_diff.result_relation
            axes = scenario_diff.input_difference_axes
    return ComparisonPresentationViewV2(
        policy_comparison=policy_capture,
        scenario_diff=scenario_capture,
        result_relation=result_relation,
        authored_structure_relation=authored_structure_relation,
        scenario_result_relation=scenario_result_relation,
        scenario_input_difference_axes=axes,
    )


def evidence_graph_view_v2_from_graph(graph: EvidenceGraph) -> EvidenceGraphViewV2:
    """Return a sanitized product view of one existing EvidenceGraph.

    This utility is intentionally separate from run Explain so a product can
    safely present a pre-existing graph without passing generic ``Source.meta``
    through to its client-side data model.
    """

    if not isinstance(graph, EvidenceGraph):
        raise ProductViewErrorV2(
            "evidence graph must be EvidenceGraph",
            code="PRODUCT_EXPLAIN_V2_EVIDENCE_GRAPH_INVALID",
        )
    metadata, omitted = _allowlisted_mapping(graph.metadata, _GRAPH_META_ALLOWLIST)
    paths: list[EvidencePathViewV2] = []
    for path in graph.paths:
        if isinstance(path, EvidenceTree):
            tree_meta, _tree_omitted = _allowlisted_mapping(path.metadata, _GRAPH_META_ALLOWLIST)
            # Tree metadata has the same no-arbitrary-meta rule.  Keeping the
            # graph-wide omitted keys is sufficient for a UI audit trail.
            paths.append(
                EvidenceTreeViewV2(
                    tree_id=path.tree_id,
                    status=path.status,
                    rules=tuple(_evidence_rule_view_v2(rule) for rule in path.rules),
                    joins=tuple(
                        EvidenceJoinViewV2(
                            join_id=join.join_id,
                            status=join.status,
                            left_occurrence_alias=join.left.rule_occurrence_alias,
                            left_port_name=join.left.port_name,
                            right_occurrence_alias=join.right.rule_occurrence_alias,
                            right_port_name=join.right.port_name,
                        )
                        for join in path.joins
                    ),
                    certainty=_certainty_view_v2(path.certainty),
                    metadata=tree_meta,
                    policy_conditions=tuple(
                        _policy_condition_view_v2(condition) for condition in path.policy_conditions
                    ),
                )
            )
        elif isinstance(path, EvidenceTimeline):
            timeline_meta, _timeline_omitted = _allowlisted_mapping(
                path.metadata, _GRAPH_META_ALLOWLIST
            )
            paths.append(
                EvidenceTimelineViewV2(
                    timeline_id=path.timeline_id,
                    status=path.status,
                    certainty=_certainty_view_v2(path.certainty),
                    event_count=len(path.events),
                    metadata=timeline_meta,
                )
            )
        else:  # pragma: no cover - EvidenceGraph DTO enforces its union today.
            raise ProductViewErrorV2(
                "evidence path is outside the supported product shape",
                code="PRODUCT_EXPLAIN_V2_EVIDENCE_PATH_UNSUPPORTED",
            )
    return EvidenceGraphViewV2(
        graph_id=graph.graph_id,
        engine=graph.engine,
        layout_hint=graph.layout_hint,
        subject_binding=_safe_mapping(graph.subject_binding),
        paths=tuple(paths),
        certainty=_certainty_view_v2(graph.certainty),
        metadata=metadata,
        omitted_metadata_keys=omitted,
    )


def _evidence_rule_view_v2(rule: EvidenceRule) -> EvidenceRuleViewV2:
    return EvidenceRuleViewV2(
        occurrence_alias=rule.occurrence_alias,
        rule_id=rule.rule_id,
        role=rule.role,
        status=rule.status,
        repr_text=rule.repr_text,
        ports=_safe_mapping(rule.ports),
        atoms=tuple(_evidence_atom_view_v2(atom) for atom in rule.atoms),
    )


def _policy_condition_view_v2(condition: EvidencePolicyCondition) -> EvidencePolicyConditionViewV2:
    return EvidencePolicyConditionViewV2(
        policy_node_id=condition.policy_node_id,
        condition_id=condition.condition_id,
        role=condition.role,
        atom=_evidence_atom_view_v2(condition.atom),
    )


def _evidence_atom_view_v2(atom: EvidenceAtom) -> EvidenceAtomViewV2:
    status, certainty, support, blocked_by = _verdict_view_v2(atom)
    return EvidenceAtomViewV2(
        atom_id=atom.atom_id,
        form_kind=_atom_form_kind(atom),
        form=_atom_form_v2(atom),
        status=status,
        repr_text=atom.repr_text,
        negated=atom.negated,
        timestep=atom.timestep,
        certainty=certainty,
        support=support,
        blocked_by=blocked_by,
    )


def _verdict_view_v2(
    atom: EvidenceAtom,
) -> tuple[
    Literal["holds", "fails", "not_reached"],
    CertaintyViewV2 | None,
    tuple[EvidenceSourceViewV2, ...],
    str | None,
]:
    verdict = atom.verdict
    if isinstance(verdict, Holds):
        return (
            "holds",
            _certainty_view_v2(verdict.certainty),
            tuple(_evidence_source_view_v2(source) for source in verdict.support),
            None,
        )
    if isinstance(verdict, Fails):
        return (
            "fails",
            _certainty_view_v2(verdict.certainty),
            tuple(_evidence_source_view_v2(source) for source in verdict.support),
            None,
        )
    if isinstance(verdict, NotReached):
        return "not_reached", None, (), verdict.blocked_by
    raise ProductViewErrorV2(
        "evidence verdict is unsupported", code="PRODUCT_EXPLAIN_V2_EVIDENCE_VERDICT_UNSUPPORTED"
    )


def _evidence_source_view_v2(source: Source) -> EvidenceSourceViewV2:
    metadata, omitted = _allowlisted_mapping(source.meta, _SOURCE_META_ALLOWLIST)
    candidate = source.meta.get("provenance_ref")
    if candidate is None:
        candidate = source.meta.get("provenance")
    descriptor = safe_opaque_provenance_descriptor_v2(candidate)
    capture = (
        CaptureStateViewV2("captured")
        if descriptor is not None
        else CaptureStateViewV2("not_captured", "V2_PROVENANCE_NOT_CAPTURED_BY_V1")
    )
    return EvidenceSourceViewV2(
        ref=source.ref,
        field=source.field,
        value=_safe_value(source.value),
        metadata=metadata,
        omitted_metadata_keys=omitted,
        opaque_provenance=descriptor,
        provenance_capture=capture,
    )


def safe_opaque_provenance_descriptor_v2(value: object) -> OpaqueProvenanceDescriptorV2 | None:
    """Return a safe structural source descriptor without importing its class.

    Only the closed ``ProvenanceRefV1`` wire/attribute shape is accepted.  A
    generic Evidence ``Source`` or arbitrary metadata object cannot become
    provenance merely because it has a suggestive string field.
    """

    if value is None:
        return None
    if isinstance(value, Mapping):
        raw = value
        source_ref = raw.get("ref")
        locator = raw.get("locator")
        origin_role = raw.get("origin_role")
        content_digest = raw.get("content_digest")
        admission_ref = raw.get("admission_ref")
        reference_digest = raw.get("reference_digest")
        keys = set(raw)
        if keys not in (
            {"ref", "locator", "origin_role", "content_digest", "admission_ref"},
            {
                "ref",
                "locator",
                "origin_role",
                "content_digest",
                "admission_ref",
                "reference_digest",
            },
        ):
            return None
    else:
        source_ref = getattr(value, "source_ref", None)
        locator = getattr(value, "locator", None)
        origin_role = getattr(value, "origin_role", None)
        content_digest = getattr(value, "content_digest", None)
        admission_ref = getattr(value, "admission_ref", None)
        reference_digest = getattr(value, "reference_digest", None)
    if (
        not isinstance(source_ref, str)
        or not _opaque_text(source_ref)
        or not isinstance(origin_role, str)
        or origin_role not in _ORIGIN_ROLES
    ):
        return None
    locator_wire = _opaque_locator_wire(locator)
    if locator_wire is None:
        return None
    if content_digest is not None and (
        not isinstance(content_digest, str) or not _sha256_token(content_digest)
    ):
        return None
    if admission_ref is not None and (
        not isinstance(admission_ref, str) or not _opaque_text(admission_ref)
    ):
        return None
    if reference_digest is not None and (
        not isinstance(reference_digest, str) or not _sha256_token(reference_digest)
    ):
        return None
    return OpaqueProvenanceDescriptorV2(
        source_ref=source_ref,
        locator=locator_wire,
        origin_role=origin_role,
        content_digest=content_digest,
        admission_ref=admission_ref,
        reference_digest=reference_digest,
    )


def _opaque_locator_wire(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        raw: Mapping[str, object] = value
    elif hasattr(value, "to_wire") and callable(getattr(value, "to_wire")):
        try:
            candidate = value.to_wire()
        except Exception:  # pragma: no cover - third-party descriptor defense.
            return None
        if not isinstance(candidate, Mapping):
            return None
        raw = candidate
    else:
        kind = getattr(value, "kind", None)
        if kind == "opaque":
            raw = {"kind": kind, "opaque_ref": getattr(value, "opaque_ref", None)}
        elif kind == "line_span":
            raw = {
                "kind": kind,
                "line_start": getattr(value, "line_start", None),
                "line_end": getattr(value, "line_end", None),
            }
        elif kind == "json_pointer":
            raw = {"kind": kind, "pointer": getattr(value, "pointer", None)}
        else:
            return None
    kind = raw.get("kind")
    if (
        kind == "opaque"
        and set(raw) == {"kind", "opaque_ref"}
        and _opaque_text(raw.get("opaque_ref"))
    ):
        return {"kind": "opaque", "opaque_ref": raw["opaque_ref"]}
    if kind == "line_span" and set(raw) == {"kind", "line_start", "line_end"}:
        start, end = raw.get("line_start"), raw.get("line_end")
        if (
            isinstance(start, int)
            and not isinstance(start, bool)
            and isinstance(end, int)
            and not isinstance(end, bool)
            and start >= 1
            and end >= start
        ):
            return {"kind": "line_span", "line_start": start, "line_end": end}
    if kind == "json_pointer" and set(raw) == {"kind", "pointer"}:
        pointer = raw.get("pointer")
        if (
            isinstance(pointer, (list, tuple))
            and 0 < len(pointer) <= 16
            and all(_opaque_text(item, max_length=128) for item in pointer)
        ):
            return {"kind": "json_pointer", "pointer": tuple(pointer)}
    return None


def _atom_form_kind(atom: EvidenceAtom) -> Literal["fact", "compare", "builtin", "aggregate"]:
    if isinstance(atom.form, Fact):
        return "fact"
    if isinstance(atom.form, Compare):
        return "compare"
    if isinstance(atom.form, Builtin):
        return "builtin"
    if isinstance(atom.form, Aggregate):
        return "aggregate"
    raise ProductViewErrorV2(
        "evidence atom form is unsupported", code="PRODUCT_EXPLAIN_V2_EVIDENCE_FORM_UNSUPPORTED"
    )


def _atom_form_v2(atom: EvidenceAtom) -> Mapping[str, object]:
    form = atom.form
    if isinstance(form, Fact):
        return {
            "predicate": form.predicate,
            "terms": tuple(_evidence_term_v2(term) for term in form.terms),
        }
    if isinstance(form, Compare):
        return {
            "op": form.op,
            "left": _evidence_term_v2(form.left),
            "right": _evidence_term_v2(form.right),
        }
    if isinstance(form, Builtin):
        return {
            "kind": form.kind,
            "operands": tuple(_evidence_term_v2(item) for item in form.operands),
        }
    if isinstance(form, Aggregate):
        return {
            "kind": form.kind,
            "body_terms": tuple(_evidence_term_v2(item) for item in form.body_terms),
            "head_terms": tuple(_evidence_term_v2(item) for item in form.head_terms),
        }
    raise ProductViewErrorV2(
        "evidence atom form is unsupported", code="PRODUCT_EXPLAIN_V2_EVIDENCE_FORM_UNSUPPORTED"
    )


def _evidence_term_v2(value: BoundVar | Const) -> EvidenceTermViewV2:
    if isinstance(value, BoundVar):
        return EvidenceTermViewV2(
            kind="bound",
            value=_safe_value(value.value),
            variable_name=value.name,
            bound_by=value.bound_by,
        )
    if isinstance(value, Const):
        return EvidenceTermViewV2(kind="const", value=_safe_value(value.value))
    raise ProductViewErrorV2(
        "evidence term is unsupported", code="PRODUCT_EXPLAIN_V2_EVIDENCE_TERM_UNSUPPORTED"
    )


def _certainty_view_v2(value: Certainty | None) -> CertaintyViewV2 | None:
    if value is None:
        return None
    return CertaintyViewV2(kind=value.kind, lo=value.lo, hi=value.hi)


def _allowlisted_mapping(
    value: Mapping[str, Any], allowed: frozenset[str]
) -> tuple[Mapping[str, object], tuple[str, ...]]:
    clean = {
        str(key): _safe_value(item)
        for key, item in value.items()
        if isinstance(key, str) and key in allowed
    }
    omitted = tuple(
        sorted(str(key) for key in value if not isinstance(key, str) or key not in allowed)
    )
    return clean, omitted


def _safe_mapping(value: Mapping[str, Any]) -> Mapping[str, object]:
    return {str(key): _safe_value(item) for key, item in value.items() if isinstance(key, str)}


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType({str(key): _safe_value(item) for key, item in value.items()})


def _safe_value(value: object, *, depth: int = 0) -> object:
    """Detach displayable values while refusing arbitrary rich objects.

    Source *metadata* is filtered before it gets here.  Fact values and ports
    may still be useful to an authorized product consumer, so JSON-like values
    survive; opaque objects become a type marker rather than invoking ``repr``
    and accidentally exposing document text or credentials.
    """

    if depth > _MAX_SAFE_VALUE_DEPTH:
        return "<depth-capped>"
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else "<non-finite>"
    if isinstance(value, Mapping):
        items = list(value.items())[:_MAX_SAFE_VALUE_ITEMS]
        return MappingProxyType(
            {
                str(key): _safe_value(item, depth=depth + 1)
                for key, item in items
                if isinstance(key, str)
            }
        )
    if isinstance(value, (tuple, list)):
        return tuple(_safe_value(item, depth=depth + 1) for item in value[:_MAX_SAFE_VALUE_ITEMS])
    return f"<unsupported:{type(value).__name__}>"


def _opaque_text(value: object, *, max_length: int = 256) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= max_length
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _sha256_token(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and value[7:] == value[7:].lower()
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def narrate_evaluation_explanation_v2(data: EvaluationExplanationDataV2) -> tuple[str, ...]:
    """Return a safe, lossy narration of structured Explain data.

    It intentionally renders identities and states only: raw selected values,
    source values, arbitrary source metadata and source content are never
    interpolated into narrative text.
    """

    if not isinstance(data, EvaluationExplanationDataV2):
        raise ProductViewErrorV2(
            "narrate requires EvaluationExplanationDataV2",
            code="PRODUCT_EXPLAIN_V2_RENDER_INPUT_INVALID",
        )
    target = data.query_descriptor
    lines = [
        f"Evaluation {data.identity.run_digest} [{data.identity.side}]",
        f"Target: {target.target_kind} {target.target_id} ({target.target_digest})",
        f"Observation: {data.outcome.observation}; conclusion: {data.outcome.logical_conclusion}",
        (
            "Result: "
            f"{data.execution.profile_kind} / completeness={data.execution.assessment.completeness}"
        ),
        f"Evidence: {data.evidence.state}",
    ]
    if data.evidence.reason_code is not None:
        lines.append(f"Evidence availability: {data.evidence.reason_code}")
    if data.policy.topology_capture.state == "captured":
        lines.append(
            f"Policy topology: {len(data.policy.topology)} nodes ({data.policy.structure_digest})"
        )
    else:
        lines.append(f"Policy topology: {data.policy.topology_capture.state}")
    lines.append(f"Scenario patch: {data.scenario.patch_capture.state}")
    lines.append(
        "Boundary: no negative proof, source authority, or action authorization is claimed"
    )
    return tuple(lines)


def render_evaluation_explanation_text_v2(data: EvaluationExplanationDataV2) -> str:
    """Join the pure narration into a stable plain-text rendering."""

    return "\n".join(narrate_evaluation_explanation_v2(data))


def narrate_evaluation_run_v2_explanation_v2(
    data: EvaluationRunV2ExplanationDataV2,
) -> tuple[str, ...]:
    """Return a safe, lossy narration of a V2 observation Explain view.

    This renderer reads only the structured DTO above.  It deliberately does
    not interpolate selected values, Scenario source content, or a probability
    as an unqualified natural-language truth claim.
    """

    if not isinstance(data, EvaluationRunV2ExplanationDataV2):
        raise ProductViewErrorV2(
            "narrate requires EvaluationRunV2ExplanationDataV2",
            code="PRODUCT_EXPLAIN_V2_RENDER_INPUT_INVALID",
        )
    identity = data.identity
    descriptor = data.query_descriptor
    lines = [
        f"Evaluation {identity.run_digest} [{identity.side}]",
        f"Target: {descriptor.target_kind} {descriptor.target_id} ({descriptor.target_digest})",
        f"Observation: engine_row_observed via {identity.engine}; conclusion: not_claimed",
        f"Profile: {data.profile.kind} / semantics={data.profile.semantic_model}",
        f"Evidence: {data.evidence.state}",
        f"Scenario world: {identity.semantic_world_digest}",
    ]
    if data.outcome.point_probability is not None:
        lines.append("Point probability: captured engine observation")
    if data.probability_materialization is not None:
        lines.append(
            "Probability materialization: "
            f"captured via {data.probability_materialization.model} "
            "(declared decimal and float64 projection remain structured data)"
        )
    if data.evidence.reason_code is not None:
        lines.append(f"Evidence availability: {data.evidence.reason_code}")
    lines.append(f"Asset descriptor: {data.asset.descriptor_capture.state}")
    lines.append(f"Choice topology: {data.choice.authored_topology.state}")
    lines.append(
        "Boundary: no evidence graph, Boolean conclusion, negative proof, source authority, or action authorization is claimed"
    )
    return tuple(lines)


def render_evaluation_run_v2_explanation_text_v2(
    data: EvaluationRunV2ExplanationDataV2,
) -> str:
    """Join V2's pure data-first narration into stable plain text."""

    return "\n".join(narrate_evaluation_run_v2_explanation_v2(data))


__all__ = [
    "CertaintyViewV2",
    "ComparisonPresentationViewV2",
    "EvaluationExplanationDataV2",
    "EvaluationRunV2ExplanationDataV2",
    "EvaluationRunV2ExplanationIdentityViewV2",
    "EvaluationRunV2OutcomePresentationViewV2",
    "EvaluationRunV2QueryDescriptorViewV2",
    "EvidenceAtomViewV2",
    "EvidenceGraphViewV2",
    "EvidenceJoinViewV2",
    "EvidencePathViewV2",
    "EvidencePolicyConditionViewV2",
    "EvidenceRuleViewV2",
    "EvidenceSourceViewV2",
    "EvidenceSupportStateV2",
    "EvidenceSupportViewV2",
    "EvidenceTermViewV2",
    "EvidenceTimelineViewV2",
    "EvidenceTreeViewV2",
    "ExplainBoundaryViewV2",
    "ExplanationIdentityViewV2",
    "OpaqueProvenanceDescriptorV2",
    "OutcomePresentationViewV2",
    "PolicyOperandViewV2",
    "PolicyPresentationViewV2",
    "PolicyProjectionNodeViewV2",
    "PolicyTopologyNodeViewV2",
    "QueryDescriptorViewV2",
    "ScenarioOperationViewV2",
    "ScenarioPresentationViewV2",
    "evidence_graph_view_v2_from_graph",
    "evaluation_explanation_data_v2_from_run",
    "evaluation_explanation_data_v2_from_evaluation_run_v2",
    "narrate_evaluation_explanation_v2",
    "narrate_evaluation_run_v2_explanation_v2",
    "render_evaluation_explanation_text_v2",
    "render_evaluation_run_v2_explanation_text_v2",
    "safe_opaque_provenance_descriptor_v2",
]
