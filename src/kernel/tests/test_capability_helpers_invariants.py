"""Cross-cutting capability helper invariant tests for A Phase 6."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import unittest

import kernel.application as application
from kernel.application import capability_helpers
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
    RuleAddConditionRequest,
    RuleAddedAtom,
    RuleDisableRequest,
    RuleLiteralPath,
    RuleLiteralReplaceRequest,
    WhyNotUniverseRequest,
    WhyNotUniverseResult,
)
from kernel.core.rules.rule_ir import RuleSpec
from kernel.core.store._support import PredWitness, SupportArtifact, normalize_binding_items
from kernel.sdk import Pred, Rule, vars as sdk_vars


HELPER_EXPORTS = (
    "CapabilityHelperError",
    "OriginPackageError",
    # Batch 2 families (Q3/Q4/Q5) shipped before Gap beta origin enforcement.
    "build_fact_value_override",
    "build_fact_remove_action",
    "build_evaluation_overlay",
    "build_frontier_view_facts",
    "build_why_not_candidate_universe",
    # Phase 1-5 families shipped by this blueprint.
    "build_check_request",
    "build_diagnose_request",
    "build_proof_frame_recheck_request",
    "build_rule_disable_request",
    "build_rule_literal_replace_request",
    "build_rule_add_condition_request",
    "build_round_event_payload",
)

CAPABILITY_FAMILY_REPRESENTATIVES = {
    "Q1 Check": "build_check_request",
    "Q2 Diagnose": "build_diagnose_request",
    "Q3 Fact Overlay": "build_fact_value_override",
    "Q4 Why-not": "build_why_not_candidate_universe",
    "Q5 Frontier": "build_frontier_view_facts",
    "Batch 4 ProofFrame": "build_proof_frame_recheck_request",
    "Batch 5 Rule overlays": "build_rule_disable_request",
    "Batch 6 Round events": "build_round_event_payload",
}


def _binding() -> tuple[tuple[str, object], ...]:
    return normalize_binding_items((("$p", "person:alice"),))


def _plan(*, body_ir: list[object] | None = None) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="helper.invariant",
        version="1.0",
        body_ir=body_ir if body_ir is not None else [("pred", "Person:exists", ["$p"])],
        heads=(CompiledHeadCall(target_pred_id="Person:eligible", head_var_names=("$p",)),),
    )


def _sdk_rule() -> Rule:
    with sdk_vars("p") as (p,):
        return Rule(
            id="helper.sdk_rule",
            version="1.0",
            select=[Pred("person:eligible", p)],
            where=[Pred("person:exists", p)],
        )


def _support(
    *, binding_items: tuple[tuple[str, object], ...] | None = None
) -> SupportArtifact:
    return SupportArtifact(
        kind="native_binding_v1",
        root_result_kind="row",
        binding_items=binding_items if binding_items is not None else _binding(),
        pred_witnesses=(
            PredWitness(pred_atom_key="b0.a0:Person:exists", asrt_ids=("a1",)),
        ),
    )


def _overlay(*, new_value: object = 26) -> EvaluationOverlay:
    return EvaluationOverlay(
        fact_actions=(
            FactValueOverride(
                asrt_id="a1",
                pred_id="Person:age",
                e_ref="person:alice",
                old_fact_tuple=("person:alice", 25),
                new_fact_tuple=("person:alice", new_value),
            ),
        )
    )


def _rule_spec(*, where: list[object] | None = None) -> RuleSpec:
    return RuleSpec(
        rule_id="person.eligible",
        version="1.0",
        select_vars=["$p"],
        where=where if where is not None else [("pred", "Person:exists", ["$p"])],
    )


def _check_result() -> CheckResult:
    return CheckResult(
        status="failed",
        requested_binding=_binding(),
        matched_count=0,
        matched_binding=None,
        evidence_envelope=None,
    )


def _diagnose_result() -> DiagnoseResult:
    return DiagnoseResult(
        status="failed",
        requested_binding=_binding(),
        matched_count=0,
        matched_binding=None,
        failure_kind="no_candidate",
        diagnostic_payload=None,
    )


def _fact_overlay_result() -> FactOverlayCheckResult:
    binding = _binding()
    return FactOverlayCheckResult(
        status="passed",
        requested_binding=binding,
        before=OverlayCheckPhase(status="passed", matched_count=1, matched_binding=binding),
        after=OverlayCheckPhase(status="passed", matched_count=1, matched_binding=binding),
        diff=OverlayCheckDiff(
            status_changed=False,
            matched_count_delta=0,
            bindings_added=(),
            bindings_removed=(),
        ),
    )


def _why_not_result() -> WhyNotUniverseResult:
    binding = _binding()
    return WhyNotUniverseResult(
        status="completed",
        requested_universe=(binding,),
        green=(binding,),
        red=(),
    )


def _proof_frame_result() -> ProofFrameRecheckResult:
    return ProofFrameRecheckResult(
        status="invalidated",
        binding_items=_binding(),
        atom_verdicts=(
            ProofFrameAtomVerdict(
                atom_key="b0.a0:Person:exists",
                verdict="invalidated",
                affected_action_indices=(0,),
            ),
        ),
    )


def _builder_cases() -> tuple[tuple[str, Any, tuple[Any, ...], dict[str, Any]], ...]:
    plan = _plan()
    support = _support()
    rule_spec = _rule_spec()
    return (
        (
            "build_check_request",
            capability_helpers.build_check_request,
            (plan, {"$p": "person:alice"}),
            {},
        ),
        (
            "build_diagnose_request",
            capability_helpers.build_diagnose_request,
            (plan, {"$p": "person:alice"}),
            {},
        ),
        (
            "build_proof_frame_recheck_request",
            capability_helpers.build_proof_frame_recheck_request,
            (support,),
            {"overlay": _overlay()},
        ),
        (
            "build_rule_disable_request",
            capability_helpers.build_rule_disable_request,
            (rule_spec, support),
            {"branch_index": 0, "atom_index": 0},
        ),
        (
            "build_rule_literal_replace_request",
            capability_helpers.build_rule_literal_replace_request,
            (rule_spec, support),
            {
                "branch_index": 0,
                "atom_index": 0,
                "literal_path": RuleLiteralPath(kind="rhs"),
                "old_literal": "us",
                "new_literal": "eu",
            },
        ),
        (
            "build_rule_add_condition_request",
            capability_helpers.build_rule_add_condition_request,
            (rule_spec, support),
            {
                "branch_index": 0,
                "added_atom": RuleAddedAtom(atom=("eq", "$p", "person:alice")),
            },
        ),
        (
            "build_round_event_payload",
            capability_helpers.build_round_event_payload,
            (),
            {
                "kind": "check_result",
                "request": CheckRequest(plan=plan, binding=_binding(), engine="native"),
                "result": _check_result(),
            },
        ),
    )


class CapabilityHelperInvariantTests(unittest.TestCase):
    def test_application_and_helper_package_exports_are_identical(self) -> None:
        for name in HELPER_EXPORTS:
            with self.subTest(name=name):
                self.assertIs(getattr(application, name), getattr(capability_helpers, name))
                self.assertIn(name, application.__all__)
                self.assertIn(name, capability_helpers.__all__)

    def test_private_binding_helpers_are_not_public_exports(self) -> None:
        forbidden = {"_binding", "_normalize_helper_binding", "_reject_sdk_origin"}

        for name in forbidden:
            with self.subTest(name=name):
                self.assertNotIn(name, capability_helpers.__all__)
                self.assertFalse(hasattr(application, name))
                if name != "_binding":
                    self.assertFalse(hasattr(capability_helpers, name))

    def test_eight_capability_families_have_importable_builder_representatives(self) -> None:
        # 8-helper coverage is by capability family. Batch 5 has three sub-builders,
        # so the exported function count is intentionally greater than eight.
        self.assertEqual(len(CAPABILITY_FAMILY_REPRESENTATIVES), 8)
        for family, name in CAPABILITY_FAMILY_REPRESENTATIVES.items():
            with self.subTest(family=family, name=name):
                self.assertTrue(callable(getattr(capability_helpers, name)))

    def test_production_helpers_do_not_import_sdk(self) -> None:
        for path, source in _helper_sources().items():
            with self.subTest(path=path.name):
                self.assertNotIn("kernel.sdk", source)
                self.assertNotIn("from kernel import sdk", source)
                self.assertNotIn("import sdk", source)

    def test_production_helpers_do_not_call_sibling_runtimes_or_recorders(self) -> None:
        forbidden = (
            "from kernel.application.derivation_check_runtime",
            "from kernel.application.diagnose_runtime",
            "from kernel.application.fact_overlay_runtime",
            "from kernel.application.proofframe_runtime",
            "from kernel.application.rule_disable_runtime",
            "from kernel.application.rule_literal_replace_runtime",
            "from kernel.application.rule_add_condition_runtime",
            "from kernel.application.why_not_runtime",
            "check_derivation_binding",
            "diagnose_derivation_binding",
            "check_fact_overlay_binding",
            "recheck_proof_frame",
            "check_rule_disable_action",
            "check_rule_literal_replace_action",
            "check_rule_add_condition_action",
            "check_why_not_universe",
            "RoundRecorder",
            "record_round_event",
            "start_round",
            "finalize_round",
        )
        for path, source in _helper_sources().items():
            for token in forbidden:
                with self.subTest(path=path.name, token=token):
                    self.assertNotIn(token, source)

    def test_phase_1_to_5_builders_are_deterministic_for_same_inputs(self) -> None:
        for name, builder, args, kwargs in _builder_cases():
            with self.subTest(name=name):
                self.assertEqual(builder(*args, **kwargs), builder(*args, **kwargs))

    def test_top_level_sdk_origin_rejected_for_phase_1_to_5_builders(self) -> None:
        sdk_rule = _sdk_rule()
        cases = (
            ("check", capability_helpers.build_check_request, (sdk_rule, {}), {}),
            ("diagnose", capability_helpers.build_diagnose_request, (sdk_rule, {}), {}),
            ("proof_frame", capability_helpers.build_proof_frame_recheck_request, (sdk_rule,), {}),
            (
                "rule_disable",
                capability_helpers.build_rule_disable_request,
                (sdk_rule, _support()),
                {"branch_index": 0, "atom_index": 0},
            ),
            (
                "rule_literal_replace",
                capability_helpers.build_rule_literal_replace_request,
                (sdk_rule, _support()),
                {
                    "branch_index": 0,
                    "atom_index": 0,
                    "literal_path": RuleLiteralPath(kind="rhs"),
                    "old_literal": "us",
                    "new_literal": "eu",
                },
            ),
            (
                "rule_add_condition",
                capability_helpers.build_rule_add_condition_request,
                (sdk_rule, _support()),
                {
                    "branch_index": 0,
                    "added_atom": RuleAddedAtom(atom=("eq", "$p", "person:alice")),
                },
            ),
            (
                "round_event",
                capability_helpers.build_round_event_payload,
                (),
                {"kind": "check_result", "request": sdk_rule, "result": _check_result()},
            ),
        )

        for name, builder, args, kwargs in cases:
            with self.subTest(name=name):
                with self.assertRaises(application.OriginPackageError):
                    builder(*args, **kwargs)

    def test_sdk_class_objects_are_rejected_for_phase_1_to_5_builders(self) -> None:
        with self.assertRaises(application.OriginPackageError):
            capability_helpers.build_check_request(_plan(), {"$rule": Rule})

    def test_nested_sdk_origin_rejected_for_representative_dataclass_paths(self) -> None:
        sdk_rule = _sdk_rule()
        cases = (
            (
                "check",
                capability_helpers.build_check_request,
                (_plan(body_ir=[sdk_rule]), {"$p": "person:alice"}),
                {},
            ),
            (
                "diagnose",
                capability_helpers.build_diagnose_request,
                (_plan(body_ir=[sdk_rule]), {"$p": "person:alice"}),
                {},
            ),
            (
                "proof_frame",
                capability_helpers.build_proof_frame_recheck_request,
                (_support(binding_items=(("$rule", sdk_rule),)),),
                {},
            ),
            (
                "rule_disable",
                capability_helpers.build_rule_disable_request,
                (_rule_spec(where=[sdk_rule]), _support()),
                {"branch_index": 0, "atom_index": 0},
            ),
            (
                "round_event",
                capability_helpers.build_round_event_payload,
                (),
                {
                    "kind": "check_result",
                    "request": CheckRequest(
                        plan=_plan(body_ir=[sdk_rule]),
                        binding=_binding(),
                        engine="native",
                    ),
                    "result": _check_result(),
                },
            ),
        )

        for name, builder, args, kwargs in cases:
            with self.subTest(name=name):
                with self.assertRaises(application.OriginPackageError):
                    builder(*args, **kwargs)

    def test_binding_cycle_guard_remains_active_for_binding_builders(self) -> None:
        recursive: dict[str, object] = {}
        recursive["self"] = recursive

        for name, builder in (
            ("check", capability_helpers.build_check_request),
            ("diagnose", capability_helpers.build_diagnose_request),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    application.CapabilityHelperError,
                    "recursive",
                ):
                    builder(_plan(), {"$payload": recursive})


def _helper_sources() -> dict[Path, str]:
    helper_dir = Path(capability_helpers.__file__).parent
    return {
        path: path.read_text(encoding="utf-8")
        for path in helper_dir.rglob("*.py")
    }


if __name__ == "__main__":
    unittest.main()
