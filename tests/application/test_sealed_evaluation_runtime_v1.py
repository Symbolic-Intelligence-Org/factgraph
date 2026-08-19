from __future__ import annotations

import inspect
import json
from dataclasses import replace

import pytest

from factgraph.application import build_schema_index, encode_entity_ref
from factgraph.application.evaluation_run_v1_runtime import (
    EvaluationRunRuntimeErrorV1,
    build_evaluation_replay_program_envelope_v1,
    capture_evaluation_replay_world_v1,
    evaluate_captured_goal_v1,
    replay_evaluation_run_v1,
)
from factgraph.application.protocol import CompiledDerivationPlan, CompiledHeadCall, EntityRef
from factgraph.application.protocol.evaluation_run_v1 import (
    EvaluationEnginePinV1,
    EvaluationExecutionProfileV1,
    EvaluationReplayProgramEnvelopeV1,
    EvaluationReplayWorldV1,
)
from factgraph.application.protocol.goal_plan_v1 import (
    GoalPlanV1,
    GoalSelectionV1,
    GoalTargetRefV1,
)
from factgraph.application.protocol.scenario_v1 import ScenarioSpecV1
from factgraph.application.protocol.sealed_evaluation_v1 import (
    SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    DecodedSealedEvaluationRequestV1,
    EvaluationAssetBundleV1,
    EvaluationAssetPinV1,
    EvaluationCaptureProfileV1,
    EvaluationSchemaCaptureV1,
    EvaluationWorldInputPinsV1,
    SealedEvaluationRequestV1,
    decode_sealed_evaluation_request_v1,
    evaluation_execution_profile_v1_bytes,
    evaluation_replay_world_v1_bytes,
    evaluation_schema_capture_v1_bytes,
    goal_plan_v1_bytes,
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
    row_limit: int = 4096,
    two_people: bool = False,
    age_only_program: bool = False,
) -> DecodedSealedEvaluationRequestV1:
    graph = SDKStore([Person])
    schema_ir = graph.schema_ir
    schema_index = build_schema_index(schema_ir)
    alice = encode_entity_ref(EntityRef("Person", {"employee_id": "alice"}), index=schema_index)
    exists_rows = [ProjectedFact("base:exists:alice", (alice,))]
    age_rows = [ProjectedFact("base:age:alice", (alice, 35))]
    if two_people:
        bob = encode_entity_ref(EntityRef("Person", {"employee_id": "bob"}), index=schema_index)
        exists_rows.append(ProjectedFact("base:exists:bob", (bob,)))
        age_rows.append(ProjectedFact("base:age:bob", (bob, 41)))
    relation = {
        "Person:exists": tuple(exists_rows),
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
    profile = EvaluationExecutionProfileV1(
        "native_deterministic_v1",
        _token("c"),
        None,
        (EvaluationEnginePinV1("native", "test-native", "test-adapter"),),
    )
    plan = GoalPlanV1(
        target=GoalTargetRefV1("policy", "person.age", "1", _token("a")),
        query_digest=_token("b"),
        result_mode="rows",
        selections=(GoalSelectionV1("age", "int"),),
        evidence_scope_digest=_token("f"),
        execution_profile_digest=profile.profile_digest,
    )
    schema = EvaluationSchemaCaptureV1(canonicalize_schema_ir_jcs(schema_ir))
    address_space_digest = _token("3")
    program = build_evaluation_replay_program_envelope_v1(
        schema_ir=schema_ir,
        address_space_digest=address_space_digest,
        plan=plan,
        execution_profile=profile,
        primary_compiled_plan=compiled,
    )
    bundle = EvaluationAssetBundleV1(
        primary_target=EvaluationAssetPinV1(
            plan.target.kind,
            plan.target.target_id,
            plan.target.target_version or "",
            plan.target.target_digest,
        ),
        candidate_target=None,
        dependencies=(),
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
        scenario_bytes=None,
        provider_capture_bytes=None,
        capture=EvaluationCaptureProfileV1(row_limit, "not_captured", "not_requested"),
    )
    return decode_sealed_evaluation_request_v1(request)


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
