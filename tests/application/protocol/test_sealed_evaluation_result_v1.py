"""Adversarial tests for the complete sealed-evaluation result graph."""

from __future__ import annotations

import base64
import json
from dataclasses import replace
from hashlib import sha256

import pytest

from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_v1 import (
    EvaluationEnginePinV1,
    EvaluationEngineResultV1,
    EvaluationExecutionProfileV1,
    EvaluationReplayFactV1,
    EvaluationReplayPayloadV1,
    EvaluationReplayProgramEnvelopeV1,
    EvaluationReplayRelationV1,
    EvaluationReplayWorldV1,
    EvaluationRunSideV1,
    EvaluationRunV1,
    ExplainTargetV1,
    ProviderReceiptRefV1,
)
from factgraph.application.protocol.goal_plan_v1 import (
    ContainsRowExpectationV1,
    GoalExpectationOutcomeV1,
    GoalPlanV1,
    GoalResultRowV1,
    GoalResultV1,
    GoalRowExpectationV1,
    GoalSelectionV1,
    GoalTargetRefV1,
    GoalTechnicalAssessmentV1,
    GoalValueV1,
)
from factgraph.application.protocol.relation_provider_v1 import (
    ProviderMaterializationV1,
    ProviderRelationRowV1,
    ProviderRequestV1,
)
from factgraph.application.protocol.scenario_v1 import (
    ResolvedScenarioOperationV1,
    ScenarioSpecV1,
    ScenarioWithoutRelationV1,
)
from factgraph.application.protocol.sealed_evaluation_result_v1 import (
    MAX_SEALED_EVALUATION_RESULT_BYTES_V1,
    EvaluationComparisonV1,
    EvaluationScenarioDiffV1,
    SealedEvaluationResultV1,
    assert_sealed_evaluation_result_matches_request_v1,
    evaluation_comparison_v1_bytes,
    evaluation_comparison_v1_from_bytes,
    evaluation_run_v1_bytes,
    evaluation_run_v1_from_bytes,
    evaluation_scenario_diff_v1_bytes,
    evaluation_scenario_diff_v1_from_bytes,
    sealed_evaluation_result_v1_bytes,
    sealed_evaluation_result_v1_from_bytes,
)
from factgraph.application.protocol.sealed_evaluation_scenario_v1 import (
    scenario_spec_v1_bytes,
)
from factgraph.application.protocol.sealed_evaluation_v1 import (
    MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1,
    SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    EvaluationAssetBundleV1,
    EvaluationAssetPinV1,
    EvaluationCaptureProfileV1,
    EvaluationProviderCaptureV1,
    EvaluationSchemaCaptureV1,
    EvaluationWorldInputPinsV1,
    SealedEvaluationRequestV1,
    evaluation_execution_profile_v1_bytes,
    evaluation_provider_capture_v1_bytes,
    evaluation_replay_world_v1_bytes,
    evaluation_schema_capture_v1_bytes,
    goal_plan_v1_bytes,
)
from factgraph.core.schema.schema_ir import canonicalize_schema_ir_jcs


def _token(character: str) -> str:
    return f"sha256:{character * 64}"


def _named_token(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _domain_token(domain: str, payload: object) -> str:
    raw = json.dumps(
        {"format": domain, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return f"sha256:{sha256(raw).hexdigest()}"


def _compiled_plan_wire(derivation_id: str) -> dict[str, object]:
    return {
        "$type": "FactGraphCompiledDerivationPlanV1",
        "derivation_id": derivation_id,
        "version": "1",
        "body_ir": [["pred", "Person.age", ["$person", "$age"]]],
        "heads": [
            {
                "target_pred_id": "__factgraph_projection__v1_age",
                "head_var_names": ["$age"],
            }
        ],
    }


def _program_record(
    plan: GoalPlanV1,
    *,
    derivation_id: str,
) -> dict[str, object]:
    compiled = _compiled_plan_wire(derivation_id)
    return {
        "$type": "FactGraphEvaluationProgramRecordV1",
        "plan_digest": plan.plan_digest,
        "query_digest": plan.query_digest,
        "target_digest": plan.target.target_digest,
        "compiled_plan_digest": _domain_token(
            "evaluation_run_v1_compiled_plan",
            compiled,
        ),
        "compiled_plan": compiled,
    }


def _resolved_operation_wire(
    operation: ResolvedScenarioOperationV1,
) -> dict[str, object]:
    return {
        "kind": operation.kind,
        "entity_ref": operation.entity_ref,
        "entity_type": operation.entity_type,
        "predicate_id": operation.predicate_id,
        "field": (
            None
            if operation.field is None
            else {
                "entity_type": operation.field.entity_type,
                "field_name": operation.field.field_name,
            }
        ),
        "assertion_id": operation.assertion_id,
        "values": [{"tag": item.tag, "value": item.value} for item in operation.values],
        "premise_ids": list(operation.premise_ids),
        "origin_refs": list(operation.origin_refs),
        "masked_witness_ids": list(operation.masked_witness_ids),
        "synthetic_witness_ids": list(operation.synthetic_witness_ids),
        "operation_digest": operation.operation_digest,
    }


def _schema_bytes() -> bytes:
    return canonicalize_schema_ir_jcs(
        {
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [{"name": "id", "type_domain": "string"}],
                }
            ],
            "generated_at": "2026-08-19T00:00:00Z",
            "predicates": [
                {
                    "arg_specs": [
                        {"name": "person", "type_domain": "entity_ref"},
                        {"name": "age", "type_domain": "int"},
                    ],
                    "group_key_indexes": [],
                    "pred_id": "Person.age",
                }
            ],
            "projection": {"entities": ["Person"], "predicates": ["Person.age"]},
            "protocol_version": {"export_v1": "1", "idref_v1": "1", "tup_v1": "1"},
            "schema_ir_version": "1",
        }
    )


def _profile() -> EvaluationExecutionProfileV1:
    return EvaluationExecutionProfileV1(
        "native_deterministic_v1",
        _token("c"),
        None,
        (EvaluationEnginePinV1("native", "0.3", "native-v1"),),
    )


def _plan(
    profile: EvaluationExecutionProfileV1,
    *,
    mode: str = "rows",
    candidate: bool = False,
    scenario_digest: str | None = None,
    kind: str = "policy",
    expectations: tuple[object, ...] = (),
) -> GoalPlanV1:
    return GoalPlanV1(
        target=GoalTargetRefV1(kind, f"{kind}.main", "1", _token("a")),  # type: ignore[arg-type]
        query_digest=_token("b"),
        result_mode=mode,  # type: ignore[arg-type]
        selections=(GoalSelectionV1("age", "int"),),
        candidate_target=(
            GoalTargetRefV1("policy", "policy.candidate", "2", _token("d")) if candidate else None
        ),
        candidate_query_digest=_token("e") if candidate else None,
        scenario_request_digest=scenario_digest,
        evidence_scope_digest=_token("f"),
        execution_profile_digest=profile.profile_digest,
        expectations=expectations,  # type: ignore[arg-type]
    )


def _candidate_plan(plan: GoalPlanV1) -> GoalPlanV1 | None:
    if plan.candidate_target is None:
        return None
    return GoalPlanV1(
        target=plan.candidate_target,
        query_digest=plan.candidate_query_digest or "",
        result_mode=plan.result_mode,
        selections=plan.selections,
        scenario_request_digest=plan.scenario_request_digest,
        evidence_scope_digest=plan.evidence_scope_digest,
        execution_profile_digest=plan.execution_profile_digest,
    )


def _world(
    side: str,
    age: int,
    *,
    semantic: str = "1",
    resolution: str = "2",
    closure: tuple[str, ...] = (),
) -> EvaluationReplayWorldV1:
    relation = EvaluationReplayRelationV1(
        "Person.age",
        ("entity_ref", "int"),
        (
            EvaluationReplayFactV1(
                f"witness:{age}",
                (
                    GoalValueV1("entity_ref", "idref_v1:Person:alice"),
                    GoalValueV1("int", age),
                ),
            ),
        ),
    )
    return EvaluationReplayWorldV1(
        side,  # type: ignore[arg-type]
        _token(semantic),
        _token(resolution),
        closure,
        (relation,),
    )


def _program(
    *,
    plan: GoalPlanV1,
    profile: EvaluationExecutionProfileV1,
    schema: EvaluationSchemaCaptureV1,
    candidate_plan: GoalPlanV1 | None,
    scenario_operation: ResolvedScenarioOperationV1 | None = None,
) -> EvaluationReplayProgramEnvelopeV1:
    if plan.scenario_request_digest is None:
        scenario_operation = None
    elif scenario_operation is None:
        scenario_operation = ResolvedScenarioOperationV1(
            kind="without_relation",
            entity_ref=None,
            entity_type=None,
            predicate_id="Person.age",
            field=None,
            premise_ids=("premise",),
        )
    scenario_patch = (
        None
        if scenario_operation is None
        else {
            "$type": "FactGraphScenarioPatchV1",
            "operations": [_resolved_operation_wire(scenario_operation)],
            "patch_digest": _domain_token(
                "evaluation_run_v1_scenario_patch",
                [scenario_operation.operation_digest],
            ),
        }
    )
    return EvaluationReplayProgramEnvelopeV1(
        schema_digest=schema.schema_digest,
        address_space_digest=_token("3"),
        plan_digest=plan.plan_digest,
        query_digest=plan.query_digest,
        target_digest=plan.target.target_digest,
        execution_profile_digest=profile.profile_digest,
        compiler_digest=profile.compiler_digest,
        compiled_program={
            "$type": "FactGraphEvaluationProgramV1",
            "primary": _program_record(plan, derivation_id="fixture-primary"),
            "candidate": (
                None
                if candidate_plan is None
                else _program_record(candidate_plan, derivation_id="fixture-candidate")
            ),
            "primary_policy_structure": None,
            "candidate_policy_structure": None,
            "primary_native_explain_context": None,
            "candidate_native_explain_context": None,
            "scenario_patch": scenario_patch,
        },
        candidate_plan_digest=None if candidate_plan is None else candidate_plan.plan_digest,
        candidate_query_digest=None if candidate_plan is None else candidate_plan.query_digest,
        candidate_target_digest=(
            None if candidate_plan is None else candidate_plan.target.target_digest
        ),
    )


def _result(
    plan: GoalPlanV1,
    *,
    age: int | None,
    outcomes: tuple[GoalExpectationOutcomeV1, ...] = (),
) -> GoalResultV1:
    rows = () if age is None else (GoalResultRowV1((("age", GoalValueV1("int", age)),)),)
    kwargs: dict[str, object] = {}
    if plan.result_mode == "exists":
        kwargs["exists_value"] = "false" if age is None else "true"
    elif plan.result_mode == "count":
        kwargs["count_value"] = len(rows)
    return GoalResultV1(
        plan.plan_digest,
        plan.result_mode,
        "complete",
        rows,
        expectation_outcomes=outcomes,
        **kwargs,  # type: ignore[arg-type]
    )


def _side(
    *,
    name: str,
    world: EvaluationReplayWorldV1,
    plan: GoalPlanV1,
    result: GoalResultV1,
) -> EvaluationRunSideV1:
    expectation = (
        "not_requested"
        if not result.expectation_outcomes
        else (
            "satisfied"
            if all(item.status == "satisfied" for item in result.expectation_outcomes)
            else result.expectation_outcomes[0].status
        )
    )
    assessment = GoalTechnicalAssessmentV1(
        plan.plan_digest,
        result.result_digest,
        "resolved" if plan.scenario_request_digest is not None else "not_requested",
        "succeeded",
        "not_requested",
        "complete",
        expectation,  # type: ignore[arg-type]
        "not_requested",
        "available",
    )
    return EvaluationRunSideV1(
        name,  # type: ignore[arg-type]
        plan.plan_digest,
        world.side,
        world.world_capture_digest,
        result,
        (EvaluationEngineResultV1("native", result),),
        assessment,
    )


def _run(
    *,
    mode: str = "rows",
    candidate: bool = False,
    scenario: ScenarioSpecV1 | None = None,
    baseline_age: int | None = 1,
    effective_age: int | None = 1,
    candidate_age: int | None = 2,
    expectations: tuple[object, ...] = (),
    outcomes: tuple[GoalExpectationOutcomeV1, ...] = (),
    explain: bool = False,
    provider_receipts: tuple[ProviderReceiptRefV1, ...] = (),
    scenario_operation: ResolvedScenarioOperationV1 | None = None,
) -> tuple[EvaluationRunV1, EvaluationSchemaCaptureV1]:
    profile = _profile()
    plan = _plan(
        profile,
        mode=mode,
        candidate=candidate,
        scenario_digest=None if scenario is None else scenario.spec_digest,
        expectations=expectations,
    )
    candidate_plan = _candidate_plan(plan)
    schema = EvaluationSchemaCaptureV1(_schema_bytes())
    baseline = _world("baseline", baseline_age or 0)
    effective = _world(
        "effective",
        effective_age or 0,
        semantic="4" if scenario is not None else "1",
        resolution="5" if scenario is not None else "2",
        closure=(_token("6"),) if scenario is not None else (),
    )
    program = _program(
        plan=plan,
        profile=profile,
        schema=schema,
        candidate_plan=candidate_plan,
        scenario_operation=scenario_operation,
    )
    payload = EvaluationReplayPayloadV1(
        schema.schema_digest,
        _token("3"),
        schema.schema_bytes,
        program.to_bytes(),
        (baseline, effective),
        provider_receipts,
    )
    baseline_result = _result(plan, age=baseline_age, outcomes=outcomes)
    effective_result = _result(plan, age=effective_age, outcomes=outcomes)
    baseline_side = _side(
        name="baseline",
        world=baseline,
        plan=plan,
        result=baseline_result,
    )
    effective_side = _side(
        name="effective",
        world=effective,
        plan=plan,
        result=effective_result,
    )
    candidate_side = None
    if candidate_plan is not None:
        candidate_result = _result(candidate_plan, age=candidate_age)
        candidate_side = _side(
            name="candidate_effective",
            world=effective,
            plan=candidate_plan,
            result=candidate_result,
        )
    explain_target = None
    if explain:
        assert effective_result.summary_anchor is not None
        explain_target = ExplainTargetV1(
            "effective",
            "summary",
            effective_result.summary_anchor.summary_anchor_digest,
        )
    return (
        EvaluationRunV1(
            plan,
            profile,
            payload,
            baseline_side,
            effective_side,
            candidate_plan,
            candidate_side,
            explain_target,
        ),
        schema,
    )


def _request_for_run(
    run: EvaluationRunV1,
    schema: EvaluationSchemaCaptureV1,
    *,
    comparison: str = "not_requested",
    explain: str = "not_captured",
    provider: EvaluationProviderCaptureV1 | None = None,
    request_baseline: EvaluationReplayWorldV1 | None = None,
) -> SealedEvaluationRequestV1:
    plan = run.plan
    dependencies: tuple[EvaluationAssetPinV1, ...] = ()
    if provider is not None:
        dependencies = (
            EvaluationAssetPinV1(
                "provider",
                "provider.main",
                "1",
                provider.request.provider_digest,
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
            if plan.candidate_target is None
            else EvaluationAssetPinV1(
                plan.candidate_target.kind,
                plan.candidate_target.target_id,
                plan.candidate_target.target_version or "",
                plan.candidate_target.target_digest,
            )
        ),
        dependencies=dependencies,
        query_digest=plan.query_digest,
        schema_digest=schema.schema_digest,
        address_space_digest=run.replay_payload.address_space_digest,
        compiler_digest=run.execution_profile.compiler_digest,
        execution_profile_digest=run.execution_profile.profile_digest,
        runtime_digest=SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    )
    scenario = (
        None
        if plan.scenario_request_digest is None
        else ScenarioSpecV1((ScenarioWithoutRelationV1("premise", "Person.age"),))
    )
    if scenario is not None and scenario.spec_digest != plan.scenario_request_digest:
        raise AssertionError("fixture Scenario does not match run Plan")
    program_row = json.loads(run.replay_payload.compiled_program_bytes)
    compiled_program = program_row["compiled_program"]
    assert type(compiled_program) is dict
    compiled_program["scenario_patch"] = None
    request_program_bytes = _canonical(program_row)
    return SealedEvaluationRequestV1(
        asset_bundle=bundle,
        goal_plan_bytes=goal_plan_v1_bytes(plan),
        execution_profile_bytes=evaluation_execution_profile_v1_bytes(run.execution_profile),
        schema_bytes=evaluation_schema_capture_v1_bytes(schema),
        program_envelope_bytes=request_program_bytes,
        baseline_world_bytes=evaluation_replay_world_v1_bytes(
            run.replay_payload.world("baseline") if request_baseline is None else request_baseline
        ),
        world_input_pins=EvaluationWorldInputPinsV1(_token("4"), _token("5")),
        scenario_bytes=None if scenario is None else scenario_spec_v1_bytes(scenario),
        provider_capture_bytes=(
            None if provider is None else evaluation_provider_capture_v1_bytes(provider)
        ),
        capture=EvaluationCaptureProfileV1(4096, explain, comparison),
    )


def _comparison(run: EvaluationRunV1) -> EvaluationComparisonV1:
    assert run.candidate_plan is not None and run.candidate_effective is not None
    primary = {item.semantic_row_digest for item in run.effective.canonical_result.rows}
    candidate = {item.semantic_row_digest for item in run.candidate_effective.canonical_result.rows}
    program = json.loads(run.replay_payload.compiled_program_bytes)["compiled_program"]
    primary_program = program["primary"]
    candidate_program = program["candidate"]
    return EvaluationComparisonV1(
        primary_plan_digest=run.plan.plan_digest,
        candidate_plan_digest=run.candidate_plan.plan_digest,
        effective_world_capture_digest=run.replay_payload.world("effective").world_capture_digest,
        primary_target_digest=run.plan.target.target_digest,
        candidate_target_digest=run.candidate_plan.target.target_digest,
        primary_compiled_plan_digest=primary_program["compiled_plan_digest"],
        candidate_compiled_plan_digest=candidate_program["compiled_plan_digest"],
        compiled_body_equal=(
            primary_program["compiled_plan"]["body_ir"]
            == candidate_program["compiled_plan"]["body_ir"]
        ),
        compiled_head_equal=(
            primary_program["compiled_plan"]["heads"] == candidate_program["compiled_plan"]["heads"]
        ),
        primary_policy_structure_digest=None,
        candidate_policy_structure_digest=None,
        authored_structure_relation="not_captured",
        shared_semantic_row_digests=tuple(sorted(primary & candidate)),
        primary_only_semantic_row_digests=tuple(sorted(primary - candidate)),
        candidate_only_semantic_row_digests=tuple(sorted(candidate - primary)),
        result_relation="equivalent" if primary == candidate else "different",
    )


def _scenario_diff(
    run: EvaluationRunV1,
    operation: ResolvedScenarioOperationV1,
) -> EvaluationScenarioDiffV1:
    baseline = run.replay_payload.world("baseline")
    effective = run.replay_payload.world("effective")
    baseline_rows = {item.semantic_row_digest for item in run.baseline.canonical_result.rows}
    effective_rows = {item.semantic_row_digest for item in run.effective.canonical_result.rows}
    patch_digest = _domain_token(
        "evaluation_run_v1_scenario_patch",
        [operation.operation_digest],
    )
    return EvaluationScenarioDiffV1(
        run_digest=run.run_digest,
        plan_digest=run.plan.plan_digest,
        scenario_request_digest=run.plan.scenario_request_digest or "",
        baseline_world_capture_digest=baseline.world_capture_digest,
        effective_world_capture_digest=effective.world_capture_digest,
        baseline_semantic_world_digest=baseline.semantic_world_digest,
        effective_semantic_world_digest=effective.semantic_world_digest,
        baseline_relation_snapshot_digest=baseline.relation_snapshot_digest,
        effective_relation_snapshot_digest=effective.relation_snapshot_digest,
        baseline_resolution_evidence_digest=baseline.resolution_evidence_digest,
        effective_resolution_evidence_digest=effective.resolution_evidence_digest,
        baseline_closure_target_digests=baseline.closure_target_digests,
        effective_closure_target_digests=effective.closure_target_digests,
        input_difference_axes=(
            "semantic_world",
            "relation_snapshot",
            "resolution_evidence",
            "closure_targets",
        ),
        scenario_operations=(operation,),
        scenario_patch_capture="captured",
        scenario_patch_application="applied",
        scenario_patch_digest=patch_digest,
        scenario_operation_digests=(operation.operation_digest,),
        shared_semantic_row_digests=tuple(sorted(baseline_rows & effective_rows)),
        baseline_only_semantic_row_digests=tuple(sorted(baseline_rows - effective_rows)),
        effective_only_semantic_row_digests=tuple(sorted(effective_rows - baseline_rows)),
        result_relation="equivalent" if baseline_rows == effective_rows else "different",
    )


@pytest.mark.parametrize(
    ("mode", "age"),
    [
        ("rows", 1),
        ("set", 1),
        ("exists", 1),
        ("exists", None),
        ("count", 1),
    ],
)
def test_complete_run_roundtrips_all_four_modes_and_complete_empty(
    mode: str,
    age: int | None,
) -> None:
    run, _ = _run(mode=mode, baseline_age=age, effective_age=age)
    raw = evaluation_run_v1_bytes(run)
    rebuilt = evaluation_run_v1_from_bytes(raw)

    assert evaluation_run_v1_bytes(rebuilt) == raw
    assert rebuilt.run_digest == run.run_digest
    assert set(json.loads(raw)) == {
        "$type",
        "plan",
        "execution_profile",
        "replay_payload",
        "baseline",
        "effective",
        "candidate_plan",
        "candidate_effective",
        "explain_target",
        "run_digest",
    }
    if mode == "exists" and age is None:
        assert rebuilt.effective.canonical_result.completeness == "complete"
        assert rebuilt.effective.canonical_result.exists_value == "false"
        assert rebuilt.effective.canonical_result.rows == ()


def test_expectation_outcome_is_exactly_bound_to_plan_and_row() -> None:
    profile = _profile()
    expected_row = GoalRowExpectationV1((("age", GoalValueV1("int", 1)),))
    expectation = ContainsRowExpectationV1("contains", expected_row)
    provisional = _plan(profile, expectations=(expectation,))
    semantic_row = GoalResultRowV1((("age", GoalValueV1("int", 1)),)).semantic_row_digest
    outcome = GoalExpectationOutcomeV1(
        expectation.expectation_id,
        expectation.expectation_digest,
        expectation.kind,
        "satisfied",
        (semantic_row,),
    )
    run, _ = _run(
        expectations=provisional.expectations,
        outcomes=(outcome,),
    )
    rebuilt = evaluation_run_v1_from_bytes(evaluation_run_v1_bytes(run))
    assert rebuilt.effective.canonical_result.expectation_outcomes == (outcome,)


def test_candidate_comparison_and_sealed_result_roundtrip_and_request_binding() -> None:
    run, schema = _run(candidate=True)
    request = _request_for_run(run, schema, comparison="published_candidate")
    comparison = _comparison(run)
    result = SealedEvaluationResultV1(
        request.request_digest,
        request.asset_bundle.bundle_digest,
        run,
        comparison,
    )

    comparison_raw = evaluation_comparison_v1_bytes(comparison)
    assert (
        evaluation_comparison_v1_bytes(evaluation_comparison_v1_from_bytes(comparison_raw))
        == comparison_raw
    )
    raw = sealed_evaluation_result_v1_bytes(result)
    rebuilt = sealed_evaluation_result_v1_from_bytes(raw)
    assert sealed_evaluation_result_v1_bytes(rebuilt) == raw
    assert rebuilt.artifact_digest == result.artifact_digest
    assert_sealed_evaluation_result_matches_request_v1(rebuilt, request)


def test_typed_scenario_diff_roundtrip_and_request_binding() -> None:
    scenario = ScenarioSpecV1((ScenarioWithoutRelationV1("premise", "Person.age"),))
    run, schema = _run(
        scenario=scenario,
        baseline_age=1,
        effective_age=2,
    )
    operation = ResolvedScenarioOperationV1(
        kind="without_relation",
        entity_ref=None,
        entity_type=None,
        predicate_id="Person.age",
        field=None,
        premise_ids=("premise",),
    )
    diff = _scenario_diff(run, operation)
    request = _request_for_run(run, schema, comparison="baseline_vs_effective")
    result = SealedEvaluationResultV1(
        request.request_digest,
        request.asset_bundle.bundle_digest,
        run,
        scenario_diff=diff,
    )

    diff_raw = evaluation_scenario_diff_v1_bytes(diff)
    assert (
        evaluation_scenario_diff_v1_bytes(evaluation_scenario_diff_v1_from_bytes(diff_raw))
        == diff_raw
    )
    rebuilt = sealed_evaluation_result_v1_from_bytes(sealed_evaluation_result_v1_bytes(result))
    assert rebuilt.scenario_diff is not None
    assert rebuilt.scenario_diff.scenario_operations == (operation,)
    assert_sealed_evaluation_result_matches_request_v1(rebuilt, request)


def test_scenario_program_patch_is_output_only_and_the_only_normalized_field() -> None:
    scenario = ScenarioSpecV1((ScenarioWithoutRelationV1("premise", "Person.age"),))
    run, schema = _run(scenario=scenario, baseline_age=1, effective_age=2)
    operation = ResolvedScenarioOperationV1(
        kind="without_relation",
        entity_ref=None,
        entity_type=None,
        predicate_id="Person.age",
        field=None,
        premise_ids=("premise",),
    )
    diff = _scenario_diff(run, operation)
    request = _request_for_run(run, schema, comparison="baseline_vs_effective")
    result = SealedEvaluationResultV1(
        request.request_digest,
        request.asset_bundle.bundle_digest,
        run,
        scenario_diff=diff,
    )
    assert request.program_envelope_bytes != run.replay_payload.compiled_program_bytes
    assert_sealed_evaluation_result_matches_request_v1(result, request)

    pre_resolved_request = replace(
        request,
        program_envelope_bytes=run.replay_payload.compiled_program_bytes,
    )
    pre_resolved_result = replace(
        result,
        request_digest=pre_resolved_request.request_digest,
    )
    with pytest.raises(ProtocolShapeError, match="cannot carry a resolved Scenario patch"):
        assert_sealed_evaluation_result_matches_request_v1(
            pre_resolved_result,
            pre_resolved_request,
        )

    missing_patch_payload = replace(
        run.replay_payload,
        compiled_program_bytes=request.program_envelope_bytes,
    )
    missing_patch_run = replace(run, replay_payload=missing_patch_payload)
    with pytest.raises(ProtocolShapeError, match="sealed Scenario patch"):
        replace(
            result,
            run=missing_patch_run,
            scenario_diff=_scenario_diff(missing_patch_run, operation),
        )

    changed_row = json.loads(run.replay_payload.compiled_program_bytes)
    changed_program = changed_row["compiled_program"]
    changed_primary = changed_program["primary"]
    changed_primary["compiled_plan"]["body_ir"] = [["pred", "Person.age", ["$person", "$changed"]]]
    changed_primary["compiled_plan_digest"] = _domain_token(
        "evaluation_run_v1_compiled_plan",
        changed_primary["compiled_plan"],
    )
    changed_envelope = EvaluationReplayProgramEnvelopeV1(
        schema_digest=run.replay_payload.program_envelope.schema_digest,
        address_space_digest=run.replay_payload.program_envelope.address_space_digest,
        plan_digest=run.replay_payload.program_envelope.plan_digest,
        query_digest=run.replay_payload.program_envelope.query_digest,
        target_digest=run.replay_payload.program_envelope.target_digest,
        execution_profile_digest=(run.replay_payload.program_envelope.execution_profile_digest),
        compiler_digest=run.replay_payload.program_envelope.compiler_digest,
        compiled_program=changed_program,
        candidate_plan_digest=run.replay_payload.program_envelope.candidate_plan_digest,
        candidate_query_digest=run.replay_payload.program_envelope.candidate_query_digest,
        candidate_target_digest=run.replay_payload.program_envelope.candidate_target_digest,
    )
    changed_payload = replace(
        run.replay_payload,
        compiled_program_bytes=changed_envelope.to_bytes(),
    )
    changed_run = replace(run, replay_payload=changed_payload)
    changed_result = replace(
        result,
        run=changed_run,
        scenario_diff=_scenario_diff(changed_run, operation),
    )
    with pytest.raises(ProtocolShapeError, match="beyond the resolved Scenario patch"):
        assert_sealed_evaluation_result_matches_request_v1(changed_result, request)


def test_structured_explain_requires_native_context_before_target_binding() -> None:
    run, schema = _run(explain=True)
    request = _request_for_run(run, schema, explain="structured_display")
    result = SealedEvaluationResultV1(
        request.request_digest,
        request.asset_bundle.bundle_digest,
        run,
    )
    with pytest.raises(ProtocolShapeError, match="native display context"):
        assert_sealed_evaluation_result_matches_request_v1(result, request)

    hidden = replace(run, explain_target=None)
    hidden_result = SealedEvaluationResultV1(
        request.request_digest,
        request.asset_bundle.bundle_digest,
        hidden,
    )
    with pytest.raises(ProtocolShapeError, match="native display context"):
        assert_sealed_evaluation_result_matches_request_v1(hidden_result, request)


def test_provider_result_uses_captured_materialization_and_exact_receipt() -> None:
    schema = EvaluationSchemaCaptureV1(_schema_bytes())
    provider_request = ProviderRequestV1(
        _token("7"),
        _token("b"),
        schema.schema_digest,
        ("Person.age",),
        ("Person.age",),
        (),
    )
    materialization = ProviderMaterializationV1(
        provider_request.provider_digest,
        provider_request.request_digest,
        "receipt:provider:1",
        _token("8"),
        provider_request.supplied_predicate_ids,
        (
            ProviderRelationRowV1(
                "Person.age",
                (
                    GoalValueV1("entity_ref", "idref_v1:Person:alice"),
                    GoalValueV1("int", 31),
                ),
                "origin:provider:1",
            ),
        ),
    )
    provider = EvaluationProviderCaptureV1(provider_request, materialization)
    receipt = ProviderReceiptRefV1(
        provider_request.provider_digest,
        provider_request.request_digest,
        materialization.materialization_digest,
        materialization.receipt_ref,
        materialization.receipt_digest,
    )
    profile = _profile()
    plan = _plan(profile, kind="relation_provider")
    candidate_plan = None
    program = _program(
        plan=plan,
        profile=profile,
        schema=schema,
        candidate_plan=candidate_plan,
    )
    request_baseline = _world("baseline", 30)
    run_baseline = _world("baseline", 31, semantic="9")
    effective = _world("effective", 31, semantic="9")
    payload = EvaluationReplayPayloadV1(
        schema.schema_digest,
        _token("3"),
        schema.schema_bytes,
        program.to_bytes(),
        (run_baseline, effective),
        (receipt,),
    )
    baseline_result = _result(plan, age=31)
    effective_result = _result(plan, age=31)
    run = EvaluationRunV1(
        plan,
        profile,
        payload,
        _side(name="baseline", world=run_baseline, plan=plan, result=baseline_result),
        _side(name="effective", world=effective, plan=plan, result=effective_result),
    )
    request = _request_for_run(
        run,
        schema,
        provider=provider,
        request_baseline=request_baseline,
    )
    result = SealedEvaluationResultV1(
        request.request_digest,
        request.asset_bundle.bundle_digest,
        run,
    )
    assert_sealed_evaluation_result_matches_request_v1(result, request)

    wrong_payload = replace(run.replay_payload, provider_receipts=())
    wrong_run = replace(run, replay_payload=wrong_payload)
    wrong = SealedEvaluationResultV1(
        request.request_digest,
        request.asset_bundle.bundle_digest,
        wrong_run,
    )
    with pytest.raises(ProtocolShapeError, match="receipt"):
        assert_sealed_evaluation_result_matches_request_v1(wrong, request)


def test_run_and_result_wire_reject_unknown_null_duplicate_float_and_base64() -> None:
    run, schema = _run()
    raw = evaluation_run_v1_bytes(run)
    body = json.loads(raw)
    body["unknown"] = None
    with pytest.raises(ProtocolShapeError):
        evaluation_run_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )
    with pytest.raises(ProtocolShapeError, match="duplicate"):
        evaluation_run_v1_from_bytes(raw[:-1] + b',"run_digest":"duplicate"}')
    body = json.loads(raw)
    body["effective"]["canonical_result"]["count_value"] = 1.5
    with pytest.raises(ProtocolShapeError, match="float"):
        evaluation_run_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )

    request = _request_for_run(run, schema)
    result_raw = sealed_evaluation_result_v1_bytes(
        SealedEvaluationResultV1(
            request.request_digest,
            request.asset_bundle.bundle_digest,
            run,
        )
    )
    result_body = json.loads(result_raw)
    result_body["run_bytes_b64u"] += "="
    with pytest.raises(ProtocolShapeError, match="unpadded"):
        sealed_evaluation_result_v1_from_bytes(
            json.dumps(result_body, sort_keys=True, separators=(",", ":")).encode()
        )
    result_body["run_bytes_b64u"] = ""
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_result_v1_from_bytes(
            json.dumps(result_body, sort_keys=True, separators=(",", ":")).encode()
        )
    result_body["run_bytes_b64u"] = "e30+"
    with pytest.raises(ProtocolShapeError, match="base64url"):
        sealed_evaluation_result_v1_from_bytes(
            json.dumps(result_body, sort_keys=True, separators=(",", ":")).encode()
        )
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_result_v1_from_bytes(b"x" * (MAX_SEALED_EVALUATION_RESULT_BYTES_V1 + 1))


def test_nested_exact_keys_depth_and_terminal_limit_ordering() -> None:
    run, _ = _run()
    raw = evaluation_run_v1_bytes(run)

    for mutate in (
        lambda body: body["baseline"]["assessment"].__setitem__("unknown", None),
        lambda body: body["effective"]["canonical_result"].pop("summary_anchor"),
        lambda body: body.__setitem__("baseline", None),
    ):
        body = json.loads(raw)
        mutate(body)
        with pytest.raises(ProtocolShapeError):
            evaluation_run_v1_from_bytes(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            )

    depth_64: object = None
    for _ in range(63):
        depth_64 = [depth_64]
    within_depth = json.dumps({"x": depth_64}, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ProtocolShapeError, match="unknown or missing"):
        evaluation_run_v1_from_bytes(within_depth)

    depth_65: object = None
    for _ in range(64):
        depth_65 = [depth_65]
    over_depth = json.dumps({"x": depth_65}, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ProtocolShapeError, match="depth limit"):
        evaluation_run_v1_from_bytes(over_depth)

    at_terminal_ceiling = b"{}" + b" " * (MAX_SEALED_EVALUATION_RESULT_BYTES_V1 - 2)
    assert len(at_terminal_ceiling) == MAX_SEALED_EVALUATION_RESULT_BYTES_V1
    with pytest.raises(ProtocolShapeError, match="canonical"):
        sealed_evaluation_result_v1_from_bytes(at_terminal_ceiling)
    with pytest.raises(ProtocolShapeError, match="within its limit"):
        sealed_evaluation_result_v1_from_bytes(at_terminal_ceiling + b" ")


def test_projection_component_ceiling_and_sealed_patch_limit_apply_before_embedding() -> None:
    with pytest.raises(ProtocolShapeError, match="within its limit"):
        evaluation_comparison_v1_from_bytes(b"x" * (MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1 + 1))

    oversized_operation = ResolvedScenarioOperationV1(
        kind="without_relation",
        entity_ref=None,
        entity_type=None,
        predicate_id="Person.age",
        field=None,
        premise_ids=("premise",),
        origin_refs=("x" * MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1,),
    )
    scenario = ScenarioSpecV1((ScenarioWithoutRelationV1("premise", "Person.age"),))
    scenario_run, _ = _run(scenario=scenario, baseline_age=1, effective_age=2)
    oversized_diff = _scenario_diff(scenario_run, oversized_operation)
    with pytest.raises(ProtocolShapeError, match="4 MiB component"):
        evaluation_scenario_diff_v1_bytes(oversized_diff)
    with pytest.raises(ProtocolShapeError, match="within its limit"):
        evaluation_scenario_diff_v1_from_bytes(
            b"x" * (MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1 + 1)
        )

    with pytest.raises(ProtocolShapeError, match="sealed Scenario patch"):
        SealedEvaluationResultV1(
            _token("1"),
            _token("2"),
            scenario_run,
            scenario_diff=oversized_diff,
        )
    with pytest.raises(ProtocolShapeError, match="size limit"):
        _run(
            scenario=scenario,
            baseline_age=1,
            effective_age=2,
            scenario_operation=oversized_operation,
        )


def test_stale_nested_digests_and_projection_splices_fail_closed() -> None:
    run, schema = _run(candidate=True)
    object.__setattr__(
        run.effective.canonical_result.rows[0],
        "semantic_row_digest",
        _token("9"),
    )
    with pytest.raises(ProtocolShapeError, match="stale|mismatch"):
        evaluation_run_v1_bytes(run)

    clean, clean_schema = _run(candidate=True)
    comparison = _comparison(clean)
    request = _request_for_run(
        clean,
        clean_schema,
        comparison="published_candidate",
    )
    with pytest.raises(ProtocolShapeError, match="Run pins"):
        SealedEvaluationResultV1(
            request.request_digest,
            request.asset_bundle.bundle_digest,
            clean,
            replace(comparison, primary_plan_digest=_token("9")),
        )
    with pytest.raises(ProtocolShapeError, match="request/bundle"):
        assert_sealed_evaluation_result_matches_request_v1(
            SealedEvaluationResultV1(
                _token("9"),
                request.asset_bundle.bundle_digest,
                clean,
                comparison,
            ),
            request,
        )
    assert schema.schema_digest == clean_schema.schema_digest


def test_comparison_digest_matches_runtime_donor_domain_and_structure_rules() -> None:
    run, _ = _run(candidate=True)
    comparison = _comparison(run)
    expected = _domain_token(
        "policy_variant_comparison_v1",
        [
            comparison.primary_plan_digest,
            comparison.candidate_plan_digest,
            comparison.effective_world_capture_digest,
            comparison.primary_target_digest,
            comparison.candidate_target_digest,
            comparison.primary_compiled_plan_digest,
            comparison.candidate_compiled_plan_digest,
            comparison.compiled_body_equal,
            comparison.compiled_head_equal,
            None,
            None,
            "not_captured",
            list(comparison.shared_semantic_row_digests),
            list(comparison.primary_only_semantic_row_digests),
            list(comparison.candidate_only_semantic_row_digests),
            comparison.result_relation,
            comparison.structural_basis,
            comparison.causal_attribution,
        ],
    )
    assert comparison.comparison_digest == expected
    with pytest.raises(ProtocolShapeError, match="bare"):
        replace(comparison, primary_policy_structure_digest=_token("1"))
    with pytest.raises(ProtocolShapeError, match="derived"):
        replace(
            comparison,
            primary_policy_structure_digest="1" * 64,
            authored_structure_relation="not_captured",
        )


def test_result_row_limit_and_hostile_rich_types_reject() -> None:
    run, _ = _run()
    rows = tuple(GoalResultRowV1((("age", GoalValueV1("int", index)),)) for index in range(4097))
    over = GoalResultV1(run.plan.plan_digest, "rows", "complete", rows)
    over_baseline = _side(
        name="baseline",
        world=run.replay_payload.world("baseline"),
        plan=run.plan,
        result=over,
    )
    over_effective = _side(
        name="effective",
        world=run.replay_payload.world("effective"),
        plan=run.plan,
        result=over,
    )
    over_run = EvaluationRunV1(
        run.plan,
        run.execution_profile,
        run.replay_payload,
        over_baseline,
        over_effective,
    )
    with pytest.raises(ProtocolShapeError, match="row limit"):
        evaluation_run_v1_bytes(over_run)

    class RunChild(EvaluationRunV1):
        pass

    with pytest.raises(ProtocolShapeError, match="exact EvaluationRunV1"):
        evaluation_run_v1_bytes(
            RunChild(
                run.plan,
                run.execution_profile,
                run.replay_payload,
                run.baseline,
                run.effective,
                run.candidate_plan,
                run.candidate_effective,
                run.explain_target,
            )
        )
    with pytest.raises(ProtocolShapeError):
        evaluation_run_v1_bytes({})  # type: ignore[arg-type]


def test_outer_run_bytes_are_the_exact_complete_codec() -> None:
    run, schema = _run()
    request = _request_for_run(run, schema)
    result = SealedEvaluationResultV1(
        request.request_digest,
        request.asset_bundle.bundle_digest,
        run,
    )
    body = json.loads(sealed_evaluation_result_v1_bytes(result))
    decoded_run_bytes = base64.urlsafe_b64decode(
        body["run_bytes_b64u"] + "=" * (-len(body["run_bytes_b64u"]) % 4)
    )
    assert decoded_run_bytes == evaluation_run_v1_bytes(run)
    assert json.loads(decoded_run_bytes)["replay_payload"]
    assert "replay_payload_bytes_b64u" not in json.loads(decoded_run_bytes)
    assert not hasattr(result, "store")
    assert not hasattr(result, "evaluator")
