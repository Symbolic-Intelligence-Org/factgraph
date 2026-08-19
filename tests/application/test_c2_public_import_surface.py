"""C2 public import surface for the neutral sealed evaluation vertical."""

from factgraph import application
from factgraph.application import protocol


def test_protocol_exports_sealed_request_and_result_contracts() -> None:
    expected = {
        "MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1",
        "MAX_SEALED_EVALUATION_JSON_DEPTH_V1",
        "MAX_SEALED_EVALUATION_REQUEST_BYTES_V1",
        "SEALED_EVALUATION_RUNTIME_DIGEST_V1",
        "DecodedSealedEvaluationRequestV1",
        "EvaluationAssetBundleV1",
        "EvaluationAssetPinV1",
        "EvaluationCaptureProfileV1",
        "EvaluationProviderCaptureV1",
        "EvaluationSchemaCaptureV1",
        "EvaluationWorldInputPinsV1",
        "SealedEvaluationRequestV1",
        "assert_sealed_evaluation_request_current_v1",
        "decode_sealed_evaluation_request_v1",
        "evaluation_execution_profile_v1_bytes",
        "evaluation_execution_profile_v1_from_bytes",
        "evaluation_provider_capture_v1_bytes",
        "evaluation_provider_capture_v1_from_bytes",
        "evaluation_replay_world_v1_bytes",
        "evaluation_replay_world_v1_from_bytes",
        "evaluation_schema_capture_v1_bytes",
        "evaluation_schema_capture_v1_from_bytes",
        "goal_plan_v1_bytes",
        "goal_plan_v1_from_bytes",
        "scenario_spec_v1_bytes",
        "scenario_spec_v1_from_bytes",
        "sealed_evaluation_request_v1_bytes",
        "sealed_evaluation_request_v1_from_bytes",
        "EvaluationComparisonV1",
        "EvaluationScenarioDiffV1",
        "SealedEvaluationResultV1",
        "MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1",
        "MAX_EVALUATION_SCENARIO_OPERATIONS_V1",
        "MAX_SEALED_EVALUATION_RESULT_BYTES_V1",
        "assert_sealed_evaluation_result_matches_request_v1",
        "evaluation_comparison_v1_bytes",
        "evaluation_comparison_v1_from_bytes",
        "evaluation_run_v1_bytes",
        "evaluation_run_v1_from_bytes",
        "evaluation_scenario_diff_v1_bytes",
        "evaluation_scenario_diff_v1_from_bytes",
        "sealed_evaluation_result_v1_bytes",
        "sealed_evaluation_result_v1_from_bytes",
    }
    assert expected <= set(protocol.__all__)
    for name in expected:
        assert hasattr(protocol, name)

    # Runtime-only comparison helpers are not promoted as protocol DTOs.
    assert not hasattr(protocol, "PolicyVariantComparisonV1")
    assert not hasattr(protocol, "ScenarioDiffV1")


def test_application_exports_only_the_two_c2_execution_seams() -> None:
    assert "evaluate_captured_goal_v1" in application.__all__
    assert "evaluate_sealed_evaluation_request_v1" in application.__all__
    assert callable(application.evaluate_captured_goal_v1)
    assert callable(application.evaluate_sealed_evaluation_request_v1)
