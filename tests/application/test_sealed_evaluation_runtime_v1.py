from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import replace

import pytest

from factgraph.application import build_schema_index, encode_entity_ref
from factgraph.application.evaluation_run_v1_runtime import (
    EvaluationRunRuntimeErrorV1,
    build_evaluation_replay_program_envelope_v1,
    capture_evaluation_replay_world_v1,
    compare_policy_variants_v1,
    evaluate_captured_goal_v1,
    evaluate_sealed_evaluation_request_v1,
    replay_evaluation_run_v1,
)
from factgraph.application.protocol import CompiledDerivationPlan, CompiledHeadCall, EntityRef
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_v1 import (
    EvaluationEnginePinV1,
    EvaluationExecutionProfileV1,
    EvaluationReplayProgramEnvelopeV1,
    EvaluationReplayWorldV1,
)
from factgraph.application.protocol.goal_plan_v1 import (
    ExactLocalAbsenceExpectationV1,
    GoalPlanV1,
    GoalSelectionV1,
    GoalTargetRefV1,
    GoalValueV1,
)
from factgraph.application.protocol.relation_provider_v1 import (
    ProviderMaterializationV1,
    ProviderRelationRowV1,
    ProviderRequestV1,
)
from factgraph.application.protocol.scenario_v1 import (
    ExactLocalClosureTargetV1,
    ScenarioSpecV1,
    ScenarioWithoutFieldV1,
)
from factgraph.application.protocol.schema_runtime import FieldPath
from factgraph.application.protocol.sealed_evaluation_result_v1 import (
    SealedEvaluationResultV1,
    sealed_evaluation_result_v1_bytes,
    sealed_evaluation_result_v1_from_bytes,
)
from factgraph.application.protocol.sealed_evaluation_v1 import (
    SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    DecodedSealedEvaluationRequestV1,
    EvaluationAssetBundleV1,
    EvaluationAssetPinV1,
    EvaluationCaptureProfileV1,
    EvaluationProviderCaptureV1,
    EvaluationSchemaCaptureV1,
    EvaluationWorldInputPinsV1,
    SealedEvaluationRequestV1,
    decode_sealed_evaluation_request_v1,
    evaluation_execution_profile_v1_bytes,
    evaluation_provider_capture_v1_bytes,
    evaluation_replay_world_v1_bytes,
    evaluation_schema_capture_v1_bytes,
    goal_plan_v1_bytes,
    scenario_spec_v1_bytes,
)
from factgraph.application.scenario_v1_runtime import (
    effective_world_to_relation_v1,
    resolve_scenario_v1,
)
from factgraph.core.schema.schema_ir import canonicalize_schema_ir_jcs
from factgraph.core.store._support import ProjectedFact
from factgraph.sdk import Entity, Field, Identity, SDKStore


def _token(character: str) -> str:
    return f"sha256:{character * 64}"


def _derived_token(label: str, payload: object) -> str:
    raw = json.dumps(
        {"format": label, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()


def _program_envelope(
    source: EvaluationReplayProgramEnvelopeV1,
    compiled_program: dict[str, object],
) -> EvaluationReplayProgramEnvelopeV1:
    return EvaluationReplayProgramEnvelopeV1(
        schema_digest=source.schema_digest,
        address_space_digest=source.address_space_digest,
        plan_digest=source.plan_digest,
        query_digest=source.query_digest,
        target_digest=source.target_digest,
        execution_profile_digest=source.execution_profile_digest,
        compiler_digest=source.compiler_digest,
        compiled_program=compiled_program,
        candidate_plan_digest=source.candidate_plan_digest,
        candidate_query_digest=source.candidate_query_digest,
        candidate_target_digest=source.candidate_target_digest,
    )


def _components(
    *,
    result_mode: str = "rows",
    row_limit: int = 4096,
    two_people: bool = False,
    age_only_program: bool = False,
    scenario: ScenarioSpecV1 | None = None,
    exact_absence: bool = False,
    candidate: bool = False,
    provider: bool = False,
    portable: bool = False,
    comparison: str = "not_requested",
) -> DecodedSealedEvaluationRequestV1:
    graph = SDKStore([Person])
    schema_ir = graph.schema_ir
    schema_index = build_schema_index(schema_ir)
    alice = encode_entity_ref(EntityRef("Person", {"employee_id": "alice"}), index=schema_index)
    exists_rows = [ProjectedFact("base:exists:alice", (alice,))]
    identity_rows = [ProjectedFact("base:employee_id:alice", (alice, "alice"))]
    age_rows = [ProjectedFact("base:age:alice", (alice, 35))]
    if two_people:
        bob = encode_entity_ref(EntityRef("Person", {"employee_id": "bob"}), index=schema_index)
        exists_rows.append(ProjectedFact("base:exists:bob", (bob,)))
        identity_rows.append(ProjectedFact("base:employee_id:bob", (bob, "bob")))
        age_rows.append(ProjectedFact("base:age:bob", (bob, 41)))
    relation = {
        "Person:exists": tuple(exists_rows),
        "person:employee_id": tuple(identity_rows),
        "person:age": tuple(age_rows),
    }
    pins = EvaluationWorldInputPinsV1(_token("4"), _token("5"))
    resolved = resolve_scenario_v1(
        ScenarioSpecV1(()),
        schema_index=schema_index,
        baseline_relation=relation,
        base_view_digest=pins.base_view_digest,
        admissibility_digest=pins.admissibility_digest,
    )
    baseline_world = capture_evaluation_replay_world_v1(
        side="baseline",
        schema_ir=schema_ir,
        semantic_world_digest=resolved.baseline_world.world_digest,
        resolution_evidence_digest=resolved.resolution_evidence_digest,
        closure_target_digests=(),
        relations=effective_world_to_relation_v1(resolved.baseline_world),
    )
    compiled = CompiledDerivationPlan(
        derivation_id="v1-age-query",
        version="1",
        body_ir=(
            [("pred", "person:age", ["$person", "$age"])]
            if age_only_program
            else [
                ("pred", "Person:exists", ["$person"]),
                ("pred", "person:age", ["$person", "$age"]),
            ]
        ),
        heads=(CompiledHeadCall("__factgraph_projection__v1_age", ("$age",)),),
    )
    engines = (
        EvaluationEnginePinV1("native", "test-native", "test-adapter"),
        EvaluationEnginePinV1("souffle", "test-souffle", "test-adapter"),
        EvaluationEnginePinV1("problog", "test-problog", "test-adapter"),
    )
    profile = EvaluationExecutionProfileV1(
        "portable_deterministic_v1" if portable else "native_deterministic_v1",
        _token("c"),
        None,
        engines if portable else engines[:1],
    )
    expectations = (
        (
            ExactLocalAbsenceExpectationV1(
                "age-absent",
                ExactLocalClosureTargetV1("field", alice, "person:age"),
            ),
        )
        if exact_absence
        else ()
    )
    candidate_target = (
        GoalTargetRefV1("policy", "person.age.candidate", "1", _token("d")) if candidate else None
    )
    candidate_query_digest = _token("e") if candidate else None
    target_kind = "relation_provider" if provider else "policy"
    plan = GoalPlanV1(
        target=GoalTargetRefV1(target_kind, "person.age", "1", _token("a")),
        query_digest=_token("b"),
        result_mode=result_mode,  # type: ignore[arg-type]
        selections=(GoalSelectionV1("age", "int"),),
        candidate_target=candidate_target,
        candidate_query_digest=candidate_query_digest,
        scenario_request_digest=None if scenario is None else scenario.spec_digest,
        evidence_scope_digest=_token("f"),
        execution_profile_digest=profile.profile_digest,
        expectations=expectations,
    )
    candidate_plan = (
        None
        if candidate_target is None
        else GoalPlanV1(
            target=candidate_target,
            query_digest=candidate_query_digest or "",
            result_mode=result_mode,  # type: ignore[arg-type]
            selections=plan.selections,
            scenario_request_digest=plan.scenario_request_digest,
            evidence_scope_digest=plan.evidence_scope_digest,
            execution_profile_digest=plan.execution_profile_digest,
        )
    )
    schema = EvaluationSchemaCaptureV1(canonicalize_schema_ir_jcs(schema_ir))
    address_space_digest = _token("3")
    program = build_evaluation_replay_program_envelope_v1(
        schema_ir=schema_ir,
        address_space_digest=address_space_digest,
        plan=plan,
        execution_profile=profile,
        primary_compiled_plan=compiled,
        candidate_plan=candidate_plan,
        candidate_compiled_plan=None if candidate_plan is None else compiled,
    )
    provider_capture = None
    dependencies: tuple[EvaluationAssetPinV1, ...] = ()
    if provider:
        provider_request = ProviderRequestV1(
            provider_digest=_token("7"),
            query_digest=plan.query_digest,
            schema_digest=schema.schema_digest,
            dependency_predicate_ids=("Person:exists", "person:age", "person:employee_id"),
            supplied_predicate_ids=("person:age",),
            bindings=(),
        )
        materialization = ProviderMaterializationV1(
            provider_digest=provider_request.provider_digest,
            request_digest=provider_request.request_digest,
            receipt_ref="receipt:provider:1",
            receipt_digest=_token("8"),
            predicate_ids=provider_request.supplied_predicate_ids,
            rows=(
                ProviderRelationRowV1(
                    "person:age",
                    (
                        # Provider values are typed and already captured; no
                        # provider callable enters the runtime owner.
                        GoalValueV1("entity_ref", alice),
                        GoalValueV1("int", 37),
                    ),
                    "origin:provider:1",
                ),
            ),
        )
        provider_capture = EvaluationProviderCaptureV1(provider_request, materialization)
        dependencies = (
            EvaluationAssetPinV1(
                "provider",
                "provider.main",
                "1",
                provider_request.provider_digest,
            ),
        )
    bundle = EvaluationAssetBundleV1(
        primary_target=EvaluationAssetPinV1(
            plan.target.kind,
            plan.target.target_id,
            plan.target.target_version or "",
            plan.target.target_digest,
        ),
        candidate_target=(
            None
            if candidate_target is None
            else EvaluationAssetPinV1(
                candidate_target.kind,
                candidate_target.target_id,
                candidate_target.target_version or "",
                candidate_target.target_digest,
            )
        ),
        dependencies=dependencies,
        query_digest=plan.query_digest,
        schema_digest=schema.schema_digest,
        address_space_digest=address_space_digest,
        compiler_digest=profile.compiler_digest,
        execution_profile_digest=profile.profile_digest,
        runtime_digest=SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    )
    request = SealedEvaluationRequestV1(
        asset_bundle=bundle,
        goal_plan_bytes=goal_plan_v1_bytes(plan),
        execution_profile_bytes=evaluation_execution_profile_v1_bytes(profile),
        schema_bytes=evaluation_schema_capture_v1_bytes(schema),
        program_envelope_bytes=program.to_bytes(),
        baseline_world_bytes=evaluation_replay_world_v1_bytes(baseline_world),
        world_input_pins=pins,
        scenario_bytes=None if scenario is None else scenario_spec_v1_bytes(scenario),
        provider_capture_bytes=(
            None
            if provider_capture is None
            else evaluation_provider_capture_v1_bytes(provider_capture)
        ),
        capture=EvaluationCaptureProfileV1(row_limit, "not_captured", comparison),
    )
    return decode_sealed_evaluation_request_v1(request)


def _request_from_components(
    components: DecodedSealedEvaluationRequestV1,
) -> SealedEvaluationRequestV1:
    return SealedEvaluationRequestV1(
        asset_bundle=components.asset_bundle,
        goal_plan_bytes=goal_plan_v1_bytes(components.goal_plan),
        execution_profile_bytes=evaluation_execution_profile_v1_bytes(components.execution_profile),
        schema_bytes=evaluation_schema_capture_v1_bytes(components.schema),
        program_envelope_bytes=components.program_envelope.to_bytes(),
        baseline_world_bytes=evaluation_replay_world_v1_bytes(components.baseline_world),
        world_input_pins=components.world_input_pins,
        scenario_bytes=(
            None if components.scenario is None else scenario_spec_v1_bytes(components.scenario)
        ),
        provider_capture_bytes=(
            None
            if components.provider_capture is None
            else evaluation_provider_capture_v1_bytes(components.provider_capture)
        ),
        capture=components.capture,
    )


def test_minimal_captured_runtime_evaluates_and_replays_without_live_state() -> None:
    components = _components()
    run = evaluate_captured_goal_v1(components)

    assert [dict(row.values)["age"].value for row in run.baseline.canonical_result.rows] == [35]
    assert run.baseline.canonical_result == run.effective.canonical_result
    assert run.replay_payload.world("baseline") == components.baseline_world
    assert run.replay_payload.compiled_program_bytes == components.program_envelope.to_bytes()
    replay = replay_evaluation_run_v1(run)
    assert replay.status == "matched"
    assert replay.baseline.result_match and replay.effective.result_match
    assert run.baseline.assessment.replay == "available"
    assert tuple(inspect.signature(evaluate_captured_goal_v1).parameters) == ("components",)
    source = inspect.getsource(evaluate_captured_goal_v1)
    assert "Store" not in source and "callback" not in source


@pytest.mark.parametrize("mode", ["rows", "exists", "count", "set"])
def test_captured_runtime_preserves_all_four_result_modes(mode: str) -> None:
    run = evaluate_captured_goal_v1(_components(result_mode=mode))
    result = run.effective.canonical_result

    assert result.result_mode == mode
    if mode == "exists":
        assert result.exists_value == "true" and len(result.rows) == 1
    elif mode == "count":
        assert result.count_value == 1 and len(result.rows) == 1
    else:
        assert result.exists_value is None and result.count_value is None
        assert len(result.rows) == 1


def test_scenario_is_resolved_after_program_decode_and_retained_in_run() -> None:
    scenario = ScenarioSpecV1(
        (
            ScenarioWithoutFieldV1(
                "premise",
                EntityRef("Person", {"employee_id": "alice"}),
                FieldPath("Person", "age"),
            ),
        )
    )
    components = _components(scenario=scenario, exact_absence=True)
    run = evaluate_captured_goal_v1(components)

    assert len(run.baseline.canonical_result.rows) == 1
    assert run.effective.canonical_result.rows == ()
    assert run.effective.canonical_result.expectation_outcomes[0].status == "satisfied"
    assert run.baseline.canonical_result.expectation_outcomes[0].status == "underdetermined"
    assert run.effective.assessment.scenario_resolution == "resolved"
    assert run.effective.assessment.exact_local_closure == "resolved"
    assert run.baseline.assessment.exact_local_closure == "required"
    output_program = json.loads(run.replay_payload.compiled_program_bytes)["compiled_program"]
    assert output_program["scenario_patch"] is not None
    assert run.replay_payload.compiled_program_bytes != components.program_envelope.to_bytes()
    replay = replay_evaluation_run_v1(run)
    assert replay.status == "matched"


def test_candidate_executes_on_shared_effective_world_and_compares_by_identity() -> None:
    components = _components(candidate=True)
    run = evaluate_captured_goal_v1(components)

    assert run.candidate_plan == components.candidate_plan
    assert run.candidate_effective is not None
    assert run.candidate_effective.world_capture_digest == run.effective.world_capture_digest
    comparison = compare_policy_variants_v1(run)
    assert comparison.result_relation == "equivalent"
    assert comparison.compiled_body_equal and comparison.compiled_head_equal
    assert comparison.primary_target_digest != comparison.candidate_target_digest
    assert replay_evaluation_run_v1(run).status == "matched"


def test_provider_uses_only_captured_materialization_and_seals_receipt() -> None:
    components = _components(provider=True)
    run = evaluate_captured_goal_v1(components)

    assert components.provider_capture is not None
    assert [dict(row.values)["age"].value for row in run.baseline.canonical_result.rows] == [37]
    assert [dict(row.values)["age"].value for row in run.effective.canonical_result.rows] == [37]
    assert run.replay_payload.world("baseline") != components.baseline_world
    assert run.replay_payload.provider_receipts == (
        components.provider_capture.materialization.to_receipt_ref_v1(),
    )
    assert replay_evaluation_run_v1(run).status == "matched"


def test_portable_profile_preserves_complete_engine_inventory_truthfully() -> None:
    run = evaluate_captured_goal_v1(_components(portable=True))

    frames = run.effective.engine_results
    assert tuple(frame.engine for frame in frames) == ("native", "souffle", "problog")
    assert frames[0].status == "succeeded"
    assert run.effective.assessment.parity in {"equivalent", "different", "unsupported"}
    assert run.effective.assessment.capability in {"supported", "unresolved"}
    assert replay_evaluation_run_v1(run).status == "matched"


def test_thin_sealed_runtime_emits_exact_terminal_result_without_unrequested_views() -> None:
    request = _request_from_components(_components())
    result = evaluate_sealed_evaluation_request_v1(request)

    assert result.request_digest == request.request_digest
    assert result.asset_bundle_digest == request.asset_bundle.bundle_digest
    assert result.comparison is None and result.scenario_diff is None
    raw = sealed_evaluation_result_v1_bytes(result)
    assert sealed_evaluation_result_v1_from_bytes(raw) == result
    assert replay_evaluation_run_v1(result.run).status == "matched"


def test_thin_sealed_runtime_derives_only_requested_candidate_comparison() -> None:
    components = _components(candidate=True, comparison="published_candidate")
    request = _request_from_components(components)
    result = evaluate_sealed_evaluation_request_v1(request)

    assert result.comparison is not None and result.scenario_diff is None
    runtime = compare_policy_variants_v1(result.run)
    assert result.comparison.comparison_digest == runtime.comparison_digest
    assert (
        sealed_evaluation_result_v1_from_bytes(sealed_evaluation_result_v1_bytes(result)) == result
    )

    forged = replace(
        result.comparison,
        compiled_body_equal=not result.comparison.compiled_body_equal,
    )
    with pytest.raises(ProtocolShapeError, match="sealed program observations"):
        SealedEvaluationResultV1(
            result.request_digest,
            result.asset_bundle_digest,
            result.run,
            comparison=forged,
        )


def test_thin_sealed_runtime_binds_requested_scenario_patch() -> None:
    scenario = ScenarioSpecV1(
        (
            ScenarioWithoutFieldV1(
                "premise",
                EntityRef("Person", {"employee_id": "alice"}),
                FieldPath("Person", "age"),
            ),
        )
    )
    components = _components(
        scenario=scenario,
        exact_absence=True,
        comparison="baseline_vs_effective",
    )
    request = _request_from_components(components)
    result = evaluate_sealed_evaluation_request_v1(request)

    assert result.comparison is None and result.scenario_diff is not None
    assert result.scenario_diff.scenario_patch_capture == "captured"
    assert (
        sealed_evaluation_result_v1_from_bytes(sealed_evaluation_result_v1_bytes(result)) == result
    )

    operation = result.scenario_diff.scenario_operations[0]
    forged_operation = replace(
        operation,
        origin_refs=tuple(sorted((*operation.origin_refs, "origin:forged"))),
    )
    forged_diff = replace(
        result.scenario_diff,
        scenario_operations=(forged_operation,),
        scenario_patch_digest=_derived_token(
            "evaluation_run_v1_scenario_patch",
            (forged_operation.operation_digest,),
        ),
        scenario_operation_digests=(forged_operation.operation_digest,),
    )
    with pytest.raises(ProtocolShapeError, match="sealed Scenario patch"):
        SealedEvaluationResultV1(
            result.request_digest,
            result.asset_bundle_digest,
            result.run,
            scenario_diff=forged_diff,
        )


def test_baseline_pins_fail_before_hostile_program_semantic_decode() -> None:
    components = _components()
    hostile = _program_envelope(
        components.program_envelope,
        {"$type": "HostileProgram", "payload": {"unsupported": True}},
    )
    stale_world = EvaluationReplayWorldV1(
        "baseline",
        _token("9"),
        components.baseline_world.resolution_evidence_digest,
        (),
        components.baseline_world.relations,
    )
    stale = replace(components, baseline_world=stale_world, program_envelope=hostile)
    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_captured_goal_v1(stale)
    assert caught.value.code == "EVALUATION_RUN_V1_PIN_INVALID"

    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_captured_goal_v1(replace(components, program_envelope=hostile))
    assert caught.value.code == "EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"


def test_request_program_rejects_pre_resolved_patch_and_capture_widening() -> None:
    components = _components()
    program = json.loads(components.program_envelope.to_bytes())["compiled_program"]
    program["scenario_patch"] = {"$type": "FactGraphScenarioPatchV1"}
    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_captured_goal_v1(
            replace(
                components,
                program_envelope=_program_envelope(components.program_envelope, program),
            )
        )
    assert caught.value.code == "EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH"

    widened = replace(
        components,
        capture=EvaluationCaptureProfileV1(4096, "structured_display", "not_requested"),
    )
    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_captured_goal_v1(widened)
    assert caught.value.code == "EVALUATION_RUN_V1_PROGRAM_CAPABILITY_REJECTED"


def test_dependency_inventory_and_row_limit_fail_closed() -> None:
    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_captured_goal_v1(_components(age_only_program=True))
    assert caught.value.code == "EVALUATION_RUN_V1_REPLAY_RELATION_INCOMPLETE"

    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_captured_goal_v1(_components(row_limit=1, two_people=True))
    assert caught.value.code == "EVALUATION_RUN_V1_PROGRAM_LIMIT_EXCEEDED"


def test_runtime_owner_rejects_wrong_concrete_input() -> None:
    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_captured_goal_v1({})  # type: ignore[arg-type]
    assert caught.value.code == "EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID"

    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_sealed_evaluation_request_v1({})  # type: ignore[arg-type]
    assert caught.value.code == "EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID"
