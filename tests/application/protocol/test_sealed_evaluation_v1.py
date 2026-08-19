"""Adversarial tests for the neutral sealed-evaluation request boundary."""

from __future__ import annotations

import base64
import json
from dataclasses import replace
from hashlib import sha256

import pytest

from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_v1 import (
    EvaluationEnginePinV1,
    EvaluationExecutionProfileV1,
    EvaluationReplayFactV1,
    EvaluationReplayProgramEnvelopeV1,
    EvaluationReplayRelationV1,
    EvaluationReplayWorldV1,
)
from factgraph.application.protocol.goal_plan_v1 import (
    ContainsRowExpectationV1,
    CountEqExpectationV1,
    ExactLocalAbsenceExpectationV1,
    ExistsExpectationV1,
    GoalPlanV1,
    GoalRowExpectationV1,
    GoalSelectionV1,
    GoalTargetRefV1,
    GoalValueV1,
    SetEqualsExpectationV1,
)
from factgraph.application.protocol.relation_provider_v1 import (
    ProviderMaterializationV1,
    ProviderRelationRowV1,
    ProviderRequestV1,
)
from factgraph.application.protocol.scenario_v1 import (
    ExactLocalClosureTargetV1,
    ScenarioSpecV1,
    ScenarioWithoutRelationV1,
)
from factgraph.application.protocol.sealed_evaluation_scenario_v1 import (
    scenario_spec_v1_bytes,
)
from factgraph.application.protocol.sealed_evaluation_v1 import (
    MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1,
    MAX_SEALED_EVALUATION_REQUEST_BYTES_V1,
    SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    DecodedSealedEvaluationRequestV1,
    EvaluationAssetBundleV1,
    EvaluationAssetPinV1,
    EvaluationCaptureProfileV1,
    EvaluationProviderCaptureV1,
    EvaluationSchemaCaptureV1,
    SealedEvaluationRequestV1,
    decode_sealed_evaluation_request_v1,
    evaluation_execution_profile_v1_bytes,
    evaluation_execution_profile_v1_from_bytes,
    evaluation_provider_capture_v1_bytes,
    evaluation_provider_capture_v1_from_bytes,
    evaluation_replay_world_v1_bytes,
    evaluation_replay_world_v1_from_bytes,
    evaluation_schema_capture_v1_bytes,
    evaluation_schema_capture_v1_from_bytes,
    goal_plan_v1_bytes,
    goal_plan_v1_from_bytes,
    sealed_evaluation_request_v1_bytes,
    sealed_evaluation_request_v1_from_bytes,
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


def _schema_ir() -> dict[str, object]:
    return {
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
                "group_key_indexes": [0],
                "pred_id": "Person.age",
            }
        ],
        "projection": {"entities": ["Person"], "predicates": ["Person.age"]},
        "protocol_version": {
            "export_v1": "1",
            "idref_v1": "1",
            "tup_v1": "1",
        },
        "schema_ir_version": "1",
    }


def _schema_ir_for_predicates(count: int, *, arity: int = 1) -> dict[str, object]:
    schema = _schema_ir()
    schema["predicates"] = [
        {
            "arg_specs": [{"name": f"value_{cell}", "type_domain": "int"} for cell in range(arity)],
            "group_key_indexes": [],
            "pred_id": f"Person.value_{index}",
        }
        for index in range(count)
    ]
    schema["projection"] = {
        "entities": ["Person"],
        "predicates": [f"Person.value_{index}" for index in range(count)],
    }
    return schema


def _profile(*, portable: bool = False) -> EvaluationExecutionProfileV1:
    engines = (
        EvaluationEnginePinV1("native", "0.3", "native-v1"),
        EvaluationEnginePinV1("souffle", "2.5", "souffle-v1"),
        EvaluationEnginePinV1("problog", "2.2", "problog-v1"),
    )
    return EvaluationExecutionProfileV1(
        "portable_deterministic_v1" if portable else "native_deterministic_v1",
        _token("c"),
        None,
        engines if portable else engines[:1],
    )


def _plan(
    profile: EvaluationExecutionProfileV1,
    *,
    kind: str = "policy",
    scenario_digest: str | None = None,
    candidate: bool = False,
    expectations: tuple[object, ...] = (),
) -> GoalPlanV1:
    return GoalPlanV1(
        target=GoalTargetRefV1(kind, "policy.main", "1", _token("a")),  # type: ignore[arg-type]
        query_digest=_token("b"),
        result_mode="rows",
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


def _world(*, side: str = "baseline", empty: bool = False) -> EvaluationReplayWorldV1:
    relations: tuple[EvaluationReplayRelationV1, ...] = ()
    if not empty:
        relations = (
            EvaluationReplayRelationV1(
                "Person.age",
                ("entity_ref", "int"),
                (
                    EvaluationReplayFactV1(
                        "witness:alice",
                        (
                            GoalValueV1("entity_ref", "idref_v1:Person:alice"),
                            GoalValueV1("int", 30),
                        ),
                    ),
                ),
            ),
        )
    return EvaluationReplayWorldV1(
        side,  # type: ignore[arg-type]
        _token("1"),
        _token("2"),
        (),
        relations,
    )


def _request(
    *,
    plan: GoalPlanV1 | None = None,
    profile: EvaluationExecutionProfileV1 | None = None,
    schema: EvaluationSchemaCaptureV1 | None = None,
    world: EvaluationReplayWorldV1 | None = None,
    scenario: ScenarioSpecV1 | None = None,
    provider: EvaluationProviderCaptureV1 | None = None,
    comparison: str = "not_requested",
) -> SealedEvaluationRequestV1:
    profile = _profile() if profile is None else profile
    scenario_digest = None if scenario is None else scenario.spec_digest
    plan = _plan(profile, scenario_digest=scenario_digest) if plan is None else plan
    schema = (
        EvaluationSchemaCaptureV1(canonicalize_schema_ir_jcs(_schema_ir()))
        if schema is None
        else schema
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
        dependencies=(),
        query_digest=plan.query_digest,
        schema_digest=schema.schema_digest,
        address_space_digest=_token("3"),
        compiler_digest=profile.compiler_digest,
        execution_profile_digest=profile.profile_digest,
        runtime_digest=SEALED_EVALUATION_RUNTIME_DIGEST_V1,
    )
    candidate_plan = None
    if plan.candidate_target is not None:
        candidate_plan = GoalPlanV1(
            target=plan.candidate_target,
            query_digest=plan.candidate_query_digest or "",
            result_mode=plan.result_mode,
            selections=plan.selections,
            scenario_request_digest=plan.scenario_request_digest,
            evidence_scope_digest=plan.evidence_scope_digest,
            execution_profile_digest=plan.execution_profile_digest,
        )
    program = EvaluationReplayProgramEnvelopeV1(
        schema_digest=schema.schema_digest,
        address_space_digest=bundle.address_space_digest,
        plan_digest=plan.plan_digest,
        query_digest=plan.query_digest,
        target_digest=plan.target.target_digest,
        execution_profile_digest=profile.profile_digest,
        compiler_digest=profile.compiler_digest,
        compiled_program={"$type": "CompiledDerivationPlanV1", "body": []},
        candidate_plan_digest=None if candidate_plan is None else candidate_plan.plan_digest,
        candidate_query_digest=None if candidate_plan is None else candidate_plan.query_digest,
        candidate_target_digest=(
            None if candidate_plan is None else candidate_plan.target.target_digest
        ),
    )
    return SealedEvaluationRequestV1(
        asset_bundle=bundle,
        goal_plan_bytes=goal_plan_v1_bytes(plan),
        execution_profile_bytes=evaluation_execution_profile_v1_bytes(profile),
        schema_bytes=evaluation_schema_capture_v1_bytes(schema),
        program_envelope_bytes=program.to_bytes(),
        baseline_world_bytes=evaluation_replay_world_v1_bytes(_world() if world is None else world),
        scenario_bytes=None if scenario is None else scenario_spec_v1_bytes(scenario),
        provider_capture_bytes=(
            None if provider is None else evaluation_provider_capture_v1_bytes(provider)
        ),
        capture=EvaluationCaptureProfileV1(4096, "not_captured", comparison),
    )


def _outer_wire(request: SealedEvaluationRequestV1) -> dict[str, object]:
    return json.loads(sealed_evaluation_request_v1_bytes(request))


def _component(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def test_valid_request_and_every_named_component_round_trip_canonically() -> None:
    request = _request()
    raw = sealed_evaluation_request_v1_bytes(request)
    rebuilt = sealed_evaluation_request_v1_from_bytes(raw)
    decoded = decode_sealed_evaluation_request_v1(rebuilt)

    assert isinstance(decoded, DecodedSealedEvaluationRequestV1)
    assert sealed_evaluation_request_v1_bytes(rebuilt) == raw
    assert (
        goal_plan_v1_bytes(goal_plan_v1_from_bytes(request.goal_plan_bytes))
        == request.goal_plan_bytes
    )
    assert (
        evaluation_execution_profile_v1_bytes(
            evaluation_execution_profile_v1_from_bytes(request.execution_profile_bytes)
        )
        == request.execution_profile_bytes
    )
    assert (
        evaluation_schema_capture_v1_bytes(
            evaluation_schema_capture_v1_from_bytes(request.schema_bytes)
        )
        == request.schema_bytes
    )
    assert (
        evaluation_replay_world_v1_bytes(
            evaluation_replay_world_v1_from_bytes(request.baseline_world_bytes)
        )
        == request.baseline_world_bytes
    )


def test_goal_plan_codec_round_trips_all_five_expectation_arms() -> None:
    profile = _profile()
    expected_row = GoalRowExpectationV1((("age", GoalValueV1("int", 30)),))
    closure = ExactLocalClosureTargetV1("relation", None, "Person.age")
    expectations = (
        ContainsRowExpectationV1("contains", expected_row),
        ExactLocalAbsenceExpectationV1("absence", closure),
        ExistsExpectationV1("exists", True),
        CountEqExpectationV1("count", 1),
        SetEqualsExpectationV1("set", (expected_row,)),
    )
    plan = _plan(profile, scenario_digest=_token("9"), expectations=expectations)
    raw = goal_plan_v1_bytes(plan)

    assert goal_plan_v1_from_bytes(raw) == plan
    assert goal_plan_v1_bytes(goal_plan_v1_from_bytes(raw)) == raw


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.pop("goal_plan_bytes_b64u"),
        lambda row: row.__setitem__("unknown", 1),
        lambda row: row.__setitem__("asset_bundle", None),
        lambda row: row.__setitem__("$type", "FactGraphSealedEvaluationRequestV2"),
    ],
)
def test_envelope_rejects_missing_unknown_null_and_wrong_type(mutation) -> None:
    row = _outer_wire(_request())
    mutation(row)
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_request_v1_from_bytes(_canonical(row))


def test_envelope_rejects_duplicate_keys_noncanonical_json_float_and_invalid_utf8() -> None:
    raw = sealed_evaluation_request_v1_bytes(_request())
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_request_v1_from_bytes(raw[:-1] + b',"$type":"duplicate"}')
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_request_v1_from_bytes(raw + b" ")
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_request_v1_from_bytes(b'{"$type":1.0}')
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_request_v1_from_bytes(b'{"$type":"\xff"}')


def test_envelope_rejects_padded_and_noncanonical_base64_before_digest() -> None:
    row = _outer_wire(_request())
    row["goal_plan_bytes_b64u"] = str(row["goal_plan_bytes_b64u"]) + "="
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_request_v1_from_bytes(_canonical(row))
    row = _outer_wire(_request())
    row["goal_plan_bytes_b64u"] = "A"
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_request_v1_from_bytes(_canonical(row))


def test_component_and_request_byte_limits_fail_closed() -> None:
    with pytest.raises(ProtocolShapeError):
        goal_plan_v1_from_bytes(b"x" * (MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1 + 1))
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_request_v1_from_bytes(b"x" * (MAX_SEALED_EVALUATION_REQUEST_BYTES_V1 + 1))


def test_json_depth_above_sixty_four_fails_before_dto_construction() -> None:
    nested: object = "leaf"
    for _ in range(65):
        nested = [nested]
    with pytest.raises(ProtocolShapeError, match="depth"):
        sealed_evaluation_request_v1_from_bytes(_canonical({"nested": nested}))


def test_goal_plan_selection_expectation_row_and_set_bounds() -> None:
    profile = _profile()
    selections = tuple(GoalSelectionV1(f"value_{index}", "int") for index in range(128))
    full_row = GoalRowExpectationV1(
        tuple(
            (selection.alias, GoalValueV1("int", index))
            for index, selection in enumerate(selections)
        )
    )
    plan_at_selection_and_value_limit = GoalPlanV1(
        target=GoalTargetRefV1("policy", "policy.main", "1", _token("a")),
        query_digest=_token("b"),
        result_mode="rows",
        selections=selections,
        evidence_scope_digest=_token("f"),
        execution_profile_digest=profile.profile_digest,
        expectations=(ContainsRowExpectationV1("contains", full_row),),
    )
    raw = goal_plan_v1_bytes(plan_at_selection_and_value_limit)
    assert goal_plan_v1_from_bytes(raw) == plan_at_selection_and_value_limit

    over_selection_limit = replace(
        plan_at_selection_and_value_limit,
        selections=selections + (GoalSelectionV1("value_128", "int"),),
    )
    with pytest.raises(ProtocolShapeError, match="selections"):
        goal_plan_v1_bytes(over_selection_limit)

    row = json.loads(raw)
    row["expectations"][0]["row"]["values"].append(
        {
            "alias": "value_128",
            "value": {
                "tag": "int",
                "value": 128,
                "value_digest": GoalValueV1("int", 128).value_digest,
            },
        }
    )
    with pytest.raises(ProtocolShapeError, match="empty or exceeds"):
        goal_plan_v1_from_bytes(_canonical(row))

    expectations = tuple(ExistsExpectationV1(f"exists_{index}", True) for index in range(128))
    plan_at_expectation_limit = _plan(profile, expectations=expectations)
    assert (
        goal_plan_v1_from_bytes(goal_plan_v1_bytes(plan_at_expectation_limit))
        == plan_at_expectation_limit
    )
    with pytest.raises(ProtocolShapeError, match="expectations"):
        goal_plan_v1_bytes(
            replace(
                plan_at_expectation_limit,
                expectations=expectations + (ExistsExpectationV1("exists_128", True),),
            )
        )

    set_rows = tuple(
        GoalRowExpectationV1((("age", GoalValueV1("int", index)),)) for index in range(1024)
    )
    plan_at_set_limit = _plan(
        profile,
        expectations=(SetEqualsExpectationV1("set", set_rows),),
    )
    assert goal_plan_v1_from_bytes(goal_plan_v1_bytes(plan_at_set_limit)) == plan_at_set_limit
    with pytest.raises(ProtocolShapeError, match="row limit"):
        goal_plan_v1_bytes(
            replace(
                plan_at_set_limit,
                expectations=(
                    SetEqualsExpectationV1(
                        "set",
                        set_rows + (GoalRowExpectationV1((("age", GoalValueV1("int", 1024)),)),),
                    ),
                ),
            )
        )


def test_world_codec_rejects_effective_and_empty_world_at_request_cross_pin_gate() -> None:
    with pytest.raises(ProtocolShapeError, match="baseline"):
        decode_sealed_evaluation_request_v1(_request(world=_world(side="effective")))
    with pytest.raises(ProtocolShapeError, match="dependency inventory"):
        decode_sealed_evaluation_request_v1(_request(world=_world(empty=True)))


def test_world_codec_rejects_duplicate_witness_identity_across_relations() -> None:
    first = _world().relations[0]
    duplicate = EvaluationReplayRelationV1(
        "Person.other",
        first.value_tags,
        first.facts,
    )
    world = EvaluationReplayWorldV1("baseline", _token("1"), _token("2"), (), (first, duplicate))
    schema_ir = _schema_ir()
    schema_ir["predicates"].append(
        {
            "arg_specs": [
                {"name": "person", "type_domain": "entity_ref"},
                {"name": "age", "type_domain": "int"},
            ],
            "group_key_indexes": [0],
            "pred_id": "Person.other",
        }
    )
    schema_ir["projection"]["predicates"].append("Person.other")
    schema = EvaluationSchemaCaptureV1(canonicalize_schema_ir_jcs(schema_ir))
    with pytest.raises(ProtocolShapeError, match="globally unique"):
        decode_sealed_evaluation_request_v1(_request(world=world, schema=schema))


def test_world_relation_and_value_bounds_are_exact() -> None:
    relations = tuple(
        EvaluationReplayRelationV1(f"Person.value_{index}", ("int",), ()) for index in range(256)
    )
    schema = EvaluationSchemaCaptureV1(canonicalize_schema_ir_jcs(_schema_ir_for_predicates(256)))
    world = EvaluationReplayWorldV1("baseline", _token("1"), _token("2"), (), relations)
    request = _request(world=world, schema=schema)
    assert len(decode_sealed_evaluation_request_v1(request).baseline_world.relations) == 256
    with pytest.raises(ProtocolShapeError):
        EvaluationReplayWorldV1(
            "baseline",
            _token("1"),
            _token("2"),
            (),
            relations + (EvaluationReplayRelationV1("Person.value_256", ("int",), ()),),
        )

    values = tuple(GoalValueV1("int", index) for index in range(64))
    fact = EvaluationReplayFactV1("witness:wide", values)
    wide_relation = EvaluationReplayRelationV1(
        "Person.value_0",
        tuple("int" for _ in range(64)),
        (fact,),
    )
    wide_schema = EvaluationSchemaCaptureV1(
        canonicalize_schema_ir_jcs(_schema_ir_for_predicates(1, arity=64))
    )
    wide_world = EvaluationReplayWorldV1("baseline", _token("1"), _token("2"), (), (wide_relation,))
    assert (
        decode_sealed_evaluation_request_v1(_request(world=wide_world, schema=wide_schema))
        .baseline_world.relations[0]
        .facts[0]
        .values
        == values
    )
    with pytest.raises(ProtocolShapeError):
        EvaluationReplayFactV1("witness:too-wide", values + (GoalValueV1("int", 64),))


def test_asset_dependency_bound_and_canonical_order() -> None:
    request = _request()
    dependencies = tuple(
        EvaluationAssetPinV1("function", f"function.{index}", "1", _named_token(str(index)))
        for index in range(512)
    )
    bounded = replace(
        request,
        asset_bundle=replace(request.asset_bundle, dependencies=tuple(reversed(dependencies))),
    )
    rebuilt = sealed_evaluation_request_v1_from_bytes(sealed_evaluation_request_v1_bytes(bounded))
    assert tuple(item.pin_digest for item in rebuilt.asset_bundle.dependencies) == tuple(
        sorted(item.pin_digest for item in dependencies)
    )
    with pytest.raises(ProtocolShapeError, match="over limit"):
        replace(
            request.asset_bundle,
            dependencies=dependencies
            + (EvaluationAssetPinV1("function", "function.512", "1", _named_token("512")),),
        )


def test_capture_profile_rejects_bool_limits_and_invalid_conditional_modes() -> None:
    with pytest.raises(ProtocolShapeError):
        EvaluationCaptureProfileV1(True, "not_captured", "not_requested")  # type: ignore[arg-type]
    with pytest.raises(ProtocolShapeError):
        EvaluationCaptureProfileV1(0, "not_captured", "not_requested")
    with pytest.raises(ProtocolShapeError, match="requires Scenario"):
        decode_sealed_evaluation_request_v1(_request(comparison="baseline_vs_effective"))
    with pytest.raises(ProtocolShapeError, match="requires a candidate"):
        decode_sealed_evaluation_request_v1(_request(comparison="published_candidate"))


def test_candidate_is_bound_by_ids_digests_and_capture_condition() -> None:
    profile = _profile()
    plan = _plan(profile, candidate=True)
    request = _request(plan=plan, profile=profile, comparison="published_candidate")
    decoded = decode_sealed_evaluation_request_v1(request)
    assert decoded.candidate_plan is not None
    assert decoded.candidate_plan.result_mode == decoded.goal_plan.result_mode
    assert decoded.candidate_plan.selections == decoded.goal_plan.selections

    bad_bundle = replace(
        request.asset_bundle,
        candidate_target=EvaluationAssetPinV1("policy", "wrong", "2", _token("d")),
    )
    with pytest.raises(ProtocolShapeError, match="Candidate"):
        decode_sealed_evaluation_request_v1(replace(request, asset_bundle=bad_bundle))


def test_scenario_presence_digest_and_comparison_bindings_are_exact() -> None:
    scenario = ScenarioSpecV1((ScenarioWithoutRelationV1("premise", "Person.age"),))
    request = _request(scenario=scenario, comparison="baseline_vs_effective")
    decoded = decode_sealed_evaluation_request_v1(request)
    assert decoded.scenario == scenario

    missing = replace(request, scenario_bytes=None)
    with pytest.raises(ProtocolShapeError, match="Scenario component presence"):
        decode_sealed_evaluation_request_v1(missing)


def _provider_capture(schema: EvaluationSchemaCaptureV1) -> EvaluationProviderCaptureV1:
    request = ProviderRequestV1(
        provider_digest=_token("7"),
        query_digest=_token("b"),
        schema_digest=schema.schema_digest,
        dependency_predicate_ids=("Person.age",),
        supplied_predicate_ids=("Person.age",),
        bindings=(),
    )
    materialization = ProviderMaterializationV1(
        provider_digest=request.provider_digest,
        request_digest=request.request_digest,
        receipt_ref="receipt:provider:1",
        receipt_digest=_token("8"),
        predicate_ids=request.supplied_predicate_ids,
        rows=(
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
    return EvaluationProviderCaptureV1(request, materialization)


def test_provider_capture_codec_roundtrip_and_rule_policy_presence_rejection() -> None:
    schema = EvaluationSchemaCaptureV1(canonicalize_schema_ir_jcs(_schema_ir()))
    provider = _provider_capture(schema)
    raw = evaluation_provider_capture_v1_bytes(provider)
    assert evaluation_provider_capture_v1_from_bytes(raw) == provider
    with pytest.raises(ProtocolShapeError, match="cannot carry"):
        decode_sealed_evaluation_request_v1(_request(schema=schema, provider=provider))


def test_relation_provider_requires_exact_dependency_and_capture_bindings() -> None:
    profile = _profile()
    schema = EvaluationSchemaCaptureV1(canonicalize_schema_ir_jcs(_schema_ir()))
    provider = _provider_capture(schema)
    plan = _plan(profile, kind="relation_provider")
    request = _request(plan=plan, profile=profile, schema=schema, provider=provider)
    dependency = EvaluationAssetPinV1(
        "provider",
        "provider.main",
        "1",
        provider.request.provider_digest,
    )
    request = replace(
        request,
        asset_bundle=replace(request.asset_bundle, dependencies=(dependency,)),
    )
    decoded = decode_sealed_evaluation_request_v1(request)
    assert decoded.provider_capture == provider

    with pytest.raises(ProtocolShapeError, match="one capture/dependency"):
        decode_sealed_evaluation_request_v1(
            replace(request, asset_bundle=replace(request.asset_bundle, dependencies=()))
        )


def test_cross_component_schema_profile_asset_and_program_splices_reject() -> None:
    request = _request()
    bad_schema = EvaluationSchemaCaptureV1(
        canonicalize_schema_ir_jcs({**_schema_ir(), "schema_ir_version": "2"})
    )
    with pytest.raises(ProtocolShapeError, match="pin mismatch"):
        decode_sealed_evaluation_request_v1(
            replace(request, schema_bytes=evaluation_schema_capture_v1_bytes(bad_schema))
        )

    other_profile = _profile(portable=True)
    with pytest.raises(ProtocolShapeError, match="profile pin"):
        decode_sealed_evaluation_request_v1(
            replace(
                request,
                execution_profile_bytes=evaluation_execution_profile_v1_bytes(other_profile),
            )
        )

    with pytest.raises(ProtocolShapeError, match="outer pin mismatch"):
        decode_sealed_evaluation_request_v1(
            replace(
                request,
                asset_bundle=replace(request.asset_bundle, query_digest=_token("9")),
            )
        )

    envelope = EvaluationReplayProgramEnvelopeV1.from_bytes(request.program_envelope_bytes)
    wrong_target_envelope = EvaluationReplayProgramEnvelopeV1(
        schema_digest=envelope.schema_digest,
        address_space_digest=envelope.address_space_digest,
        plan_digest=envelope.plan_digest,
        query_digest=envelope.query_digest,
        target_digest=_token("9"),
        execution_profile_digest=envelope.execution_profile_digest,
        compiler_digest=envelope.compiler_digest,
        compiled_program=envelope.compiled_program,
    )
    with pytest.raises(ProtocolShapeError, match="outer pin mismatch"):
        decode_sealed_evaluation_request_v1(
            replace(request, program_envelope_bytes=wrong_target_envelope.to_bytes())
        )


def test_stale_frozen_component_digests_and_wrong_concrete_types_reject() -> None:
    plan = goal_plan_v1_from_bytes(_request().goal_plan_bytes)
    object.__setattr__(plan, "query_digest", _token("9"))
    with pytest.raises(ProtocolShapeError, match="stale"):
        goal_plan_v1_bytes(plan)

    profile = _profile()
    object.__setattr__(profile.engines[0], "engine_version", "tampered")
    with pytest.raises(ProtocolShapeError, match="stale"):
        evaluation_execution_profile_v1_bytes(profile)

    with pytest.raises(ProtocolShapeError):
        goal_plan_v1_bytes({})  # type: ignore[arg-type]
    with pytest.raises(ProtocolShapeError):
        sealed_evaluation_request_v1_bytes({})  # type: ignore[arg-type]


def test_program_body_remains_opaque_until_after_all_outer_pins_validate() -> None:
    request = _request()
    envelope = EvaluationReplayProgramEnvelopeV1(
        schema_digest=request.asset_bundle.schema_digest,
        address_space_digest=request.asset_bundle.address_space_digest,
        plan_digest=goal_plan_v1_from_bytes(request.goal_plan_bytes).plan_digest,
        query_digest=request.asset_bundle.query_digest,
        target_digest=request.asset_bundle.primary_target.artifact_digest,
        execution_profile_digest=request.asset_bundle.execution_profile_digest,
        compiler_digest=request.asset_bundle.compiler_digest,
        compiled_program={"$type": "UnsupportedButCanonicalProgram", "payload": {"x": 1}},
    )
    decoded = decode_sealed_evaluation_request_v1(
        replace(request, program_envelope_bytes=envelope.to_bytes())
    )
    assert decoded.program_envelope.compiled_program["$type"] == "UnsupportedButCanonicalProgram"

    wrong_pin = EvaluationReplayProgramEnvelopeV1(
        schema_digest=request.asset_bundle.schema_digest,
        address_space_digest=request.asset_bundle.address_space_digest,
        plan_digest=goal_plan_v1_from_bytes(request.goal_plan_bytes).plan_digest,
        query_digest=request.asset_bundle.query_digest,
        target_digest=_token("9"),
        execution_profile_digest=request.asset_bundle.execution_profile_digest,
        compiler_digest=request.asset_bundle.compiler_digest,
        compiled_program={"$type": "HostileSemanticBody", "payload": {"unsupported": True}},
    )
    with pytest.raises(ProtocolShapeError, match="outer pin mismatch"):
        decode_sealed_evaluation_request_v1(
            replace(request, program_envelope_bytes=wrong_pin.to_bytes())
        )


def test_outer_component_bytes_are_not_mapping_or_live_object_fallbacks() -> None:
    request = _request()
    row = _outer_wire(request)
    assert _component(str(row["goal_plan_bytes_b64u"])) == request.goal_plan_bytes
    with pytest.raises(ProtocolShapeError):
        SealedEvaluationRequestV1(  # type: ignore[arg-type]
            asset_bundle=request.asset_bundle,
            goal_plan_bytes={},
            execution_profile_bytes=request.execution_profile_bytes,
            schema_bytes=request.schema_bytes,
            program_envelope_bytes=request.program_envelope_bytes,
            baseline_world_bytes=request.baseline_world_bytes,
            scenario_bytes=None,
            provider_capture_bytes=None,
            capture=request.capture,
        )
