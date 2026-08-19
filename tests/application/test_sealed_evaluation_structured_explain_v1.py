from __future__ import annotations

import inspect
import json
from dataclasses import replace

import pytest

from factgraph.application import (
    build_resolved_rule,
    build_schema_index,
    compile_targeted_evaluation_query,
    encode_entity_ref,
    resolve_evaluation_query_target,
)
from factgraph.application.evaluation_run_v1_runtime import (
    EvaluationRunRuntimeErrorV1,
    _materialize_native_derivation_plan,
    build_evaluation_replay_program_envelope_v1,
    capture_evaluation_replay_world_v1,
    evaluate_sealed_evaluation_request_v1,
    explain_evaluation_run_v1,
)
from factgraph.application.protocol import (
    EntityRef,
    EvaluationQuerySelection,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_v1 import (
    EvaluationEnginePinV1,
    EvaluationExecutionProfileV1,
    ExplainTargetV1,
)
from factgraph.application.protocol.goal_plan_v1 import (
    GoalPlanV1,
    GoalSelectionV1,
    GoalTargetRefV1,
)
from factgraph.application.protocol.scenario_v1 import ScenarioSpecV1
from factgraph.application.protocol.sealed_evaluation_result_v1 import (
    SealedEvaluationResultV1,
    assert_sealed_evaluation_result_matches_request_v1,
    sealed_evaluation_result_v1_bytes,
    sealed_evaluation_result_v1_from_bytes,
)
from factgraph.application.protocol.sealed_evaluation_v1 import (
    SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    EvaluationAssetBundleV1,
    EvaluationAssetPinV1,
    EvaluationCaptureProfileV1,
    EvaluationSchemaCaptureV1,
    EvaluationWorldInputPinsV1,
    SealedEvaluationRequestV1,
    evaluation_execution_profile_v1_bytes,
    evaluation_replay_world_v1_bytes,
    evaluation_schema_capture_v1_bytes,
    goal_plan_v1_bytes,
)
from factgraph.application.scenario_v1_runtime import (
    effective_world_to_relation_v1,
    resolve_scenario_v1,
)
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.schema.schema_ir import canonicalize_schema_ir_jcs
from factgraph.core.store._support import ProjectedFact
from factgraph.sdk import Entity, Field, Identity, SDKStore


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()


def _token(char: str) -> str:
    return f"sha256:{char * 64}"


def _request(*, with_context: bool = True) -> SealedEvaluationRequestV1:
    graph = SDKStore([Person])
    schema_ir = graph.schema_ir
    schema_index = build_schema_index(schema_ir)
    person, age = Var("$person"), Var("$age")
    rule = build_resolved_rule(
        id="person_age",
        version="1",
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
        },
        schema_index=schema_index,
    )
    target = resolve_evaluation_query_target(rule, schema_index=schema_index)
    query = compile_targeted_evaluation_query(
        target,
        bindings=(),
        selections=(EvaluationQuerySelection("age", SemanticPortAddress("target", "age")),),
        schema_index=schema_index,
    )
    compiled, _traces = _materialize_native_derivation_plan(query.compiled_query._lowering_plan)
    profile = EvaluationExecutionProfileV1(
        "native_deterministic_v1",
        _token("c"),
        None,
        (EvaluationEnginePinV1("native", "test-native", "test-adapter"),),
    )
    plan = GoalPlanV1(
        GoalTargetRefV1("rule", "person_age", "1", target.run_target.target_digest),
        f"sha256:{query.compiled_query.query_digest}",
        "rows",
        (GoalSelectionV1("age", "int"),),
        evidence_scope_digest=_token("f"),
        execution_profile_digest=profile.profile_digest,
    )
    ref = encode_entity_ref(EntityRef("Person", {"employee_id": "alice"}), index=schema_index)
    relation = {
        "Person:exists": (ProjectedFact("base:exists:alice", (ref,)),),
        "person:age": (ProjectedFact("base:age:alice", (ref, 35)),),
    }
    world_pins = EvaluationWorldInputPinsV1(_token("4"), _token("5"))
    resolved = resolve_scenario_v1(
        ScenarioSpecV1(()),
        schema_index=schema_index,
        baseline_relation=relation,
        base_view_digest=world_pins.base_view_digest,
        admissibility_digest=world_pins.admissibility_digest,
    )
    world = capture_evaluation_replay_world_v1(
        side="baseline",
        schema_ir=schema_ir,
        semantic_world_digest=resolved.baseline_world.world_digest,
        resolution_evidence_digest=resolved.resolution_evidence_digest,
        closure_target_digests=(),
        relations=effective_world_to_relation_v1(resolved.baseline_world),
    )
    envelope = build_evaluation_replay_program_envelope_v1(
        schema_ir=schema_ir,
        address_space_digest=f"sha256:{target.run_target.address_space_digest}",
        plan=plan,
        execution_profile=profile,
        primary_compiled_plan=compiled,
        primary_policy_structure=target.run_target.policy_structure if with_context else None,
        primary_run_target=target.run_target if with_context else None,
        primary_lowering_plan=query.compiled_query._lowering_plan if with_context else None,
    )
    schema = EvaluationSchemaCaptureV1(canonicalize_schema_ir_jcs(schema_ir))
    bundle = EvaluationAssetBundleV1(
        primary_target=EvaluationAssetPinV1(
            "rule", "person_age", "1", target.run_target.target_digest
        ),
        candidate_target=None,
        dependencies=(),
        query_digest=plan.query_digest,
        schema_digest=schema.schema_digest,
        address_space_digest=envelope.address_space_digest,
        compiler_digest=profile.compiler_digest,
        execution_profile_digest=profile.profile_digest,
        runtime_digest=SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    )
    return SealedEvaluationRequestV1(
        asset_bundle=bundle,
        goal_plan_bytes=goal_plan_v1_bytes(plan),
        execution_profile_bytes=evaluation_execution_profile_v1_bytes(profile),
        schema_bytes=evaluation_schema_capture_v1_bytes(schema),
        program_envelope_bytes=envelope.to_bytes(),
        baseline_world_bytes=evaluation_replay_world_v1_bytes(world),
        world_input_pins=world_pins,
        scenario_bytes=None,
        provider_capture_bytes=None,
        capture=EvaluationCaptureProfileV1(4096, "structured_display", "not_requested"),
    )


def test_structured_display_binds_effective_summary_and_roundtrips() -> None:
    request = _request()
    result = evaluate_sealed_evaluation_request_v1(request)
    assert result.run.explain_target is not None
    assert result.run.explain_target.side == "effective"
    assert result.run.explain_target.kind == "summary"
    assert result.run.explain_target.anchor_digest == (
        result.run.effective.canonical_result.summary_anchor.summary_anchor_digest  # type: ignore[union-attr]
    )
    assert result.run.baseline.assessment.explain == "available"
    assert result.run.effective.assessment.explain == "available"
    encoded = sealed_evaluation_result_v1_bytes(result)
    assert sealed_evaluation_result_v1_from_bytes(encoded) == result


def test_structured_display_detached_explain_is_not_live_store_access() -> None:
    result = evaluate_sealed_evaluation_request_v1(_request())
    target = result.run.explain_target
    assert target is not None
    explanation = explain_evaluation_run_v1(result.run, target)
    assert explanation.observation == "result_summary_observed"
    assert explanation.logical_conclusion == "not_claimed"
    assert "Store" not in inspect.getsource(explain_evaluation_run_v1)
    assert "callback" not in inspect.getsource(explain_evaluation_run_v1)


def test_missing_native_context_fails_closed() -> None:
    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_sealed_evaluation_request_v1(_request(with_context=False))
    assert caught.value.code == "EVALUATION_RUN_V1_PROGRAM_CAPABILITY_REJECTED"


def test_tampered_native_context_fails_closed() -> None:
    request = _request()
    envelope = json.loads(request.program_envelope_bytes)
    context = envelope["compiled_program"]["primary_native_explain_context"]
    context["context_digest"] = _token("0")
    tampered_program = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    tampered = SealedEvaluationRequestV1(
        asset_bundle=request.asset_bundle,
        goal_plan_bytes=request.goal_plan_bytes,
        execution_profile_bytes=request.execution_profile_bytes,
        schema_bytes=request.schema_bytes,
        program_envelope_bytes=tampered_program,
        baseline_world_bytes=request.baseline_world_bytes,
        world_input_pins=request.world_input_pins,
        scenario_bytes=request.scenario_bytes,
        provider_capture_bytes=request.provider_capture_bytes,
        capture=request.capture,
    )
    with pytest.raises(EvaluationRunRuntimeErrorV1) as caught:
        evaluate_sealed_evaluation_request_v1(tampered)
    assert caught.value.code in {
        "EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH",
        "EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
    }


def test_structured_display_rejects_another_valid_side_summary_target() -> None:
    request = _request()
    result = evaluate_sealed_evaluation_request_v1(request)
    baseline_summary = result.run.baseline.canonical_result.summary_anchor
    forged_run = replace(
        result.run,
        explain_target=ExplainTargetV1(
            "baseline",
            "summary",
            baseline_summary.summary_anchor_digest,
        ),
    )
    forged = SealedEvaluationResultV1(
        result.request_digest,
        result.asset_bundle_digest,
        forged_run,
    )
    with pytest.raises(ProtocolShapeError, match="primary effective summary"):
        assert_sealed_evaluation_result_matches_request_v1(forged, request)
