from __future__ import annotations

from dataclasses import replace

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
    evaluation_replay_payload_v1_bytes,
    evaluation_replay_payload_v1_from_bytes,
    evaluation_replay_program_envelope_v1_from_bytes,
)
from factgraph.application.protocol.goal_plan_v1 import (
    GoalPlanV1,
    GoalResultRowV1,
    GoalResultV1,
    GoalSelectionV1,
    GoalTargetRefV1,
    GoalTechnicalAssessmentV1,
    GoalValueV1,
)


def _token(character: str) -> str:
    return f"sha256:{character * 64}"


def _world(side: str, age: int) -> EvaluationReplayWorldV1:
    relation = EvaluationReplayRelationV1(
        "Person.age",
        ("string", "int"),
        (
            EvaluationReplayFactV1(
                f"witness:{side}:alice",
                (GoalValueV1("string", "alice"), GoalValueV1("int", age)),
            ),
        ),
    )
    return EvaluationReplayWorldV1(
        side,  # type: ignore[arg-type]
        _token("c" if side == "baseline" else "d"),
        _token("e" if side == "baseline" else "f"),
        (),
        (relation,),
    )


def _payload(
    profile: EvaluationExecutionProfileV1,
    plan: GoalPlanV1,
    candidate_plan: GoalPlanV1 | None = None,
) -> EvaluationReplayPayloadV1:
    program = EvaluationReplayProgramEnvelopeV1(
        schema_digest=_token("a"),
        address_space_digest=_token("b"),
        plan_digest=plan.plan_digest,
        query_digest=plan.query_digest,
        target_digest=plan.target.target_digest,
        execution_profile_digest=profile.profile_digest,
        compiler_digest=profile.compiler_digest,
        compiled_program={"$type": "CompiledDerivationPlanV1", "body": []},
        candidate_plan_digest=(None if candidate_plan is None else candidate_plan.plan_digest),
        candidate_query_digest=(None if candidate_plan is None else candidate_plan.query_digest),
        candidate_target_digest=(
            None if candidate_plan is None else candidate_plan.target.target_digest
        ),
    )
    return EvaluationReplayPayloadV1(
        _token("a"),
        _token("b"),
        b'{"entities":[],"predicates":[]}',
        program.to_bytes(),
        (_world("baseline", 35), _world("effective", 22)),
        (
            ProviderReceiptRefV1(
                _token("1"), _token("2"), _token("3"), "receipt:lookup:7", _token("4")
            ),
        ),
    )


def _profile(*, portable: bool = False) -> EvaluationExecutionProfileV1:
    engines = (
        (EvaluationEnginePinV1("native", "0.3", "native-v1"),)
        if not portable
        else (
            EvaluationEnginePinV1("native", "0.3", "native-v1"),
            EvaluationEnginePinV1("souffle", "2.5", "souffle-v1"),
            EvaluationEnginePinV1("problog", "2.2", "problog-v1"),
        )
    )
    return EvaluationExecutionProfileV1(
        "portable_deterministic_v1" if portable else "native_deterministic_v1",
        _token("5"),
        None,
        engines,
    )


def _plan(
    profile: EvaluationExecutionProfileV1,
    *,
    target: str = "a",
    candidate_target: str | None = None,
) -> GoalPlanV1:
    return GoalPlanV1(
        GoalTargetRefV1("policy", f"policy.{target}", "1", _token(target)),
        _token("6"),
        "rows",
        (GoalSelectionV1("age", "int"),),
        candidate_target=(
            None
            if candidate_target is None
            else GoalTargetRefV1(
                "policy", f"policy.{candidate_target}", "1", _token(candidate_target)
            )
        ),
        candidate_query_digest=None if candidate_target is None else _token("6"),
        execution_profile_digest=profile.profile_digest,
    )


def _result(plan: GoalPlanV1, age: int = 22) -> GoalResultV1:
    return GoalResultV1(
        plan.plan_digest,
        "rows",
        "complete",
        (GoalResultRowV1((("age", GoalValueV1("int", age)),)),),
    )


def _side(
    *,
    name: str,
    world: EvaluationReplayWorldV1,
    plan: GoalPlanV1,
    profile: EvaluationExecutionProfileV1,
    age: int,
) -> EvaluationRunSideV1:
    result = _result(plan, age)
    assessment = GoalTechnicalAssessmentV1(
        plan.plan_digest,
        result.result_digest,
        "resolved",
        "succeeded",
        "equivalent" if profile.kind == "portable_deterministic_v1" else "not_requested",
        "complete",
        "not_requested",
        "available",
        "available",
    )
    engine_results = tuple(EvaluationEngineResultV1(pin.engine, result) for pin in profile.engines)
    return EvaluationRunSideV1(
        name,  # type: ignore[arg-type]
        plan.plan_digest,
        world.side,
        world.world_capture_digest,
        result,
        engine_results,
        assessment,
    )


def test_replay_payload_round_trips_canonically_without_live_store_surface() -> None:
    profile = _profile()
    plan = _plan(profile)
    payload = _payload(profile, plan)

    raw = payload.to_bytes()
    restored = EvaluationReplayPayloadV1.from_bytes(raw)

    assert raw == evaluation_replay_payload_v1_bytes(restored)
    assert restored.payload_digest == payload.payload_digest
    assert restored.world("effective").relations[0].facts[0].values[-1].value == 22
    assert not hasattr(restored, "store")
    assert not hasattr(restored, "resolver")


def test_replay_codec_rejects_noncanonical_duplicate_and_spliced_payloads() -> None:
    profile = _profile()
    plan = _plan(profile)
    payload = _payload(profile, plan)
    raw = payload.to_bytes()

    with pytest.raises(ProtocolShapeError, match="duplicate"):
        evaluation_replay_payload_v1_from_bytes(
            raw.replace(b'"schema_digest"', b'"schema_digest":"x","schema_digest"', 1)
        )
    with pytest.raises(ProtocolShapeError, match="canonical"):
        evaluation_replay_payload_v1_from_bytes(raw + b"\n")

    other = _payload(profile, plan)
    effective = other.world("effective")
    bad_payload = replace(
        payload,
        worlds=(payload.world("baseline"), replace(effective, semantic_world_digest=_token("9"))),
    )
    assert bad_payload.payload_digest != payload.payload_digest
    assert (
        evaluation_replay_payload_v1_from_bytes(bad_payload.to_bytes()).payload_digest
        == bad_payload.payload_digest
    )


def test_replay_program_envelope_is_strict_and_run_bound() -> None:
    profile = _profile()
    plan = _plan(profile)
    payload = _payload(profile, plan)
    envelope = payload.program_envelope

    assert evaluation_replay_program_envelope_v1_from_bytes(envelope.to_bytes()) == envelope
    with pytest.raises(TypeError):
        envelope.compiled_program["tamper"] = True  # type: ignore[index]
    with pytest.raises(ProtocolShapeError, match="canonical"):
        evaluation_replay_program_envelope_v1_from_bytes(envelope.to_bytes() + b"\n")

    bad_envelope = replace(envelope, target_digest=_token("9"))
    bad_payload = replace(payload, compiled_program_bytes=bad_envelope.to_bytes())
    baseline = _side(
        name="baseline",
        world=bad_payload.world("baseline"),
        plan=plan,
        profile=profile,
        age=35,
    )
    effective = _side(
        name="effective",
        world=bad_payload.world("effective"),
        plan=plan,
        profile=profile,
        age=22,
    )
    with pytest.raises(ProtocolShapeError, match="replay program envelope does not match run pins"):
        EvaluationRunV1(plan, profile, bad_payload, baseline, effective)


def test_completed_native_run_seals_baseline_effective_and_explicit_explain_row() -> None:
    profile = _profile()
    plan = _plan(profile)
    payload = _payload(profile, plan)
    baseline = _side(
        name="baseline",
        world=payload.world("baseline"),
        plan=plan,
        profile=profile,
        age=35,
    )
    effective = _side(
        name="effective",
        world=payload.world("effective"),
        plan=plan,
        profile=profile,
        age=22,
    )
    assert effective.canonical_result.rows[0].anchor is not None
    target = ExplainTargetV1(
        "effective", "row", effective.canonical_result.rows[0].anchor.anchor_digest
    )

    run = EvaluationRunV1(plan, profile, payload, baseline, effective, explain_target=target)

    assert run.run_digest.startswith("sha256:")
    assert run.baseline.world_capture_digest != run.effective.world_capture_digest
    assert run.explain_target == target

    with pytest.raises(ProtocolShapeError, match="Explain target does not belong"):
        EvaluationRunV1(
            plan,
            profile,
            payload,
            baseline,
            effective,
            explain_target=ExplainTargetV1("effective", "row", _token("0")),
        )


def test_portable_run_requires_exact_real_engine_inventory_and_parity() -> None:
    profile = _profile(portable=True)
    plan = _plan(profile)
    payload = _payload(profile, plan)
    baseline = _side(
        name="baseline",
        world=payload.world("baseline"),
        plan=plan,
        profile=profile,
        age=35,
    )
    effective = _side(
        name="effective",
        world=payload.world("effective"),
        plan=plan,
        profile=profile,
        age=22,
    )
    run = EvaluationRunV1(plan, profile, payload, baseline, effective)
    assert tuple(item.engine for item in run.effective.engine_results) == (
        "native",
        "souffle",
        "problog",
    )

    with pytest.raises(ProtocolShapeError, match="engines do not match profile"):
        EvaluationExecutionProfileV1(
            "portable_deterministic_v1",
            _token("5"),
            None,
            (EvaluationEnginePinV1("native", "0.3", "native-v1"),),
        )
    with pytest.raises(ProtocolShapeError, match="does not permit engine configuration"):
        EvaluationExecutionProfileV1(
            "portable_deterministic_v1",
            _token("5"),
            _token("7"),
            profile.engines,
        )
    with pytest.raises(ProtocolShapeError, match="does not permit engine configuration"):
        EvaluationExecutionProfileV1(
            "native_deterministic_v1",
            _token("5"),
            _token("7"),
            (EvaluationEnginePinV1("native", "0.3", "native-v1"),),
        )


def test_per_engine_frames_preserve_unsupported_and_failed_without_fake_result() -> None:
    profile = _profile(portable=True)
    plan = _plan(profile)
    payload = _payload(profile, plan)
    baseline = _side(
        name="baseline",
        world=payload.world("baseline"),
        plan=plan,
        profile=profile,
        age=35,
    )
    effective = _side(
        name="effective",
        world=payload.world("effective"),
        plan=plan,
        profile=profile,
        age=22,
    )
    unsupported_frame = EvaluationEngineResultV1(
        "problog",
        None,
        "unsupported",
        "PORTABLE_PROFILE_UNSUPPORTED",
    )
    assert unsupported_frame.semantic_row_set_digest is None
    unsupported_effective = replace(
        effective,
        engine_results=(
            effective.engine_results[0],
            effective.engine_results[1],
            unsupported_frame,
        ),
        assessment=replace(effective.assessment, parity="unsupported"),
    )
    run = EvaluationRunV1(plan, profile, payload, baseline, unsupported_effective)
    assert run.effective.engine_results[-1].status == "unsupported"

    failed_frame = EvaluationEngineResultV1("problog", None, "failed", "PROBLOG_ADAPTER_FAILURE")
    failed_effective = replace(
        effective,
        engine_results=(
            effective.engine_results[0],
            effective.engine_results[1],
            failed_frame,
        ),
        assessment=replace(effective.assessment, parity="unresolved"),
    )
    run = EvaluationRunV1(plan, profile, payload, baseline, failed_effective)
    assert run.effective.engine_results[-1].status == "failed"

    with pytest.raises(ProtocolShapeError, match="must not carry a result"):
        EvaluationEngineResultV1(
            "problog",
            effective.canonical_result,
            "unsupported",
            "PORTABLE_PROFILE_UNSUPPORTED",
        )
    with pytest.raises(ProtocolShapeError, match="requires a failure diagnostic"):
        EvaluationEngineResultV1("problog", None, "failed")
    with pytest.raises(ProtocolShapeError, match="requires unsupported parity"):
        EvaluationRunV1(
            plan,
            profile,
            payload,
            baseline,
            replace(
                unsupported_effective, assessment=replace(effective.assessment, parity="equivalent")
            ),
        )


def test_portable_successful_row_set_difference_is_explicit_not_silently_canonicalized() -> None:
    profile = _profile(portable=True)
    plan = _plan(profile)
    payload = _payload(profile, plan)
    baseline = _side(
        name="baseline",
        world=payload.world("baseline"),
        plan=plan,
        profile=profile,
        age=35,
    )
    effective = _side(
        name="effective",
        world=payload.world("effective"),
        plan=plan,
        profile=profile,
        age=22,
    )
    divergent = _result(plan, age=99)
    observed = replace(
        effective,
        engine_results=(
            EvaluationEngineResultV1("native", effective.canonical_result),
            EvaluationEngineResultV1("souffle", divergent),
            EvaluationEngineResultV1("problog", effective.canonical_result),
        ),
        assessment=replace(effective.assessment, parity="different"),
    )
    run = EvaluationRunV1(plan, profile, payload, baseline, observed)
    assert run.effective.assessment.parity == "different"
    with pytest.raises(ProtocolShapeError, match="parity does not match"):
        EvaluationRunV1(
            plan,
            profile,
            payload,
            baseline,
            replace(observed, assessment=replace(observed.assessment, parity="equivalent")),
        )


def test_candidate_comparison_requires_independent_target_same_projection_and_effective_world() -> (
    None
):
    profile = _profile()
    plan = _plan(profile, target="a", candidate_target="b")
    candidate = _plan(profile, target="b")
    payload = _payload(profile, plan, candidate)
    baseline = _side(
        name="baseline",
        world=payload.world("baseline"),
        plan=plan,
        profile=profile,
        age=35,
    )
    effective = _side(
        name="effective",
        world=payload.world("effective"),
        plan=plan,
        profile=profile,
        age=22,
    )
    candidate_effective = _side(
        name="candidate_effective",
        world=payload.world("effective"),
        plan=candidate,
        profile=profile,
        age=22,
    )
    run = EvaluationRunV1(
        plan,
        profile,
        payload,
        baseline,
        effective,
        candidate,
        candidate_effective,
    )
    assert run.candidate_effective is candidate_effective

    with pytest.raises(ProtocolShapeError, match="present together"):
        EvaluationRunV1(plan, profile, payload, baseline, effective, candidate_plan=candidate)
    with pytest.raises(ProtocolShapeError, match="does not match the primary candidate pin"):
        EvaluationRunV1(
            plan,
            profile,
            payload,
            baseline,
            effective,
            plan,
            candidate_effective,
        )

    bad_envelope = replace(
        payload.program_envelope,
        candidate_target_digest=_token("9"),
    )
    bad_payload = replace(payload, compiled_program_bytes=bad_envelope.to_bytes())
    bad_baseline = _side(
        name="baseline",
        world=bad_payload.world("baseline"),
        plan=plan,
        profile=profile,
        age=35,
    )
    bad_effective = _side(
        name="effective",
        world=bad_payload.world("effective"),
        plan=plan,
        profile=profile,
        age=22,
    )
    bad_candidate_effective = _side(
        name="candidate_effective",
        world=bad_payload.world("effective"),
        plan=candidate,
        profile=profile,
        age=22,
    )
    with pytest.raises(ProtocolShapeError, match="candidate target does not match plan"):
        EvaluationRunV1(
            plan,
            profile,
            bad_payload,
            bad_baseline,
            bad_effective,
            candidate,
            bad_candidate_effective,
        )


def test_engine_result_and_run_side_reject_cross_plan_and_result_splicing() -> None:
    profile = _profile()
    plan = _plan(profile, target="a")
    other = _plan(profile, target="b")
    payload = _payload(profile, plan)
    result = _result(plan)
    other_result = _result(other)
    assessment = GoalTechnicalAssessmentV1(
        plan.plan_digest,
        result.result_digest,
        "resolved",
        "succeeded",
        "not_requested",
        "complete",
        "not_requested",
        "available",
        "available",
    )
    with pytest.raises(ProtocolShapeError, match="does not match canonical"):
        EvaluationRunSideV1(
            "baseline",
            plan.plan_digest,
            "baseline",
            payload.world("baseline").world_capture_digest,
            result,
            (EvaluationEngineResultV1("native", other_result),),
            assessment,
        )


def test_run_side_preserves_mapping_selection_shape_and_result_assessment_completeness() -> None:
    profile = _profile()
    plan = GoalPlanV1(
        GoalTargetRefV1("policy", "policy.nonalpha", "1", _token("8")),
        _token("6"),
        "rows",
        (GoalSelectionV1("z_age", "int"), GoalSelectionV1("a_age", "int")),
        execution_profile_digest=profile.profile_digest,
    )
    payload = _payload(profile, plan)
    result = GoalResultV1(
        plan.plan_digest,
        "rows",
        "resource_limited",
        (GoalResultRowV1((("z_age", GoalValueV1("int", 35)), ("a_age", GoalValueV1("int", 22)))),),
    )
    assessment = GoalTechnicalAssessmentV1(
        plan.plan_digest,
        result.result_digest,
        "not_requested",
        "succeeded",
        "not_requested",
        "resource_limited",
        "not_requested",
        "available",
        "available",
    )
    side = EvaluationRunSideV1(
        "baseline",
        plan.plan_digest,
        "baseline",
        payload.world("baseline").world_capture_digest,
        result,
        (EvaluationEngineResultV1("native", result),),
        assessment,
    )
    # GoalResult normalizes aliases alphabetically, while Query preserves the
    # caller's select order.  V1 compares typed mappings, not tuple position.
    assert tuple(alias for alias, _ in side.canonical_result.rows[0].values) == (
        "a_age",
        "z_age",
    )
    bad_assessment = replace(assessment, completeness="incomplete")
    with pytest.raises(ProtocolShapeError, match="assessment does not match completed result"):
        EvaluationRunSideV1(
            "baseline",
            plan.plan_digest,
            "baseline",
            payload.world("baseline").world_capture_digest,
            result,
            (EvaluationEngineResultV1("native", result),),
            bad_assessment,
        )

    effective = replace(
        side,
        name="effective",
        world_side="effective",
        world_capture_digest=payload.world("effective").world_capture_digest,
    )
    run = EvaluationRunV1(plan, profile, payload, side, effective)
    assert run.effective.canonical_result.result_digest == result.result_digest
