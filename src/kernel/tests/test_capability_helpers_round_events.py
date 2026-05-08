"""Tests for round event capability helper builders."""

from __future__ import annotations

import unittest

from kernel.application import (
    CapabilityHelperError,
    OriginPackageError,
    build_round_event_payload,
)
from kernel.application.protocol import (
    CheckRequest,
    CheckResult,
    CompiledDerivationPlan,
    CompiledHeadCall,
    DiagnoseRequest,
    DiagnoseResult,
    EvaluationOverlay,
    FactOverlayCheckRequest,
    FactOverlayCheckResult,
    FactValueOverride,
    OverlayCheckDiff,
    OverlayCheckPhase,
    ProofFrameAtomVerdict,
    ProofFrameRecheckRequest,
    ProofFrameRecheckResult,
    WhyNotUniverseRequest,
    WhyNotUniverseResult,
)
from kernel.audit.round_events import (
    project_check_event_payload,
    project_diagnose_event_payload,
    project_fact_overlay_event_payload,
    project_proof_frame_event_payload,
    project_why_not_event_payload,
)
from kernel.core.store._support import PredWitness, SupportArtifact, normalize_binding_items
from kernel.sdk import Pred, Rule, vars as sdk_vars


def _binding() -> tuple[tuple[str, object], ...]:
    return normalize_binding_items((("$p", "person:alice"),))


def _plan() -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="helper.round_event",
        version="1.0",
        body_ir=[("pred", "Person:exists", ["$p"])],
        heads=(CompiledHeadCall(target_pred_id="Person:eligible", head_var_names=("$p",)),),
    )


def _overlay() -> EvaluationOverlay:
    return EvaluationOverlay(
        fact_actions=(
            FactValueOverride(
                asrt_id="a1",
                pred_id="Person:age",
                e_ref="person:alice",
                old_fact_tuple=("person:alice", 25),
                new_fact_tuple=("person:alice", 26),
            ),
        )
    )


def _support() -> SupportArtifact:
    return SupportArtifact(
        kind="native_binding_v1",
        root_result_kind="row",
        binding_items=_binding(),
        pred_witnesses=(
            PredWitness(pred_atom_key="b0.a0:Person:exists", asrt_ids=("a1",)),
        ),
    )


def _sdk_rule() -> Rule:
    with sdk_vars("p", "age") as (p, age):
        return Rule(
            id="helper.sdk_rule",
            version="1.0",
            select=[Pred("person:eligible", p)],
            where=[Pred("person:age", p, age)],
        )


def _check_pair() -> tuple[CheckRequest, CheckResult]:
    binding = _binding()
    request = CheckRequest(plan=_plan(), binding=binding, engine="native")
    result = CheckResult(
        status="failed",
        requested_binding=binding,
        matched_count=0,
        matched_binding=None,
        evidence_envelope=None,
    )
    return request, result


def _diagnose_pair() -> tuple[DiagnoseRequest, DiagnoseResult]:
    binding = _binding()
    request = DiagnoseRequest(plan=_plan(), binding=binding, engine="native")
    result = DiagnoseResult(
        status="failed",
        requested_binding=binding,
        matched_count=0,
        matched_binding=None,
        failure_kind="no_candidate",
        diagnostic_payload=None,
    )
    return request, result


def _fact_overlay_pair() -> tuple[FactOverlayCheckRequest, FactOverlayCheckResult]:
    binding = _binding()
    request = FactOverlayCheckRequest(
        plan=_plan(),
        binding=binding,
        overlay=_overlay(),
        engine="native",
    )
    result = FactOverlayCheckResult(
        status="passed",
        requested_binding=binding,
        before=OverlayCheckPhase(
            status="passed",
            matched_count=1,
            matched_binding=binding,
        ),
        after=OverlayCheckPhase(
            status="passed",
            matched_count=1,
            matched_binding=binding,
        ),
        diff=OverlayCheckDiff(
            status_changed=False,
            matched_count_delta=0,
            bindings_added=(),
            bindings_removed=(),
        ),
    )
    return request, result


def _why_not_pair() -> tuple[WhyNotUniverseRequest, WhyNotUniverseResult]:
    binding = _binding()
    request = WhyNotUniverseRequest(
        plan=_plan(),
        candidate_universe=(binding,),
        engine="native",
    )
    result = WhyNotUniverseResult(
        status="completed",
        requested_universe=(binding,),
        green=(binding,),
        red=(),
    )
    return request, result


def _proof_frame_pair() -> tuple[ProofFrameRecheckRequest, ProofFrameRecheckResult]:
    binding = _binding()
    request = ProofFrameRecheckRequest(support_artifact=_support(), overlay=_overlay())
    result = ProofFrameRecheckResult(
        status="invalidated",
        binding_items=binding,
        atom_verdicts=(
            ProofFrameAtomVerdict(
                atom_key="b0.a0:Person:exists",
                verdict="invalidated",
                affected_action_indices=(0,),
            ),
        ),
    )
    return request, result


def _cases() -> dict[str, tuple[object, object, object]]:
    return {
        "check_result": (*_check_pair(), project_check_event_payload),
        "diagnose_result": (*_diagnose_pair(), project_diagnose_event_payload),
        "fact_overlay_result": (*_fact_overlay_pair(), project_fact_overlay_event_payload),
        "why_not_result": (*_why_not_pair(), project_why_not_event_payload),
        "proof_frame_result": (*_proof_frame_pair(), project_proof_frame_event_payload),
    }


class BuildRoundEventPayloadTests(unittest.TestCase):
    def test_builds_payloads_matching_existing_projectors(self) -> None:
        for kind, (request, result, projector) in _cases().items():
            with self.subTest(kind=kind):
                self.assertEqual(
                    build_round_event_payload(
                        kind=kind,
                        request=request,
                        result=result,
                    ),
                    projector(request, result),
                )

    def test_rejects_unknown_and_lifecycle_kinds(self) -> None:
        request, result = _check_pair()
        for kind in (
            "unknown_result",
            "round_started",
            "round_finalized",
        ):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(CapabilityHelperError, "unknown kind"):
                    build_round_event_payload(kind=kind, request=request, result=result)

    def test_rejects_rule_overlay_kinds_not_supported_by_round_projectors(self) -> None:
        request, result = _check_pair()
        for kind in (
            "rule_disable",
            "rule_literal_replace",
            "rule_add_condition",
            "rule_disable_result",
            "rule_literal_replace_result",
            "rule_add_condition_result",
        ):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(CapabilityHelperError, "unknown kind"):
                    build_round_event_payload(kind=kind, request=request, result=result)

    def test_rejects_non_string_kind(self) -> None:
        request, result = _check_pair()

        with self.assertRaisesRegex(CapabilityHelperError, "kind"):
            build_round_event_payload(kind=object(), request=request, result=result)  # type: ignore[arg-type]

    def test_rejects_mismatched_request_type_for_each_kind(self) -> None:
        for kind, (_, result, _) in _cases().items():
            wrong_request = _diagnose_pair()[0] if kind == "check_result" else _check_pair()[0]
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(CapabilityHelperError, "expects request"):
                    build_round_event_payload(
                        kind=kind,
                        request=wrong_request,
                        result=result,
                    )

    def test_rejects_mismatched_result_type_for_each_kind(self) -> None:
        for kind, (request, _, _) in _cases().items():
            wrong_result = _diagnose_pair()[1] if kind == "check_result" else _check_pair()[1]
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(CapabilityHelperError, "expects result"):
                    build_round_event_payload(
                        kind=kind,
                        request=request,
                        result=wrong_result,
                    )

    def test_sdk_origin_request_raises_origin_package_error(self) -> None:
        result = _check_pair()[1]

        with self.assertRaises(OriginPackageError):
            build_round_event_payload(
                kind="check_result",
                request=_sdk_rule(),
                result=result,
            )

    def test_sdk_origin_result_raises_origin_package_error(self) -> None:
        request = _check_pair()[0]

        with self.assertRaises(OriginPackageError):
            build_round_event_payload(
                kind="check_result",
                request=request,
                result=_sdk_rule(),
            )

    def test_phase_5_exports_from_application_and_helper_package(self) -> None:
        from kernel import application
        from kernel.application import capability_helpers

        self.assertIs(application.build_round_event_payload, build_round_event_payload)
        self.assertIs(capability_helpers.build_round_event_payload, build_round_event_payload)


if __name__ == "__main__":
    unittest.main()
