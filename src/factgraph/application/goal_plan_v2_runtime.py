"""Detached Q20 product evaluation runtime.

This module is intentionally a parallel execution seam.  It does not widen
the legacy ``SDKStore.eval`` or GoalPlan V1 APIs.  Its public input is a
product-authored Rule/Policy, a normal compiled typed Query, a closed V2
execution profile, and an optional Scenario V2.  One call captures the live
view once, resolves an isolated effective world, materializes a fresh core
``Store``, and seals an :class:`EvaluationRunV2` that can later replay without
the original graph, ledger, registry, provider, or asset object.

The only shipped V2 execution models are deliberately small:

* ``native_deterministic_v2`` evaluates the positive typed Query with Native;
* ``problog_point_v2`` evaluates ProbLog point probabilities and records
  Native/Soufflé as explicit unsupported frames; and
* a product ``WeightedChoice`` is lowered only through the dedicated ProbLog
  annotated-disjunction adapter.

No generic config bag, V1 provider, V1 expectation, or resealed V1 run leaks
through this boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
import json
import math
import time
from typing import TYPE_CHECKING, Any, Literal, NoReturn, cast

from factgraph.adapters.problog.rule_ext import (
    ProbLogRuleExt,
    ProbLogWeightedChoiceArm,
    ProbLogWeightedChoiceBranch,
    ProbLogWeightedChoiceExt,
)
from factgraph.application.derivation_runtime import evaluate_derivation_plans
from factgraph.application.evaluation_query_target_runtime import (
    TargetedCompiledEvaluationQueryV0,
    assert_targeted_evaluation_query_current,
    targeted_evaluation_query_wrapper_digest_v0,
)
from factgraph.application.evaluation_query_runtime import (
    ResolvedEvaluationQueryNavigationSelectionV0,
    compile_evaluation_query,
)
from factgraph.application.policy_runtime import compile_policy
from factgraph.application.portable_evaluation_runtime import (
    PortableEvaluationError,
    execute_portable_deterministic_v1,
    portable_dependency_predicate_ids_v1,
)
from factgraph.application.protocol.derivation import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DerivationEvaluateRequest,
)
from factgraph.application.protocol.evaluation_run_v2 import (
    BranchWitnessV2,
    EvaluationEngineFrameV2,
    EvaluationFunctionCallV2,
    EvaluationFunctionMaterializationV2,
    EvaluationReplayPayloadV2,
    EvaluationReplayWorldV2,
    EvaluationRunPlanV2,
    EvaluationRunSideV2,
    EvaluationRunV2,
    EvaluationSelectedRowV2,
    EvaluationProbabilityMaterializationV2,
    assert_evaluation_run_v2_current,
    problog_probability_materialization_v2_from_world,
)
from factgraph.application.protocol.execution_profile_v2 import (
    EvaluationExecutionProfileV2,
    EvaluationTargetPinV2,
    ProbLogPointSemanticsV2,
    ResolvedExecutionAttachmentV2,
    ResolvedExecutionAttachmentsV2,
    assert_evaluation_execution_profile_v2_current,
    profile_accepts_fact_semantics_v2,
    validate_resolved_execution_attachments_v2,
)
from factgraph.application.protocol.goal_plan_v1 import GoalValueV1
from factgraph.application.protocol.evaluation_query import (
    EvaluationQuery,
    EvaluationQuerySelection,
)
from factgraph.application.protocol.policy import Policy, PolicyOccurrence
from factgraph.application.protocol.rule import PortType, Rule
from factgraph.application.protocol.provenance_v1 import (
    ProvenanceLocatorV1,
    ProvenanceRefV1,
)
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprEvaluationTrace,
    _materialize_adapter_derivation_plan,
)
from factgraph.application.evaluation_run_bundle_runtime import _receipt_case_index
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.scenario_v1 import ScenarioSpecV1, ScenarioValueV1
from factgraph.application.protocol.scenario_v2 import (
    EffectiveWorldFactV2,
    EffectiveWorldV2,
    FactSemanticsV2,
    ScenarioDisplayV2,
    ScenarioMetaV2,
    ScenarioSpecV2,
    canonical_decimal_v2,
)
from factgraph.application.protocol.schema_runtime import EntityRef
from factgraph.application.scenario_v1_runtime import (
    ScenarioResolutionErrorV1,
    resolve_scenario_v1,
    scenario_dependency_predicate_ids_v1,
    select_dependency_relation_v1,
)
from factgraph.application.scenario_v2_runtime import (
    ScenarioResolutionErrorV2,
    build_effective_world_v2,
    effective_world_v2_relation,
    resolve_scenario_v2_from_v1,
    world_has_probabilistic_semantics_v2,
)
from factgraph.application.schema_runtime import build_schema_index, encode_entity_ref
from factgraph.application.semantic_address_runtime import SemanticAddressSpace
from factgraph.application.weighted_choice_problog_v2 import (
    ProductWeightedChoiceProbLogV2Error,
    lower_product_policy_weighted_choice_to_problog_v2,
)
from factgraph.core.derivation.candidates import DerivationOutput
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms
from factgraph.core.schema.schema_ir import ensure_schema_ir, schema_digest
from factgraph.core.semantics import SemanticsProfile
from factgraph.core.store._support import ProjectedFact
from factgraph.core.store.runtime import Store
from factgraph.core.view.projector import project_view_facts_with_witness
from factgraph.core.rules.where_ast import Origin, PredAtom, Var
from factgraph.sdk.product_authoring import (
    FunctionOccurrenceTopologyV1,
    ProductPolicyV1,
    ProductRuleV1,
    WeightedChoiceArmV1,
    WeightedChoiceTopologyV1,
    _function_port_predicate_id,
    asset_snapshot_v1,
    assert_asset_binding_current_v1,
)

# The public SDK V2 profile builder deliberately uses this exact digest.  It
# remains a compiler *pin*, not a claim that an arbitrary runtime environment
# has been remotely attested.
GOAL_PLAN_V2_COMPILER_DIGEST = sha256_token(b"factgraph-sdk-product-scenario-execution-v2")

_PROGRAM_TYPE = "FactGraphProductEvaluationProgramV2"
_PROGRAM_VERSION = "2"
_STRUCTURAL_VALUE_TYPE = "FactGraphStructuralValueV1"
_MAX_PROGRAM_DEPTH = 64
_MAX_PROGRAM_NODES = 100_000

_ProductTarget = ProductRuleV1 | ProductPolicyV1
_TargetSide = Literal["primary", "candidate"]


class ProductEvaluationRuntimeErrorV2(ValueError):
    """Fail-closed V2 construction/execution/replay rejection."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProductInvocationAggregateLimitsV2:
    """Explicit whole-invocation limits layered over unchanged V2 profiles.

    Aggregate ``units`` are protocol-defined as one per successful engine
    frame plus one per emitted observation and one per retained branch
    witness.  This definition is separate from every engine's own resource
    vocabulary and therefore does not reinterpret profile digests.
    """

    timeout_ms: int | None = None
    max_rows: int | None = None
    max_units: int | None = None
    max_evidence_bytes: int | None = None
    max_capture_bytes: int | None = None
    max_scenarios: int | None = None
    limits_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "timeout_ms",
            "max_rows",
            "max_units",
            "max_evidence_bytes",
            "max_capture_bytes",
            "max_scenarios",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                _fail(
                    f"aggregate {name} must be a non-negative integer or None",
                    "PRODUCT_INVOCATION_AGGREGATE_LIMIT_INVALID",
                )
        expected = _token(
            "product_invocation_aggregate_limits_v2",
            {
                name: getattr(self, name)
                for name in (
                    "timeout_ms",
                    "max_rows",
                    "max_units",
                    "max_evidence_bytes",
                    "max_capture_bytes",
                    "max_scenarios",
                )
            },
        )
        if hasattr(self, "limits_digest"):
            if self.limits_digest != expected:
                _fail(
                    "aggregate limits seal is stale",
                    "PRODUCT_INVOCATION_AGGREGATE_LIMIT_INVALID",
                )
            return
        object.__setattr__(self, "limits_digest", expected)


@dataclass
class _ProductInvocationAggregateMeterV2:
    limits: ProductInvocationAggregateLimitsV2
    started_ns: int = field(default_factory=time.monotonic_ns)
    rows: int = 0
    units: int = 0
    evidence_bytes: int = 0
    capture_bytes: int = 0

    def check_deadline(self) -> None:
        if self.limits.timeout_ms is None:
            return
        elapsed_ms = (time.monotonic_ns() - self.started_ns) // 1_000_000
        if elapsed_ms > self.limits.timeout_ms:
            self._exceeded("timeout_ms", int(elapsed_ms), self.limits.timeout_ms)

    def charge_side(
        self,
        side: EvaluationRunSideV2,
        capture: EvaluationReplayWorldV2,
    ) -> None:
        self.check_deadline()
        successful_frames = tuple(
            frame for frame in side.engine_frames if frame.status == "succeeded"
        )
        row_count = sum(len(frame.observations) for frame in successful_frames)
        witness_count = sum(len(frame.branch_witnesses) for frame in successful_frames)
        evidence_bytes = sum(
            len(
                json.dumps(
                    {
                        "branch": witness.compiled_branch_id,
                        "side": witness.evaluation_side,
                        "row": witness.row_identity_digest,
                        "proof": witness.proof_identity_digest,
                        "evidence": witness.evidence_references,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            for frame in successful_frames
            for witness in frame.branch_witnesses
        )
        capture_bytes = len(
            json.dumps(
                capture.to_wire(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        )
        self.rows += row_count
        self.units += len(successful_frames) + row_count + witness_count
        self.evidence_bytes += evidence_bytes
        self.capture_bytes += capture_bytes
        self._check("max_rows", self.rows)
        self._check("max_units", self.units)
        self._check("max_evidence_bytes", self.evidence_bytes)
        self._check("max_capture_bytes", self.capture_bytes)

    def charge_program_capture(self, byte_count: int) -> None:
        self.capture_bytes += byte_count
        self._check("max_capture_bytes", self.capture_bytes)

    def _check(self, name: str, observed: int) -> None:
        limit = getattr(self.limits, name)
        if limit is not None and observed > limit:
            self._exceeded(name, observed, limit)

    @staticmethod
    def _exceeded(dimension: str, observed: int, limit: int) -> NoReturn:
        _fail(
            f"aggregate {dimension} exceeded: observed={observed}, limit={limit}",
            "PRODUCT_INVOCATION_AGGREGATE_LIMIT_EXCEEDED",
        )


@dataclass(frozen=True)
class ProductEvaluationInvocationV2:
    """In-process V2 intent ready for one captured execution.

    The graph reference is intentionally absent from the durable run.  It is
    used only by :meth:`run` to take the one permitted live view capture.
    """

    _graph: "SDKStore"
    primary: TargetedCompiledEvaluationQueryV0
    product_target: _ProductTarget
    profile: EvaluationExecutionProfileV2
    scenario: ScenarioSpecV2 | None = None
    candidate: TargetedCompiledEvaluationQueryV0 | None = None
    candidate_product_target: _ProductTarget | None = None
    aggregate_limits: ProductInvocationAggregateLimitsV2 | None = None

    def run(self) -> EvaluationRunV2:
        """Capture one graph view and execute this Product V2 invocation.

        Returns:
            A sealed ``EvaluationRunV2`` containing named baseline,
            effective, and optional candidate-effective result sides.

        Raises:
            ProductEvaluationRuntimeErrorV2: If a target/profile/Scenario
                seal is stale, materialization fails, or an engine violates
                the declared Product V2 contract.

        Notes:
            ``run()`` performs the one permitted live graph capture. Open the
            returned carrier with ``outcome_from_run_v2(...)`` for structured
            result, Explain, and detached replay views.
        """
        return execute_product_evaluation_invocation_v2(self)


@dataclass(frozen=True)
class EvaluationRunReplaySideV2:
    """One detached V2 replay comparison; it never claims proof parity."""

    side: Literal["baseline", "effective", "candidate_effective"]
    declared_frame_digests: tuple[str, ...]
    observed_frame_digests: tuple[str, ...]
    frame_match: bool


@dataclass(frozen=True)
class EvaluationRunReplayV2:
    """Replay report computed from a sealed :class:`EvaluationRunV2` only."""

    run_digest: str
    replay_payload_digest: str
    status: Literal["matched", "mismatch"]
    baseline: EvaluationRunReplaySideV2
    effective: EvaluationRunReplaySideV2
    candidate_effective: EvaluationRunReplaySideV2 | None = None
    engine_pin_attestation: Literal["sealed_declared_pins_not_runtime_attested"] = (
        "sealed_declared_pins_not_runtime_attested"
    )
    proof_parity: Literal["not_claimed"] = "not_claimed"


@dataclass(frozen=True)
class CapturedFunctionDefinitionV2:
    """Replay-validated Function definition data without an executable callable."""

    occurrence_alias: str
    function_id: str
    function_version: str | None
    function_digest: str
    signature_digest: str
    implementation_digest: str
    relation_predicate_id: str
    ports: tuple[tuple[str, str, str, str], ...]
    input_bindings: tuple[tuple[str, str, str], ...]
    topology_digest: str
    asset_meta_json: str
    asset_descriptor_digest: str
    asset_binding_digest: str


def build_product_evaluation_invocation_v2(
    *,
    graph: "SDKStore",
    primary: TargetedCompiledEvaluationQueryV0,
    product_target: _ProductTarget,
    profile: EvaluationExecutionProfileV2,
    scenario: ScenarioSpecV2 | None = None,
    candidate: TargetedCompiledEvaluationQueryV0 | None = None,
    candidate_product_target: _ProductTarget | None = None,
    aggregate_limits: ProductInvocationAggregateLimitsV2 | None = None,
) -> ProductEvaluationInvocationV2:
    """Seal V2 intent without reading a live ledger or invoking an engine.

    The existing typed Query compiler remains the sole Query compiler.  This
    entry merely rejects V1-only features and establishes the product asset /
    profile target bindings that V1 did not need to carry.
    """

    if not isinstance(primary, TargetedCompiledEvaluationQueryV0):
        _fail("primary must be TargetedCompiledEvaluationQueryV0", "V2_PRIMARY_INVALID")
    if not isinstance(product_target, (ProductRuleV1, ProductPolicyV1)):
        _fail(
            "V2 execution requires a ProductRuleV1 or ProductPolicyV1", "V2_PRODUCT_TARGET_REQUIRED"
        )
    if not isinstance(profile, EvaluationExecutionProfileV2):
        _fail("profile must be EvaluationExecutionProfileV2", "V2_PROFILE_INVALID")
    if scenario is not None and not isinstance(scenario, ScenarioSpecV2):
        _fail("scenario must be ScenarioSpecV2", "V2_SCENARIO_INVALID")
    if (candidate is None) != (candidate_product_target is None):
        _fail(
            "candidate compiled Query and candidate Product target must appear together",
            "V2_CANDIDATE_TARGET_REQUIRED",
        )
    if candidate is not None and not isinstance(candidate, TargetedCompiledEvaluationQueryV0):
        _fail("candidate must be TargetedCompiledEvaluationQueryV0", "V2_CANDIDATE_INVALID")
    if candidate_product_target is not None and not isinstance(
        candidate_product_target, (ProductRuleV1, ProductPolicyV1)
    ):
        _fail("candidate Product target is invalid", "V2_CANDIDATE_TARGET_INVALID")
    if aggregate_limits is not None and not isinstance(
        aggregate_limits, ProductInvocationAggregateLimitsV2
    ):
        _fail(
            "aggregate_limits must be ProductInvocationAggregateLimitsV2",
            "PRODUCT_INVOCATION_AGGREGATE_LIMIT_INVALID",
        )
    if (
        primary.compiled_query.applicable_branch_ids
        or (candidate is not None and candidate.compiled_query.applicable_branch_ids)
    ) and profile.kind != "native_deterministic_v2":
        _fail(
            "branch witnesses currently require native deterministic V2",
            "BRANCH_WITNESS_ENGINE_UNSUPPORTED",
        )

    _assert_profile_compiler(profile)
    _assert_targeted_product_match(primary, product_target, side="primary")
    _assert_profile_target_inventory(
        profile,
        primary=product_target,
        candidate=candidate_product_target,
    )
    _assert_no_v1_only_query_features(primary)
    if candidate is not None:
        assert candidate_product_target is not None
        _assert_targeted_product_match(candidate, candidate_product_target, side="candidate")
        _assert_no_v1_only_query_features(candidate)
        _assert_candidate_projection(primary, candidate)
    _validate_profile_attachment_inventory(
        profile,
        primary=product_target,
        candidate=candidate_product_target,
    )
    return ProductEvaluationInvocationV2(
        graph,
        primary,
        product_target,
        profile,
        scenario,
        candidate,
        candidate_product_target,
        aggregate_limits,
    )


def execute_product_evaluation_invocation_v2(
    invocation: ProductEvaluationInvocationV2,
) -> EvaluationRunV2:
    """Capture, resolve, isolate, evaluate, and seal one V2 product run."""

    if not isinstance(invocation, ProductEvaluationInvocationV2):
        _fail("invocation must be ProductEvaluationInvocationV2", "V2_INVOCATION_INVALID")
    _assert_invocation_current(invocation)

    aggregate = (
        None
        if invocation.aggregate_limits is None
        else _ProductInvocationAggregateMeterV2(invocation.aggregate_limits)
    )
    if aggregate is not None:
        scenario_count = 0 if invocation.scenario is None else 1
        limits = invocation.aggregate_limits
        assert limits is not None
        scenario_limit = limits.max_scenarios
        if scenario_limit is not None and scenario_count > scenario_limit:
            aggregate._exceeded("max_scenarios", scenario_count, scenario_limit)
        aggregate.check_deadline()

    graph = invocation._graph
    base_schema_ir = ensure_schema_ir(dict(graph.schema_ir))
    schema_ir = _execution_schema_ir_v2(
        base_schema_ir,
        products=(invocation.product_target, invocation.candidate_product_target),
    )
    schema_pin = schema_digest(schema_ir)
    primary_program, primary_dependencies, primary_base, primary_traces = _materialize_program(
        invocation.primary,
        invocation.product_target,
        invocation.profile,
        schema_ir=schema_ir,
        side="primary",
    )
    candidate_program: CompiledDerivationPlan | None = None
    candidate_base: CompiledDerivationPlan | None = None
    candidate_dependencies: tuple[str, ...] = ()
    candidate_traces: tuple[RuleExprEvaluationTrace, ...] = ()
    if invocation.candidate is not None:
        assert invocation.candidate_product_target is not None
        candidate_program, candidate_dependencies, candidate_base, candidate_traces = _materialize_program(
            invocation.candidate,
            invocation.candidate_product_target,
            invocation.profile,
            schema_ir=schema_ir,
            side="candidate",
        )

    dependency_ids = tuple(sorted(set(primary_dependencies) | set(candidate_dependencies)))
    authored_function_predicate_ids = {
        _function_port_predicate_id(item.relation_predicate_id, port.name)
        for product in (invocation.product_target, invocation.candidate_product_target)
        for item in _functions_for(product)
        for port in (*item.function.inputs, item.function.output)
    }
    dependency_ids = _expand_virtual_entity_dependencies_v2(
        dependency_ids, schema_ir=base_schema_ir
    )
    # Capture once.  Everything after this point consumes only immutable
    # ProjectedFact tuples / V2 worlds; it does not reopen the caller ledger.
    base_view_digest = graph._view_snapshot_digest(query_typed_values=True)
    full_relation = project_view_facts_with_witness(graph.ledger, base_schema_ir)
    if graph._view_snapshot_digest(query_typed_values=True) != base_view_digest:
        _fail("FactGraph view changed during V2 capture", "V2_VIEW_CHANGED_DURING_CAPTURE")

    if invocation.scenario is not None:
        v1_spec = ScenarioSpecV1(tuple(item.operation for item in invocation.scenario.operations))
        try:
            scenario_dependencies = scenario_dependency_predicate_ids_v1(
                v1_spec,
                schema_index=graph._application_schema_index,
                admitted_relation=full_relation,
            )
        except ScenarioResolutionErrorV1 as exc:
            _raise_from(exc, prefix="Scenario dependency", default="V2_SCENARIO_DEPENDENCY_INVALID")
        dependency_ids = tuple(sorted(set(dependency_ids) | set(scenario_dependencies)))

    capture_dependency_ids = tuple(
        item for item in dependency_ids if item not in authored_function_predicate_ids
    )

    try:
        baseline_relation = select_dependency_relation_v1(
            full_relation, dependency_predicate_ids=capture_dependency_ids
        )
    except ScenarioResolutionErrorV1 as exc:
        _raise_from(exc, prefix="V2 dependency relation", default="V2_DEPENDENCY_INVALID")

    admissibility_digest = _token(
        "product_evaluation_v2_admission",
        {"mode": "captured_all", "dependency_predicate_ids": dependency_ids},
    )
    baseline_metadata = _baseline_metadata_by_witness(graph, baseline_relation)
    baseline_world: EffectiveWorldV2
    effective_world: EffectiveWorldV2
    if invocation.scenario is None:
        baseline_world = _baseline_world_v2(
            schema_digest=schema_pin,
            base_view_digest=base_view_digest,
            admissibility_digest=admissibility_digest,
            dependency_predicate_ids=capture_dependency_ids,
            relation=baseline_relation,
            metadata_by_witness=baseline_metadata,
            predicate_tags=_predicate_tags(schema_ir),
        )
        effective_world = baseline_world
    else:
        try:
            resolved_v1 = resolve_scenario_v1(
                v1_spec,
                schema_index=graph._application_schema_index,
                baseline_relation=baseline_relation,
                base_view_digest=base_view_digest,
                admissibility_digest=admissibility_digest,
            )
            resolved_v2 = resolve_scenario_v2_from_v1(
                spec=invocation.scenario,
                resolved_v1=resolved_v1,
                baseline_metadata_by_witness_id=baseline_metadata,
            )
        except (ScenarioResolutionErrorV1, ScenarioResolutionErrorV2) as exc:
            _raise_from(
                exc, prefix="Scenario V2 resolution", default="V2_SCENARIO_RESOLUTION_INVALID"
            )
        baseline_world = resolved_v2.baseline_world
        effective_world = resolved_v2.effective_world

    function_predicate_ids = tuple(sorted(authored_function_predicate_ids))
    baseline_world = _world_with_execution_schema_v2(
        baseline_world,
        schema_digest_value=schema_pin,
        function_predicate_ids=function_predicate_ids,
    )
    effective_world = _world_with_execution_schema_v2(
        effective_world,
        schema_digest_value=schema_pin,
        function_predicate_ids=function_predicate_ids,
    )

    _assert_world_profile_compatibility(invocation.profile, baseline_world)
    _assert_world_profile_compatibility(invocation.profile, effective_world)
    primary_plan = _run_plan(invocation.primary, invocation.product_target, side="primary")
    candidate_plan = (
        None
        if invocation.candidate is None
        else _run_plan(invocation.candidate, invocation.candidate_product_target, side="candidate")
    )
    baseline_capture = EvaluationReplayWorldV2("baseline", baseline_world)
    effective_capture = EvaluationReplayWorldV2("effective", effective_world)

    baseline_side = _execute_side(
        name="baseline",
        world=baseline_world,
        capture=baseline_capture,
        plan=primary_plan,
        program=primary_program,
        profile=invocation.profile,
        schema_ir=schema_ir,
        selection_shape=_selection_shape(invocation.primary),
        product=invocation.product_target,
        source_schema_index=graph._application_schema_index,
        traces=primary_traces if invocation.primary.compiled_query.applicable_branch_ids else (),
    )
    if aggregate is not None:
        aggregate.charge_side(baseline_side, baseline_capture)
        aggregate.check_deadline()
    effective_side = _execute_side(
        name="effective",
        world=effective_world,
        capture=effective_capture,
        plan=primary_plan,
        program=primary_program,
        profile=invocation.profile,
        schema_ir=schema_ir,
        selection_shape=_selection_shape(invocation.primary),
        product=invocation.product_target,
        source_schema_index=graph._application_schema_index,
        traces=primary_traces if invocation.primary.compiled_query.applicable_branch_ids else (),
    )
    if aggregate is not None:
        aggregate.charge_side(effective_side, effective_capture)
        aggregate.check_deadline()
    candidate_side: EvaluationRunSideV2 | None = None
    candidate_capture: EvaluationReplayWorldV2 | None = None
    if candidate_plan is not None:
        assert (
            candidate_program is not None
            and candidate_base is not None
            and invocation.candidate is not None
        )
        candidate_capture = EvaluationReplayWorldV2("candidate_effective", effective_world)
        candidate_side = _execute_side(
            name="candidate_effective",
            world=effective_world,
            capture=candidate_capture,
            plan=candidate_plan,
            program=candidate_program,
            profile=invocation.profile,
            schema_ir=schema_ir,
            selection_shape=_selection_shape(invocation.candidate),
            product=invocation.candidate_product_target,
            source_schema_index=graph._application_schema_index,
            traces=(
                candidate_traces
                if invocation.candidate is not None
                and invocation.candidate.compiled_query.applicable_branch_ids
                else ()
            ),
        )
        if aggregate is not None:
            aggregate.charge_side(candidate_side, candidate_capture)
            aggregate.check_deadline()

    _assert_function_observations_deterministic_v2(
        tuple(side for side in (baseline_side, effective_side, candidate_side) if side is not None)
    )
    if graph._view_snapshot_digest(query_typed_values=True) != base_view_digest:
        _fail(
            "source FactGraph changed during trusted in-process Function execution",
            "V2_VIEW_CHANGED_DURING_FUNCTION",
        )

    program_bytes = _encode_program_envelope(
        schema_ir=schema_ir,
        profile=invocation.profile,
        primary_plan=primary_plan,
        primary_program=primary_program,
        primary_base_program=primary_base,
        primary_target=invocation.primary,
        primary_product=invocation.product_target,
        candidate_plan=candidate_plan,
        candidate_program=candidate_program,
        candidate_base_program=candidate_base,
        candidate_target=invocation.candidate,
        candidate_product=invocation.candidate_product_target,
    )
    if len(program_bytes) > invocation.profile.capture.max_capture_bytes:
        _fail("V2 replay program exceeds profile capture budget", "V2_CAPTURE_LIMIT_EXCEEDED")
    if aggregate is not None:
        aggregate.charge_program_capture(len(program_bytes))
        aggregate.check_deadline()
    worlds: tuple[EvaluationReplayWorldV2, ...] = (
        (baseline_capture, effective_capture)
        if candidate_capture is None
        else (baseline_capture, effective_capture, candidate_capture)
    )
    payload = EvaluationReplayPayloadV2(
        schema_digest=schema_pin,
        # The payload's historical top-level pin names the primary address
        # space.  Each plan below carries its own pin, so a valid candidate
        # Policy may use an independently authored address space.
        address_space_digest=primary_plan.address_space_digest,
        profile_bytes=invocation.profile.to_bytes(),
        compiled_program_bytes=program_bytes,
        worlds=worlds,
    )
    if len(payload.compiled_program_bytes) > invocation.profile.capture.max_capture_bytes:
        _fail("V2 replay payload exceeds profile capture budget", "V2_CAPTURE_LIMIT_EXCEEDED")
    return EvaluationRunV2(
        primary_plan=primary_plan,
        profile=invocation.profile,
        replay_payload=payload,
        baseline=baseline_side,
        effective=effective_side,
        candidate_plan=candidate_plan,
        candidate_effective=candidate_side,
    )


def replay_product_evaluation_run_v2(run: EvaluationRunV2) -> EvaluationRunReplayV2:
    """Replay exactly one sealed V2 run without a graph, provider, or asset.

    A malformed/tampered payload raises a typed error.  A valid replay whose
    observations differ returns ``status='mismatch'`` rather than disguising
    the difference as a successful current evaluation.
    """

    if not isinstance(run, EvaluationRunV2):
        _fail("run must be EvaluationRunV2", "V2_REPLAY_INPUT_INVALID")
    try:
        assert_evaluation_run_v2_current(run)
    except Exception as exc:
        _raise_from(exc, prefix="V2 run", default="V2_REPLAY_PROTOCOL_INVALID")
    decoded = _decode_program_envelope(run)
    profile = run.profile
    baseline = _replay_side(
        declared=run.baseline,
        name="baseline",
        world=run.replay_payload.world("baseline").world,
        plan=run.primary_plan,
        program=decoded.primary_program,
        profile=profile,
        schema_ir=decoded.schema_ir,
        selection_shape=decoded.primary_selection_shape,
    )
    effective = _replay_side(
        declared=run.effective,
        name="effective",
        world=run.replay_payload.world("effective").world,
        plan=run.primary_plan,
        program=decoded.primary_program,
        profile=profile,
        schema_ir=decoded.schema_ir,
        selection_shape=decoded.primary_selection_shape,
    )
    candidate: EvaluationRunReplaySideV2 | None = None
    if run.candidate_plan is not None:
        if decoded.candidate_program is None or decoded.candidate_selection_shape is None:
            _fail("V2 replay program omits candidate", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
        candidate = _replay_side(
            declared=run.candidate_effective,
            name="candidate_effective",
            world=run.replay_payload.world("candidate_effective").world,
            plan=run.candidate_plan,
            program=decoded.candidate_program,
            profile=profile,
            schema_ir=decoded.schema_ir,
            selection_shape=decoded.candidate_selection_shape,
        )
    all_match = (
        baseline.frame_match
        and effective.frame_match
        and (candidate is None or candidate.frame_match)
    )
    return EvaluationRunReplayV2(
        run_digest=run.run_digest,
        replay_payload_digest=run.replay_payload.payload_digest,
        status="matched" if all_match else "mismatch",
        baseline=baseline,
        effective=effective,
        candidate_effective=candidate,
    )


# Short public spelling mirrors V1's detached replay helper.
replay_evaluation_run_v2 = replay_product_evaluation_run_v2


def choice_capture_from_evaluation_run_v2(
    run: EvaluationRunV2,
    *,
    side: Literal["primary", "candidate"] = "primary",
) -> WeightedChoiceTopologyV1 | None:
    """Return one replay-validated authored WeightedChoice topology, if present.

    This is deliberately a read-only extraction seam for product presentation.
    It validates the same sealed program envelope used by detached replay and
    returns only the captured topology (key, arms, weights and condition node
    ids).  It never resolves a live asset, chooses an arm, or claims a proof.
    """

    if side not in {"primary", "candidate"}:
        _fail("choice capture side is unsupported", "V2_CHOICE_CAPTURE_SIDE_INVALID")
    try:
        assert_evaluation_run_v2_current(run)
    except Exception as exc:
        _raise_from(exc, prefix="V2 choice capture run", default="V2_REPLAY_PROTOCOL_INVALID")
    _decode_program_envelope(run)
    envelope = _parse_canonical_json(
        run.replay_payload.compiled_program_bytes, label="V2 replay program"
    )
    row = _exact_keys(
        envelope,
        {
            "$type",
            "version",
            "schema",
            "schema_digest",
            "source_schema_digest",
            "profile_digest",
            "address_space_digest",
            "primary",
            "candidate",
        },
        label="V2 replay program",
    )
    record = row[side]
    if record is None:
        if side == "candidate":
            _fail("V2 choice capture candidate is absent", "V2_CHOICE_CAPTURE_SIDE_INVALID")
        _fail("V2 choice capture primary record is absent", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    if not isinstance(record, Mapping):
        _fail("V2 choice capture program record is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    capture = _choice_capture_from_wire(record.get("choice_capture"))
    if capture is None:
        return None
    return _choice_topology_from_validated_capture(capture)


def function_capture_from_evaluation_run_v2(
    run: EvaluationRunV2,
    *,
    side: Literal["primary", "candidate"] = "primary",
) -> tuple[CapturedFunctionDefinitionV2, ...]:
    """Return replay-validated Function definitions without executable code."""

    if side not in {"primary", "candidate"}:
        _fail("Function capture side is unsupported", "V2_FUNCTION_CAPTURE_SIDE_INVALID")
    try:
        assert_evaluation_run_v2_current(run)
    except Exception as exc:
        _raise_from(exc, prefix="V2 Function capture run", default="V2_REPLAY_PROTOCOL_INVALID")
    decoded = _decode_program_envelope(run)
    envelope = _parse_canonical_json(
        run.replay_payload.compiled_program_bytes, label="V2 replay program"
    )
    record = envelope.get(side) if isinstance(envelope, Mapping) else None
    if not isinstance(record, Mapping):
        _fail("V2 Function capture program record is absent", "V2_FUNCTION_CAPTURE_SIDE_INVALID")
    plan = run.primary_plan if side == "primary" else run.candidate_plan
    if plan is None:
        _fail("V2 Function capture plan is absent", "V2_FUNCTION_CAPTURE_SIDE_INVALID")
    carrier = _query_carrier_from_wire(
        record.get("query_carrier"),
        plan=plan,
        expected_schema_digest=envelope["source_schema_digest"],  # type: ignore[arg-type,index]
    )
    program = decoded.primary_program if side == "primary" else decoded.candidate_program
    if program is None:
        _fail("V2 Function capture program is absent", "V2_FUNCTION_CAPTURE_SIDE_INVALID")
    capture = _function_capture_from_wire(
        record.get("function_capture"),
        plan=plan,
        carrier=carrier,
        program=program,
        schema_ir=decoded.schema_ir,
    )
    if capture is None:
        return ()
    occurrences = capture["occurrences"]
    assert isinstance(occurrences, list)
    result: list[CapturedFunctionDefinitionV2] = []
    for occurrence in occurrences:
        assert isinstance(occurrence, Mapping)
        ports = occurrence["ports"]
        bindings = occurrence["input_bindings"]
        assert isinstance(ports, list) and isinstance(bindings, list)
        result.append(
            CapturedFunctionDefinitionV2(
                occurrence_alias=occurrence["alias"],  # type: ignore[arg-type]
                function_id=occurrence["function_id"],  # type: ignore[arg-type]
                function_version=occurrence["function_version"],  # type: ignore[arg-type]
                function_digest=occurrence["function_digest"],  # type: ignore[arg-type]
                signature_digest=occurrence["signature_digest"],  # type: ignore[arg-type]
                implementation_digest=occurrence["implementation_digest"],  # type: ignore[arg-type]
                relation_predicate_id=occurrence["relation_predicate_id"],  # type: ignore[arg-type]
                ports=tuple(
                    (item["name"], item["tag"], item["mode"], item["predicate_id"])
                    for item in ports
                    if isinstance(item, Mapping)
                ),  # type: ignore[misc]
                input_bindings=tuple(
                    (
                        item["port_name"],
                        item["source"]["occurrence_alias"],
                        item["source"]["port_name"],
                    )
                    for item in bindings
                    if isinstance(item, Mapping) and isinstance(item.get("source"), Mapping)
                ),  # type: ignore[misc]
                topology_digest=occurrence["topology_digest"],  # type: ignore[arg-type]
                asset_meta_json=json.dumps(
                    occurrence["asset_meta"],
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                asset_descriptor_digest=occurrence["asset_descriptor_digest"],  # type: ignore[arg-type]
                asset_binding_digest=occurrence["asset_binding_digest"],  # type: ignore[arg-type]
            )
        )
    return tuple(result)


def _assert_invocation_current(invocation: ProductEvaluationInvocationV2) -> None:
    _assert_profile_compiler(invocation.profile)
    _assert_targeted_product_match(invocation.primary, invocation.product_target, side="primary")
    _assert_profile_target_inventory(
        invocation.profile,
        primary=invocation.product_target,
        candidate=invocation.candidate_product_target,
    )
    _assert_no_v1_only_query_features(invocation.primary)
    if invocation.aggregate_limits is not None:
        ProductInvocationAggregateLimitsV2.__post_init__(invocation.aggregate_limits)
    if (
        (
            invocation.primary.compiled_query.applicable_branch_ids
            or (
                invocation.candidate is not None
                and invocation.candidate.compiled_query.applicable_branch_ids
            )
        )
        and invocation.profile.kind != "native_deterministic_v2"
    ):
        _fail(
            "branch witnesses currently require native deterministic V2",
            "BRANCH_WITNESS_ENGINE_UNSUPPORTED",
        )
    if invocation.scenario is not None:
        try:
            ScenarioSpecV2.__post_init__(invocation.scenario)
        except Exception as exc:
            _raise_from(exc, prefix="Scenario V2", default="V2_SCENARIO_INVALID")
    if (invocation.candidate is None) != (invocation.candidate_product_target is None):
        _fail("candidate target splice", "V2_INVOCATION_CANDIDATE_SPLICE")
    if invocation.candidate is not None:
        assert invocation.candidate_product_target is not None
        _assert_targeted_product_match(
            invocation.candidate, invocation.candidate_product_target, side="candidate"
        )
        _assert_no_v1_only_query_features(invocation.candidate)
        _assert_candidate_projection(invocation.primary, invocation.candidate)
    _validate_profile_attachment_inventory(
        invocation.profile,
        primary=invocation.product_target,
        candidate=invocation.candidate_product_target,
    )


def _assert_profile_compiler(profile: EvaluationExecutionProfileV2) -> None:
    try:
        assert_evaluation_execution_profile_v2_current(profile)
    except Exception as exc:
        _raise_from(exc, prefix="V2 profile", default="V2_PROFILE_INVALID")
    if profile.compiler_digest != GOAL_PLAN_V2_COMPILER_DIGEST:
        _fail(
            "V2 profile compiler pin is unsupported by this runner", "V2_PROFILE_COMPILER_MISMATCH"
        )
    if not profile.target_pins:
        _fail("V2 public execution requires profile target_pins", "V2_PROFILE_TARGET_PIN_REQUIRED")


def _assert_no_v1_only_query_features(targeted: TargetedCompiledEvaluationQueryV0) -> None:
    try:
        assert_targeted_evaluation_query_current(targeted)
    except Exception as exc:
        _raise_from(exc, prefix="V2 typed Query", default="V2_QUERY_INVALID")
    if targeted.expectations:
        _fail("V2 rows execution does not support V1 expectations", "V2_EXPECTATIONS_UNSUPPORTED")


def _assert_targeted_product_match(
    targeted: TargetedCompiledEvaluationQueryV0,
    product: _ProductTarget,
    *,
    side: _TargetSide,
) -> None:
    _assert_no_v1_only_query_features(targeted)
    try:
        assert_asset_binding_current_v1(product)
        _assert_weighted_topology_current(product)
    except Exception as exc:
        _raise_from(exc, prefix="Product asset", default="V2_ASSET_BINDING_INVALID")
    source = targeted.target.run_target
    expected_kind = "rule" if isinstance(product, ProductRuleV1) else "policy"
    expected_id = product.rule.id if isinstance(product, ProductRuleV1) else product.policy.id
    expected_version = (
        product.rule.version if isinstance(product, ProductRuleV1) else product.policy.version
    )
    if (
        source.original_target_kind != expected_kind
        or source.target_id != expected_id
        or source.target_version != expected_version
    ):
        _fail("compiled Query does not match Product target identity", "V2_TARGET_QUERY_SPLICE")
    if isinstance(product, ProductRuleV1):
        pins = source.rule_pins
        if len(pins) != 1 or (
            pins[0].rule_id,
            pins[0].rule_version,
            pins[0].rule_content_digest,
        ) != (product.rule.id, product.rule.version, product.rule.content_digest):
            _fail(
                "compiled Query does not match Product Rule content pin", "V2_TARGET_QUERY_SPLICE"
            )
    else:
        if source.address_space_digest != product.address_space.address_space_digest:
            _fail(
                "compiled Query does not match Product Policy address space",
                "V2_TARGET_QUERY_SPLICE",
            )
    # ``side`` is intentionally accepted here so callers cannot accidentally
    # reuse one compiled Query in the candidate slot without later profile
    # pin validation.
    if side not in {"primary", "candidate"}:  # pragma: no cover - Literal guard.
        _fail("V2 target side is invalid", "V2_TARGET_SIDE_INVALID")


def _product_pin(product: _ProductTarget, *, side: _TargetSide) -> EvaluationTargetPinV2:
    if isinstance(product, ProductRuleV1):
        return EvaluationTargetPinV2(
            side=side,
            target_kind="rule",
            target_id=product.rule.id,
            target_version=product.rule.version,
            target_digest=product.logical_identity_digest,
        )
    return EvaluationTargetPinV2(
        side=side,
        target_kind="policy",
        target_id=product.policy.id,
        target_version=product.policy.version,
        target_digest=product.logical_identity_digest,
    )


def _assert_profile_target_inventory(
    profile: EvaluationExecutionProfileV2,
    *,
    primary: _ProductTarget,
    candidate: _ProductTarget | None,
) -> None:
    expected = {_product_pin(primary, side="primary").pin_digest}
    if candidate is not None:
        expected.add(_product_pin(candidate, side="candidate").pin_digest)
    actual = {item.pin_digest for item in profile.target_pins}
    if actual != expected:
        _fail(
            "V2 profile target pins do not exactly cover this primary/candidate invocation",
            "V2_PROFILE_TARGET_PIN_MISMATCH",
        )


def _assert_candidate_projection(
    primary: TargetedCompiledEvaluationQueryV0,
    candidate: TargetedCompiledEvaluationQueryV0,
) -> None:
    left = tuple((item.alias, item.value_type) for item in primary.compiled_query.selections)
    right = tuple((item.alias, item.value_type) for item in candidate.compiled_query.selections)
    if left != right:
        _fail(
            "candidate Query must have the same selected shape", "V2_CANDIDATE_PROJECTION_MISMATCH"
        )


def _validate_profile_attachments(
    profile: EvaluationExecutionProfileV2,
    product: _ProductTarget,
    *,
    side: _TargetSide,
) -> ResolvedExecutionAttachmentsV2:
    """Prove attachment ownership and reject Rule/occurrence slot overlap."""

    pin = _product_pin(product, side=side)
    attachments = tuple(
        item for item in profile.attachments if item.target.pin_digest == pin.pin_digest
    )
    if profile.kind in {"native_deterministic_v2", "portable_deterministic_v2"}:
        if attachments:
            _fail("deterministic V2 profile has attachments", "V2_PROFILE_ATTACHMENT_UNSUPPORTED")
        return ResolvedExecutionAttachmentsV2(profile.profile_digest, ())

    known_occurrences: dict[str, tuple[str, str | None, str]] = {}
    if isinstance(product, ProductPolicyV1):
        known_occurrences = {
            item.occurrence.alias: (
                item.occurrence.rule.id,
                item.occurrence.rule.version,
                item.occurrence.rule.content_digest,
            )
            for item in product.address_space.occurrences
        }
    slots_by_attachment: list[ResolvedExecutionAttachmentV2] = []
    rule_slots: set[str] = set()
    occurrence_slots: set[str] = set()
    choice_nodes = {choice.node_id: choice for choice in _choices_for(product)}
    choice_attachment_nodes: set[str] = set()
    for attachment in attachments:
        slots: tuple[str, ...]
        if attachment.kind == "rule":
            expected_rules: tuple[tuple[str, str | None, str, str], ...]
            if isinstance(product, ProductRuleV1):
                expected_rules = (
                    (product.rule.id, product.rule.version, product.rule.content_digest, "target"),
                )
            else:
                expected_rules = tuple(
                    (rule_id, version, digest, alias)
                    for alias, (rule_id, version, digest) in known_occurrences.items()
                    if (rule_id, version, digest)
                    == (
                        attachment.rule_id,
                        attachment.rule_version,
                        _strip_token(attachment.rule_digest),
                    )
                )
            if not expected_rules:
                _fail(
                    "Rule attachment does not resolve in Product target",
                    "V2_PROFILE_RULE_TARGET_MISMATCH",
                )
            if any(
                (rule_id, version, digest)
                != (
                    attachment.rule_id,
                    attachment.rule_version,
                    _strip_token(attachment.rule_digest),
                )
                for rule_id, version, digest, _alias in expected_rules
            ):
                _fail(
                    "Rule attachment content pin mismatches target",
                    "V2_PROFILE_RULE_TARGET_MISMATCH",
                )
            slots = tuple(
                _token(
                    "product_v2_rule_attachment_slot", {"target": pin.pin_digest, "alias": alias}
                )
                for _rule_id, _version, _digest, alias in expected_rules
            )
            rule_slots.update(slots)
        elif attachment.kind == "occurrence":
            if not isinstance(product, ProductPolicyV1):
                _fail(
                    "occurrence attachment requires Policy Product target",
                    "V2_PROFILE_OCCURRENCE_TARGET_MISMATCH",
                )
            actual = known_occurrences.get(attachment.occurrence_alias or "")
            if actual != (
                attachment.rule_id,
                attachment.rule_version,
                _strip_token(attachment.rule_digest),
            ):
                _fail(
                    "occurrence attachment does not resolve exactly",
                    "V2_PROFILE_OCCURRENCE_TARGET_MISMATCH",
                )
            slots = (
                _token(
                    "product_v2_rule_attachment_slot",
                    {"target": pin.pin_digest, "alias": attachment.occurrence_alias},
                ),
            )
            occurrence_slots.update(slots)
        else:
            node_id = attachment.structural_node_id
            if node_id not in choice_nodes:
                _fail(
                    "choice attachment does not resolve in Product Policy",
                    "V2_PROFILE_CHOICE_TARGET_MISMATCH",
                )
            if node_id in choice_attachment_nodes:
                _fail("duplicate V2 choice attachment", "V2_PROFILE_CHOICE_ATTACHMENT_DUPLICATE")
            choice_attachment_nodes.add(node_id)
            slots = (
                _token(
                    "product_v2_choice_attachment_slot", {"target": pin.pin_digest, "node": node_id}
                ),
            )
        slots_by_attachment.append(
            ResolvedExecutionAttachmentV2(attachment.attachment_digest, slots)
        )
    if rule_slots & occurrence_slots:
        _fail(
            "Rule and occurrence V2 attachments overlap on the same Policy occurrence",
            "V2_PROFILE_ATTACHMENT_OVERLAP",
        )
    required_choice_nodes = set(choice_nodes)
    if required_choice_nodes != choice_attachment_nodes:
        _fail(
            "every authored WeightedChoice requires one explicit V2 choice activation attachment",
            "V2_WEIGHTED_CHOICE_ACTIVATION_REQUIRED",
        )
    return ResolvedExecutionAttachmentsV2(profile.profile_digest, tuple(slots_by_attachment))


def _validate_profile_attachment_inventory(
    profile: EvaluationExecutionProfileV2,
    *,
    primary: _ProductTarget,
    candidate: _ProductTarget | None,
) -> ResolvedExecutionAttachmentsV2:
    """Resolve every profile attachment exactly once across its target sides.

    ``validate_resolved_execution_attachments_v2`` deliberately requires
    complete profile coverage.  A side-local resolver is useful while building
    each program record, but using it directly for a primary/candidate profile
    used to reject a perfectly valid second target as if its attachments were
    missing.  Aggregate the side proofs here, then let the protocol own the
    exact-cover assertion.
    """

    primary_resolved = _validate_profile_attachments(profile, primary, side="primary")
    candidate_resolved = (
        ()
        if candidate is None
        else _validate_profile_attachments(profile, candidate, side="candidate").attachments
    )
    resolved = ResolvedExecutionAttachmentsV2(
        profile.profile_digest,
        (*primary_resolved.attachments, *candidate_resolved),
    )
    try:
        validate_resolved_execution_attachments_v2(profile, resolved)
    except Exception as exc:
        _raise_from(exc, prefix="V2 execution attachment", default="V2_PROFILE_ATTACHMENT_INVALID")
    return resolved


def _choices_for(product: _ProductTarget) -> tuple[WeightedChoiceTopologyV1, ...]:
    return product.weighted_choices if isinstance(product, ProductPolicyV1) else ()


def _functions_for(product: _ProductTarget | None) -> tuple[FunctionOccurrenceTopologyV1, ...]:
    if not isinstance(product, ProductPolicyV1):
        return ()
    return product.function_occurrences


def _function_entity_type(topology: FunctionOccurrenceTopologyV1) -> str:
    return f"FactGraphFunctionCallV1_{topology.topology_digest[7:23]}"


def _function_schema_ids(topology: FunctionOccurrenceTopologyV1) -> tuple[str, str, str]:
    entity_type = _function_entity_type(topology)
    return (
        entity_type,
        f"{entity_type}:exists",
        f"__factgraph_function_call_key_v1:{topology.topology_digest[7:]}",
    )


def _execution_schema_ir_v2(
    base_schema_ir: dict[str, Any],
    *,
    products: tuple[_ProductTarget | None, ...],
) -> dict[str, Any]:
    functions = tuple(
        sorted(
            (item for product in products for item in _functions_for(product)),
            key=lambda item: item.topology_digest,
        )
    )
    if not functions:
        return ensure_schema_ir(dict(base_schema_ir))
    try:
        schema = json.loads(
            json.dumps(
                base_schema_ir,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        _raise_from(exc, prefix="V2 schema", default="V2_SCHEMA_INVALID")
    assert isinstance(schema, dict)
    existing_predicates = {item["pred_id"] for item in schema["predicates"]}
    existing_entities = {item["entity_type"] for item in schema["entities"]}
    for topology in functions:
        entity_type, exists_id, identity_id = _function_schema_ids(topology)
        port_predicate_ids = tuple(
            _function_port_predicate_id(topology.relation_predicate_id, port.name)
            for port in (*topology.function.inputs, topology.function.output)
        )
        if entity_type in existing_entities or any(
            pred_id in existing_predicates
            for pred_id in (exists_id, identity_id, *port_predicate_ids)
        ):
            _fail(
                "Function execution schema namespace collides with the authored schema",
                "V2_FUNCTION_SCHEMA_COLLISION",
            )
        existing_entities.add(entity_type)
        existing_predicates.update((exists_id, identity_id, *port_predicate_ids))
        schema["entities"].append(
            {
                "entity_type": entity_type,
                "identity_fields": [{"name": "call_key", "type_domain": "string"}],
            }
        )
        schema["predicates"].extend(
            (
                {
                    "pred_id": exists_id,
                    "owner_type": entity_type,
                    "arity": 1,
                    "arg_specs": [{"name": "call", "type_domain": "entity_ref"}],
                    "cardinality": "single",
                    "group_key_indexes": [0],
                    "is_entity_exists": True,
                },
                {
                    "pred_id": identity_id,
                    "owner_type": entity_type,
                    "arity": 2,
                    "arg_specs": [
                        {"name": "call", "type_domain": "entity_ref"},
                        {"name": "call_key", "type_domain": "string"},
                    ],
                    "cardinality": "single",
                    "group_key_indexes": [0],
                    "py_field_name": "call_key",
                    "is_identity_field": True,
                },
                *(
                    {
                        "pred_id": predicate_id,
                        "owner_type": entity_type,
                        "arity": 2,
                        "arg_specs": [
                            {"name": "call", "type_domain": "entity_ref"},
                            {"name": port.name, "type_domain": port.scalar_domain},
                        ],
                        "cardinality": "single",
                        "group_key_indexes": [0],
                    }
                    for port, predicate_id in zip(
                        (*topology.function.inputs, topology.function.output),
                        port_predicate_ids,
                        strict=True,
                    )
                ),
            )
        )
        schema["projection"]["entities"].append(entity_type)
        schema["projection"]["predicates"].extend((exists_id, identity_id, *port_predicate_ids))
    schema["entities"] = sorted(schema["entities"], key=lambda item: item["entity_type"])
    schema["predicates"] = sorted(schema["predicates"], key=lambda item: item["pred_id"])
    schema["projection"]["entities"] = sorted(set(schema["projection"]["entities"]))
    schema["projection"]["predicates"] = sorted(set(schema["projection"]["predicates"]))
    return ensure_schema_ir(schema)


def _world_with_execution_schema_v2(
    world: EffectiveWorldV2,
    *,
    schema_digest_value: str,
    function_predicate_ids: tuple[str, ...],
) -> EffectiveWorldV2:
    return EffectiveWorldV2(
        schema_digest=schema_digest_value,
        base_view_digest=world.base_view_digest,
        admissibility_digest=world.admissibility_digest,
        dependency_predicate_ids=tuple(
            sorted(set(world.dependency_predicate_ids) | set(function_predicate_ids))
        ),
        facts=world.facts,
        closure_target_digests=world.closure_target_digests,
        operation_evidence=world.operation_evidence,
    )


def _assert_weighted_topology_current(product: _ProductTarget) -> None:
    """Recompute the mutable sidecar's canonical seal before every V2 use.

    Frozen dataclasses can still be tampered with through ``object.__setattr__``
    by hostile in-process code.  ``assert_asset_binding_current_v1`` verifies
    the surrounding Product wrapper; this additional check recomputes each
    choice's self-seal so V2 lowering never trusts a stale arm/topology tuple.
    """

    if not isinstance(product, ProductPolicyV1):
        return
    for choice in product.weighted_choices:
        # Constructing a value from the public fields forces the canonical
        # constructor to recompute all derived fields.  Compare every exposed
        # derived seal, not merely the outer tuple ordering.
        rebuilt = WeightedChoiceTopologyV1(
            choice_id=choice.choice_id,
            selection_key=choice.selection_key,
            arms=choice.arms,
            skeleton_node_id=choice.skeleton_node_id,
            kind=choice.kind,
        )
        if rebuilt != choice or rebuilt.topology_digest != choice.topology_digest:
            _fail("WeightedChoice topology seal is stale", "V2_WEIGHTED_CHOICE_TOPOLOGY_STALE")


def _materialize_program(
    targeted: TargetedCompiledEvaluationQueryV0,
    product: _ProductTarget,
    profile: EvaluationExecutionProfileV2,
    *,
    schema_ir: dict[str, Any],
    side: _TargetSide,
) -> tuple[
    CompiledDerivationPlan,
    tuple[str, ...],
    CompiledDerivationPlan,
    tuple[RuleExprEvaluationTrace, ...],
]:
    engine: Literal["native", "problog"] = (
        "problog" if profile.kind == "problog_point_v2" else "native"
    )
    try:
        base, traces = _materialize_adapter_derivation_plan(
            targeted.compiled_query._lowering_plan,
            engine=engine,
        )
        dependencies = portable_dependency_predicate_ids_v1(base, schema_ir=schema_ir)
    except (PortableEvaluationError, ValueError, TypeError) as exc:
        _raise_from(exc, prefix="V2 Query materialization", default="V2_QUERY_CAPABILITY_REJECTED")
    program = base
    if profile.kind == "problog_point_v2":
        if isinstance(product, ProductPolicyV1) and product.weighted_choices:
            try:
                program = lower_product_policy_weighted_choice_to_problog_v2(
                    target=product,
                    compiled_policy=targeted.target.compiled_policy,
                    plan=base,
                )
            except ProductWeightedChoiceProbLogV2Error as exc:
                _raise_from(
                    exc,
                    prefix="WeightedChoice ProbLog lowering",
                    default="V2_WEIGHTED_CHOICE_LOWERING_FAILED",
                )
        if profile.resources.timeout_ms is not None:
            program = replace(
                program,
                engine_options={"timeout": max(1, math.ceil(profile.resources.timeout_ms / 1000))},
            )
    elif profile.resources.timeout_ms is not None:
        # The Native evaluator currently has no closed timeout option.  Do not
        # accept a resource field and silently ignore it.
        _fail("native deterministic V2 timeout is not implemented", "V2_NATIVE_TIMEOUT_UNSUPPORTED")
    return program, dependencies, base, traces


def _baseline_metadata_by_witness(
    graph: "SDKStore",
    relation: Mapping[str, Sequence[ProjectedFact]],
) -> dict[str, ScenarioMetaV2]:
    output: dict[str, ScenarioMetaV2] = {}
    for facts in relation.values():
        for fact in facts:
            rows = graph.ledger.effective_meta_rows(asrt_id=fact.asrt_id)
            meta = {row.key: row.value for row in rows}
            raw_kind = meta.get("raw_kind")
            bound = meta.get("bound")
            if (raw_kind is None) != (bound is None):
                _fail(
                    "baseline uncertainty metadata is incomplete", "V2_BASELINE_SEMANTICS_INVALID"
                )
            semantics: FactSemanticsV2 | None = None
            if raw_kind is not None:
                try:
                    semantics = FactSemanticsV2.probabilistic_point(
                        _exact_point_bound(raw_kind, bound)
                    )
                except Exception as exc:
                    _raise_from(
                        exc,
                        prefix="baseline uncertainty metadata",
                        default="V2_BASELINE_SEMANTICS_INVALID",
                    )
            source = meta.get("source")
            source_loc = meta.get("source_loc")
            if (source is None) != (source_loc is None):
                _fail(
                    "baseline source/source_loc metadata is incomplete",
                    "V2_BASELINE_PROVENANCE_INVALID",
                )
            provenance: tuple[ProvenanceRefV1, ...] = ()
            if source is not None:
                if not isinstance(source, str) or not isinstance(source_loc, str):
                    _fail(
                        "baseline source/source_loc metadata is malformed",
                        "V2_BASELINE_PROVENANCE_INVALID",
                    )
                try:
                    provenance = (
                        ProvenanceRefV1(
                            source_ref=source,
                            locator=ProvenanceLocatorV1.opaque(source_loc),
                            origin_role="baseline_support",
                        ),
                    )
                except Exception as exc:
                    _raise_from(
                        exc, prefix="baseline provenance", default="V2_BASELINE_PROVENANCE_INVALID"
                    )
            note = meta.get("note")
            if note is not None and not isinstance(note, str):
                _fail("baseline note metadata is malformed", "V2_BASELINE_DISPLAY_INVALID")
            try:
                output[fact.asrt_id] = ScenarioMetaV2(
                    fact_semantics=semantics,
                    provenance=provenance,
                    display=ScenarioDisplayV2(note=note),
                )
            except Exception as exc:
                _raise_from(exc, prefix="baseline metadata", default="V2_BASELINE_METADATA_INVALID")
    return output


def _exact_point_bound(raw_kind: object, bound: object) -> object:
    if raw_kind != "probabilistic" or not isinstance(bound, (tuple, list)) or len(bound) != 2:
        _fail(
            "only exact probabilistic point bounds are supported", "V2_BASELINE_SEMANTICS_INVALID"
        )
    left = canonical_decimal_v2(bound[0], field_name="baseline bound[0]")
    right = canonical_decimal_v2(bound[1], field_name="baseline bound[1]")
    if left != right:
        _fail("baseline probability interval is unsupported", "V2_BASELINE_SEMANTICS_INVALID")
    return left


def _baseline_world_v2(
    *,
    schema_digest: str,
    base_view_digest: str,
    admissibility_digest: str,
    dependency_predicate_ids: tuple[str, ...],
    relation: Mapping[str, Sequence[ProjectedFact]],
    metadata_by_witness: Mapping[str, ScenarioMetaV2],
    predicate_tags: Mapping[str, tuple[str, ...]],
) -> EffectiveWorldV2:
    facts: list[EffectiveWorldFactV2] = []
    for predicate_id, rows in relation.items():
        tags = predicate_tags.get(predicate_id)
        if tags is None:
            _fail("captured predicate is missing schema tags", "V2_WORLD_SCHEMA_MISMATCH")
        for row in rows:
            values = _projected_fact_values_v2(row, predicate_id=predicate_id, tags=tags)
            metadata = metadata_by_witness.get(row.asrt_id, ScenarioMetaV2())
            facts.append(
                EffectiveWorldFactV2(
                    predicate_id=predicate_id,
                    witness_id=row.asrt_id,
                    values=values,
                    origin="baseline_support",
                    fact_semantics=metadata.fact_semantics,
                    provenance=metadata.provenance,
                    display=metadata.display,
                )
            )
    return build_effective_world_v2(
        schema_digest=schema_digest,
        base_view_digest=base_view_digest,
        admissibility_digest=admissibility_digest,
        dependency_predicate_ids=dependency_predicate_ids,
        facts=tuple(facts),
    )


def _projected_fact_values_v2(
    row: ProjectedFact,
    *,
    predicate_id: str,
    tags: tuple[str, ...],
) -> tuple[ScenarioValueV1, ...]:
    if len(row.fact_tuple) != len(tags):
        _fail("captured fact arity does not match schema", "V2_WORLD_SCHEMA_MISMATCH")
    try:
        return tuple(
            ScenarioValueV1.from_raw(tag, raw)  # type: ignore[arg-type]
            for tag, raw in zip(tags, row.fact_tuple, strict=True)
        )
    except Exception as exc:
        _raise_from(
            exc,
            prefix=f"captured fact {predicate_id}",
            default="V2_WORLD_SCHEMA_MISMATCH",
        )


def _assert_world_profile_compatibility(
    profile: EvaluationExecutionProfileV2,
    world: EffectiveWorldV2,
) -> None:
    for fact in world.facts:
        try:
            profile_accepts_fact_semantics_v2(profile, fact.fact_semantics)
        except Exception as exc:
            _raise_from(exc, prefix="V2 world semantics", default="V2_WORLD_SEMANTICS_UNSUPPORTED")
    if profile.kind in {
        "native_deterministic_v2",
        "portable_deterministic_v2",
    } and world_has_probabilistic_semantics_v2(world):
        _fail(
            "native deterministic V2 cannot execute probabilistic facts",
            "V2_WORLD_SEMANTICS_UNSUPPORTED",
        )


def _run_plan(
    targeted: TargetedCompiledEvaluationQueryV0,
    product: _ProductTarget | None,
    *,
    side: _TargetSide,
) -> EvaluationRunPlanV2:
    if product is None:  # pragma: no cover - guarded at invocation boundary.
        _fail("Product target is required", "V2_PRODUCT_TARGET_REQUIRED")
    pin = _product_pin(product, side=side)
    snapshot = asset_snapshot_v1(product)
    meta = snapshot["asset_meta"]
    if not isinstance(meta, dict):  # Product authoring invariant, rechecked here.
        _fail("Product asset snapshot metadata is malformed", "V2_ASSET_SNAPSHOT_INVALID")
    if meta.get("state") == "absent":
        descriptor_bytes = None
        descriptor_digest = None
    else:
        descriptor_bytes = _canonical_json_bytes(meta, label="V2 asset descriptor")
        descriptor_digest = snapshot.get("descriptor_digest")
    return EvaluationRunPlanV2(
        target=pin,
        query_digest=_query_token(targeted),
        asset_descriptor_bytes=descriptor_bytes,
        asset_descriptor_digest=descriptor_digest if isinstance(descriptor_digest, str) else None,
        asset_binding_digest=_require_token(
            snapshot.get("asset_binding_digest"), "V2 asset binding"
        ),
        address_space_digest=_address_space_token(targeted),
    )


def _execute_side(
    *,
    name: Literal["baseline", "effective", "candidate_effective"],
    world: EffectiveWorldV2,
    capture: EvaluationReplayWorldV2,
    plan: EvaluationRunPlanV2,
    program: CompiledDerivationPlan,
    profile: EvaluationExecutionProfileV2,
    schema_ir: dict[str, Any],
    selection_shape: tuple[tuple[str, str], ...],
    product: _ProductTarget | None = None,
    source_schema_index: Any | None = None,
    captured_function_materializations: tuple[EvaluationFunctionMaterializationV2, ...] = (),
    traces: tuple[RuleExprEvaluationTrace, ...] = (),
) -> EvaluationRunSideV2:
    frames, function_materializations = _execute_program_on_world(
        world=world,
        program=program,
        profile=profile,
        schema_ir=schema_ir,
        selection_shape=selection_shape,
        product=product,
        source_schema_index=source_schema_index,
        captured_function_materializations=captured_function_materializations,
        side=name,
        traces=traces,
    )
    return EvaluationRunSideV2(
        name=name,
        plan_digest=plan.plan_digest,
        world_capture_digest=capture.world_capture_digest,
        engine_frames=frames,
        expectation_support=(
            "unsupported" if profile.kind == "problog_point_v2" else "not_requested"
        ),
        function_materializations=function_materializations,
    )


def _execute_program_on_world(
    *,
    world: EffectiveWorldV2,
    program: CompiledDerivationPlan,
    profile: EvaluationExecutionProfileV2,
    schema_ir: dict[str, Any],
    selection_shape: tuple[tuple[str, str], ...],
    product: _ProductTarget | None = None,
    source_schema_index: Any | None = None,
    captured_function_materializations: tuple[EvaluationFunctionMaterializationV2, ...] = (),
    side: Literal["baseline", "effective", "candidate_effective"] = "effective",
    traces: tuple[RuleExprEvaluationTrace, ...] = (),
) -> tuple[
    tuple[EvaluationEngineFrameV2, ...],
    tuple[EvaluationFunctionMaterializationV2, ...],
]:
    store, probability_materialization = _materialize_world_store_v2(
        world, schema_ir=schema_ir, profile=profile
    )
    functions = _functions_for(product)
    if functions and captured_function_materializations:
        _fail(
            "live and captured Function materializations cannot be mixed",
            "V2_FUNCTION_MATERIALIZATION_SPLICE",
        )
    if functions:
        if not isinstance(product, ProductPolicyV1) or source_schema_index is None:
            _fail(
                "live Function materialization requires its Product Policy context",
                "V2_FUNCTION_CONTEXT_REQUIRED",
            )
        function_materializations = _materialize_function_occurrences_v2(
            store=store,
            product=product,
            functions=functions,
            source_schema_index=source_schema_index,
            execution_schema_ir=schema_ir,
            profile=profile,
        )
    else:
        function_materializations = captured_function_materializations
        _inject_captured_function_materializations_v2(
            store=store,
            materializations=function_materializations,
            schema_ir=schema_ir,
        )
    if profile.kind == "native_deterministic_v2":
        if traces:
            store._capture_all_query_style_supports = True
        outputs = _evaluate_engine(engine="native", store=store, program=program, profile=profile)
        rows = _selected_rows(
            outputs,
            selection_shape=selection_shape,
            probability_required=False,
            max_rows=profile.resources.max_rows,
        )
        witnesses = _branch_witnesses_v2(
            outputs,
            rows=rows,
            selection_shape=selection_shape,
            store=store,
            traces=traces,
            side=side,
        )
        return (
            EvaluationEngineFrameV2(
                "native", "succeeded", rows, branch_witnesses=witnesses
            ),
        ), function_materializations
    if profile.kind == "portable_deterministic_v2":
        relation = _portable_relation_with_functions_v2(
            world=world,
            program=program,
            schema_ir=schema_ir,
            materializations=function_materializations,
        )
        try:
            portable = execute_portable_deterministic_v1(
                program,
                schema_ir=schema_ir,
                effective_relations=relation,
            )
        except PortableEvaluationError as exc:
            _raise_from(
                exc,
                prefix="V2 portable deterministic execution",
                default="V2_PORTABLE_EXECUTION_FAILED",
            )
        frames: list[EvaluationEngineFrameV2] = []
        for execution in portable.executions:
            converted: list[EvaluationSelectedRowV2] = []
            for portable_row in execution.rows:
                if len(portable_row.terms) != len(selection_shape):
                    _fail(
                        "portable row does not align with V2 Query selections",
                        "V2_PROJECTION_WIDTH_MISMATCH",
                    )
                values: list[tuple[str, GoalValueV1]] = []
                for (alias, expected_tag), (actual_tag, raw) in zip(
                    selection_shape, portable_row.terms, strict=True
                ):
                    if actual_tag != expected_tag:
                        _fail(
                            "portable row type does not align with V2 Query selections",
                            "V2_PROJECTION_TYPE_MISMATCH",
                        )
                    values.append(
                        (
                            alias,
                            GoalValueV1(
                                cast(
                                    Literal[
                                        "entity_ref",
                                        "string",
                                        "int",
                                        "float64",
                                        "bool",
                                        "bytes",
                                        "time",
                                        "uuid",
                                    ],
                                    actual_tag,
                                ),
                                raw,
                            ),
                        )
                    )
                converted.append(EvaluationSelectedRowV2(tuple(values)))
            frames.append(
                EvaluationEngineFrameV2(
                    cast(Literal["native", "souffle", "problog"], execution.engine),
                    "succeeded",
                    tuple(converted),
                )
            )
        return tuple(frames), function_materializations
    outputs = _evaluate_engine(engine="problog", store=store, program=program, profile=profile)
    rows = _selected_rows(
        outputs,
        selection_shape=selection_shape,
        probability_required=True,
        max_rows=profile.resources.max_rows,
        suppress_zero_probability_rows=(
            probability_materialization is not None
            and any(item.action == "omitted_zero" for item in probability_materialization.entries)
        ),
    )
    # Profile engine order is protocol-fixed: problog, native, souffle.
    return (
        EvaluationEngineFrameV2(
            "problog",
            "succeeded",
            rows,
            probability_materialization=probability_materialization,
        ),
        EvaluationEngineFrameV2(
            "native", "unsupported", diagnostic_code="V2_PROBABILISTIC_NATIVE_UNSUPPORTED"
        ),
        EvaluationEngineFrameV2(
            "souffle", "unsupported", diagnostic_code="V2_PROBABILISTIC_SOUFFLE_UNSUPPORTED"
        ),
    ), function_materializations


def _portable_relation_with_functions_v2(
    *,
    world: EffectiveWorldV2,
    program: CompiledDerivationPlan,
    schema_ir: dict[str, Any],
    materializations: tuple[EvaluationFunctionMaterializationV2, ...],
) -> dict[str, tuple[ProjectedFact, ...]]:
    """Build the exact portable dependency relation after Function materialization."""

    dependencies = portable_dependency_predicate_ids_v1(program, schema_ir=schema_ir)
    world_relation = effective_world_v2_relation(world)
    relation: dict[str, list[ProjectedFact]] = {
        predicate_id: [
            ProjectedFact(
                fact.witness_id,
                tuple(value.to_raw() for value in fact.values),
            )
            for fact in world_relation.get(predicate_id, ())
        ]
        for predicate_id in dependencies
    }
    for materialization in materializations:
        port_predicates = tuple(
            _function_port_predicate_id(materialization.relation_predicate_id, name)
            for name, _tag, _mode in materialization.ports
        )
        if any(predicate_id not in relation for predicate_id in port_predicates):
            _fail(
                "Function materialization is not a dependency of the portable program",
                "V2_FUNCTION_PROGRAM_MISMATCH",
            )
        for call in materialization.calls:
            for name, value in (*call.inputs, call.output):
                predicate_id = _function_port_predicate_id(
                    materialization.relation_predicate_id, name
                )
                relation[predicate_id].append(
                    ProjectedFact(
                        _token(
                            "product_function_port_witness_v1",
                            {"call_digest": call.call_digest, "port_name": name},
                        ),
                        (call.call_key, value.value),
                    )
                )
    return {predicate_id: tuple(rows) for predicate_id, rows in relation.items()}


def _materialize_function_occurrences_v2(
    *,
    store: Store,
    product: ProductPolicyV1,
    functions: tuple[FunctionOccurrenceTopologyV1, ...],
    source_schema_index: Any,
    execution_schema_ir: dict[str, Any],
    profile: EvaluationExecutionProfileV2,
) -> tuple[EvaluationFunctionMaterializationV2, ...]:
    execution_index = build_schema_index(execution_schema_ir)
    by_alias = {item.occurrence.alias: item for item in product.address_space.occurrences}
    materializations: list[EvaluationFunctionMaterializationV2] = []
    for topology in functions:
        source_alias = topology.input_bindings[0].source.occurrence_alias
        source_managed = by_alias.get(source_alias)
        if source_managed is None or any(
            item.source.occurrence_alias != source_alias for item in topology.input_bindings
        ):
            _fail(
                "Function input source occurrence is absent or inconsistent",
                "V2_FUNCTION_INPUT_SOURCE_INVALID",
            )
        source_space = SemanticAddressSpace((source_managed,))
        source_policy = Policy(
            f"__factgraph_function_input_v1__{topology.alias}",
            PolicyOccurrence(source_alias),
        )
        try:
            compiled_policy = compile_policy(
                source_policy,
                address_space=source_space,
                schema_index=source_schema_index,
            )
            input_query = EvaluationQuery(
                compiled_policy.policy_digest,
                tuple(
                    EvaluationQuerySelection(item.port_name, item.source)
                    for item in topology.input_bindings
                ),
            )
            compiled_query = compile_evaluation_query(
                input_query,
                compiled_policy=compiled_policy,
                address_space=source_space,
                schema_index=source_schema_index,
            )
            input_program, _traces = _materialize_adapter_derivation_plan(
                compiled_query._lowering_plan,
                engine="native",
            )
            outputs = _evaluate_engine(
                engine="native",
                store=store,
                program=input_program,
                profile=profile,
            )
            input_rows = _selected_rows(
                outputs,
                selection_shape=tuple(
                    (item.name, item.scalar_domain) for item in topology.function.inputs
                ),
                probability_required=False,
                max_rows=profile.resources.max_rows,
            )
        except ProductEvaluationRuntimeErrorV2:
            raise
        except Exception as exc:
            _raise_from(
                exc,
                prefix=f"Function {topology.alias} input materialization",
                default="V2_FUNCTION_INPUT_MATERIALIZATION_FAILED",
            )

        calls: list[EvaluationFunctionCallV2] = []
        for row in input_rows:
            by_name = dict(row.values)
            ordered_inputs = tuple(
                (port.name, by_name[port.name]) for port in topology.function.inputs
            )
            try:
                raw_output = topology.function.implementation(
                    *(value.value for _name, value in ordered_inputs)
                )
            except Exception as exc:
                _raise_from(
                    exc,
                    prefix=f"Function {topology.alias} invocation",
                    default="V2_FUNCTION_INVOCATION_FAILED",
                )
            try:
                output = GoalValueV1(
                    topology.function.output.scalar_domain,
                    raw_output,
                )
            except Exception as exc:
                _raise_from(
                    exc,
                    prefix=f"Function {topology.alias} output",
                    default="V2_FUNCTION_OUTPUT_INVALID",
                )
            call_key_token = _token(
                "product_function_call_key_v1",
                {
                    "occurrence_alias": topology.alias,
                    "function_digest": topology.function.logical_identity_digest,
                    "inputs": tuple((name, value.value_digest) for name, value in ordered_inputs),
                },
            )
            entity_type, _exists_id, _identity_id = _function_schema_ids(topology)
            try:
                call_key = encode_entity_ref(
                    EntityRef(entity_type, {"call_key": call_key_token}),
                    index=execution_index,
                )
            except Exception as exc:
                _raise_from(
                    exc,
                    prefix="Function call identity",
                    default="V2_FUNCTION_CALL_IDENTITY_INVALID",
                )
            call = EvaluationFunctionCallV2(
                occurrence_alias=topology.alias,
                function_digest=topology.function.logical_identity_digest,
                implementation_digest=topology.function.implementation_digest,
                relation_predicate_id=topology.relation_predicate_id,
                call_key=call_key,
                inputs=ordered_inputs,
                output=(topology.function.output.name, output),
            )
            _insert_function_call_v2(store, call)
            calls.append(call)
        materializations.append(
            EvaluationFunctionMaterializationV2(
                occurrence_alias=topology.alias,
                function_digest=topology.function.logical_identity_digest,
                signature_digest=topology.function.signature_digest,
                implementation_digest=topology.function.implementation_digest,
                relation_predicate_id=topology.relation_predicate_id,
                ports=tuple(
                    (port.name, port.scalar_domain, "input") for port in topology.function.inputs
                )
                + (
                    (
                        topology.function.output.name,
                        topology.function.output.scalar_domain,
                        "output",
                    ),
                ),
                calls=tuple(calls),
            )
        )
    return tuple(materializations)


def _insert_function_call_v2(store: Store, call: EvaluationFunctionCallV2) -> None:
    try:
        for name, value in (*call.inputs, call.output):
            set_field(
                store.ledger,
                _function_port_predicate_id(call.relation_predicate_id, name),
                call.call_key,
                [(value.tag, value.value)],
            )
    except Exception as exc:
        _raise_from(
            exc,
            prefix=f"Function {call.occurrence_alias} relation materialization",
            default="V2_FUNCTION_RELATION_MATERIALIZATION_FAILED",
        )


def _assert_function_observations_deterministic_v2(
    sides: tuple[EvaluationRunSideV2, ...],
) -> None:
    observed: dict[tuple[str, tuple[str, ...]], str] = {}
    for side in sides:
        for materialization in side.function_materializations:
            for call in materialization.calls:
                key = (
                    call.function_digest,
                    tuple(value.value_digest for _name, value in call.inputs),
                )
                previous = observed.setdefault(key, call.output[1].value_digest)
                if previous != call.output[1].value_digest:
                    _fail(
                        "Function returned different outputs for the same typed inputs in one run",
                        "V2_FUNCTION_NONDETERMINISTIC_OUTPUT",
                    )


def _inject_captured_function_materializations_v2(
    *,
    store: Store,
    materializations: tuple[EvaluationFunctionMaterializationV2, ...],
    schema_ir: dict[str, Any],
) -> None:
    predicate_ids = {item["pred_id"] for item in schema_ir["predicates"]}
    for materialization in materializations:
        port_predicate_ids = tuple(
            _function_port_predicate_id(materialization.relation_predicate_id, name)
            for name, _tag, _mode in materialization.ports
        )
        if any(predicate_id not in predicate_ids for predicate_id in port_predicate_ids):
            _fail(
                "captured Function relation is absent from replay schema",
                "V2_FUNCTION_REPLAY_SCHEMA_MISMATCH",
            )
        for call in materialization.calls:
            _insert_function_call_v2(store, call)


def _evaluate_engine(
    *,
    engine: Literal["native", "problog"],
    store: Store,
    program: CompiledDerivationPlan,
    profile: EvaluationExecutionProfileV2,
) -> list[DerivationOutput]:
    semantics: SemanticsProfile | None = None
    if engine == "problog":
        if not isinstance(profile.semantics, ProbLogPointSemanticsV2):
            _fail("ProbLog V2 profile has malformed semantics", "V2_PROFILE_INVALID")
        # Register exactly the selected adapter inside this isolated call.
        import factgraph.adapters.problog  # noqa: F401

        semantics = SemanticsProfile(
            name=profile.name or "factgraph-product-problog-v2",
            engine="problog",
            uncertainty_projection={
                "probabilistic": {
                    "policy": "identity_probability",
                    "materialization": profile.semantics.materialization,
                },
                "fallback": "reject_unconfigured",
            },
            fallback="reject_unconfigured",
        )
    try:
        outputs = evaluate_derivation_plans(
            DerivationEvaluateRequest(plans=(program,), engine=engine, semantics_profile=semantics),
            store=store,
        )
    except Exception as exc:
        _raise_from(exc, prefix=f"V2 {engine} execution", default="V2_ENGINE_EXECUTION_FAILED")
    if not all(
        isinstance(item, DerivationOutput) for item in outputs
    ):  # pragma: no cover - runtime seam.
        _fail("engine returned non-DerivationOutput", "V2_ENGINE_OUTPUT_INVALID")
    return outputs


def _selected_rows(
    outputs: Sequence[DerivationOutput],
    *,
    selection_shape: tuple[tuple[str, str], ...],
    probability_required: bool,
    max_rows: int,
    suppress_zero_probability_rows: bool = False,
) -> tuple[EvaluationSelectedRowV2, ...]:
    shape = selection_shape
    rows: dict[str, EvaluationSelectedRowV2] = {}
    for output in outputs:
        # ProbLog prints a zero-confidence placeholder for a query whose only
        # support was a declared p=0 Scenario premise.  It has unbound terms,
        # so it is not an observed selected row.  The sealed materialization
        # frame records the omitted input explicitly; suppress only in that
        # exact circumstance rather than weakening normal projection checks.
        if (
            suppress_zero_probability_rows
            and probability_required
            and output.confidence_kind == "probability"
            and output.confidence == 0.0
        ):
            continue
        if output.candidate_kind != "fact" or not isinstance(output.payload, dict):
            _fail("engine output is not a query-style fact row", "V2_ENGINE_OUTPUT_INVALID")
        raw_terms = output.payload.get("terms")
        if not isinstance(raw_terms, list) or len(raw_terms) != len(shape):
            _fail(
                "engine output terms do not align with V2 Query selections",
                "V2_PROJECTION_WIDTH_MISMATCH",
            )
        values: list[tuple[str, GoalValueV1]] = []
        for (alias, expected_tag), raw_term in zip(shape, raw_terms, strict=True):
            values.append((alias, _goal_value_from_term(raw_term, expected_tag)))
        point_probability: str | None = None
        if probability_required:
            if output.confidence_kind != "probability" or output.confidence is None:
                _fail(
                    "ProbLog point output lacks probability observation",
                    "V2_PROBLOG_PROBABILITY_MISSING",
                )
            try:
                point_probability = canonical_decimal_v2(
                    output.confidence, field_name="ProbLog output probability"
                )
            except Exception as exc:
                _raise_from(
                    exc,
                    prefix="ProbLog output probability",
                    default="V2_PROBLOG_PROBABILITY_INVALID",
                )
            if Decimal(point_probability) < 0 or Decimal(point_probability) > 1:
                _fail(
                    "ProbLog point observation is outside [0, 1]", "V2_PROBLOG_PROBABILITY_INVALID"
                )
        elif output.confidence is not None or output.confidence_kind != "none":
            _fail(
                "native deterministic output unexpectedly has uncertainty",
                "V2_NATIVE_OUTPUT_SEMANTICS_INVALID",
            )
        row = EvaluationSelectedRowV2(tuple(values), point_probability=point_probability)
        existing = rows.get(row.row_identity_digest)
        if existing is not None and existing.observation_digest != row.observation_digest:
            _fail(
                "engine produced conflicting observations for one selected row",
                "V2_ROW_OBSERVATION_CONFLICT",
            )
        rows[row.row_identity_digest] = row
    if len(rows) > max_rows:
        _fail("V2 execution exceeded profile max_rows", "V2_RESOURCE_MAX_ROWS_EXCEEDED")
    return tuple(sorted(rows.values(), key=lambda item: item.observation_digest))


def _branch_witnesses_v2(
    outputs: Sequence[DerivationOutput],
    *,
    rows: tuple[EvaluationSelectedRowV2, ...],
    selection_shape: tuple[tuple[str, str], ...],
    store: Store,
    traces: tuple[RuleExprEvaluationTrace, ...],
    side: Literal["baseline", "effective", "candidate_effective"],
) -> tuple[BranchWitnessV2, ...]:
    if not traces:
        return ()
    branch_by_case = {trace.runtime_case_index: trace.branch_id for trace in traces}
    if len(branch_by_case) != len(traces):
        _fail("branch trace case indexes are ambiguous", "BRANCH_WITNESS_TRACE_INVALID")
    retained_rows = {row.row_identity_digest for row in rows}
    witnesses: dict[str, BranchWitnessV2] = {}
    for output in outputs:
        artifact = store._lookup_support_artifact(output.support_digest)
        if artifact is None:
            _fail(
                "native branch-aware output lacks its support artifact",
                "BRANCH_WITNESS_SUPPORT_MISSING",
            )
        try:
            case_index = _receipt_case_index(artifact)
        except Exception as exc:
            _raise_from(
                exc,
                prefix="branch witness support",
                default="BRANCH_WITNESS_SUPPORT_INVALID",
            )
        projected = _selected_rows(
            (output,),
            selection_shape=selection_shape,
            probability_required=False,
            max_rows=1,
        )
        if len(projected) != 1 or projected[0].row_identity_digest not in retained_rows:
            _fail(
                "branch witness cannot be correlated with a retained result row",
                "BRANCH_WITNESS_ROW_MISMATCH",
            )
        evidence_references = tuple(
            sorted(
                {
                    output.support_digest,
                    *(
                        edge.child_support_digest
                        for edge in artifact.rule_ref_edges
                        if edge.child_support_digest is not None
                    ),
                }
            )
        )
        branch_id = branch_by_case.get(case_index)
        if branch_id is None:
            _fail(
                "native support case is outside the compiled branch inventory",
                "BRANCH_WITNESS_TRACE_MISMATCH",
            )
        witness = BranchWitnessV2(
            compiled_branch_id=branch_id,
            evaluation_side=side,
            row_identity_digest=projected[0].row_identity_digest,
            proof_identity_digest=output.support_digest,
            evidence_references=evidence_references,
        )
        witnesses.setdefault(witness.witness_digest, witness)
    return tuple(sorted(witnesses.values(), key=lambda item: item.witness_digest))


def _goal_value_from_term(value: object, expected_tag: str) -> GoalValueV1:
    if not isinstance(value, Mapping):
        _fail("engine output term is malformed", "V2_PROJECTION_TERM_INVALID")
    if expected_tag == "entity_ref":
        if set(value) != {"kind", "value"} or value.get("kind") != "entity_ref":
            _fail("engine output entity reference term is malformed", "V2_PROJECTION_TYPE_MISMATCH")
        raw = value.get("value")
    else:
        if (
            set(value) != {"kind", "tag", "value"}
            or value.get("kind") != "literal"
            or value.get("tag") != expected_tag
        ):
            _fail(
                "engine output term type mismatches V2 Query selection",
                "V2_PROJECTION_TYPE_MISMATCH",
            )
        raw = value.get("value")
    try:
        _index, normalized, tag = claim_args_from_rest_terms([(expected_tag, raw)])[0]
        return GoalValueV1(
            cast(
                Literal["entity_ref", "string", "int", "float64", "bool", "bytes", "time", "uuid"],
                tag,
            ),
            normalized,
        )
    except Exception as exc:
        _raise_from(exc, prefix="engine output value", default="V2_PROJECTION_VALUE_INVALID")


def _materialize_world_store_v2(
    world: EffectiveWorldV2,
    *,
    schema_ir: dict[str, Any],
    profile: EvaluationExecutionProfileV2,
) -> tuple[Store, EvaluationProbabilityMaterializationV2 | None]:
    _assert_world_profile_compatibility(profile, world)
    predicate_tags = _predicate_tags(schema_ir)
    store = Store(schema_ir)
    probability_materialization = (
        problog_probability_materialization_v2_from_world(world)
        if profile.kind == "problog_point_v2"
        else None
    )
    materialized_by_fact = (
        {}
        if probability_materialization is None
        else {entry.fact_evidence_digest: entry for entry in probability_materialization.entries}
    )
    for fact in world.facts:
        tags = predicate_tags.get(fact.predicate_id)
        if tags is None or len(tags) != len(fact.values) or not tags or tags[0] != "entity_ref":
            _fail("V2 world fact does not match captured schema", "V2_WORLD_SCHEMA_MISMATCH")
        if tuple(value.tag for value in fact.values) != tags:
            _fail("V2 world fact tags do not match captured schema", "V2_WORLD_SCHEMA_MISMATCH")
        raw_values = tuple(value.to_raw() for value in fact.values)
        if not isinstance(raw_values[0], str):
            _fail("V2 world entity reference is malformed", "V2_WORLD_SCHEMA_MISMATCH")
        schema_predicate = next(
            (
                item
                for item in schema_ir.get("predicates", ())
                if isinstance(item, Mapping) and item.get("pred_id") == fact.predicate_id
            ),
            None,
        )
        if isinstance(schema_predicate, Mapping) and schema_predicate.get(
            "is_entity_exists"
        ) is True:
            # Entity-domain authority is the complete active Identity bundle.
            # The captured virtual row is evidence, never a persisted premise.
            continue
        meta: dict[str, object] | None = None
        if fact.fact_semantics is not None:
            entry = materialized_by_fact.get(fact.evidence_fact_digest)
            if entry is None:
                _fail(
                    "V2 fact semantic is missing its ProbLog materialization",
                    "V2_WORLD_MATERIALIZATION_FAILED",
                )
            if entry.action == "omitted_zero":
                # The sealed world still records the caller's p=0 premise,
                # while the legacy ProbLog source deliberately omits it: its
                # fact syntax accepts only probabilities in (0, 1].
                continue
            try:
                numeric_probability = float.fromhex(entry.float64_hex)
            except ValueError as exc:  # pragma: no cover - projection DTO guards it.
                _raise_from(
                    exc,
                    prefix="V2 point probability materialization",
                    default="V2_WORLD_MATERIALIZATION_FAILED",
                )
            if not math.isfinite(numeric_probability) or not 0.0 < numeric_probability <= 1.0:
                _fail(
                    "V2 point probability cannot materialize into core metadata",
                    "V2_WORLD_MATERIALIZATION_FAILED",
                )
            meta = {
                "raw_kind": "probabilistic",
                "bound": [numeric_probability, numeric_probability],
            }
        try:
            set_field(
                store.ledger,
                fact.predicate_id,
                raw_values[0],
                list(zip(tags[1:], raw_values[1:], strict=True)),
                meta=meta,
            )
        except Exception as exc:
            _raise_from(
                exc,
                prefix="V2 isolated world materialization",
                default="V2_WORLD_MATERIALIZATION_FAILED",
            )
    return store, probability_materialization


def _expand_virtual_entity_dependencies_v2(
    dependency_ids: tuple[str, ...],
    *,
    schema_ir: Mapping[str, Any],
) -> tuple[str, ...]:
    """Capture Identity prerequisites for every virtual Entity-domain input."""

    predicates = tuple(
        item for item in schema_ir.get("predicates", ()) if isinstance(item, Mapping)
    )
    by_id = {
        item["pred_id"]: item for item in predicates if isinstance(item.get("pred_id"), str)
    }
    expanded = set(dependency_ids)
    for predicate_id in dependency_ids:
        predicate = by_id.get(predicate_id)
        if predicate is None or predicate.get("is_entity_exists") is not True:
            continue
        owner = predicate.get("owner_type")
        expanded.update(
            item["pred_id"]
            for item in predicates
            if item.get("owner_type") == owner
            and item.get("is_identity_field") is True
            and isinstance(item.get("pred_id"), str)
        )
    return tuple(sorted(expanded))


def _predicate_tags(schema_ir: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for item in schema_ir.get("predicates", []):
        if not isinstance(item, Mapping) or not isinstance(item.get("pred_id"), str):
            continue
        specs = item.get("arg_specs")
        if not isinstance(specs, list) or not all(
            isinstance(arg, Mapping) and isinstance(arg.get("type_domain"), str) for arg in specs
        ):
            continue
        result[item["pred_id"]] = tuple(str(arg["type_domain"]) for arg in specs)
    return result


def _encode_program_envelope(
    *,
    schema_ir: dict[str, Any],
    profile: EvaluationExecutionProfileV2,
    primary_plan: EvaluationRunPlanV2,
    primary_program: CompiledDerivationPlan,
    primary_base_program: CompiledDerivationPlan,
    primary_target: TargetedCompiledEvaluationQueryV0,
    primary_product: _ProductTarget,
    candidate_plan: EvaluationRunPlanV2 | None,
    candidate_program: CompiledDerivationPlan | None,
    candidate_base_program: CompiledDerivationPlan | None,
    candidate_target: TargetedCompiledEvaluationQueryV0 | None,
    candidate_product: _ProductTarget | None,
) -> bytes:
    if (
        (candidate_plan is None) != (candidate_program is None)
        or (candidate_plan is None) != (candidate_base_program is None)
        or (candidate_plan is None) != (candidate_target is None)
    ):
        _fail("candidate replay program fields are inconsistent", "V2_PROGRAM_CAPTURE_INVALID")
    primary = _program_record(
        plan=primary_plan,
        program=primary_program,
        base_program=primary_base_program,
        targeted=primary_target,
        product=primary_product,
        profile=profile,
        side="primary",
    )
    candidate = (
        None
        if candidate_plan is None
        else _program_record(
            plan=candidate_plan,
            program=candidate_program,
            base_program=candidate_base_program,
            targeted=candidate_target,
            product=candidate_product,
            profile=profile,
            side="candidate",
        )
    )
    return _canonical_json_bytes(
        {
            "$type": _PROGRAM_TYPE,
            "version": _PROGRAM_VERSION,
            "schema": schema_ir,
            "schema_digest": schema_digest(schema_ir),
            "source_schema_digest": primary_target.target.run_target.schema_digest,
            "profile_digest": profile.profile_digest,
            "address_space_digest": primary_plan.address_space_digest,
            "primary": primary,
            "candidate": candidate,
        },
        label="V2 replay program",
    )


def _program_record(
    *,
    plan: EvaluationRunPlanV2 | None,
    program: CompiledDerivationPlan | None,
    base_program: CompiledDerivationPlan | None,
    targeted: TargetedCompiledEvaluationQueryV0 | None,
    product: _ProductTarget | None,
    profile: EvaluationExecutionProfileV2,
    side: _TargetSide,
) -> dict[str, object]:
    if (
        plan is None
        or program is None
        or base_program is None
        or targeted is None
        or product is None
    ):
        _fail("V2 program record is incomplete", "V2_PROGRAM_CAPTURE_INVALID")
    resolved = _validate_profile_attachments(profile, product, side=side)
    query_carrier = _query_carrier_to_wire(targeted, product=product, plan=plan)
    choice_capture = _choice_capture_to_wire(product)
    function_capture = _function_capture_to_wire(product, plan=plan)
    _assert_final_program_is_derived(
        profile=profile,
        plan=plan,
        base_program=base_program,
        program=program,
        choice_capture=choice_capture,
    )
    record: dict[str, object] = {
        "plan": _run_plan_to_wire(plan),
        "base_compiled": _compiled_plan_to_wire(base_program),
        "compiled": _compiled_plan_to_wire(program),
        "selection_shape": [
            {"alias": alias, "tag": tag} for alias, tag in _selection_shape(targeted)
        ],
        "query_carrier": query_carrier,
        "choice_capture": choice_capture,
        "function_capture": function_capture,
        "attachment_resolution": _resolved_attachments_to_wire(resolved),
    }
    record["compiler_materialization_digest"] = _compiler_materialization_digest(
        profile=profile,
        plan=plan,
        query_carrier=query_carrier,
        base_program=base_program,
        program=program,
        choice_capture=choice_capture,
        function_capture=function_capture,
        resolved=resolved,
    )
    return record


def _compiled_plan_digest(plan: CompiledDerivationPlan) -> str:
    return _token("goal_plan_v2_compiled_derivation", _compiled_plan_to_wire(plan))


def _resolved_attachments_to_wire(
    value: ResolvedExecutionAttachmentsV2,
) -> dict[str, object]:
    return {
        "profile_digest": value.profile_digest,
        "attachments": [
            {
                "attachment_digest": item.attachment_digest,
                "lowering_slot_digests": list(item.lowering_slot_digests),
                "resolution_digest": item.resolution_digest,
            }
            for item in value.attachments
        ],
        "resolution_digest": value.resolution_digest,
    }


def _choice_capture_to_wire(product: _ProductTarget) -> dict[str, object] | None:
    choices = _choices_for(product)
    if not choices:
        return None
    if len(choices) != 1:
        _fail(
            "V2 replay supports exactly one WeightedChoice topology",
            "V2_WEIGHTED_CHOICE_MULTIPLE_UNSUPPORTED",
        )
    choice = choices[0]
    return {
        "choice_id": choice.choice_id,
        "node_id": choice.node_id,
        "topology_digest": choice.topology_digest,
        "selection_key": [
            {"occurrence_alias": item.occurrence_alias, "port_name": item.port_name}
            for item in choice.selection_key
        ],
        "arms": [
            {
                "arm_id": arm.arm_id,
                "probability": arm.probability,
                "condition_node_id": arm.condition_node_id,
            }
            for arm in choice.arms
        ],
        "skeleton_node_id": choice.skeleton_node_id,
    }


def _function_capture_to_wire(
    product: _ProductTarget,
    *,
    plan: EvaluationRunPlanV2,
) -> dict[str, object] | None:
    functions = _functions_for(product)
    if not functions:
        return None
    assert isinstance(product, ProductPolicyV1)
    occurrences: list[dict[str, object]] = []
    for topology in functions:
        snapshot = asset_snapshot_v1(topology.function)
        ports = [
            {
                "name": port.name,
                "tag": port.scalar_domain,
                "mode": "input",
                "predicate_id": _function_port_predicate_id(
                    topology.relation_predicate_id, port.name
                ),
            }
            for port in topology.function.inputs
        ]
        ports.append(
            {
                "name": topology.function.output.name,
                "tag": topology.function.output.scalar_domain,
                "mode": "output",
                "predicate_id": _function_port_predicate_id(
                    topology.relation_predicate_id, topology.function.output.name
                ),
            }
        )
        occurrences.append(
            {
                "alias": topology.alias,
                "function_id": topology.function.id,
                "function_version": topology.function.version,
                "function_digest": topology.function.logical_identity_digest,
                "signature_digest": topology.function.signature_digest,
                "implementation_digest": topology.function.implementation_digest,
                "relation_predicate_id": topology.relation_predicate_id,
                "ports": ports,
                "input_bindings": [
                    {
                        "port_name": item.port_name,
                        "source": {
                            "occurrence_alias": item.source.occurrence_alias,
                            "port_name": item.source.port_name,
                        },
                    }
                    for item in topology.input_bindings
                ],
                "topology_digest": topology.topology_digest,
                "asset_meta": snapshot["asset_meta"],
                "asset_descriptor_digest": snapshot["descriptor_digest"],
                "asset_binding_digest": snapshot["asset_binding_digest"],
            }
        )
    return {
        "product_target_digest": plan.target.target_digest,
        "occurrences": occurrences,
    }


def _query_carrier_to_wire(
    targeted: TargetedCompiledEvaluationQueryV0,
    *,
    product: _ProductTarget,
    plan: EvaluationRunPlanV2,
) -> dict[str, object]:
    """Capture the compiler-owned Query/target lineage without rehydrating V1.

    The replay record does not manufacture an in-process V0 target.  It keeps
    the exact data needed to recompute the V0 Query intent digest and wrapper
    seal, plus the normalized source target's Rule/policy pins.  This makes a
    body-only program swap fail even when its observations happen to coincide.
    """

    compiled = targeted.compiled_query
    source = targeted.target.run_target
    if plan.address_space_digest != _address_space_token(targeted):
        _fail(
            "V2 program plan does not match compiled Query address space",
            "V2_PROGRAM_TARGET_SPLICE",
        )
    if (
        source.original_target_kind != plan.target.target_kind
        or source.target_id != plan.target.target_id
        or source.target_version != plan.target.target_version
        or plan.target.target_digest != product.logical_identity_digest
    ):
        _fail("V2 program source target does not match product plan", "V2_PROGRAM_TARGET_SPLICE")

    def sources(value: object) -> list[dict[str, str]]:
        raw = getattr(value, "sources", None)
        if not isinstance(raw, tuple):
            _fail("compiled Query sources are malformed", "V2_PROGRAM_QUERY_CARRIER_INVALID")
        output: list[dict[str, str]] = []
        for item in raw:
            branch_id = getattr(item, "branch_id", None)
            occurrence_alias = getattr(item, "occurrence_alias", None)
            port_name = getattr(item, "port_name", None)
            if not all(
                isinstance(part, str) and part for part in (branch_id, occurrence_alias, port_name)
            ):
                _fail("compiled Query source is malformed", "V2_PROGRAM_QUERY_CARRIER_INVALID")
            assert isinstance(branch_id, str)
            assert isinstance(occurrence_alias, str)
            assert isinstance(port_name, str)
            output.append(
                {
                    "branch_id": branch_id,
                    "occurrence_alias": occurrence_alias,
                    "port_name": port_name,
                }
            )
        if not output:
            _fail("compiled Query source inventory is empty", "V2_PROGRAM_QUERY_CARRIER_INVALID")
        return output

    def address(value: object) -> dict[str, str]:
        occurrence_alias = getattr(value, "occurrence_alias", None)
        port_name = getattr(value, "port_name", None)
        if not isinstance(occurrence_alias, str) or not isinstance(port_name, str):
            _fail("compiled Query address is malformed", "V2_PROGRAM_QUERY_CARRIER_INVALID")
        return {"occurrence_alias": occurrence_alias, "port_name": port_name}

    bindings: list[dict[str, object]] = []
    for binding in compiled.bindings:
        bindings.append(
            {
                "address": address(binding.address),
                "tag": binding.value_type,
                "value_digest": _hex_to_token(binding.value_digest, label="Query binding value"),
                "sources": sources(binding),
            }
        )
    selections: list[dict[str, object]] = []
    for selection in compiled.selections:
        if isinstance(selection, ResolvedEvaluationQueryNavigationSelectionV0):
            navigation = selection.navigation
            field = navigation.field
            selections.append(
                {
                    "kind": "field_navigation_v0",
                    "alias": selection.alias,
                    "base": address(navigation.base),
                    "field_entity_type": field.entity_type,
                    "field_name": field.field_name,
                    "field_predicate_id": selection.field_predicate_id,
                    "tag": selection.value_type,
                    "sources": sources(selection),
                }
            )
        else:
            selections.append(
                {
                    "kind": "port",
                    "alias": selection.alias,
                    "address": address(selection.address),
                    "tag": selection.value_type,
                    "sources": sources(selection),
                }
            )
    rule_pins: list[dict[str, object]] = []
    for rule_pin in source.rule_pins:
        rule_pins.append(
            {
                "occurrence_alias": rule_pin.occurrence_alias,
                "rule_id": rule_pin.rule_id,
                "rule_version": rule_pin.rule_version,
                "rule_content_digest": _hex_to_token(
                    rule_pin.rule_content_digest, label="source Rule content"
                ),
                "semantic_contract_digest": _hex_to_token(
                    rule_pin.semantic_contract_digest, label="source semantic contract"
                ),
            }
        )
    return {
        "compiler_digest": GOAL_PLAN_V2_COMPILER_DIGEST,
        "product_target": {
            "target_kind": plan.target.target_kind,
            "target_id": plan.target.target_id,
            "target_version": plan.target.target_version,
            "logical_identity_digest": plan.target.target_digest,
        },
        "source_target": {
            "original_target_kind": source.original_target_kind,
            "normalization_kind": source.normalization_kind,
            "target_id": source.target_id,
            "target_version": source.target_version,
            "normalized_policy_id": source.normalized_policy_id,
            "normalized_policy_version": source.normalized_policy_version,
            "policy_digest": _hex_to_token(source.policy_digest, label="source Policy"),
            "address_space_digest": _hex_to_token(
                source.address_space_digest, label="source address space"
            ),
            "schema_digest": source.schema_digest,
            "policy_structure_digest": _hex_to_token(
                source.policy_structure.structure_digest, label="source Policy structure"
            ),
            "rule_pins": rule_pins,
            "target_digest": source.target_digest,
        },
        "query": {
            "query_digest": _query_token(targeted),
            "wrapper_digest": targeted.wrapper_digest,
            "policy_digest": _hex_to_token(compiled.policy_digest, label="Query Policy"),
            "address_space_digest": _hex_to_token(
                compiled.address_space_digest, label="Query address space"
            ),
            "schema_digest": compiled.schema_digest,
            "bindings": bindings,
            "selections": selections,
            "projection_head": {
                "id": compiled.projection_head.id,
                "version": compiled.projection_head.version,
                "content_digest": _hex_to_token(
                    compiled.projection_head.content_digest, label="Query projection head"
                ),
            },
            "lowering_canonical_key": _encode_structural(compiled._lowering_plan.canonical_key),
            **(
                {"applicable_branch_ids": list(compiled.applicable_branch_ids)}
                if compiled.applicable_branch_ids
                else {}
            ),
        },
    }


def _compiler_materialization_digest(
    *,
    profile: EvaluationExecutionProfileV2,
    plan: EvaluationRunPlanV2,
    query_carrier: Mapping[str, object],
    base_program: CompiledDerivationPlan,
    program: CompiledDerivationPlan,
    choice_capture: Mapping[str, object] | None,
    function_capture: Mapping[str, object] | None,
    resolved: ResolvedExecutionAttachmentsV2,
) -> str:
    return _token(
        "goal_plan_v2_compiler_materialization",
        {
            "compiler_digest": GOAL_PLAN_V2_COMPILER_DIGEST,
            "profile_digest": profile.profile_digest,
            "plan_digest": plan.plan_digest,
            "query_carrier_digest": _token("goal_plan_v2_query_carrier", query_carrier),
            "base_compiled_digest": _compiled_plan_digest(base_program),
            "compiled_digest": _compiled_plan_digest(program),
            "choice_capture_digest": None
            if choice_capture is None
            else _token("goal_plan_v2_choice_capture", choice_capture),
            "function_capture_digest": None
            if function_capture is None
            else _token("goal_plan_v2_function_capture", function_capture),
            "attachment_resolution_digest": resolved.resolution_digest,
        },
    )


def _assert_final_program_is_derived(
    *,
    profile: EvaluationExecutionProfileV2,
    plan: EvaluationRunPlanV2,
    base_program: CompiledDerivationPlan,
    program: CompiledDerivationPlan,
    choice_capture: Mapping[str, object] | None,
) -> None:
    """Validate the closed compiler/lowering relation retained for replay."""

    if base_program.engine_ext is not None or base_program.engine_options:
        _fail("V2 base materialization has an unexpected engine carrier", "V2_PROGRAM_BASE_INVALID")
    if (
        program.derivation_id != base_program.derivation_id
        or program.version != base_program.version
        or program.body_ir != base_program.body_ir
        or program.heads != base_program.heads
    ):
        _fail(
            "V2 executable program is not derived from its base materialization",
            "V2_PROGRAM_LOWERING_MISMATCH",
        )
    if profile.kind in {"native_deterministic_v2", "portable_deterministic_v2"}:
        if choice_capture is not None:
            _fail(
                "WeightedChoice requires the ProbLog V2 profile",
                "V2_WEIGHTED_CHOICE_PROFILE_REQUIRED",
            )
        if program != base_program:
            _fail(
                "deterministic V2 program carries an unsupported lowering",
                "V2_PROGRAM_LOWERING_MISMATCH",
            )
        return

    expected_options: dict[str, object] = {}
    if profile.resources.timeout_ms is not None:
        expected_options["timeout"] = max(1, math.ceil(profile.resources.timeout_ms / 1000))
    if program.engine_options != expected_options:
        _fail("ProbLog V2 engine options are not profile-derived", "V2_PROGRAM_LOWERING_MISMATCH")
    if choice_capture is None:
        if program.engine_ext is not None:
            _fail(
                "ProbLog V2 program has an undeclared engine extension",
                "V2_PROGRAM_LOWERING_MISMATCH",
            )
        return
    capture_arms = choice_capture.get("arms")
    if not isinstance(capture_arms, list) or not all(
        isinstance(item, Mapping) for item in capture_arms
    ):
        _fail("WeightedChoice capture arms are malformed", "V2_PROGRAM_LOWERING_MISMATCH")
    if (
        not isinstance(program.engine_ext, ProbLogRuleExt)
        or program.engine_ext.weighted_choice is None
    ):
        _fail(
            "WeightedChoice V2 program lacks its annotated-disjunction lowering",
            "V2_PROGRAM_LOWERING_MISMATCH",
        )
    extension = _engine_ext_to_wire(program.engine_ext)
    assert isinstance(extension, dict)  # established by _engine_ext_to_wire
    if (
        extension["choice_id"] != choice_capture["choice_id"]
        or extension["choice_node_id"] != choice_capture["node_id"]
        or extension["topology_digest"] != choice_capture["topology_digest"]
        or extension["arms"]
        != [{"arm_id": item["arm_id"], "probability": item["probability"]} for item in capture_arms]
    ):
        _fail(
            "WeightedChoice lowering does not match captured topology",
            "V2_PROGRAM_LOWERING_MISMATCH",
        )
    choice_attachments = tuple(
        attachment
        for attachment in profile.attachments
        if attachment.target.pin_digest == plan.target.pin_digest and attachment.kind == "choice"
    )
    if (
        len(choice_attachments) != 1
        or choice_attachments[0].structural_node_id != choice_capture["node_id"]
    ):
        _fail(
            "WeightedChoice lowering is not activated by this profile",
            "V2_WEIGHTED_CHOICE_ACTIVATION_REQUIRED",
        )


def _run_plan_to_wire(plan: EvaluationRunPlanV2) -> dict[str, object]:
    return {
        "target": plan.target.to_wire(),
        "query_digest": plan.query_digest,
        "asset_descriptor": (
            None
            if plan.asset_descriptor_bytes is None
            else json.loads(plan.asset_descriptor_bytes.decode("utf-8"))
        ),
        "asset_descriptor_digest": plan.asset_descriptor_digest,
        "asset_binding_digest": plan.asset_binding_digest,
        "address_space_digest": plan.address_space_digest,
        "plan_digest": plan.plan_digest,
    }


def _compiled_plan_to_wire(plan: CompiledDerivationPlan) -> dict[str, object]:
    if plan.body_confidence is not None or plan.head_spec is not None:
        _fail(
            "V2 replay program has unsupported compiled plan feature",
            "V2_PROGRAM_CAPABILITY_REJECTED",
        )
    if len(plan.heads) != 1:
        _fail("V2 replay program requires one projection head", "V2_PROGRAM_CAPABILITY_REJECTED")
    return {
        "derivation_id": plan.derivation_id,
        "version": plan.version,
        "body_ir": _encode_structural(plan.body_ir),
        "heads": [
            {"target_pred_id": item.target_pred_id, "head_var_names": list(item.head_var_names)}
            for item in plan.heads
        ],
        "engine_ext": _engine_ext_to_wire(plan.engine_ext),
        "engine_options": dict(plan.engine_options),
    }


def _engine_ext_to_wire(value: object) -> object:
    if value is None:
        return None
    if (
        not isinstance(value, ProbLogRuleExt)
        or value.case_probabilities is not None
        or value.weighted_choice is None
    ):
        _fail("V2 replay program engine extension is unsupported", "V2_PROGRAM_CAPABILITY_REJECTED")
    choice = value.weighted_choice
    return {
        "kind": "problog_weighted_choice_v2",
        "choice_id": choice.choice_id,
        "choice_node_id": choice.choice_node_id,
        "topology_digest": choice.topology_digest,
        "arms": [{"arm_id": arm.arm_id, "probability": arm.probability} for arm in choice.arms],
        "branches": [
            {
                "branch_index": branch.branch_index,
                "arm_id": branch.arm_id,
                "key_variables": list(branch.key_variables),
            }
            for branch in choice.branches
        ],
        "domain_key_variables": list(choice.domain_key_variables),
        "domain_body": _encode_structural(choice.domain_body),
    }


@dataclass(frozen=True)
class _DecodedProgramV2:
    schema_ir: dict[str, Any]
    primary_program: CompiledDerivationPlan
    primary_selection_shape: tuple[tuple[str, str], ...]
    candidate_program: CompiledDerivationPlan | None
    candidate_selection_shape: tuple[tuple[str, str], ...] | None


def _query_carrier_from_wire(
    value: object,
    *,
    plan: EvaluationRunPlanV2,
    expected_schema_digest: str,
) -> dict[str, object]:
    """Validate the detached compiler carrier and rederive its Query seal."""

    row = _exact_keys(
        value,
        {"compiler_digest", "product_target", "source_target", "query"},
        label="V2 replay Query carrier",
    )
    if row["compiler_digest"] != GOAL_PLAN_V2_COMPILER_DIGEST:
        _fail(
            "V2 replay Query carrier compiler pin is unsupported", "V2_REPLAY_PROGRAM_PIN_MISMATCH"
        )
    product_target = _exact_keys(
        row["product_target"],
        {"target_kind", "target_id", "target_version", "logical_identity_digest"},
        label="V2 replay product target",
    )
    if (
        product_target["target_kind"] != plan.target.target_kind
        or product_target["target_id"] != plan.target.target_id
        or product_target["target_version"] != plan.target.target_version
        or product_target["logical_identity_digest"] != plan.target.target_digest
    ):
        _fail("V2 replay product target does not match run plan", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    _require_token(product_target["logical_identity_digest"], "V2 replay product logical identity")

    source = _exact_keys(
        row["source_target"],
        {
            "original_target_kind",
            "normalization_kind",
            "target_id",
            "target_version",
            "normalized_policy_id",
            "normalized_policy_version",
            "policy_digest",
            "address_space_digest",
            "schema_digest",
            "policy_structure_digest",
            "rule_pins",
            "target_digest",
        },
        label="V2 replay source target",
    )
    if source["original_target_kind"] not in {"rule", "policy"} or source[
        "normalization_kind"
    ] not in {
        "rule_lift_v0",
        "policy_direct_v0",
    }:
        _fail("V2 replay source target normalization is invalid", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    expected_normalization = {
        "rule": "rule_lift_v0",
        "policy": "policy_direct_v0",
    }[source["original_target_kind"]]
    if source["normalization_kind"] != expected_normalization:
        _fail(
            "V2 replay source target normalization mismatches kind",
            "V2_REPLAY_PROGRAM_SHAPE_INVALID",
        )
    for key in ("target_id", "normalized_policy_id"):
        _wire_text(source[key], label=f"V2 replay source target {key}")
    for key in ("target_version", "normalized_policy_version"):
        _wire_optional_text(source[key], label=f"V2 replay source target {key}")
    for key in (
        "policy_digest",
        "address_space_digest",
        "schema_digest",
        "policy_structure_digest",
        "target_digest",
    ):
        _require_token(source[key], f"V2 replay source target {key}")
    if (
        source["original_target_kind"] != plan.target.target_kind
        or source["target_id"] != plan.target.target_id
        or source["target_version"] != plan.target.target_version
        or source["address_space_digest"] != plan.address_space_digest
        or source["schema_digest"] != expected_schema_digest
    ):
        _fail(
            "V2 replay source target is not bound to run plan/payload",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    source_rule_pins = _validate_source_rule_pins(source["rule_pins"])

    query_value = row["query"]
    query_keys = {
            "query_digest",
            "wrapper_digest",
            "policy_digest",
            "address_space_digest",
            "schema_digest",
            "bindings",
            "selections",
            "projection_head",
            "lowering_canonical_key",
        }
    if isinstance(query_value, Mapping) and "applicable_branch_ids" in query_value:
        query_keys.add("applicable_branch_ids")
    query = _exact_keys(
        query_value,
        query_keys,
        label="V2 replay Query carrier query",
    )
    for key in (
        "query_digest",
        "wrapper_digest",
        "policy_digest",
        "address_space_digest",
        "schema_digest",
    ):
        _require_token(query[key], f"V2 replay Query {key}")
    if (
        query["query_digest"] != plan.query_digest
        or query["policy_digest"] != source["policy_digest"]
        or query["address_space_digest"] != source["address_space_digest"]
        or query["schema_digest"] != source["schema_digest"]
    ):
        _fail(
            "V2 replay Query carrier pins do not match plan/source",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    bindings = _validate_query_bindings_wire(query["bindings"])
    selections = _validate_query_selections_wire(query["selections"])
    applicable_branch_ids: tuple[str, ...] = ()
    if "applicable_branch_ids" in query:
        raw_branch_ids = query["applicable_branch_ids"]
        if (
            not isinstance(raw_branch_ids, list)
            or not raw_branch_ids
            or not all(isinstance(item, str) and item for item in raw_branch_ids)
            or len(set(raw_branch_ids)) != len(raw_branch_ids)
        ):
            _fail(
                "V2 replay Query applicable branch inventory is malformed",
                "V2_REPLAY_PROGRAM_SHAPE_INVALID",
            )
        applicable_branch_ids = tuple(raw_branch_ids)
    projection_head = _exact_keys(
        query["projection_head"],
        {"id", "version", "content_digest"},
        label="V2 replay Query projection head",
    )
    _wire_text(projection_head["id"], label="V2 replay Query projection head id")
    _wire_optional_text(projection_head["version"], label="V2 replay Query projection head version")
    _require_token(
        projection_head["content_digest"], "V2 replay Query projection head content digest"
    )
    lowering_key = _decode_structural(query["lowering_canonical_key"])
    if not isinstance(lowering_key, tuple) or not _structural_contains(
        lowering_key, _strip_token(query["query_digest"])
    ):
        _fail(
            "V2 replay Query lowering carrier does not bind Query digest",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    if not _structural_contains(lowering_key, _strip_token(projection_head["content_digest"])):
        _fail(
            "V2 replay Query lowering carrier does not bind projection head",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    for pin in source_rule_pins:
        if not _structural_contains(lowering_key, _strip_token(pin["rule_content_digest"])):
            _fail(
                "V2 replay Query lowering carrier omits source Rule pin",
                "V2_REPLAY_PROGRAM_PIN_MISMATCH",
            )
    actual_query_digest = _compiled_query_digest_from_wire(
        policy_digest=query["policy_digest"],
        address_space_digest=query["address_space_digest"],
        schema_digest=query["schema_digest"],
        bindings=bindings,
        selections=selections,
        applicable_branch_ids=applicable_branch_ids,
    )
    if query["query_digest"] != actual_query_digest:
        _fail(
            "V2 replay Query digest does not match captured intent",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    expected_wrapper = targeted_evaluation_query_wrapper_digest_v0(
        _strip_token(query["query_digest"]),
        source["target_digest"],  # type: ignore[arg-type]
    )
    if query["wrapper_digest"] != expected_wrapper:
        _fail(
            "V2 replay Query wrapper does not match captured target",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    return row


def _wire_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    return value


def _wire_optional_text(value: object, *, label: str) -> str | None:
    if value is not None:
        return _wire_text(value, label=label)
    return None


def _wire_address(value: object, *, label: str) -> dict[str, str]:
    row = _exact_keys(value, {"occurrence_alias", "port_name"}, label=label)
    return {
        "occurrence_alias": _wire_text(row["occurrence_alias"], label=f"{label} occurrence"),
        "port_name": _wire_text(row["port_name"], label=f"{label} port"),
    }


def _wire_sources(value: object, *, label: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        _fail(f"{label} sources are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    result: list[dict[str, str]] = []
    for index, item in enumerate(value):
        row = _exact_keys(
            item,
            {"branch_id", "occurrence_alias", "port_name"},
            label=f"{label} source[{index}]",
        )
        result.append(
            {
                "branch_id": _wire_text(row["branch_id"], label=f"{label} source branch"),
                "occurrence_alias": _wire_text(
                    row["occurrence_alias"], label=f"{label} source occurrence"
                ),
                "port_name": _wire_text(row["port_name"], label=f"{label} source port"),
            }
        )
    if len({tuple(item.values()) for item in result}) != len(result):
        _fail(f"{label} sources are duplicated", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    return result


def _validate_source_rule_pins(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        _fail("V2 replay source Rule pins are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    result: list[dict[str, object]] = []
    aliases: set[str] = set()
    for index, item in enumerate(value):
        row = _exact_keys(
            item,
            {
                "occurrence_alias",
                "rule_id",
                "rule_version",
                "rule_content_digest",
                "semantic_contract_digest",
            },
            label=f"V2 replay source Rule pin[{index}]",
        )
        alias = _wire_text(row["occurrence_alias"], label="V2 replay source Rule alias")
        if alias in aliases:
            _fail("V2 replay source Rule aliases are duplicated", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        aliases.add(alias)
        result.append(
            {
                "occurrence_alias": alias,
                "rule_id": _wire_text(row["rule_id"], label="V2 replay source Rule id"),
                "rule_version": _wire_optional_text(
                    row["rule_version"], label="V2 replay source Rule version"
                ),
                "rule_content_digest": _require_token(
                    row["rule_content_digest"], "V2 replay source Rule content digest"
                ),
                "semantic_contract_digest": _require_token(
                    row["semantic_contract_digest"], "V2 replay source Rule contract digest"
                ),
            }
        )
    return result


def _validate_query_bindings_wire(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        _fail("V2 replay Query bindings are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    result: list[dict[str, object]] = []
    for index, item in enumerate(value):
        row = _exact_keys(
            item,
            {"address", "tag", "value_digest", "sources"},
            label=f"V2 replay Query binding[{index}]",
        )
        result.append(
            {
                "address": _wire_address(row["address"], label="V2 replay Query binding address"),
                "tag": _wire_text(row["tag"], label="V2 replay Query binding tag"),
                "value_digest": _require_token(
                    row["value_digest"], "V2 replay Query binding value digest"
                ),
                "sources": _wire_sources(row["sources"], label="V2 replay Query binding"),
            }
        )
    return result


def _validate_query_selections_wire(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        _fail("V2 replay Query selections are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    result: list[dict[str, object]] = []
    aliases: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            _fail("V2 replay Query selection is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        kind = item.get("kind")
        if kind == "port":
            row = _exact_keys(
                item,
                {"kind", "alias", "address", "tag", "sources"},
                label=f"V2 replay Query selection[{index}]",
            )
            normalized: dict[str, object] = {
                "kind": "port",
                "alias": _wire_text(row["alias"], label="V2 replay Query selection alias"),
                "address": _wire_address(row["address"], label="V2 replay Query selection address"),
                "tag": _wire_text(row["tag"], label="V2 replay Query selection tag"),
                "sources": _wire_sources(row["sources"], label="V2 replay Query selection"),
            }
        elif kind == "field_navigation_v0":
            row = _exact_keys(
                item,
                {
                    "kind",
                    "alias",
                    "base",
                    "field_entity_type",
                    "field_name",
                    "field_predicate_id",
                    "tag",
                    "sources",
                },
                label=f"V2 replay Query selection[{index}]",
            )
            normalized = {
                "kind": "field_navigation_v0",
                "alias": _wire_text(row["alias"], label="V2 replay Query selection alias"),
                "base": _wire_address(row["base"], label="V2 replay Query navigation base"),
                "field_entity_type": _wire_text(
                    row["field_entity_type"], label="V2 replay Query navigation entity"
                ),
                "field_name": _wire_text(
                    row["field_name"], label="V2 replay Query navigation field"
                ),
                "field_predicate_id": _wire_text(
                    row["field_predicate_id"], label="V2 replay Query navigation predicate"
                ),
                "tag": _wire_text(row["tag"], label="V2 replay Query selection tag"),
                "sources": _wire_sources(row["sources"], label="V2 replay Query selection"),
            }
        else:
            _fail(
                "V2 replay Query selection kind is unsupported", "V2_REPLAY_PROGRAM_SHAPE_INVALID"
            )
        alias = normalized["alias"]
        assert isinstance(alias, str)
        if alias in aliases:
            _fail(
                "V2 replay Query selection aliases are duplicated",
                "V2_REPLAY_PROGRAM_SHAPE_INVALID",
            )
        aliases.add(alias)
        result.append(normalized)
    return result


def _compiled_query_digest_from_wire(
    *,
    policy_digest: object,
    address_space_digest: object,
    schema_digest: object,
    bindings: Sequence[Mapping[str, object]],
    selections: Sequence[Mapping[str, object]],
    applicable_branch_ids: tuple[str, ...] = (),
) -> str:
    def address(item: Mapping[str, object]) -> list[object]:
        raw_address = item["address"]
        raw_sources = item["sources"]
        assert isinstance(raw_address, Mapping) and isinstance(raw_sources, Sequence)
        return [
            raw_address["occurrence_alias"],
            raw_address["port_name"],
            tuple(
                (source["branch_id"], source["occurrence_alias"], source["port_name"])
                for source in raw_sources
                if isinstance(source, Mapping)
            ),
        ]

    binding_payload = [
        [
            *address(item),
            item["tag"],
            _strip_token(item["value_digest"]),
        ]
        for item in bindings
    ]
    selection_payload: list[list[object]] = []
    for item in selections:
        if item["kind"] == "port":
            selection_payload.append([item["alias"], *address(item), item["tag"]])
        else:
            base = item["base"]
            sources = item["sources"]
            assert isinstance(base, Mapping) and isinstance(sources, Sequence)
            selection_payload.append(
                [
                    "field_navigation_v0",
                    item["alias"],
                    base["occurrence_alias"],
                    base["port_name"],
                    item["field_entity_type"],
                    item["field_name"],
                    item["field_predicate_id"],
                    tuple(
                        (source["branch_id"], source["occurrence_alias"], source["port_name"])
                        for source in sources
                        if isinstance(source, Mapping)
                    ),
                    item["tag"],
                ]
            )
    payload = {
        "format": "compiled_evaluation_query_v0",
        "policy_digest": _strip_token(policy_digest),
        "address_space_digest": _strip_token(address_space_digest),
        "schema_digest": schema_digest,
        "bindings": binding_payload,
        "selections": selection_payload,
    }
    if applicable_branch_ids:
        payload["applicable_branch_ids"] = list(applicable_branch_ids)
    return f"sha256:{sha256_hex(_canonical_json_bytes(payload, label='V2 replay Query intent'))}"


def _structural_contains(value: object, needle: object) -> bool:
    if value == needle:
        return True
    if isinstance(value, tuple):
        return any(_structural_contains(item, needle) for item in value)
    if isinstance(value, list):
        return any(_structural_contains(item, needle) for item in value)
    if isinstance(value, dict):
        return any(_structural_contains(item, needle) for item in value.values())
    return False


def _choice_capture_from_wire(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    row = _exact_keys(
        value,
        {"choice_id", "node_id", "topology_digest", "selection_key", "arms", "skeleton_node_id"},
        label="V2 replay WeightedChoice capture",
    )
    if not isinstance(row["selection_key"], list) or not isinstance(row["arms"], list):
        _fail("V2 replay WeightedChoice capture is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    try:
        selection_key = tuple(
            SemanticPortAddress(
                _wire_address(item, label="V2 replay WeightedChoice key")["occurrence_alias"],
                _wire_address(item, label="V2 replay WeightedChoice key")["port_name"],
            )
            for item in row["selection_key"]
        )
        arms: list[WeightedChoiceArmV1] = []
        normalized_arms: list[dict[str, str]] = []
        for index, item in enumerate(row["arms"]):
            arm = _exact_keys(
                item,
                {"arm_id", "probability", "condition_node_id"},
                label=f"V2 replay WeightedChoice arm[{index}]",
            )
            arm_id = _wire_text(arm["arm_id"], label="V2 replay WeightedChoice arm id")
            probability = _wire_text(
                arm["probability"], label="V2 replay WeightedChoice arm probability"
            )
            condition_node_id = _wire_text(
                arm["condition_node_id"], label="V2 replay WeightedChoice arm condition"
            )
            arms.append(WeightedChoiceArmV1(arm_id, probability, condition_node_id))
            normalized_arms.append(
                {
                    "arm_id": arm_id,
                    "probability": probability,
                    "condition_node_id": condition_node_id,
                }
            )
        rebuilt = WeightedChoiceTopologyV1(
            choice_id=_wire_text(row["choice_id"], label="V2 replay WeightedChoice id"),
            selection_key=selection_key,
            arms=tuple(arms),
            skeleton_node_id=_wire_text(
                row["skeleton_node_id"], label="V2 replay WeightedChoice skeleton"
            ),
        )
    except Exception as exc:
        _raise_from(
            exc,
            prefix="V2 replay WeightedChoice capture",
            default="V2_REPLAY_PROGRAM_SHAPE_INVALID",
        )
    if row["node_id"] != rebuilt.node_id or row["topology_digest"] != rebuilt.topology_digest:
        _fail("V2 replay WeightedChoice topology seal is stale", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    expected_arms = [
        {
            "arm_id": arm.arm_id,
            "probability": arm.probability,
            "condition_node_id": arm.condition_node_id,
        }
        for arm in rebuilt.arms
    ]
    if normalized_arms != expected_arms:
        _fail("V2 replay WeightedChoice arms are noncanonical", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    return row


def _function_capture_from_wire(
    value: object,
    *,
    plan: EvaluationRunPlanV2,
    carrier: Mapping[str, object],
    program: CompiledDerivationPlan,
    schema_ir: Mapping[str, object],
) -> dict[str, object] | None:
    if value is None:
        return None
    row = _exact_keys(
        value,
        {"product_target_digest", "occurrences"},
        label="V2 replay Function capture",
    )
    if row["product_target_digest"] != plan.target.target_digest:
        _fail(
            "V2 replay Function capture target pin mismatches plan",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    occurrences = row["occurrences"]
    if not isinstance(occurrences, list) or not occurrences:
        _fail(
            "V2 replay Function capture occurrences are malformed",
            "V2_REPLAY_PROGRAM_SHAPE_INVALID",
        )
    source = carrier.get("source_target")
    if not isinstance(source, Mapping) or not isinstance(source.get("rule_pins"), list):
        _fail("V2 replay Function source pins are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    source_pins = {
        item["occurrence_alias"]: item
        for item in source["rule_pins"]
        if isinstance(item, Mapping) and isinstance(item.get("occurrence_alias"), str)
    }
    predicates_raw = schema_ir.get("predicates")
    if not isinstance(predicates_raw, list):
        _fail("V2 replay Function schema predicates are malformed", "V2_REPLAY_SCHEMA_INVALID")
    predicates = {item.get("pred_id"): item for item in predicates_raw if isinstance(item, Mapping)}
    aliases: list[str] = []
    for index, item in enumerate(occurrences):
        occurrence = _exact_keys(
            item,
            {
                "alias",
                "function_id",
                "function_version",
                "function_digest",
                "signature_digest",
                "implementation_digest",
                "relation_predicate_id",
                "ports",
                "input_bindings",
                "topology_digest",
                "asset_meta",
                "asset_descriptor_digest",
                "asset_binding_digest",
            },
            label=f"V2 replay Function occurrence[{index}]",
        )
        alias = _wire_text(occurrence["alias"], label="V2 replay Function alias")
        function_id = _wire_text(occurrence["function_id"], label="V2 replay Function id")
        function_version = _wire_optional_text(
            occurrence["function_version"], label="V2 replay Function version"
        )
        relation_id = _wire_text(
            occurrence["relation_predicate_id"], label="V2 replay Function relation"
        )
        implementation_digest = _require_token(
            occurrence["implementation_digest"], "V2 replay Function implementation"
        )
        ports_raw = occurrence["ports"]
        bindings_raw = occurrence["input_bindings"]
        if (
            not isinstance(ports_raw, list)
            or len(ports_raw) < 2
            or not isinstance(bindings_raw, list)
        ):
            _fail(
                "V2 replay Function ports/bindings are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID"
            )
        ports: list[dict[str, str]] = []
        for port_index, port_value in enumerate(ports_raw):
            port = _exact_keys(
                port_value,
                {"name", "tag", "mode", "predicate_id"},
                label=f"V2 replay Function port[{port_index}]",
            )
            name = _wire_text(port["name"], label="V2 replay Function port name")
            tag = _wire_text(port["tag"], label="V2 replay Function port tag")
            mode = _wire_text(port["mode"], label="V2 replay Function port mode")
            predicate_id = _wire_text(
                port["predicate_id"], label="V2 replay Function port predicate"
            )
            if (
                tag not in {"string", "int", "float64", "bool", "time", "uuid"}
                or mode not in {"input", "output"}
                or predicate_id != _function_port_predicate_id(relation_id, name)
            ):
                _fail(
                    "V2 replay Function port contract is invalid", "V2_REPLAY_PROGRAM_PIN_MISMATCH"
                )
            predicate = predicates.get(predicate_id)
            if not isinstance(predicate, Mapping):
                _fail(
                    "V2 replay Function predicate is absent from schema",
                    "V2_REPLAY_PROGRAM_PIN_MISMATCH",
                )
            arg_specs = predicate.get("arg_specs")
            if (
                predicate.get("arity") != 2
                or not isinstance(arg_specs, list)
                or len(arg_specs) != 2
                or not isinstance(arg_specs[0], Mapping)
                or not isinstance(arg_specs[1], Mapping)
                or arg_specs[0].get("type_domain") != "entity_ref"
                or arg_specs[1].get("type_domain") != tag
                or not _structural_contains(program.body_ir, predicate_id)
            ):
                _fail(
                    "V2 replay Function program/schema binding is invalid",
                    "V2_REPLAY_PROGRAM_PIN_MISMATCH",
                )
            ports.append({"name": name, "tag": tag, "mode": mode, "predicate_id": predicate_id})
        if (
            len({port["name"] for port in ports}) != len(ports)
            or any(port["mode"] != "input" for port in ports[:-1])
            or ports[-1]["mode"] != "output"
        ):
            _fail(
                "V2 replay Function port order is noncanonical", "V2_REPLAY_PROGRAM_SHAPE_INVALID"
            )
        bindings: list[dict[str, object]] = []
        for binding_index, binding_value in enumerate(bindings_raw):
            binding = _exact_keys(
                binding_value,
                {"port_name", "source"},
                label=f"V2 replay Function binding[{binding_index}]",
            )
            bindings.append(
                {
                    "port_name": _wire_text(
                        binding["port_name"], label="V2 replay Function binding port"
                    ),
                    "source": _wire_address(
                        binding["source"], label="V2 replay Function binding source"
                    ),
                }
            )
        if [item["port_name"] for item in bindings] != sorted(port["name"] for port in ports[:-1]):
            _fail(
                "V2 replay Function input bindings are noncanonical",
                "V2_REPLAY_PROGRAM_SHAPE_INVALID",
            )
        signature_digest = _token(
            "product_function_signature_v1",
            {
                "inputs": tuple((port["name"], port["tag"]) for port in ports[:-1]),
                "output": (ports[-1]["name"], ports[-1]["tag"]),
            },
        )
        function_digest = _token(
            "product_function_logical_identity_v1",
            {
                "id": function_id,
                "version": function_version,
                "signature_digest": signature_digest,
                "implementation_digest": implementation_digest,
                "semantics": "pure_deterministic_total_v1",
            },
        )
        topology_digest = _token(
            "product_function_occurrence_v1",
            {
                "alias": alias,
                "function_digest": function_digest,
                "signature_digest": signature_digest,
                "relation_predicate_id": relation_id,
                "input_bindings": tuple(
                    (
                        binding["port_name"],
                        binding["source"]["occurrence_alias"],  # type: ignore[index]
                        binding["source"]["port_name"],  # type: ignore[index]
                    )
                    for binding in bindings
                ),
            },
        )
        if (
            occurrence["signature_digest"] != signature_digest
            or occurrence["function_digest"] != function_digest
            or occurrence["topology_digest"] != topology_digest
        ):
            _fail("V2 replay Function capture seal is stale", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
        asset_meta = occurrence["asset_meta"]
        if not isinstance(asset_meta, Mapping):
            _fail("V2 replay Function AssetMeta is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        descriptor_digest: object
        if asset_meta.get("state") == "absent":
            if (
                set(asset_meta) != {"format", "state"}
                or asset_meta.get("format") != "asset_meta_v1"
            ):
                _fail(
                    "V2 replay Function absent AssetMeta is malformed",
                    "V2_REPLAY_PROGRAM_SHAPE_INVALID",
                )
            descriptor_digest = "absent"
        else:
            if (
                set(asset_meta) != {"format", "name", "description", "tags"}
                or asset_meta.get("format") != "asset_meta_v1"
            ):
                _fail(
                    "V2 replay Function AssetMeta is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID"
                )
            descriptor_digest = _token("asset_meta_v1", asset_meta)
        asset_binding_digest = _token(
            "asset_binding_v1",
            {
                "target_kind": "function",
                "logical_identity_digest": function_digest,
                "descriptor_state": "absent" if descriptor_digest == "absent" else "present",
                "descriptor_digest": descriptor_digest,
            },
        )
        if (
            occurrence["asset_descriptor_digest"] != descriptor_digest
            or occurrence["asset_binding_digest"] != asset_binding_digest
        ):
            _fail("V2 replay Function asset binding is stale", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
        input_vars = tuple(Var(f"$__function_input_{offset}") for offset in range(len(ports) - 1))
        output_var = Var("$__function_output")
        call_key = Var("$__function_call_key")
        source_rule = Rule(
            id=f"__factgraph_function_v1__{function_id}",
            version=function_version,
            when=tuple(
                PredAtom(port["predicate_id"], [call_key, variable])
                for port, variable in zip(ports, (*input_vars, output_var), strict=True)
            ),
            ports={
                port["name"]: variable
                for port, variable in zip(ports, (*input_vars, output_var), strict=True)
            },
        )
        pin = source_pins.get(alias)
        if not isinstance(pin, Mapping) or pin.get("rule_content_digest") != _hex_to_token(
            source_rule.content_digest, label="Function source Rule"
        ):
            _fail(
                "V2 replay Function source Rule pin mismatches capture",
                "V2_REPLAY_PROGRAM_PIN_MISMATCH",
            )
        aliases.append(alias)
    if aliases != sorted(aliases) or len(set(aliases)) != len(aliases):
        _fail("V2 replay Function occurrences are noncanonical", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    return row


def _choice_topology_from_validated_capture(
    capture: Mapping[str, object],
) -> WeightedChoiceTopologyV1:
    """Rehydrate only the already validated public topology capture."""

    raw_key = capture["selection_key"]
    raw_arms = capture["arms"]
    assert isinstance(raw_key, list) and isinstance(raw_arms, list)
    selection_key = tuple(
        SemanticPortAddress(
            item["occurrence_alias"],
            item["port_name"],  # type: ignore[index,arg-type]
        )
        for item in raw_key
        if isinstance(item, Mapping)
    )
    arms = tuple(
        WeightedChoiceArmV1(
            item["arm_id"],
            item["probability"],
            item["condition_node_id"],  # type: ignore[index,arg-type]
        )
        for item in raw_arms
        if isinstance(item, Mapping)
    )
    topology = WeightedChoiceTopologyV1(
        choice_id=capture["choice_id"],  # type: ignore[arg-type]
        selection_key=selection_key,
        arms=arms,
        skeleton_node_id=capture["skeleton_node_id"],  # type: ignore[arg-type]
    )
    if (
        topology.node_id != capture["node_id"]
        or topology.topology_digest != capture["topology_digest"]
    ):
        _fail("V2 replay WeightedChoice topology seal is stale", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    return topology


def _resolved_attachments_from_wire(
    value: object,
    *,
    profile: EvaluationExecutionProfileV2,
    plan: EvaluationRunPlanV2,
    carrier: Mapping[str, object],
    choice_capture: Mapping[str, object] | None,
) -> ResolvedExecutionAttachmentsV2:
    row = _exact_keys(
        value,
        {"profile_digest", "attachments", "resolution_digest"},
        label="V2 replay attachment resolution",
    )
    if row["profile_digest"] != profile.profile_digest or not isinstance(row["attachments"], list):
        _fail(
            "V2 replay attachment resolution profile is invalid", "V2_REPLAY_PROGRAM_PIN_MISMATCH"
        )
    actual_items: list[ResolvedExecutionAttachmentV2] = []
    for index, item in enumerate(row["attachments"]):
        item_row = _exact_keys(
            item,
            {"attachment_digest", "lowering_slot_digests", "resolution_digest"},
            label=f"V2 replay attachment resolution[{index}]",
        )
        slots = item_row["lowering_slot_digests"]
        attachment_digest = item_row["attachment_digest"]
        if (
            not isinstance(attachment_digest, str)
            or not isinstance(slots, list)
            or not all(isinstance(slot, str) for slot in slots)
        ):
            _fail("V2 replay attachment slots are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        try:
            resolved_item = ResolvedExecutionAttachmentV2(
                attachment_digest,
                tuple(slots),
            )
        except Exception as exc:
            _raise_from(
                exc,
                prefix="V2 replay attachment resolution",
                default="V2_REPLAY_PROGRAM_SHAPE_INVALID",
            )
        if item_row["resolution_digest"] != resolved_item.resolution_digest:
            _fail("V2 replay attachment item is noncanonical", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
        actual_items.append(resolved_item)
    try:
        actual = ResolvedExecutionAttachmentsV2(profile.profile_digest, tuple(actual_items))
    except Exception as exc:
        _raise_from(
            exc, prefix="V2 replay attachment resolution", default="V2_REPLAY_PROGRAM_SHAPE_INVALID"
        )
    if row["resolution_digest"] != actual.resolution_digest:
        _fail("V2 replay attachment resolution is noncanonical", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    expected = _resolved_attachments_from_carrier(
        profile=profile,
        plan=plan,
        carrier=carrier,
        choice_capture=choice_capture,
    )
    if actual != expected:
        _fail(
            "V2 replay attachment slots do not resolve from captured target",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    return actual


def _resolved_attachments_from_carrier(
    *,
    profile: EvaluationExecutionProfileV2,
    plan: EvaluationRunPlanV2,
    carrier: Mapping[str, object],
    choice_capture: Mapping[str, object] | None,
) -> ResolvedExecutionAttachmentsV2:
    attachments = tuple(
        item for item in profile.attachments if item.target.pin_digest == plan.target.pin_digest
    )
    if profile.kind in {"native_deterministic_v2", "portable_deterministic_v2"}:
        if attachments or choice_capture is not None:
            _fail(
                "native V2 replay attachment carrier is invalid", "V2_REPLAY_PROGRAM_PIN_MISMATCH"
            )
        return ResolvedExecutionAttachmentsV2(profile.profile_digest, ())
    source = carrier["source_target"]
    assert isinstance(source, Mapping)
    rule_pins_raw = source["rule_pins"]
    assert isinstance(rule_pins_raw, list)
    known_occurrences = {
        str(item["occurrence_alias"]): (
            item["rule_id"],
            item["rule_version"],
            item["rule_content_digest"],
        )
        for item in rule_pins_raw
        if isinstance(item, Mapping)
    }
    resolved: list[ResolvedExecutionAttachmentV2] = []
    rule_slots: set[str] = set()
    occurrence_slots: set[str] = set()
    choice_nodes = set() if choice_capture is None else {choice_capture["node_id"]}
    choice_attachment_nodes: set[object] = set()
    for attachment in attachments:
        if attachment.kind == "rule":
            expected_rules: tuple[tuple[object, object, object, str], ...]
            if plan.target.target_kind == "rule":
                direct_pin = known_occurrences.get("target")
                if direct_pin is None or len(known_occurrences) != 1:
                    _fail(
                        "V2 replay direct Rule target does not have one target occurrence",
                        "V2_REPLAY_PROGRAM_PIN_MISMATCH",
                    )
                expected_rules = (
                    (
                        direct_pin[0],
                        direct_pin[1],
                        direct_pin[2],
                        "target",
                    ),
                )
            else:
                expected_rules = tuple(
                    (rule_id, version, digest, alias)
                    for alias, (rule_id, version, digest) in known_occurrences.items()
                    if (rule_id, version, digest)
                    == (attachment.rule_id, attachment.rule_version, attachment.rule_digest)
                )
            if not expected_rules or any(
                (rule_id, version, digest)
                != (attachment.rule_id, attachment.rule_version, attachment.rule_digest)
                for rule_id, version, digest, _alias in expected_rules
            ):
                _fail(
                    "V2 replay Rule attachment does not resolve", "V2_REPLAY_PROGRAM_PIN_MISMATCH"
                )
            slots = tuple(
                _token(
                    "product_v2_rule_attachment_slot",
                    {"target": plan.target.pin_digest, "alias": alias},
                )
                for _rule_id, _version, _digest, alias in expected_rules
            )
            rule_slots.update(slots)
        elif attachment.kind == "occurrence":
            if plan.target.target_kind != "policy":
                _fail(
                    "V2 replay occurrence attachment targets non-Policy",
                    "V2_REPLAY_PROGRAM_PIN_MISMATCH",
                )
            actual = known_occurrences.get(attachment.occurrence_alias or "")
            if actual != (attachment.rule_id, attachment.rule_version, attachment.rule_digest):
                _fail(
                    "V2 replay occurrence attachment does not resolve",
                    "V2_REPLAY_PROGRAM_PIN_MISMATCH",
                )
            slots = (
                _token(
                    "product_v2_rule_attachment_slot",
                    {"target": plan.target.pin_digest, "alias": attachment.occurrence_alias},
                ),
            )
            occurrence_slots.update(slots)
        else:
            node_id = attachment.structural_node_id
            if node_id not in choice_nodes or node_id in choice_attachment_nodes:
                _fail(
                    "V2 replay choice attachment does not resolve", "V2_REPLAY_PROGRAM_PIN_MISMATCH"
                )
            choice_attachment_nodes.add(node_id)
            slots = (
                _token(
                    "product_v2_choice_attachment_slot",
                    {"target": plan.target.pin_digest, "node": node_id},
                ),
            )
        resolved.append(ResolvedExecutionAttachmentV2(attachment.attachment_digest, slots))
    if rule_slots & occurrence_slots or choice_attachment_nodes != choice_nodes:
        _fail(
            "V2 replay attachment slots overlap or omit a choice", "V2_REPLAY_PROGRAM_PIN_MISMATCH"
        )
    try:
        return ResolvedExecutionAttachmentsV2(profile.profile_digest, tuple(resolved))
    except Exception as exc:
        _raise_from(
            exc, prefix="V2 replay attachment slots", default="V2_REPLAY_PROGRAM_PIN_MISMATCH"
        )


def _decode_program_envelope(run: EvaluationRunV2) -> _DecodedProgramV2:
    value = _parse_canonical_json(
        run.replay_payload.compiled_program_bytes, label="V2 replay program"
    )
    row = _exact_keys(
        value,
        {
            "$type",
            "version",
            "schema",
            "schema_digest",
            "source_schema_digest",
            "profile_digest",
            "address_space_digest",
            "primary",
            "candidate",
        },
        label="V2 replay program",
    )
    if row["$type"] != _PROGRAM_TYPE or row["version"] != _PROGRAM_VERSION:
        _fail("V2 replay program type/version is invalid", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    if (
        row["profile_digest"] != run.profile.profile_digest
        or row["address_space_digest"] != run.replay_payload.address_space_digest
    ):
        _fail(
            "V2 replay program profile/address-space pin mismatches run",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    if not isinstance(row["schema"], dict):
        _fail("V2 replay schema is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    try:
        schema_ir = ensure_schema_ir(dict(row["schema"]))
    except Exception as exc:
        _raise_from(exc, prefix="V2 replay schema", default="V2_REPLAY_SCHEMA_INVALID")
    if (
        schema_digest(schema_ir) != run.replay_payload.schema_digest
        or row["schema_digest"] != run.replay_payload.schema_digest
    ):
        _fail("V2 replay schema digest mismatches run", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    _require_token(row["source_schema_digest"], "V2 replay source schema digest")
    primary_plan, primary_program, primary_shape = _decode_program_record(
        row["primary"],
        expected=run.primary_plan,
        profile=run.profile,
        expected_schema_digest=row["source_schema_digest"],  # type: ignore[arg-type]
        schema_ir=schema_ir,
    )
    if primary_plan != run.primary_plan:
        _fail("V2 replay primary plan mismatches run", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    primary_selection_shape = primary_shape
    candidate_program: CompiledDerivationPlan | None = None
    candidate_selection_shape: tuple[tuple[str, str], ...] | None = None
    if run.candidate_plan is None:
        if row["candidate"] is not None:
            _fail("V2 replay program has undeclared candidate", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    else:
        if row["candidate"] is None:
            _fail("V2 replay program omits declared candidate", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
        candidate_plan, candidate_program, candidate_shape = _decode_program_record(
            row["candidate"],
            expected=run.candidate_plan,
            profile=run.profile,
            expected_schema_digest=row["source_schema_digest"],  # type: ignore[arg-type]
            schema_ir=schema_ir,
        )
        if candidate_plan != run.candidate_plan:
            _fail("V2 replay candidate plan mismatches run", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
        candidate_selection_shape = candidate_shape
    return _DecodedProgramV2(
        schema_ir=schema_ir,
        primary_program=primary_program,
        primary_selection_shape=primary_selection_shape,
        candidate_program=candidate_program,
        candidate_selection_shape=candidate_selection_shape,
    )


def _decode_program_record(
    value: object,
    *,
    expected: EvaluationRunPlanV2,
    profile: EvaluationExecutionProfileV2,
    expected_schema_digest: str,
    schema_ir: Mapping[str, object],
) -> tuple[EvaluationRunPlanV2, CompiledDerivationPlan, tuple[tuple[str, str], ...]]:
    row = _exact_keys(
        value,
        {
            "plan",
            "base_compiled",
            "compiled",
            "selection_shape",
            "query_carrier",
            "choice_capture",
            "function_capture",
            "attachment_resolution",
            "compiler_materialization_digest",
        },
        label="V2 replay program record",
    )
    plan = _run_plan_from_wire(row["plan"])
    if plan.plan_digest != expected.plan_digest:
        _fail("V2 replay plan digest mismatches run", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    carrier = _query_carrier_from_wire(
        row["query_carrier"],
        plan=plan,
        expected_schema_digest=expected_schema_digest,
    )
    choice_capture = _choice_capture_from_wire(row["choice_capture"])
    resolved = _resolved_attachments_from_wire(
        row["attachment_resolution"],
        profile=profile,
        plan=plan,
        carrier=carrier,
        choice_capture=choice_capture,
    )
    base_program = _compiled_plan_from_wire(row["base_compiled"])
    program = _compiled_plan_from_wire(row["compiled"])
    function_capture = _function_capture_from_wire(
        row["function_capture"],
        plan=plan,
        carrier=carrier,
        program=program,
        schema_ir=schema_ir,
    )
    shape = _selection_shape_from_wire(row["selection_shape"])
    query_shape = tuple((item["alias"], item["tag"]) for item in carrier["query"]["selections"])  # type: ignore[index]
    if shape != query_shape:
        _fail(
            "V2 replay selection shape does not match captured Query",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    _assert_final_program_is_derived(
        profile=profile,
        plan=plan,
        base_program=base_program,
        program=program,
        choice_capture=choice_capture,
    )
    actual_materialization = _compiler_materialization_digest(
        profile=profile,
        plan=plan,
        query_carrier=carrier,
        base_program=base_program,
        program=program,
        choice_capture=choice_capture,
        function_capture=function_capture,
        resolved=resolved,
    )
    if row["compiler_materialization_digest"] != actual_materialization:
        _fail(
            "V2 replay compiler materialization binding mismatches record",
            "V2_REPLAY_PROGRAM_PIN_MISMATCH",
        )
    return plan, program, shape


def _run_plan_from_wire(value: object) -> EvaluationRunPlanV2:
    row = _exact_keys(
        value,
        {
            "target",
            "query_digest",
            "asset_descriptor",
            "asset_descriptor_digest",
            "asset_binding_digest",
            "address_space_digest",
            "plan_digest",
        },
        label="V2 replay plan",
    )
    target_row = _exact_keys(
        row["target"],
        {"side", "target_kind", "target_id", "target_version", "target_digest"},
        label="V2 replay target",
    )
    target = EvaluationTargetPinV2(
        side=target_row["side"],  # type: ignore[arg-type]
        target_kind=target_row["target_kind"],  # type: ignore[arg-type]
        target_id=target_row["target_id"],  # type: ignore[arg-type]
        target_version=target_row["target_version"],  # type: ignore[arg-type]
        target_digest=target_row["target_digest"],  # type: ignore[arg-type]
    )
    descriptor = row["asset_descriptor"]
    if descriptor is None:
        descriptor_bytes = None
    else:
        descriptor_bytes = _canonical_json_bytes(descriptor, label="V2 replay asset descriptor")
    try:
        plan = EvaluationRunPlanV2(
            target=target,
            query_digest=row["query_digest"],  # type: ignore[arg-type]
            asset_descriptor_bytes=descriptor_bytes,
            asset_descriptor_digest=row["asset_descriptor_digest"],  # type: ignore[arg-type]
            asset_binding_digest=row["asset_binding_digest"],  # type: ignore[arg-type]
            address_space_digest=row["address_space_digest"],  # type: ignore[arg-type]
        )
    except Exception as exc:
        _raise_from(exc, prefix="V2 replay plan", default="V2_REPLAY_PROGRAM_SHAPE_INVALID")
    if row["plan_digest"] != plan.plan_digest:
        _fail("V2 replay plan is not canonical", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    return plan


def _compiled_plan_from_wire(value: object) -> CompiledDerivationPlan:
    row = _exact_keys(
        value,
        {"derivation_id", "version", "body_ir", "heads", "engine_ext", "engine_options"},
        label="V2 replay compiled plan",
    )
    heads_raw = row["heads"]
    if not isinstance(heads_raw, list) or len(heads_raw) != 1:
        _fail("V2 replay compiled plan heads are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    heads: list[CompiledHeadCall] = []
    for item in heads_raw:
        head = _exact_keys(item, {"target_pred_id", "head_var_names"}, label="V2 replay head")
        if not isinstance(head["head_var_names"], list):
            _fail("V2 replay head vars are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        heads.append(CompiledHeadCall(head["target_pred_id"], tuple(head["head_var_names"])))  # type: ignore[arg-type]
    body = _decode_structural(row["body_ir"])
    if not isinstance(body, list) or not isinstance(row["engine_options"], dict):
        _fail(
            "V2 replay compiled plan body/options are malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID"
        )
    try:
        plan = CompiledDerivationPlan(
            derivation_id=row["derivation_id"],  # type: ignore[arg-type]
            version=row["version"],  # type: ignore[arg-type]
            body_ir=body,
            heads=tuple(heads),
            engine_ext=_engine_ext_from_wire(row["engine_ext"]),
            engine_options=dict(row["engine_options"]),
        )
    except Exception as exc:
        _raise_from(
            exc, prefix="V2 replay compiled plan", default="V2_REPLAY_PROGRAM_SHAPE_INVALID"
        )
    if _canonical_json_bytes(
        _compiled_plan_to_wire(plan), label="V2 replay compiled plan"
    ) != _canonical_json_bytes(value, label="V2 replay compiled plan"):
        _fail("V2 replay compiled plan is noncanonical", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    return plan


def _engine_ext_from_wire(value: object) -> ProbLogRuleExt | None:
    if value is None:
        return None
    row = _exact_keys(
        value,
        {
            "kind",
            "choice_id",
            "choice_node_id",
            "topology_digest",
            "arms",
            "branches",
            "domain_key_variables",
            "domain_body",
        },
        label="V2 replay engine extension",
    )
    if (
        row["kind"] != "problog_weighted_choice_v2"
        or not isinstance(row["arms"], list)
        or not isinstance(row["branches"], list)
        or not isinstance(row["domain_key_variables"], list)
    ):
        _fail("V2 replay engine extension is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    try:
        choice = ProbLogWeightedChoiceExt(
            choice_id=row["choice_id"],  # type: ignore[arg-type]
            choice_node_id=row["choice_node_id"],  # type: ignore[arg-type]
            topology_digest=row["topology_digest"],  # type: ignore[arg-type]
            arms=tuple(
                ProbLogWeightedChoiceArm(item["arm_id"], item["probability"])
                for item in row["arms"]
                if isinstance(item, dict)
            ),
            branches=tuple(
                ProbLogWeightedChoiceBranch(
                    item["branch_index"], item["arm_id"], tuple(item["key_variables"])
                )
                for item in row["branches"]
                if isinstance(item, dict) and isinstance(item.get("key_variables"), list)
            ),
            domain_key_variables=tuple(row["domain_key_variables"]),  # type: ignore[arg-type]
            domain_body=_decode_structural(row["domain_body"]),  # type: ignore[arg-type]
        )
    except Exception as exc:
        _raise_from(
            exc, prefix="V2 replay engine extension", default="V2_REPLAY_PROGRAM_SHAPE_INVALID"
        )
    return ProbLogRuleExt(weighted_choice=choice)


def _selection_shape_from_wire(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list) or not value:
        _fail("V2 replay selection shape is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    output: list[tuple[str, str]] = []
    for item in value:
        row = _exact_keys(item, {"alias", "tag"}, label="V2 replay selection")
        if not isinstance(row["alias"], str) or not isinstance(row["tag"], str):
            _fail("V2 replay selection shape is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        output.append((row["alias"], row["tag"]))
    if len({alias for alias, _tag in output}) != len(output):
        _fail("V2 replay selection aliases are duplicated", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    return tuple(output)


def _selection_shape(
    targeted: TargetedCompiledEvaluationQueryV0,
) -> tuple[tuple[str, str], ...]:
    """Extract the one replay-safe part of a compiled Query needed for rows.

    Replay must not fabricate a V0 ``TargetedCompiledEvaluationQuery`` just to
    normalize result terms.  The sealed program record carries the ordered
    projection aliases/types, and this helper makes that deliberately small
    carrier explicit.
    """

    return tuple((item.alias, item.value_type) for item in targeted.compiled_query.selections)


def _replay_side(
    *,
    declared: EvaluationRunSideV2 | None,
    name: Literal["baseline", "effective", "candidate_effective"],
    world: EffectiveWorldV2,
    plan: EvaluationRunPlanV2,
    program: CompiledDerivationPlan,
    profile: EvaluationExecutionProfileV2,
    schema_ir: dict[str, Any],
    selection_shape: tuple[tuple[str, str], ...],
) -> EvaluationRunReplaySideV2:
    if declared is None:
        _fail("V2 replay declared side is absent", "V2_REPLAY_PROGRAM_PIN_MISMATCH")
    capture = EvaluationReplayWorldV2(name, world)
    observed = _execute_side(
        name=name,
        world=world,
        capture=capture,
        plan=plan,
        program=program,
        profile=profile,
        schema_ir=schema_ir,
        selection_shape=selection_shape,
        captured_function_materializations=declared.function_materializations,
    )
    # Detached replay has always declared ``proof_parity='not_claimed'``.
    # Branch witnesses are retained proof-path evidence, so compare the
    # historical engine outcome surface while leaving witness attestation to
    # the sealed run itself.
    declared_digests = tuple(
        EvaluationEngineFrameV2(
            engine=item.engine,
            status=item.status,
            observations=item.observations,
            diagnostic_code=item.diagnostic_code,
            probability_materialization=item.probability_materialization,
        ).frame_digest
        for item in declared.engine_frames
    )
    observed_digests = tuple(item.frame_digest for item in observed.engine_frames)
    return EvaluationRunReplaySideV2(
        side=name,
        declared_frame_digests=declared_digests,
        observed_frame_digests=observed_digests,
        frame_match=(
            declared_digests == observed_digests
            and tuple(item.materialization_digest for item in declared.function_materializations)
            == tuple(item.materialization_digest for item in observed.function_materializations)
        ),
    )


def _address_space_token(targeted: TargetedCompiledEvaluationQueryV0) -> str:
    return _hex_to_token(targeted.compiled_query.address_space_digest, label="address space")


def _query_token(targeted: TargetedCompiledEvaluationQueryV0) -> str:
    return _hex_to_token(targeted.compiled_query.query_digest, label="Query")


def _hex_to_token(value: object, *, label: str) -> str:
    raw: object
    if isinstance(value, str) and value.startswith("sha256:"):
        raw = value[7:]
    else:
        raw = value
    if (
        not isinstance(raw, str)
        or len(raw) != 64
        or raw != raw.lower()
        or any(ch not in "0123456789abcdef" for ch in raw)
    ):
        _fail(f"{label} digest is invalid", "V2_DIGEST_INVALID")
    return f"sha256:{raw}"


def _strip_token(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        _fail("Rule content token is invalid", "V2_PROFILE_RULE_TARGET_MISMATCH")
    return value[7:]


def _require_token(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        _fail(f"{label} must be SHA-256 token", "V2_DIGEST_INVALID")
    return value


def _token(label: str, payload: object) -> str:
    return f"sha256:{sha256_hex(_canonical_json_bytes({'format': label, 'payload': payload}, label=label))}"


def _canonical_json_bytes(value: object, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ProductEvaluationRuntimeErrorV2(
            f"{label} cannot be canonical JSON", code="V2_CANONICAL_JSON_INVALID"
        ) from exc


def _parse_canonical_json(raw: object, *, label: str) -> object:
    if not isinstance(raw, bytes) or not raw:
        _fail(f"{label} bytes are invalid", "V2_REPLAY_PROGRAM_SHAPE_INVALID")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        output: dict[str, object] = {}
        for key, value in items:
            if key in output:
                _fail(f"{label} has duplicate JSON key", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
            output[key] = value
        return output

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda text: (_ for _ in ()).throw(ValueError(text)),
        )
    except Exception as exc:
        _raise_from(exc, prefix=label, default="V2_REPLAY_PROGRAM_SHAPE_INVALID")
    if _canonical_json_bytes(value, label=label) != raw:
        _fail(f"{label} is not canonical JSON", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    return value


def _exact_keys(value: object, expected: set[str], *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(f"{label} has unsupported or missing fields", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    return value


def _encode_structural(value: object, *, depth: int = 0) -> dict[str, object]:
    if depth > _MAX_PROGRAM_DEPTH:
        _fail("V2 replay program exceeds structural depth", "V2_PROGRAM_LIMIT_EXCEEDED")
    if value is None or isinstance(value, (str, bool, int)) and not isinstance(value, float):
        return {"$type": _STRUCTURAL_VALUE_TYPE, "kind": "scalar", "value": value}
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("V2 replay program has non-finite float", "V2_PROGRAM_SHAPE_INVALID")
        return {"$type": _STRUCTURAL_VALUE_TYPE, "kind": "float64", "value": value.hex()}
    if isinstance(value, Var):
        return {
            "$type": _STRUCTURAL_VALUE_TYPE,
            "kind": "var",
            "name": value.name,
            "origin": (
                None
                if value.origin is None
                else {"source": value.origin.source, "path": value.origin.path}
            ),
        }
    if isinstance(value, PortType):
        return {
            "$type": _STRUCTURAL_VALUE_TYPE,
            "kind": "port_type",
            "port_kind": value.kind,
            "entity_type": value.entity_type,
        }
    if isinstance(value, tuple):
        return {
            "$type": _STRUCTURAL_VALUE_TYPE,
            "kind": "tuple",
            "items": [_encode_structural(item, depth=depth + 1) for item in value],
        }
    if isinstance(value, list):
        return {
            "$type": _STRUCTURAL_VALUE_TYPE,
            "kind": "list",
            "items": [_encode_structural(item, depth=depth + 1) for item in value],
        }
    if isinstance(value, dict):
        if not all(isinstance(key, str) and key for key in value):
            _fail("V2 replay program map keys are invalid", "V2_PROGRAM_SHAPE_INVALID")
        return {
            "$type": _STRUCTURAL_VALUE_TYPE,
            "kind": "map",
            "items": [
                [key, _encode_structural(item, depth=depth + 1)]
                for key, item in sorted(value.items())
            ],
        }
    _fail(
        "V2 replay program has unsupported structural value: "
        f"{type(value).__name__}",
        "V2_PROGRAM_SHAPE_INVALID",
    )


def _decode_structural(value: object, *, depth: int = 0, budget: list[int] | None = None) -> object:
    if depth > _MAX_PROGRAM_DEPTH:
        _fail("V2 replay program exceeds structural depth", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    if budget is None:
        budget = [_MAX_PROGRAM_NODES]
    budget[0] -= 1
    if budget[0] < 0:
        _fail("V2 replay program exceeds structural node budget", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    row = (
        _exact_keys(value, {"$type", "kind", "value"}, label="V2 structural value")
        if isinstance(value, dict) and value.get("kind") in {"scalar", "float64"}
        else None
    )
    if row is not None:
        if row["$type"] != _STRUCTURAL_VALUE_TYPE:
            _fail("V2 structural type is invalid", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        if row["kind"] == "scalar":
            if row["value"] is not None and not isinstance(row["value"], (str, bool, int)):
                _fail("V2 structural scalar is invalid", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
            return row["value"]
        if not isinstance(row["value"], str):
            _fail("V2 structural float is invalid", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        try:
            result = float.fromhex(row["value"])
        except ValueError as exc:
            _raise_from(
                exc, prefix="V2 structural float", default="V2_REPLAY_PROGRAM_SHAPE_INVALID"
            )
        if not math.isfinite(result) or result.hex() != row["value"]:
            _fail("V2 structural float is noncanonical", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        return result
    if isinstance(value, dict) and value.get("kind") == "var":
        row = _exact_keys(
            value,
            {"$type", "kind", "name", "origin"},
            label="V2 structural Var",
        )
        if (
            row["$type"] != _STRUCTURAL_VALUE_TYPE
            or not isinstance(row["name"], str)
            or not row["name"]
        ):
            _fail("V2 structural Var is invalid", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        origin_value = row["origin"]
        origin = None
        if origin_value is not None:
            origin_row = _exact_keys(
                origin_value,
                {"source", "path"},
                label="V2 structural Var origin",
            )
            if origin_row["source"] not in {"sdk", "authoring", "raw_ir"} or (
                origin_row["path"] is not None
                and not isinstance(origin_row["path"], str)
            ):
                _fail(
                    "V2 structural Var origin is invalid",
                    "V2_REPLAY_PROGRAM_SHAPE_INVALID",
                )
            origin = Origin(
                cast(Literal["sdk", "authoring", "raw_ir"], origin_row["source"]),
                origin_row["path"],
            )
        return Var(row["name"], origin)
    if isinstance(value, dict) and value.get("kind") == "port_type":
        row = _exact_keys(
            value,
            {"$type", "kind", "port_kind", "entity_type"},
            label="V2 structural PortType",
        )
        if row["$type"] != _STRUCTURAL_VALUE_TYPE or row["port_kind"] not in {
            "value",
            "entity_ref",
        }:
            _fail(
                "V2 structural PortType is invalid",
                "V2_REPLAY_PROGRAM_SHAPE_INVALID",
            )
        if row["entity_type"] is not None and not isinstance(
            row["entity_type"], str
        ):
            _fail(
                "V2 structural PortType Entity is invalid",
                "V2_REPLAY_PROGRAM_SHAPE_INVALID",
            )
        return PortType(
            cast(Literal["entity_ref", "value"], row["port_kind"]),
            row["entity_type"],
        )
    if (
        not isinstance(value, dict)
        or value.get("$type") != _STRUCTURAL_VALUE_TYPE
        or value.get("kind") not in {"tuple", "list", "map"}
    ):
        _fail("V2 structural value is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    kind = value["kind"]
    if set(value) != {"$type", "kind", "items"} or not isinstance(value.get("items"), list):
        _fail("V2 structural collection is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
    items = value["items"]
    if kind == "tuple":
        return tuple(_decode_structural(item, depth=depth + 1, budget=budget) for item in items)
    if kind == "list":
        return [_decode_structural(item, depth=depth + 1, budget=budget) for item in items]
    output: dict[str, object] = {}
    previous: str | None = None
    for item in items:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not item[0]
            or (previous is not None and item[0] <= previous)
        ):
            _fail("V2 structural map is malformed", "V2_REPLAY_PROGRAM_SHAPE_INVALID")
        previous = item[0]
        output[item[0]] = _decode_structural(item[1], depth=depth + 1, budget=budget)
    return output


def _fail(message: str, code: str) -> NoReturn:
    raise ProductEvaluationRuntimeErrorV2(message, code=code)


def _raise_from(exc: Exception, *, prefix: str, default: str) -> NoReturn:
    code = getattr(exc, "code", default)
    raise ProductEvaluationRuntimeErrorV2(f"{prefix} rejected: {exc}", code=code) from exc


if TYPE_CHECKING:  # pragma: no cover
    from factgraph.sdk.store import SDKStore


__all__ = [
    "CapturedFunctionDefinitionV2",
    "EvaluationRunReplaySideV2",
    "EvaluationRunReplayV2",
    "GOAL_PLAN_V2_COMPILER_DIGEST",
    "ProductEvaluationInvocationV2",
    "ProductInvocationAggregateLimitsV2",
    "ProductEvaluationRuntimeErrorV2",
    "build_product_evaluation_invocation_v2",
    "choice_capture_from_evaluation_run_v2",
    "execute_product_evaluation_invocation_v2",
    "function_capture_from_evaluation_run_v2",
    "replay_evaluation_run_v2",
    "replay_product_evaluation_run_v2",
]
