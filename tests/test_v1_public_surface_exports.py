"""Import-only smoke coverage for the deliberately separate Q18 V1 surface."""

from __future__ import annotations

import factgraph.application as application
import factgraph.application.protocol as protocol
import factgraph.sdk as sdk
from factgraph.application.evaluation_run_v1_runtime import (
    EvaluationRunExplanationV1,
    EvaluationRunReplayV1,
    PolicyVariantComparisonV1,
    ScenarioDiffV1,
)
from factgraph.application.goal_plan_v1_runtime import (
    GoalPlanFailureV1,
    GoalPlanInvocationV1,
    GoalPlanRunV1,
    native_deterministic_profile_v1,
    portable_deterministic_profile_v1,
    provider_binding_slot_v1,
)
from factgraph.application.protocol import (
    ContainsRowExpectationV1,
    CountEqExpectationV1,
    EvaluationEnginePinV1,
    EvaluationExecutionProfileV1,
    EvaluationRunV1,
    EvidenceScopeV1,
    ExactLocalAbsenceExpectationV1,
    ExactLocalClosureTargetV1,
    ExistsExpectationV1,
    ExplainTargetV1,
    GoalPlanV1,
    GoalResultRowV1,
    GoalResultV1,
    GoalRowExpectationV1,
    GoalTechnicalAssessmentV1,
    GoalValueV1,
    ProviderMaterializationV1,
    ProviderRelationRowV1,
    ProviderRequestV1,
    RelationProviderV1,
    ScenarioCreateEphemeralEntityV1,
    ScenarioEnsureMemberV1,
    ScenarioEnsureRelationV1,
    ScenarioSetEffectiveValueV1,
    ScenarioSetExactMembersV1,
    ScenarioSpecV1,
    ScenarioValueV1,
    ScenarioWithoutEntityV1,
    ScenarioWithoutAssertionV1,
    ScenarioWithoutFieldV1,
    ScenarioWithoutRelationV1,
    ScenarioWithoutValueV1,
    SetEqualsExpectationV1,
)
from factgraph.sdk.evaluation_query_builder import (
    EvaluationQueryBuilderV1,
    ProviderQueryTargetV1,
    ScenarioGoalPlanBuilderV1,
)


V1_SDK_EXPORTS = frozenset(
    {
        "EvaluationQueryBuilderV1",
        "ProviderQueryTargetV1",
        "ScenarioGoalPlanBuilderV1",
        "GoalPlanInvocationV1",
        "GoalPlanRunV1",
        "GoalPlanFailureV1",
        "GoalPlanV1",
        "GoalValueV1",
        "GoalRowExpectationV1",
        "ContainsRowExpectationV1",
        "ExactLocalAbsenceExpectationV1",
        "ExistsExpectationV1",
        "CountEqExpectationV1",
        "SetEqualsExpectationV1",
        "GoalResultRowV1",
        "GoalResultV1",
        "GoalTechnicalAssessmentV1",
        "EvidenceScopeV1",
        "ExactLocalClosureTargetV1",
        "ScenarioSpecV1",
        "ScenarioValueV1",
        "ScenarioSetEffectiveValueV1",
        "ScenarioEnsureMemberV1",
        "ScenarioSetExactMembersV1",
        "ScenarioWithoutFieldV1",
        "ScenarioWithoutValueV1",
        "ScenarioCreateEphemeralEntityV1",
        "ScenarioEnsureRelationV1",
        "ScenarioWithoutRelationV1",
        "ScenarioWithoutEntityV1",
        "ScenarioWithoutAssertionV1",
        "RelationProviderV1",
        "ProviderRequestV1",
        "ProviderRelationRowV1",
        "ProviderMaterializationV1",
        "provider_binding_slot_v1",
        "EvaluationEnginePinV1",
        "EvaluationExecutionProfileV1",
        "native_deterministic_profile_v1",
        "portable_deterministic_profile_v1",
        "EvaluationRunV1",
        "ExplainTargetV1",
        "EvaluationRunExplanationV1",
        "EvaluationRunReplayV1",
        "PolicyVariantComparisonV1",
        "ScenarioDiffV1",
    }
)


def test_v1_protocol_reexports_are_identity_preserving() -> None:
    assert protocol.GoalPlanV1 is GoalPlanV1
    assert protocol.ScenarioSpecV1 is ScenarioSpecV1
    assert protocol.RelationProviderV1 is RelationProviderV1
    assert protocol.EvaluationRunV1 is EvaluationRunV1
    assert protocol.ExplainTargetV1 is ExplainTargetV1
    assert V1_SDK_EXPORTS <= set(sdk.__all__)
    assert len(sdk.__all__) == len(set(sdk.__all__))


def test_application_exports_v1_runtime_without_replacing_v0_protocols() -> None:
    assert application.GoalPlanInvocationV1 is GoalPlanInvocationV1
    assert application.GoalPlanRunV1 is GoalPlanRunV1
    assert application.GoalPlanFailureV1 is GoalPlanFailureV1
    assert application.native_deterministic_profile_v1 is native_deterministic_profile_v1
    assert application.portable_deterministic_profile_v1 is portable_deterministic_profile_v1
    assert application.provider_binding_slot_v1 is provider_binding_slot_v1
    assert application.EvaluationRunExplanationV1 is EvaluationRunExplanationV1
    assert application.EvaluationRunReplayV1 is EvaluationRunReplayV1
    assert application.PolicyVariantComparisonV1 is PolicyVariantComparisonV1
    assert application.ScenarioDiffV1 is ScenarioDiffV1
    assert "ScenarioFieldSubstitutionV0" in protocol.__all__
    assert "EvaluationRunBundleV0" in protocol.__all__


def test_sdk_reexports_all_user_constructible_v1_intent_and_result_types() -> None:
    expected = {
        "EvaluationQueryBuilderV1": EvaluationQueryBuilderV1,
        "ProviderQueryTargetV1": ProviderQueryTargetV1,
        "ScenarioGoalPlanBuilderV1": ScenarioGoalPlanBuilderV1,
        "GoalPlanInvocationV1": GoalPlanInvocationV1,
        "GoalPlanRunV1": GoalPlanRunV1,
        "GoalPlanFailureV1": GoalPlanFailureV1,
        "GoalPlanV1": GoalPlanV1,
        "GoalValueV1": GoalValueV1,
        "GoalRowExpectationV1": GoalRowExpectationV1,
        "ContainsRowExpectationV1": ContainsRowExpectationV1,
        "ExactLocalAbsenceExpectationV1": ExactLocalAbsenceExpectationV1,
        "ExistsExpectationV1": ExistsExpectationV1,
        "CountEqExpectationV1": CountEqExpectationV1,
        "SetEqualsExpectationV1": SetEqualsExpectationV1,
        "GoalResultRowV1": GoalResultRowV1,
        "GoalResultV1": GoalResultV1,
        "GoalTechnicalAssessmentV1": GoalTechnicalAssessmentV1,
        "EvidenceScopeV1": EvidenceScopeV1,
        "ExactLocalClosureTargetV1": ExactLocalClosureTargetV1,
        "ScenarioSpecV1": ScenarioSpecV1,
        "ScenarioValueV1": ScenarioValueV1,
        "ScenarioSetEffectiveValueV1": ScenarioSetEffectiveValueV1,
        "ScenarioEnsureMemberV1": ScenarioEnsureMemberV1,
        "ScenarioSetExactMembersV1": ScenarioSetExactMembersV1,
        "ScenarioWithoutFieldV1": ScenarioWithoutFieldV1,
        "ScenarioWithoutValueV1": ScenarioWithoutValueV1,
        "ScenarioCreateEphemeralEntityV1": ScenarioCreateEphemeralEntityV1,
        "ScenarioEnsureRelationV1": ScenarioEnsureRelationV1,
        "ScenarioWithoutRelationV1": ScenarioWithoutRelationV1,
        "ScenarioWithoutEntityV1": ScenarioWithoutEntityV1,
        "ScenarioWithoutAssertionV1": ScenarioWithoutAssertionV1,
        "RelationProviderV1": RelationProviderV1,
        "ProviderRequestV1": ProviderRequestV1,
        "ProviderRelationRowV1": ProviderRelationRowV1,
        "ProviderMaterializationV1": ProviderMaterializationV1,
        "provider_binding_slot_v1": provider_binding_slot_v1,
        "EvaluationEnginePinV1": EvaluationEnginePinV1,
        "EvaluationExecutionProfileV1": EvaluationExecutionProfileV1,
        "native_deterministic_profile_v1": native_deterministic_profile_v1,
        "portable_deterministic_profile_v1": portable_deterministic_profile_v1,
        "EvaluationRunV1": EvaluationRunV1,
        "ExplainTargetV1": ExplainTargetV1,
        "EvaluationRunExplanationV1": EvaluationRunExplanationV1,
        "EvaluationRunReplayV1": EvaluationRunReplayV1,
        "PolicyVariantComparisonV1": PolicyVariantComparisonV1,
        "ScenarioDiffV1": ScenarioDiffV1,
    }
    assert set(expected) == set(V1_SDK_EXPORTS)
    for name, value in expected.items():
        assert getattr(sdk, name) is value

    # The V1 exports are additive.  Established V0 names retain their identity
    # instead of becoming aliases to the new generic Scenario/Run contract.
    assert sdk.ScenarioFieldSubstitutionV0 is protocol.ScenarioFieldSubstitutionV0
    assert sdk.ScenarioRunV0 is protocol.ScenarioRunV0
    assert sdk.EvaluateResult is protocol.EvaluateResult
