"""Emit the deterministic C2 sealed-evaluation golden from an installed wheel.

Run this file with ``python -I`` outside the source tree.  It deliberately uses
only published FactGraph surfaces and a fixed schema snapshot timestamp so two
supported Python runtimes receive byte-identical input.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import factgraph
from factgraph.application import (
    build_evaluation_replay_program_envelope_v1,
    build_schema_index,
    encode_entity_ref,
    evaluate_sealed_evaluation_request_v1,
    replay_evaluation_run_v1,
)
from factgraph.application.protocol import (
    SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    CompiledDerivationPlan,
    CompiledHeadCall,
    EffectiveWorldFactV1,
    EffectiveWorldV1,
    EntityRef,
    EvaluationAssetBundleV1,
    EvaluationAssetPinV1,
    EvaluationCaptureProfileV1,
    EvaluationEnginePinV1,
    EvaluationExecutionProfileV1,
    EvaluationReplayFactV1,
    EvaluationReplayRelationV1,
    EvaluationReplayWorldV1,
    EvaluationSchemaCaptureV1,
    EvaluationWorldInputPinsV1,
    GoalPlanV1,
    GoalSelectionV1,
    GoalTargetRefV1,
    GoalValueV1,
    ResolvedScenarioV1,
    ScenarioSpecV1,
    ScenarioValueV1,
    SealedEvaluationRequestV1,
    evaluation_execution_profile_v1_bytes,
    evaluation_replay_world_v1_bytes,
    evaluation_schema_capture_v1_bytes,
    goal_plan_v1_bytes,
    sealed_evaluation_request_v1_bytes,
    sealed_evaluation_request_v1_from_bytes,
    sealed_evaluation_result_v1_bytes,
    sealed_evaluation_result_v1_from_bytes,
)
from factgraph.core.schema.schema_ir import canonicalize_schema_ir_jcs
from factgraph.sdk import Entity, Field, Identity, SDKStore


def _token(character: str) -> str:
    return f"sha256:{character * 64}"


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()


graph = SDKStore([Person])
schema_ir = {**graph.schema_ir, "generated_at": "2026-08-19T00:00:00Z"}
schema_index = build_schema_index(schema_ir)
schema = EvaluationSchemaCaptureV1(canonicalize_schema_ir_jcs(schema_ir))
alice = encode_entity_ref(EntityRef("Person", {"employee_id": "alice"}), index=schema_index)
world_pins = EvaluationWorldInputPinsV1(_token("4"), _token("5"))
empty_scenario = ScenarioSpecV1(())
# Current capture closure includes the selected entity's Identity relation;
# replay must contain that same dependency even though the query selects age.
effective_world = EffectiveWorldV1(
    schema_digest=schema.schema_digest,
    base_view_digest=world_pins.base_view_digest,
    admissibility_digest=world_pins.admissibility_digest,
    dependency_predicate_ids=("Person:exists", "person:age", "person:employee_id"),
    facts=(
        EffectiveWorldFactV1(
            "Person:exists",
            "base:exists:alice",
            (ScenarioValueV1.from_raw("entity_ref", alice),),
            "baseline",
        ),
        EffectiveWorldFactV1(
            "person:age",
            "base:age:alice",
            (
                ScenarioValueV1.from_raw("entity_ref", alice),
                ScenarioValueV1.from_raw("int", 35),
            ),
            "baseline",
        ),
        EffectiveWorldFactV1(
            "person:employee_id",
            "base:identity:alice",
            (
                ScenarioValueV1.from_raw("entity_ref", alice),
                ScenarioValueV1.from_raw("string", "alice"),
            ),
            "baseline",
        ),
    ),
)
resolved_empty = ResolvedScenarioV1(empty_scenario, effective_world, effective_world)
baseline_world = EvaluationReplayWorldV1(
    side="baseline",
    semantic_world_digest=effective_world.world_digest,
    resolution_evidence_digest=resolved_empty.resolution_evidence_digest,
    closure_target_digests=(),
    relations=(
        EvaluationReplayRelationV1(
            "Person:exists",
            ("entity_ref",),
            (
                EvaluationReplayFactV1(
                    "base:exists:alice",
                    (GoalValueV1("entity_ref", alice),),
                ),
            ),
        ),
        EvaluationReplayRelationV1(
            "person:age",
            ("entity_ref", "int"),
            (
                EvaluationReplayFactV1(
                    "base:age:alice",
                    (GoalValueV1("entity_ref", alice), GoalValueV1("int", 35)),
                ),
            ),
        ),
        EvaluationReplayRelationV1(
            "person:employee_id",
            ("entity_ref", "string"),
            (
                EvaluationReplayFactV1(
                    "base:identity:alice",
                    (GoalValueV1("entity_ref", alice), GoalValueV1("string", "alice")),
                ),
            ),
        ),
    ),
)
profile = EvaluationExecutionProfileV1(
    "native_deterministic_v1",
    _token("c"),
    None,
    (EvaluationEnginePinV1("native", "golden-native", "golden-adapter"),),
)
plan = GoalPlanV1(
    target=GoalTargetRefV1("policy", "person.age", "1", _token("a")),
    query_digest=_token("b"),
    result_mode="rows",
    selections=(GoalSelectionV1("age", "int"),),
    evidence_scope_digest=_token("f"),
    execution_profile_digest=profile.profile_digest,
)
compiled = CompiledDerivationPlan(
    derivation_id="c2-installed-golden",
    version="1",
    body_ir=[
        ("pred", "Person:exists", ["$person"]),
        ("pred", "person:age", ["$person", "$age"]),
    ],
    heads=(CompiledHeadCall("__factgraph_projection__v1_age", ("$age",)),),
)
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
    world_input_pins=world_pins,
    scenario_bytes=None,
    provider_capture_bytes=None,
    capture=EvaluationCaptureProfileV1(4096, "not_captured", "not_requested"),
)
request_bytes = sealed_evaluation_request_v1_bytes(request)
assert sealed_evaluation_request_v1_from_bytes(request_bytes) == request
result = evaluate_sealed_evaluation_request_v1(request)
result_bytes = sealed_evaluation_result_v1_bytes(result)
assert sealed_evaluation_result_v1_from_bytes(result_bytes) == result
replay = replay_evaluation_run_v1(result.run)
assert replay.status == "matched"
assert replay.baseline.result_match and replay.effective.result_match
assert len(result.run.effective.canonical_result.rows) == 1

print(
    json.dumps(
        {
            "factgraph_file": str(Path(factgraph.__file__).resolve()),
            "python": ".".join(map(str, sys.version_info[:3])),
            "asset_bundle_digest": bundle.bundle_digest,
            "goal_plan_digest": plan.plan_digest,
            "goal_plan_sha256": hashlib.sha256(goal_plan_v1_bytes(plan)).hexdigest(),
            "profile_digest": profile.profile_digest,
            "profile_sha256": hashlib.sha256(
                evaluation_execution_profile_v1_bytes(profile)
            ).hexdigest(),
            "program_digest": program.envelope_digest,
            "program_sha256": hashlib.sha256(program.to_bytes()).hexdigest(),
            "request_bytes": len(request_bytes),
            "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
            "request_digest": request.request_digest,
            "result_bytes": len(result_bytes),
            "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
            "artifact_digest": result.artifact_digest,
            "run_digest": result.run.run_digest,
            "row_digest": result.run.effective.canonical_result.rows[0].semantic_row_digest,
            "schema_digest": schema.schema_digest,
            "schema_sha256": hashlib.sha256(evaluation_schema_capture_v1_bytes(schema)).hexdigest(),
            "world_capture_digest": baseline_world.world_capture_digest,
            "world_sha256": hashlib.sha256(
                evaluation_replay_world_v1_bytes(baseline_world)
            ).hexdigest(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
)
