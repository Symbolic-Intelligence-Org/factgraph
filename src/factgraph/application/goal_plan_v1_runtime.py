"""Execution bridge for the sealed, portable V1 GoalPlan contract.

This module is intentionally the only new path that joins the established
structured Rule/Policy Query compiler to Scenario v1, restricted relation
providers, and the isolated deterministic evaluator.  It does not alter the
V0 ``SDKStore.eval`` dispatch, its live Explain surface, or its native-only
Scenario compatibility seam.

The order is fixed and auditable:

``compile -> capture view -> evidence admission -> provider materialization
-> Scenario resolution -> isolated evaluation -> sealed Run``.

No adapter reads the caller's Store after relation capture.  A provider is
materialized before evaluation and replay consumes its captured relation and
receipt rather than its callable.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms
from factgraph.core.store._support import ProjectedFact
from factgraph.core.view.projector import project_view_facts_with_witness

from .evaluation_query_target_runtime import (
    TargetedCompiledEvaluationQueryV0,
    assert_targeted_evaluation_query_current,
)
from .evaluation_run_v1_runtime import (
    capture_evaluation_replay_payload_v1,
    capture_evaluation_replay_world_v1,
)
from .portable_evaluation_runtime import (
    PortableEngineObservationFrameV1,
    PortableEvaluationError,
    PortableSelectedRowV1,
    execute_native_deterministic_v1,
    observe_portable_deterministic_v1,
    portable_dependency_predicate_ids_v1,
)
from .protocol.evaluation_run_v1 import (
    EvaluationEnginePinV1,
    EvaluationEngineResultV1,
    EvaluationExecutionProfileV1,
    EvaluationReplayPayloadV1,
    EvaluationRunSideV1,
    EvaluationRunV1,
    ExplainTargetV1,
    ProviderReceiptRefV1,
)
from .protocol.goal_plan_v1 import (
    ContainsRowExpectationV1,
    CountEqExpectationV1,
    ExactLocalAbsenceExpectationV1,
    ExactLocalClosureStateV1,
    ExistsExpectationV1,
    GoalExistsValueV1,
    GoalExpectationOutcomeV1,
    GoalExpectationStatusV1,
    GoalExpectationV1,
    GoalPlanV1,
    GoalResultModeV1,
    GoalResultRowV1,
    GoalResultV1,
    GoalRowExpectationV1,
    GoalSelectionV1,
    GoalTargetRefV1,
    GoalTechnicalAssessmentV1,
    GoalValueV1,
    ScenarioResolutionStateV1,
    SetEqualsExpectationV1,
)
from .protocol.relation_provider_v1 import (
    ProviderMaterializationError,
    ProviderRequestV1,
    RelationProviderV1,
    invoke_relation_provider_v1,
)
from .protocol.rule_expr_lowering import _materialize_adapter_derivation_plan
from .protocol.scenario_v1 import (
    EffectiveWorldV1,
    EvidenceScopeV1,
    ExactLocalClosureTargetV1,
    ResolvedScenarioV1,
    ScenarioSpecV1,
)
from .relation_provider_v1_runtime import (
    ProviderRelationMaterializationError,
    merge_provider_materialization_v1,
)
from .scenario_v1_runtime import (
    ScenarioResolutionErrorV1,
    apply_evidence_scope_v1,
    effective_world_to_relation_v1,
    resolve_scenario_v1,
    scenario_dependency_predicate_ids_v1,
    select_dependency_relation_v1,
)

if TYPE_CHECKING:  # pragma: no cover - prevents SDK/application import cycle.
    from factgraph.sdk.store import SDKStore

    from .evaluation_run_v1_runtime import (
        EvaluationRunExplanationV1,
        EvaluationRunReplayV1,
        PolicyVariantComparisonV1,
        ScenarioDiffV1,
    )


GOAL_PLAN_V1_COMPILER_DIGEST = sha256_token(b"factgraph.goal_plan_v1.compiler.v1")


class GoalPlanRuntimeError(ValueError):
    """A typed construction or execution rejection for the V1 path."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class GoalPlanFailureV1:
    """A fail-closed execution outcome before a completed ``EvaluationRunV1``.

    A failed provider, resolver, or adapter cannot be represented as a
    successful-looking zero-row result.  The technical assessment stays
    multi-axis and the opaque detail digest avoids serializing exception text
    or a live Store into a durable artifact.
    """

    plan: GoalPlanV1
    assessment: GoalTechnicalAssessmentV1
    code: str
    detail_digest: str


@dataclass(frozen=True)
class GoalPlanRunV1:
    """Completed V1 run plus optional immutable comparison material.

    ``EvaluationRunV1`` is the durable core.  The wrapper owns only ergonomic
    explicit ``explain`` / ``replay`` dispatch and an optional comparison DTO
    produced by the runtime; it never provides an implicit first-row Explain.
    """

    run: EvaluationRunV1
    comparison: PolicyVariantComparisonV1 | None = None
    # Kept alongside (rather than inside) the durable Run DTO because it is a
    # derived, no-reexecution view over the sealed baseline/effective pair.
    # ``None`` means this was an ordinary Query without an explicit Scenario,
    # not an empty or causally-neutral Scenario diff.
    scenario_diff: ScenarioDiffV1 | None = None

    def explain(self, target: ExplainTargetV1) -> EvaluationRunExplanationV1:
        """Explain one explicit V1 row or summary target.

        Args:
            target: Run-bound Explain target; no implicit first row is chosen.

        Returns:
            A detached V1 explanation under the run's evidence boundary.
        """
        from .evaluation_run_v1_runtime import explain_evaluation_run_v1

        return explain_evaluation_run_v1(self.run, target=target)

    def replay(self) -> EvaluationRunReplayV1:
        """Replay the sealed V1 capture without consulting live graph state.

        Returns:
            A detached replay comparison and typed parity status.

        Notes:
            Replay never invokes a live Provider or reads the current ledger.
        """
        from .evaluation_run_v1_runtime import replay_evaluation_run_v1

        return replay_evaluation_run_v1(self.run)


@dataclass(frozen=True)
class GoalPlanInvocationV1:
    """In-process compiled GoalPlan ready for one captured execution.

    The graph reference is deliberately excluded from all durable protocol
    values.  Calling ``run`` takes exactly one view capture and then operates
    on detached immutable relations only.
    """

    _graph: SDKStore
    plan: GoalPlanV1
    primary: TargetedCompiledEvaluationQueryV0
    profile: EvaluationExecutionProfileV1
    scenario: ScenarioSpecV1 | None
    evidence_scope: EvidenceScopeV1
    candidate: TargetedCompiledEvaluationQueryV0 | None = None
    provider: RelationProviderV1 | None = None

    def run(self) -> GoalPlanRunV1 | GoalPlanFailureV1:
        """Capture one view and execute this compiled V1 invocation.

        Returns:
            A completed sealed run or an explicit fail-closed outcome.
        """
        return execute_goal_plan_invocation_v1(self)


def native_deterministic_profile_v1(
    *,
    native_engine_version: str = "factgraph-native-v1",
    native_adapter_version: str = "factgraph-native-adapter-v1",
) -> EvaluationExecutionProfileV1:
    """Return the library's zero-config native deterministic profile.

    Callers that need a different environment pin must construct their own
    ``EvaluationExecutionProfileV1``.  V1 rejects arbitrary engine config
    until a canonical config codec exists, so this factory cannot hide config
    drift behind an opaque digest.

    Args:
        native_engine_version: Exact Native engine version pin.
        native_adapter_version: Exact Native adapter version pin.

    Returns:
        A sealed zero-config Native deterministic V1 profile.
    """

    return EvaluationExecutionProfileV1(
        kind="native_deterministic_v1",
        compiler_digest=GOAL_PLAN_V1_COMPILER_DIGEST,
        config_digest=None,
        engines=(EvaluationEnginePinV1("native", native_engine_version, native_adapter_version),),
    )


def portable_deterministic_profile_v1(
    *,
    native_engine_version: str = "factgraph-native-v1",
    native_adapter_version: str = "factgraph-native-adapter-v1",
    souffle_engine_version: str = "souffle-v1",
    souffle_adapter_version: str = "factgraph-souffle-adapter-v1",
    problog_engine_version: str = "problog-v1",
    problog_adapter_version: str = "factgraph-problog-adapter-v1",
) -> EvaluationExecutionProfileV1:
    """Return the explicit all-three-engine selected-row parity profile.

    Args:
        native_engine_version: Native engine version pin.
        native_adapter_version: Native adapter version pin.
        souffle_engine_version: Soufflé engine version pin.
        souffle_adapter_version: Soufflé adapter version pin.
        problog_engine_version: ProbLog engine version pin.
        problog_adapter_version: ProbLog adapter version pin.

    Returns:
        A sealed deterministic V1 profile for Native, Soufflé and ProbLog.

    Notes:
        The profile claims selected-row parity only; proof parity remains
        explicitly unclaimed.
    """

    return EvaluationExecutionProfileV1(
        kind="portable_deterministic_v1",
        compiler_digest=GOAL_PLAN_V1_COMPILER_DIGEST,
        config_digest=None,
        engines=(
            EvaluationEnginePinV1("native", native_engine_version, native_adapter_version),
            EvaluationEnginePinV1("souffle", souffle_engine_version, souffle_adapter_version),
            EvaluationEnginePinV1("problog", problog_engine_version, problog_adapter_version),
        ),
    )


def build_goal_plan_invocation_v1(
    *,
    graph: SDKStore,
    primary: TargetedCompiledEvaluationQueryV0,
    result_mode: GoalResultModeV1,
    expectations: tuple[GoalExpectationV1, ...],
    scenario: ScenarioSpecV1 | None,
    evidence_scope: EvidenceScopeV1,
    profile: EvaluationExecutionProfileV1 | None,
    candidate: TargetedCompiledEvaluationQueryV0 | None,
    provider: RelationProviderV1 | None,
) -> GoalPlanInvocationV1:
    """Seal one V1 Query/Scenario intent without touching the ledger."""

    if not isinstance(primary, TargetedCompiledEvaluationQueryV0):
        raise GoalPlanRuntimeError(
            "primary must be a compiled typed Query", code="GOAL_PRIMARY_INVALID"
        )
    assert_targeted_evaluation_query_current(primary)
    if not isinstance(evidence_scope, EvidenceScopeV1):
        raise GoalPlanRuntimeError(
            "evidence_scope must be EvidenceScopeV1", code="GOAL_SCOPE_INVALID"
        )
    if scenario is not None and not isinstance(scenario, ScenarioSpecV1):
        raise GoalPlanRuntimeError("scenario must be ScenarioSpecV1", code="GOAL_SCENARIO_INVALID")
    if profile is None:
        profile = native_deterministic_profile_v1()
    if not isinstance(profile, EvaluationExecutionProfileV1):
        raise GoalPlanRuntimeError(
            "profile must be EvaluationExecutionProfileV1", code="GOAL_PROFILE_INVALID"
        )
    if not isinstance(expectations, tuple):
        raise GoalPlanRuntimeError("expectations must be a tuple", code="GOAL_EXPECTATIONS_INVALID")
    if candidate is not None:
        if provider is not None:
            raise GoalPlanRuntimeError(
                "immutable candidate comparison cannot be combined with a relation provider target",
                code="GOAL_PROVIDER_CANDIDATE_UNSUPPORTED",
            )
        assert_targeted_evaluation_query_current(candidate)
        _assert_candidate_projection(primary, candidate)
    if provider is not None and not isinstance(provider, RelationProviderV1):
        raise GoalPlanRuntimeError(
            "provider must be RelationProviderV1", code="GOAL_PROVIDER_INVALID"
        )

    primary_target = _target_ref(primary, provider=provider)
    candidate_target = None if candidate is None else _target_ref(candidate, provider=None)
    selections = tuple(
        GoalSelectionV1(item.alias, item.value_type) for item in primary.compiled_query.selections
    )
    if result_mode == "exists" and any(
        isinstance(item, ContainsRowExpectationV1) for item in expectations
    ):
        raise GoalPlanRuntimeError(
            "contains_row expectation requires rows/set/count result mode, not exists",
            code="GOAL_EXPECTATION_MODE_UNSUPPORTED",
        )
    plan = GoalPlanV1(
        target=primary_target,
        query_digest=_query_token(primary),
        result_mode=result_mode,
        selections=selections,
        candidate_target=candidate_target,
        candidate_query_digest=None if candidate is None else _query_token(candidate),
        scenario_request_digest=None if scenario is None else scenario.spec_digest,
        evidence_scope_digest=evidence_scope.scope_digest,
        execution_profile_digest=profile.profile_digest,
        expectations=expectations,
    )
    return GoalPlanInvocationV1(
        graph,
        plan,
        primary,
        profile,
        scenario,
        evidence_scope,
        candidate,
        provider,
    )


def execute_goal_plan_invocation_v1(
    invocation: GoalPlanInvocationV1,
) -> GoalPlanRunV1 | GoalPlanFailureV1:
    """Capture, resolve, evaluate, and seal one V1 invocation.

    Expected domain/capability errors become a typed failure assessment.  A
    successful return is always a fully validated ``EvaluationRunV1``; it is
    never a partial run whose zero rows could be read as false.
    """

    if not isinstance(invocation, GoalPlanInvocationV1):
        raise GoalPlanRuntimeError(
            "invocation must be GoalPlanInvocationV1", code="GOAL_INVOCATION_INVALID"
        )
    try:
        _assert_invocation_matches_plan(invocation)
        assert_targeted_evaluation_query_current(invocation.primary)
        if invocation.candidate is not None:
            assert_targeted_evaluation_query_current(invocation.candidate)
        return _execute_goal_plan(invocation)
    except GoalPlanRuntimeError as exc:
        return _failure(invocation, exc.code, type(exc).__name__)
    except PortableEvaluationError as exc:
        return _failure(invocation, exc.code, type(exc).__name__)
    except (
        ScenarioResolutionErrorV1,
        ProviderMaterializationError,
        ProviderRelationMaterializationError,
    ) as exc:
        return _failure(invocation, exc.code, type(exc).__name__)
    except Exception as exc:  # noqa: BLE001 - fail closed; never repackage as an empty result: engine/provider/scenario faults become a typed GOAL_EXECUTION_FAILED assessment.
        return _failure(invocation, "GOAL_EXECUTION_FAILED", type(exc).__name__)


def _assert_invocation_matches_plan(invocation: GoalPlanInvocationV1) -> None:
    """Reject an in-memory splice before it can observe a live relation.

    ``GoalPlanInvocationV1`` deliberately keeps an in-process graph reference
    out of its durable protocol payload.  That convenience must not turn its
    public frozen dataclass fields into independent authority: a caller using
    ``dataclasses.replace`` (or an accidental wrapper bug) cannot substitute a
    different compiled Query, Scenario, provider, candidate, profile, or
    admission scope beneath an already sealed GoalPlan.
    """

    try:
        GoalPlanV1.__post_init__(invocation.plan)
        EvaluationExecutionProfileV1.__post_init__(invocation.profile)
        EvidenceScopeV1.__post_init__(invocation.evidence_scope)
        if invocation.scenario is not None:
            ScenarioSpecV1.__post_init__(invocation.scenario)
    except Exception as exc:
        raise GoalPlanRuntimeError(
            "GoalPlan invocation has malformed sealed intent",
            code="GOAL_INVOCATION_PROTOCOL_INVALID",
        ) from exc
    if _target_ref(invocation.primary, provider=invocation.provider) != invocation.plan.target:
        raise GoalPlanRuntimeError(
            "GoalPlan target does not match its compiled Query/provider",
            code="GOAL_INVOCATION_TARGET_SPLICE",
        )
    if _query_token(invocation.primary) != invocation.plan.query_digest:
        raise GoalPlanRuntimeError(
            "GoalPlan query digest does not match its compiled Query",
            code="GOAL_INVOCATION_QUERY_SPLICE",
        )
    selections = tuple(
        GoalSelectionV1(item.alias, item.value_type)
        for item in invocation.primary.compiled_query.selections
    )
    if selections != invocation.plan.selections:
        raise GoalPlanRuntimeError(
            "GoalPlan selections do not match its compiled Query",
            code="GOAL_INVOCATION_SELECTION_SPLICE",
        )
    scenario_digest = None if invocation.scenario is None else invocation.scenario.spec_digest
    if scenario_digest != invocation.plan.scenario_request_digest:
        raise GoalPlanRuntimeError(
            "GoalPlan Scenario does not match its sealed request",
            code="GOAL_INVOCATION_SCENARIO_SPLICE",
        )
    if invocation.evidence_scope.scope_digest != invocation.plan.evidence_scope_digest:
        raise GoalPlanRuntimeError(
            "GoalPlan evidence scope does not match its sealed admission intent",
            code="GOAL_INVOCATION_SCOPE_SPLICE",
        )
    if invocation.profile.profile_digest != invocation.plan.execution_profile_digest:
        raise GoalPlanRuntimeError(
            "GoalPlan profile does not match its sealed execution pin",
            code="GOAL_INVOCATION_PROFILE_SPLICE",
        )
    if (invocation.candidate is None) != (invocation.plan.candidate_target is None):
        raise GoalPlanRuntimeError(
            "GoalPlan candidate presence does not match its sealed target",
            code="GOAL_INVOCATION_CANDIDATE_SPLICE",
        )
    if invocation.candidate is not None:
        if _target_ref(invocation.candidate, provider=None) != invocation.plan.candidate_target:
            raise GoalPlanRuntimeError(
                "GoalPlan candidate target does not match its compiled Query",
                code="GOAL_INVOCATION_CANDIDATE_SPLICE",
            )
        if _query_token(invocation.candidate) != invocation.plan.candidate_query_digest:
            raise GoalPlanRuntimeError(
                "GoalPlan candidate query does not match its sealed target invocation",
                code="GOAL_INVOCATION_CANDIDATE_SPLICE",
            )
        if invocation.provider is not None:
            raise GoalPlanRuntimeError(
                "GoalPlan provider/candidate combination is unsupported",
                code="GOAL_PROVIDER_CANDIDATE_UNSUPPORTED",
            )


def _execute_goal_plan(invocation: GoalPlanInvocationV1) -> GoalPlanRunV1:
    graph = invocation._graph
    schema_ir = graph.schema_ir
    schema_index = graph._application_schema_index
    primary_program, _ = _materialize_adapter_derivation_plan(
        invocation.primary.compiled_query._lowering_plan,
        engine="native",
    )
    primary_dependencies = portable_dependency_predicate_ids_v1(
        primary_program, schema_ir=schema_ir
    )
    primary_dependencies = _expand_virtual_entity_dependencies_v1(
        primary_dependencies, schema_ir=schema_ir
    )
    candidate_program = None
    candidate_dependencies: tuple[str, ...] = ()
    if invocation.candidate is not None:
        candidate_program, _ = _materialize_adapter_derivation_plan(
            invocation.candidate.compiled_query._lowering_plan,
            engine="native",
        )
        candidate_dependencies = portable_dependency_predicate_ids_v1(
            candidate_program, schema_ir=schema_ir
        )
        candidate_dependencies = _expand_virtual_entity_dependencies_v1(
            candidate_dependencies, schema_ir=schema_ir
        )
    # A candidate may legitimately add or remove an extensional dependency.
    # The *world* is nevertheless the same immutable Scenario world for both
    # targets, so capture the canonical union once and select each program's
    # exact dependency subset immediately before its isolated execution.  Do
    # not force policy authors to preserve incidental dependency inventory just
    # to compare two immutable business rules.
    dependency_ids = tuple(sorted(set(primary_dependencies) | set(candidate_dependencies)))

    # One live view capture.  Every later resolver/adapter consumes detached
    # ProjectedFact tuples selected from this snapshot, never ``graph._store``.
    base_view_digest = graph._view_snapshot_digest(query_typed_values=True)
    full_relation = project_view_facts_with_witness(graph.ledger, schema_ir)
    if graph._view_snapshot_digest(query_typed_values=True) != base_view_digest:
        raise GoalPlanRuntimeError(
            "FactGraph view changed while the GoalPlan input relation was captured",
            code="GOAL_VIEW_CHANGED_DURING_CAPTURE",
        )
    admitted = apply_evidence_scope_v1(full_relation, invocation.evidence_scope)
    if invocation.scenario is not None:
        # Program dependencies answer the Rule/Policy.  A Scenario has its
        # own explicit finite input requirements (visibility anchors,
        # ephemeral identity anchors, relation targets, or one debug witness).
        # Resolve those requirements only from the already admitted projected
        # relation and union them before the one sealed world is selected.
        dependency_ids = tuple(
            sorted(
                set(dependency_ids)
                | set(
                    scenario_dependency_predicate_ids_v1(
                        invocation.scenario,
                        schema_index=schema_index,
                        admitted_relation=admitted.relation,
                    )
                )
            )
        )
    baseline_relation = select_dependency_relation_v1(
        admitted.relation,
        dependency_predicate_ids=dependency_ids,
    )
    admissibility_digest = _admissibility_digest(
        scope_digest=invocation.evidence_scope.scope_digest,
        application_digest=admitted.admissibility_digest,
        provider_digest=None,
    )
    provider_receipts: tuple[ProviderReceiptRefV1, ...] = ()
    if invocation.provider is not None:
        # A provider receives no Store capability, but Python callbacks may
        # still close over arbitrary caller state.  Capture the live-view pin
        # immediately around the call so a persistent Ledger/view mutation is
        # never folded into a seemingly normal V1 result.  This is detection,
        # not a sandbox or rollback mechanism: provider code remains a trusted
        # in-process extension until a separately authorized isolation model
        # exists.
        provider_view_digest = graph._view_snapshot_digest(query_typed_values=True)
        if provider_view_digest != base_view_digest:
            raise GoalPlanRuntimeError(
                "FactGraph view changed after GoalPlan capture and before provider materialization",
                code="GOAL_VIEW_CHANGED_BEFORE_PROVIDER",
            )
        provider_request = ProviderRequestV1(
            provider_digest=invocation.provider.provider_digest,
            query_digest=invocation.plan.query_digest,
            schema_digest=invocation.primary.compiled_query.schema_digest,
            dependency_predicate_ids=dependency_ids,
            supplied_predicate_ids=invocation.provider.supplied_predicate_ids,
            bindings=_provider_bindings(invocation.primary),
        )
        materialization = invoke_relation_provider_v1(invocation.provider, provider_request)
        if graph._view_snapshot_digest(query_typed_values=True) != provider_view_digest:
            raise GoalPlanRuntimeError(
                "FactGraph view changed while RelationProviderV1 materialized its result",
                code="GOAL_VIEW_CHANGED_DURING_PROVIDER",
            )
        baseline_relation = merge_provider_materialization_v1(
            baseline_relation,
            request=provider_request,
            materialization=materialization,
            schema_ir=schema_ir,
        )
        provider_receipts = (materialization.to_receipt_ref_v1(),)
        admissibility_digest = _admissibility_digest(
            scope_digest=invocation.evidence_scope.scope_digest,
            application_digest=admitted.admissibility_digest,
            provider_digest=materialization.materialization_digest,
        )

    resolved = resolve_scenario_v1(
        ScenarioSpecV1(()) if invocation.scenario is None else invocation.scenario,
        schema_index=schema_index,
        baseline_relation=baseline_relation,
        base_view_digest=base_view_digest,
        admissibility_digest=admissibility_digest,
    )
    baseline_relation = effective_world_to_relation_v1(resolved.baseline_world)
    effective_relation = effective_world_to_relation_v1(resolved.effective_world)
    baseline_execution_relation = select_dependency_relation_v1(
        baseline_relation, dependency_predicate_ids=primary_dependencies
    )
    effective_execution_relation = select_dependency_relation_v1(
        effective_relation, dependency_predicate_ids=primary_dependencies
    )
    baseline_capture = capture_evaluation_replay_world_v1(
        side="baseline",
        schema_ir=schema_ir,
        semantic_world_digest=resolved.baseline_world.world_digest,
        resolution_evidence_digest=resolved.resolution_evidence_digest,
        closure_target_digests=tuple(
            target.target_digest for target in resolved.baseline_world.closure.targets
        ),
        relations=select_dependency_relation_v1(
            baseline_relation,
            dependency_predicate_ids=dependency_ids,
        ),
    )
    effective_capture = capture_evaluation_replay_world_v1(
        side="effective",
        schema_ir=schema_ir,
        semantic_world_digest=resolved.effective_world.world_digest,
        resolution_evidence_digest=resolved.resolution_evidence_digest,
        closure_target_digests=tuple(
            target.target_digest for target in resolved.effective_world.closure.targets
        ),
        relations=select_dependency_relation_v1(
            effective_relation,
            dependency_predicate_ids=dependency_ids,
        ),
    )
    baseline_side = _evaluate_side(
        name="baseline",
        world=resolved.baseline_world,
        resolved=resolved,
        relation=baseline_execution_relation,
        program=primary_program,
        plan=invocation.plan,
        profile=invocation.profile,
        schema_ir=schema_ir,
        world_capture_digest=baseline_capture.world_capture_digest,
        is_effective=False,
    )
    effective_side = _evaluate_side(
        name="effective",
        world=resolved.effective_world,
        resolved=resolved,
        relation=effective_execution_relation,
        program=primary_program,
        plan=invocation.plan,
        profile=invocation.profile,
        schema_ir=schema_ir,
        world_capture_digest=effective_capture.world_capture_digest,
        is_effective=True,
    )

    candidate_plan = None
    candidate_side = None
    if invocation.candidate is not None:
        assert candidate_program is not None
        candidate_plan = GoalPlanV1(
            target=_target_ref(invocation.candidate, provider=None),
            query_digest=_query_token(invocation.candidate),
            result_mode=invocation.plan.result_mode,
            selections=invocation.plan.selections,
            scenario_request_digest=invocation.plan.scenario_request_digest,
            evidence_scope_digest=invocation.plan.evidence_scope_digest,
            execution_profile_digest=invocation.profile.profile_digest,
        )
        candidate_side = _evaluate_side(
            name="candidate_effective",
            world=resolved.effective_world,
            resolved=resolved,
            relation=select_dependency_relation_v1(
                effective_relation,
                dependency_predicate_ids=candidate_dependencies,
            ),
            program=candidate_program,
            plan=candidate_plan,
            profile=invocation.profile,
            schema_ir=schema_ir,
            world_capture_digest=effective_capture.world_capture_digest,
            is_effective=True,
        )

    replay_payload = _build_replay_payload(
        invocation,
        primary_program=primary_program,
        candidate_program=candidate_program,
        provider_receipts=provider_receipts,
        candidate_plan=candidate_plan,
        baseline_capture=baseline_capture,
        effective_capture=effective_capture,
        resolved=resolved,
    )
    run = EvaluationRunV1(
        plan=invocation.plan,
        execution_profile=invocation.profile,
        replay_payload=replay_payload,
        baseline=baseline_side,
        effective=effective_side,
        candidate_plan=candidate_plan,
        candidate_effective=candidate_side,
    )
    comparison = _comparison_if_available(run)
    scenario_diff = _scenario_diff_if_available(run)
    return GoalPlanRunV1(run, comparison, scenario_diff)


def _evaluate_side(
    *,
    name: Literal["baseline", "effective", "candidate_effective"],
    world: EffectiveWorldV1,
    resolved: ResolvedScenarioV1,
    relation: Mapping[str, Sequence[ProjectedFact]],
    program: object,
    plan: GoalPlanV1,
    profile: EvaluationExecutionProfileV1,
    schema_ir: dict[str, Any],
    world_capture_digest: str,
    is_effective: bool,
) -> EvaluationRunSideV1:
    # ``program`` remains object here to keep import ownership localized; the
    # isolated executor validates it is an actual CompiledDerivationPlan.
    if profile.kind == "portable_deterministic_v1":
        observed = observe_portable_deterministic_v1(  # type: ignore[arg-type]
            program,
            schema_ir=schema_ir,
            effective_relations=relation,
        )
        observations = observed.frames
    else:
        observations = (
            PortableEngineObservationFrameV1(
                engine="native",
                status="succeeded",
                evaluation=execute_native_deterministic_v1(  # type: ignore[arg-type]
                    program,
                    schema_ir=schema_ir,
                    effective_relations=relation,
                ),
            ),
        )
    frames: list[EvaluationEngineResultV1] = []
    for observed_frame in observations:
        if observed_frame.status == "succeeded":
            assert observed_frame.evaluation is not None
            engine_result = _goal_result_from_rows(
                plan,
                observed_frame.evaluation.rows,
                world=world,
                is_effective=is_effective,
            )
            frames.append(EvaluationEngineResultV1(observed_frame.engine, engine_result))
        else:
            assert observed_frame.diagnostic is not None
            frames.append(
                EvaluationEngineResultV1(
                    engine=observed_frame.engine,
                    result=None,
                    status=observed_frame.status,
                    diagnostic_code=observed_frame.diagnostic.code,
                    diagnostic_detail_digest=observed_frame.diagnostic.detail_digest,
                )
            )
    canonical_frame = frames[0]
    if canonical_frame.status != "succeeded" or canonical_frame.result is None:
        raise GoalPlanRuntimeError(
            "the Native canonical engine did not produce a result",
            code="GOAL_CANONICAL_ENGINE_UNAVAILABLE",
        )
    result = canonical_frame.result
    if profile.kind == "native_deterministic_v1":
        parity: Literal["equivalent", "different", "unsupported", "unresolved", "not_requested"] = (
            "not_requested"
        )
        capability: Literal["supported", "unresolved"] = "supported"
    elif any(frame.status == "failed" for frame in frames):
        parity = "unresolved"
        capability = "unresolved"
    elif any(frame.status == "unsupported" for frame in frames):
        parity = "unsupported"
        capability = "unresolved"
    else:
        parity = (
            "equivalent"
            if len({frame.semantic_row_set_digest for frame in frames}) == 1
            else "different"
        )
        capability = "supported"
    assessment = _assessment_for_result(
        plan,
        result,
        scenario_requested=plan.scenario_request_digest is not None,
        is_effective=is_effective,
        world=world,
        parity=parity,
        capability=capability,
    )
    return EvaluationRunSideV1(
        name=name,
        plan_digest=plan.plan_digest,
        world_side="baseline" if name == "baseline" else "effective",
        world_capture_digest=world_capture_digest,
        canonical_result=result,
        engine_results=tuple(frames),
        assessment=assessment,
    )


def _goal_result_from_rows(
    plan: GoalPlanV1,
    rows: Sequence[PortableSelectedRowV1],
    *,
    world: EffectiveWorldV1,
    is_effective: bool,
) -> GoalResultV1:
    logical_rows = tuple(_goal_row(plan, row) for row in rows)
    exists_value: GoalExistsValueV1 | None
    if plan.result_mode == "exists":
        result_rows = logical_rows[:1]
        exists_value = "true" if logical_rows else "false"
        count_value = None
    elif plan.result_mode == "count":
        result_rows = logical_rows
        exists_value = None
        count_value = len(logical_rows)
    else:
        result_rows = logical_rows
        exists_value = None
        count_value = None
    outcomes = _evaluate_expectations(
        plan,
        result_rows=result_rows,
        all_rows=logical_rows,
        world=world,
        is_effective=is_effective,
    )
    return GoalResultV1(
        plan_digest=plan.plan_digest,
        result_mode=plan.result_mode,
        completeness="complete",
        rows=result_rows,
        exists_value=exists_value,
        count_value=count_value,
        expectation_outcomes=outcomes,
    )


def _goal_row(plan: GoalPlanV1, row: PortableSelectedRowV1) -> GoalResultRowV1:
    if len(row.terms) != len(plan.selections):
        raise GoalPlanRuntimeError(
            "engine projection width does not match GoalPlan selections",
            code="GOAL_PROJECTION_WIDTH_MISMATCH",
        )
    values: list[tuple[str, GoalValueV1]] = []
    for selection, (tag, raw) in zip(plan.selections, row.terms, strict=True):
        if tag != selection.value_tag:
            raise GoalPlanRuntimeError(
                "engine projection type does not match GoalPlan selection",
                code="GOAL_PROJECTION_TYPE_MISMATCH",
            )
        values.append((selection.alias, _goal_value_from_raw(tag, raw)))
    return GoalResultRowV1(tuple(values))


def _evaluate_expectations(
    plan: GoalPlanV1,
    *,
    result_rows: tuple[GoalResultRowV1, ...],
    all_rows: tuple[GoalResultRowV1, ...],
    world: EffectiveWorldV1,
    is_effective: bool,
) -> tuple[GoalExpectationOutcomeV1, ...]:
    outcomes: list[GoalExpectationOutcomeV1] = []
    for expectation in plan.expectations:
        status: GoalExpectationStatusV1
        matches: tuple[str, ...] = ()
        code: str
        if isinstance(expectation, ContainsRowExpectationV1):
            matches = tuple(
                sorted(
                    row.semantic_row_digest
                    for row in result_rows
                    if _row_matches(row, expectation.row)
                )
            )
            status = "satisfied" if matches else "not_satisfied"
            code = "GOAL_CONTAINS_ROW_SATISFIED" if matches else "GOAL_CONTAINS_ROW_NOT_SATISFIED"
        elif isinstance(expectation, ExistsExpectationV1):
            actual = bool(all_rows)
            if actual == expectation.expected:
                status = "satisfied"
                code = "GOAL_EXISTS_SATISFIED"
            else:
                status = "not_satisfied"
                code = "GOAL_EXISTS_NOT_SATISFIED"
        elif isinstance(expectation, CountEqExpectationV1):
            if len(all_rows) == expectation.expected_count:
                status = "satisfied"
                code = "GOAL_COUNT_SATISFIED"
            else:
                status = "not_satisfied"
                code = "GOAL_COUNT_NOT_SATISFIED"
        elif isinstance(expectation, SetEqualsExpectationV1):
            set_actual = {_row_value_shape(row) for row in all_rows}
            expected = {
                tuple((alias, value.tag, value.value_digest) for alias, value in item.values)
                for item in expectation.rows
            }
            if set_actual == expected:
                status = "satisfied"
                code = "GOAL_SET_EQUALS_SATISFIED"
            else:
                status = "not_satisfied"
                code = "GOAL_SET_EQUALS_NOT_SATISFIED"
        elif isinstance(expectation, ExactLocalAbsenceExpectationV1):
            if not is_effective:
                status = "underdetermined"
                code = "GOAL_EXACT_LOCAL_CLOSURE_NOT_EFFECTIVE"
            elif expectation.closure_target not in world.closure.targets:
                status = "underdetermined"
                code = "GOAL_EXACT_LOCAL_CLOSURE_UNRESOLVED"
            elif _closure_target_holds(expectation.closure_target, world):
                status = "satisfied"
                code = "GOAL_EXACT_LOCAL_ABSENCE_SATISFIED"
            else:
                raise GoalPlanRuntimeError(
                    "Scenario closure target does not match its sealed effective world",
                    code="GOAL_EXACT_LOCAL_CLOSURE_INTEGRITY",
                )
        else:  # pragma: no cover - closed union guard.
            raise GoalPlanRuntimeError(
                "unknown GoalPlan expectation", code="GOAL_EXPECTATION_UNKNOWN"
            )
        outcomes.append(
            GoalExpectationOutcomeV1(
                expectation.expectation_id,
                expectation.expectation_digest,
                expectation.kind,
                status,
                matches,
                code,
            )
        )
    return tuple(outcomes)


def _assessment_for_result(
    plan: GoalPlanV1,
    result: GoalResultV1,
    *,
    scenario_requested: bool,
    is_effective: bool,
    world: EffectiveWorldV1,
    parity: Literal["equivalent", "different", "unsupported", "unresolved", "not_requested"],
    capability: Literal["supported", "unresolved"],
) -> GoalTechnicalAssessmentV1:
    statuses = tuple(item.status for item in result.expectation_outcomes)
    if not statuses:
        expectation: GoalExpectationStatusV1 | Literal["not_requested"] = "not_requested"
    elif "unsupported" in statuses:
        expectation = "unsupported"
    elif "underdetermined" in statuses:
        expectation = "underdetermined"
    elif "not_satisfied" in statuses:
        expectation = "not_satisfied"
    else:
        expectation = "satisfied"
    absence_requested = any(
        isinstance(item, ExactLocalAbsenceExpectationV1) for item in plan.expectations
    )
    if not absence_requested:
        closure: ExactLocalClosureStateV1 = "not_requested"
    elif not is_effective:
        closure = "required"
    elif all(
        item.closure_target in world.closure.targets
        for item in plan.expectations
        if isinstance(item, ExactLocalAbsenceExpectationV1)
    ):
        closure = "resolved"
    else:
        closure = "unresolved"
    return GoalTechnicalAssessmentV1(
        plan_digest=plan.plan_digest,
        result_digest=result.result_digest,
        scenario_resolution="resolved" if scenario_requested else "not_requested",
        execution="succeeded",
        parity=parity,
        completeness=result.completeness,
        expectation=expectation,
        explain="available",
        replay="available",
        contract_validity="valid",
        exact_local_closure=closure,
        capability=capability,
    )


def _build_replay_payload(
    invocation: GoalPlanInvocationV1,
    *,
    primary_program: object,
    candidate_program: object | None,
    provider_receipts: tuple[ProviderReceiptRefV1, ...],
    candidate_plan: GoalPlanV1 | None,
    baseline_capture: object,
    effective_capture: object,
    resolved: ResolvedScenarioV1,
) -> EvaluationReplayPayloadV1:
    if not isinstance(baseline_capture, type(effective_capture)):
        raise GoalPlanRuntimeError(
            "replay world captures are malformed", code="GOAL_REPLAY_CAPTURE_INVALID"
        )
    return capture_evaluation_replay_payload_v1(
        schema_ir=invocation._graph.schema_ir,
        address_space_digest=_sha_token_from_digest(
            invocation.primary.compiled_query.address_space_digest,
            label="address space",
        ),
        plan=invocation.plan,
        execution_profile=invocation.profile,
        primary_compiled_plan=primary_program,  # type: ignore[arg-type]
        baseline_world=baseline_capture,  # type: ignore[arg-type]
        effective_world=effective_capture,  # type: ignore[arg-type]
        candidate_plan=candidate_plan,
        candidate_compiled_plan=candidate_program,  # type: ignore[arg-type]
        primary_policy_structure=invocation.primary.target.run_target.policy_structure,
        candidate_policy_structure=(
            None
            if invocation.candidate is None
            else invocation.candidate.target.run_target.policy_structure
        ),
        primary_run_target=invocation.primary.target.run_target,
        candidate_run_target=(
            None if invocation.candidate is None else invocation.candidate.target.run_target
        ),
        primary_lowering_plan=invocation.primary.compiled_query._lowering_plan,
        candidate_lowering_plan=(
            None
            if invocation.candidate is None
            else invocation.candidate.compiled_query._lowering_plan
        ),
        scenario_operations=(
            None if invocation.scenario is None else resolved.effective_world.operations
        ),
        provider_receipts=provider_receipts,
    )


def _closure_target_holds(target: ExactLocalClosureTargetV1, world: EffectiveWorldV1) -> bool:
    facts = world.facts
    if target.kind == "field":
        return not any(
            fact.predicate_id == target.predicate_id
            and fact.values
            and fact.values[0].to_raw() == target.entity_ref
            for fact in facts
        )
    if target.kind == "member":
        return not any(
            fact.predicate_id == target.predicate_id
            and len(fact.values) >= 2
            and fact.values[0].to_raw() == target.entity_ref
            and fact.values[1] == target.value
            for fact in facts
        )
    if target.kind == "exact_set":
        actual = {
            fact.values[1]
            for fact in facts
            if fact.predicate_id == target.predicate_id
            and len(fact.values) >= 2
            and fact.values[0].to_raw() == target.entity_ref
        }
        return actual == set(target.members)
    if target.kind == "relation":
        return not any(fact.predicate_id == target.predicate_id for fact in facts)
    if target.kind == "entity":
        return not any(
            value.tag == "entity_ref" and value.to_raw() == target.entity_ref
            for fact in facts
            for value in fact.values
        )
    if target.kind == "assertion":
        return not any(fact.witness_id == target.assertion_id for fact in facts)
    raise AssertionError("validated closure target kind is unreachable")


def _provider_bindings(
    primary: TargetedCompiledEvaluationQueryV0,
) -> tuple[tuple[str, GoalValueV1], ...]:
    """Expose bindings under opaque structured-address slots, never dotted paths.

    Provider contracts name stable slot IDs, while the underlying Query keeps
    its ``SemanticPortAddress``.  This avoids inventing a lossy textual path
    grammar for aliases or port names that may themselves contain punctuation.
    """

    values: list[tuple[str, GoalValueV1]] = []
    for binding in primary.compiled_query.bindings:
        alias = provider_binding_slot_v1(
            binding.address.occurrence_alias,
            binding.address.port_name,
        )
        values.append((alias, _goal_value_from_raw(binding.value_type, binding.normalized_value)))
    return tuple(values)


def provider_binding_slot_v1(occurrence_alias: str, port_name: str) -> str:
    """Return the opaque canonical Provider slot for one structured port.

    Args:
        occurrence_alias: Structured Rule occurrence alias.
        port_name: Public semantic-port name.

    Returns:
        A stable opaque slot token for a Provider request.

    Raises:
        GoalPlanRuntimeError: If either name is empty.
    """

    if not isinstance(occurrence_alias, str) or not occurrence_alias:
        raise GoalPlanRuntimeError(
            "provider occurrence alias is invalid", code="GOAL_PROVIDER_SLOT_INVALID"
        )
    if not isinstance(port_name, str) or not port_name:
        raise GoalPlanRuntimeError(
            "provider port name is invalid", code="GOAL_PROVIDER_SLOT_INVALID"
        )
    return "slot:" + sha256_hex(
        _canonical_json_bytes({"occurrence_alias": occurrence_alias, "port_name": port_name})
    )


def _expand_virtual_entity_dependencies_v1(
    dependency_ids: tuple[str, ...],
    *,
    schema_ir: Mapping[str, Any],
) -> tuple[str, ...]:
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


def _target_ref(
    targeted: TargetedCompiledEvaluationQueryV0,
    *,
    provider: RelationProviderV1 | None,
) -> GoalTargetRefV1:
    target = targeted.target.run_target
    if provider is None:
        return GoalTargetRefV1(
            target.original_target_kind,
            target.target_id,
            target.target_version,
            _sha_token_from_digest(target.target_digest, label="target"),
        )
    composite = sha256_token(
        _canonical_json_bytes(
            {
                "format": "relation_provider_query_target_v1",
                "base_target_digest": target.target_digest,
                "provider_digest": provider.provider_digest,
            }
        )
    )
    return GoalTargetRefV1(
        "relation_provider",
        f"{target.target_id}@{provider.provider_id}",
        provider.version,
        composite,
    )


def _query_token(targeted: TargetedCompiledEvaluationQueryV0) -> str:
    return _sha_token_from_digest(targeted.compiled_query.query_digest, label="Query")


def _sha_token_from_digest(value: object, *, label: str) -> str:
    raw: object
    if isinstance(value, str) and value.startswith("sha256:"):
        raw = value[7:]
    else:
        raw = value
    if (
        not isinstance(raw, str)
        or len(raw) != 64
        or raw != raw.lower()
        or any(character not in "0123456789abcdef" for character in raw)
    ):
        raise GoalPlanRuntimeError(
            f"compiled {label} digest is not sha256 hex",
            code="GOAL_DIGEST_INVALID",
        )
    return f"sha256:{raw}"


def _assert_candidate_projection(
    primary: TargetedCompiledEvaluationQueryV0,
    candidate: TargetedCompiledEvaluationQueryV0,
) -> None:
    primary_shape = tuple(
        (item.alias, item.value_type) for item in primary.compiled_query.selections
    )
    candidate_shape = tuple(
        (item.alias, item.value_type) for item in candidate.compiled_query.selections
    )
    if primary_shape != candidate_shape:
        raise GoalPlanRuntimeError(
            "candidate Query must expose the same ordered selection aliases and types",
            code="GOAL_CANDIDATE_PROJECTION_MISMATCH",
        )


def _row_matches(row: GoalResultRowV1, expected: GoalRowExpectationV1) -> bool:
    actual = dict(row.values)
    return all(actual.get(alias) == value for alias, value in expected.values)


def _row_value_shape(row: GoalResultRowV1) -> tuple[tuple[str, str, str], ...]:
    return tuple((alias, value.tag, value.value_digest) for alias, value in row.values)


def _goal_value_from_raw(tag: str, raw: object) -> GoalValueV1:
    try:
        _index, normalized, canonical_tag = claim_args_from_rest_terms([(tag, raw)])[0]
        return GoalValueV1(canonical_tag, normalized)
    except (TypeError, ValueError) as exc:
        raise GoalPlanRuntimeError(
            "value cannot enter canonical GoalPlan storage", code="GOAL_VALUE_INVALID"
        ) from exc


def _admissibility_digest(
    *,
    scope_digest: str,
    application_digest: str,
    provider_digest: str | None,
) -> str:
    return sha256_token(
        _canonical_json_bytes(
            {
                "format": "goal_plan_v1_admissibility",
                "scope_digest": scope_digest,
                "application_digest": application_digest,
                "provider_materialization_digest": provider_digest,
            }
        )
    )


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise GoalPlanRuntimeError(
            "value is not canonical JSON", code="GOAL_CANONICAL_JSON_INVALID"
        ) from exc


def _failure(invocation: GoalPlanInvocationV1, code: str, detail: str) -> GoalPlanFailureV1:
    """Project a typed rejection into independent technical assessment axes.

    A sealed Query splice is a contract-integrity failure; an impossible
    Scenario algebra is a resolution conflict; a fragment outside the finite
    profile is a capability rejection.  None of those should collapse into
    the former catch-all ``execution=failed`` status merely because no rows
    were evaluated.
    """

    unsupported = "UNSUPPORTED" in code or code in {
        "SCENARIO_TARGET_OUTSIDE_DEPENDENCY",
        "SCENARIO_DEPENDENCY_MISSING",
        "SCENARIO_EPHEMERAL_DEPENDENCY_UNAVAILABLE",
        "SCENARIO_RELATION_ENTITY_VISIBILITY_UNAVAILABLE",
        # Identity/existence mutation is intentionally outside the V1
        # Scenario algebra, not an engine failure or an unresolved fact.
        "SCENARIO_PROTECTED_FIELD",
    }
    scenario_conflict = code == "SCENARIO_OPERATION_CONFLICT"
    contract_invalid = (
        code.startswith((
            "GOAL_INVOCATION_",
            "GOAL_PRIMARY_INVALID",
            "GOAL_PROFILE_INVALID",
            "GOAL_SCOPE_INVALID",
            "GOAL_SCENARIO_INVALID",
            "GOAL_EXPECTATIONS_INVALID",
            "GOAL_PROVIDER_INVALID",
        ))
        or code.endswith(("_SPLICE", "_PROTOCOL_INVALID"))
    )
    scenario_resolution: ScenarioResolutionStateV1
    if invocation.scenario is None:
        scenario_resolution = "not_requested"
    elif scenario_conflict:
        scenario_resolution = "conflict"
    elif unsupported:
        scenario_resolution = "unsupported"
    else:
        scenario_resolution = "unresolved"
    assessment = GoalTechnicalAssessmentV1(
        plan_digest=invocation.plan.plan_digest,
        result_digest=None,
        scenario_resolution=scenario_resolution,
        execution="unsupported" if unsupported else "failed",
        parity="unsupported"
        if unsupported and invocation.profile.kind == "portable_deterministic_v1"
        else (
            "not_requested"
            if invocation.profile.kind == "native_deterministic_v1"
            else "unresolved"
        ),
        completeness="unsupported" if unsupported else "unknown",
        expectation="not_requested",
        explain="unavailable",
        replay="unavailable",
        contract_validity="invalid" if contract_invalid else "valid",
        exact_local_closure=(
            "not_requested"
            if not any(
                isinstance(item, ExactLocalAbsenceExpectationV1)
                for item in invocation.plan.expectations
            )
            else "unsupported"
            if unsupported
            else "unresolved"
        ),
        capability="rejected" if unsupported else "unresolved",
    )
    return GoalPlanFailureV1(
        invocation.plan,
        assessment,
        code,
        sha256_token(_canonical_json_bytes({"code": code, "detail": detail})),
    )


def _comparison_if_available(run: EvaluationRunV1) -> PolicyVariantComparisonV1 | None:
    if run.candidate_plan is None:
        return None
    try:
        from .evaluation_run_v1_runtime import compare_policy_variants_v1
    except ImportError:  # temporary during staged implementation; no durable claim.
        return None
    return compare_policy_variants_v1(run)


def _scenario_diff_if_available(run: EvaluationRunV1) -> ScenarioDiffV1 | None:
    """Return the sealed Scenario view only for an explicitly Scenario-bound run.

    This deliberately does not infer a ``what-if`` merely because every V1
    run carries uniform baseline/effective worlds.  The runtime helper derives
    input and normalized-result differences from the captured worlds only; it
    neither rereads a Store nor attributes causality to an operation.
    """

    if run.plan.scenario_request_digest is None:
        return None
    from .evaluation_run_v1_runtime import diff_scenario_run_v1

    return diff_scenario_run_v1(run)


__all__ = [
    "GOAL_PLAN_V1_COMPILER_DIGEST",
    "GoalPlanFailureV1",
    "GoalPlanInvocationV1",
    "GoalPlanRunV1",
    "GoalPlanRuntimeError",
    "build_goal_plan_invocation_v1",
    "execute_goal_plan_invocation_v1",
    "native_deterministic_profile_v1",
    "portable_deterministic_profile_v1",
    "provider_binding_slot_v1",
]
