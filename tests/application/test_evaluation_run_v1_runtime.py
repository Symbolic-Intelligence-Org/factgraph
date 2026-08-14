from __future__ import annotations

import inspect
import unittest
from collections.abc import Mapping
from dataclasses import replace

from factgraph.application import build_schema_index, encode_entity_ref
from factgraph.application.evaluation_run_v1_runtime import (
    EvaluationRunRuntimeErrorV1,
    build_evaluation_replay_program_envelope_v1,
    capture_evaluation_replay_payload_v1,
    capture_evaluation_replay_world_v1,
    compare_policy_variants_v1,
    decode_evaluation_replay_program_v1,
    diff_scenario_run_v1,
    explain_evaluation_run_v1,
    replay_evaluation_run_v1,
)
from factgraph.application.protocol import CompiledDerivationPlan, CompiledHeadCall, EntityRef
from factgraph.application.protocol.evaluation_run_v1 import (
    EvaluationEnginePinV1,
    EvaluationEngineResultV1,
    EvaluationExecutionProfileV1,
    EvaluationRunSideV1,
    EvaluationRunV1,
    ExplainTargetV1,
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
from factgraph.application.protocol.policy import (
    PolicyAll,
    PolicyCompare,
    PolicyCompareStructureNodeV0,
    PolicyFieldNavigation,
    PolicyOccurrence,
    PolicyStructureNodeV0,
    PolicyStructureV0,
    PolicyUnify,
)
from factgraph.application.protocol.scenario_v1 import ResolvedScenarioOperationV1
from factgraph.application.protocol.schema_runtime import FieldPath
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.core.store._support import ProjectedFact
from factgraph.sdk import Entity, Field, Identity, SDKStore


def _token(character: str) -> str:
    return f"sha256:{character * 64}"


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()


class EvaluationRunV1RuntimeTests(unittest.TestCase):
    def _fixture(self):
        graph = SDKStore([Person])
        schema = graph.schema_ir
        index = build_schema_index(schema)
        alice = encode_entity_ref(
            # The construction path exercises the same canonical entity-ref
            # format which the captured relation has to replay.
            EntityRef("Person", {"employee_id": "alice"}),
            index=index,
        )
        baseline_relation = {
            "Person:exists": (ProjectedFact("base:exists:alice", (alice,)),),
            "person:age": (ProjectedFact("base:age:alice", (alice, 35)),),
        }
        effective_relation = {
            "Person:exists": (ProjectedFact("effective:exists:alice", (alice,)),),
            "person:age": (ProjectedFact("effective:age:alice", (alice, 22)),),
        }
        compiled = CompiledDerivationPlan(
            derivation_id="v1-age-query",
            version="1",
            body_ir=[
                ("pred", "Person:exists", ["$person"]),
                ("pred", "person:age", ["$person", "$age"]),
            ],
            heads=(CompiledHeadCall("__factgraph_projection__v1_age", ("$age",)),),
        )
        profile = EvaluationExecutionProfileV1(
            "native_deterministic_v1",
            _token("c"),
            None,
            (EvaluationEnginePinV1("native", "test-native", "test-adapter"),),
        )
        plan = GoalPlanV1(
            GoalTargetRefV1("policy", "person.age", "1", _token("a")),
            _token("b"),
            "rows",
            (GoalSelectionV1("age", "int"),),
            execution_profile_digest=profile.profile_digest,
        )
        baseline_world = capture_evaluation_replay_world_v1(
            side="baseline",
            schema_ir=schema,
            semantic_world_digest=_token("d"),
            resolution_evidence_digest=_token("e"),
            closure_target_digests=(),
            relations=baseline_relation,
        )
        effective_world = capture_evaluation_replay_world_v1(
            side="effective",
            schema_ir=schema,
            semantic_world_digest=_token("f"),
            resolution_evidence_digest=_token("0"),
            closure_target_digests=(),
            relations=effective_relation,
        )
        payload = capture_evaluation_replay_payload_v1(
            schema_ir=schema,
            address_space_digest=_token("1"),
            plan=plan,
            execution_profile=profile,
            primary_compiled_plan=compiled,
            baseline_world=baseline_world,
            effective_world=effective_world,
        )
        return schema, compiled, profile, plan, payload

    def _side(
        self, *, name: str, plan: GoalPlanV1, world, profile, age: int
    ) -> EvaluationRunSideV1:
        result = GoalResultV1(
            plan.plan_digest,
            "rows",
            "complete",
            (GoalResultRowV1((("age", GoalValueV1("int", age)),)),),
        )
        assessment = GoalTechnicalAssessmentV1(
            plan.plan_digest,
            result.result_digest,
            "not_requested",
            "succeeded",
            "not_requested",
            "complete",
            "not_requested",
            "available",
            "available",
        )
        return EvaluationRunSideV1(
            name,
            plan.plan_digest,
            world.side,
            world.world_capture_digest,
            result,
            (EvaluationEngineResultV1("native", result),),
            assessment,
        )

    def _run(self) -> EvaluationRunV1:
        _schema, _compiled, profile, plan, payload = self._fixture()
        return EvaluationRunV1(
            plan,
            profile,
            payload,
            self._side(
                name="baseline",
                plan=plan,
                world=payload.world("baseline"),
                profile=profile,
                age=35,
            ),
            self._side(
                name="effective",
                plan=plan,
                world=payload.world("effective"),
                profile=profile,
                age=22,
            ),
        )

    def _single_occurrence_structure(self, alias: str) -> PolicyStructureV0:
        occurrence = PolicyOccurrence(alias)
        return PolicyStructureV0(
            occurrence.node_id,
            (
                PolicyStructureNodeV0(
                    occurrence.node_id,
                    "occurrence",
                    occurrence_alias=alias,
                ),
            ),
        )

    def _variant_run(
        self,
        *,
        primary_policy_structure: PolicyStructureV0 | None = None,
        candidate_policy_structure: PolicyStructureV0 | None = None,
    ) -> EvaluationRunV1:
        schema, compiled, profile, plan, seed_payload = self._fixture()
        candidate = GoalPlanV1(
            GoalTargetRefV1("policy", "person.age.candidate", "1", _token("9")),
            _token("8"),
            "rows",
            (GoalSelectionV1("age", "int"),),
            execution_profile_digest=profile.profile_digest,
        )
        primary = GoalPlanV1(
            plan.target,
            plan.query_digest,
            plan.result_mode,
            plan.selections,
            candidate_target=candidate.target,
            candidate_query_digest=candidate.query_digest,
            execution_profile_digest=profile.profile_digest,
        )
        payload = capture_evaluation_replay_payload_v1(
            schema_ir=schema,
            address_space_digest=_token("1"),
            plan=primary,
            execution_profile=profile,
            primary_compiled_plan=compiled,
            baseline_world=seed_payload.world("baseline"),
            effective_world=seed_payload.world("effective"),
            candidate_plan=candidate,
            candidate_compiled_plan=compiled,
            primary_policy_structure=primary_policy_structure,
            candidate_policy_structure=candidate_policy_structure,
        )
        baseline = self._side(
            name="baseline", plan=primary, world=payload.world("baseline"), profile=profile, age=35
        )
        effective = self._side(
            name="effective",
            plan=primary,
            world=payload.world("effective"),
            profile=profile,
            age=22,
        )
        candidate_effective = self._side(
            name="candidate_effective",
            plan=candidate,
            world=payload.world("effective"),
            profile=profile,
            age=22,
        )
        return EvaluationRunV1(
            primary,
            profile,
            payload,
            baseline,
            effective,
            candidate,
            candidate_effective,
        )

    def test_capture_binds_canonical_body_head_schema_and_all_run_pins(self) -> None:
        schema, compiled, profile, plan, _payload = self._fixture()
        envelope = build_evaluation_replay_program_envelope_v1(
            schema_ir=schema,
            address_space_digest=_token("1"),
            plan=plan,
            execution_profile=profile,
            primary_compiled_plan=compiled,
        )
        record = envelope.compiled_program["primary"]
        self.assertIsInstance(record, Mapping)
        self.assertEqual(record["plan_digest"], plan.plan_digest)
        self.assertEqual(record["query_digest"], plan.query_digest)
        self.assertEqual(record["target_digest"], plan.target.target_digest)
        self.assertEqual(
            record["compiled_plan"]["heads"][0]["head_var_names"],  # type: ignore[index]
            ("$age",),
        )

    def test_detached_explain_retains_sealed_authored_structure_and_resolved_patch(self) -> None:
        schema, compiled, profile, plan, seed_payload = self._fixture()
        left, right = PolicyOccurrence("left"), PolicyOccurrence("right")
        left_person = SemanticPortAddress("left", "person")
        right_person = SemanticPortAddress("right", "person")
        unify = PolicyUnify(left_person, right_person)
        comparison = PolicyCompare.gt(
            PolicyFieldNavigation(left_person, FieldPath("Person", "age")),
            PolicyFieldNavigation(right_person, FieldPath("Person", "age")),
        )
        root = PolicyAll((left, right, unify, comparison))
        structure = PolicyStructureV0(
            root.node_id,
            tuple(
                sorted(
                    (
                        PolicyStructureNodeV0(
                            left.node_id,
                            "occurrence",
                            occurrence_alias="left",
                        ),
                        PolicyStructureNodeV0(
                            right.node_id,
                            "occurrence",
                            occurrence_alias="right",
                        ),
                        PolicyStructureNodeV0(
                            unify.node_id,
                            "unify",
                            left=unify.left,
                            right=unify.right,
                        ),
                        PolicyCompareStructureNodeV0(
                            comparison.node_id,
                            comparison.op,
                            comparison.left,
                            comparison.right,
                        ),
                        PolicyStructureNodeV0(
                            root.node_id,
                            "all",
                            child_node_ids=tuple(child.node_id for child in root.children),
                        ),
                    ),
                    key=lambda item: item.node_id,
                )
            ),
        )
        operation = ResolvedScenarioOperationV1(
            "without_relation",
            None,
            None,
            "person:age",
            None,
            premise_ids=("premise-1",),
            origin_refs=("source-1",),
            masked_witness_ids=("effective:age:alice",),
        )
        payload = capture_evaluation_replay_payload_v1(
            schema_ir=schema,
            address_space_digest=_token("1"),
            plan=plan,
            execution_profile=profile,
            primary_compiled_plan=compiled,
            baseline_world=seed_payload.world("baseline"),
            effective_world=seed_payload.world("effective"),
            primary_policy_structure=structure,
            scenario_operations=(operation,),
        )
        run = EvaluationRunV1(
            plan,
            profile,
            payload,
            self._side(
                name="baseline",
                plan=plan,
                world=payload.world("baseline"),
                profile=profile,
                age=35,
            ),
            self._side(
                name="effective",
                plan=plan,
                world=payload.world("effective"),
                profile=profile,
                age=22,
            ),
        )

        decoded = decode_evaluation_replay_program_v1(run)
        explanation = explain_evaluation_run_v1(
            run,
            ExplainTargetV1(
                "effective",
                "row",
                run.effective.canonical_result.rows[0].anchor.anchor_digest,  # type: ignore[union-attr]
            ),
        )

        self.assertEqual(decoded.primary_policy_structure, structure)
        self.assertEqual(decoded.scenario_operations, (operation,))
        self.assertEqual(explanation.policy_structure, structure)
        self.assertEqual(explanation.policy_structure_capture, "captured")
        self.assertEqual(explanation.scenario_operations, (operation,))
        self.assertEqual(explanation.scenario_patch_capture, "captured")
        self.assertEqual(explanation.scenario_patch_application, "applied")
        # This fixture deliberately uses the compatibility envelope without a
        # restricted native Explain context.  It may retain static structure
        # and Scenario patch data, but it must not fabricate a graph.
        self.assertEqual(explanation.engine_evidence, "not_captured")
        self.assertIsNone(explanation.evidence_graph)
        self.assertIsNone(explanation.policy_projection)

    def test_detached_replay_uses_only_run_and_matches_captured_results(self) -> None:
        run = self._run()

        report = replay_evaluation_run_v1(run)

        self.assertEqual(report.status, "matched")
        self.assertTrue(report.baseline.result_match)
        self.assertTrue(report.effective.engine_frame_match)
        self.assertEqual(report.proof_parity, "not_claimed")
        self.assertNotIn("store", inspect.signature(replay_evaluation_run_v1).parameters)

    def test_scenario_diff_is_sealed_descriptive_and_exposes_no_causal_or_evidence_claim(
        self,
    ) -> None:
        schema, compiled, profile, ordinary_plan, seed_payload = self._fixture()
        plan = replace(ordinary_plan, scenario_request_digest=_token("2"))
        operation = ResolvedScenarioOperationV1(
            "set_effective_value",
            "entref_v1:Person:alice",
            "Person",
            "person:age",
            FieldPath("Person", "age"),
            values=(),
            premise_ids=("premise-1",),
            origin_refs=("source-1",),
        )
        payload = capture_evaluation_replay_payload_v1(
            schema_ir=schema,
            address_space_digest=_token("1"),
            plan=plan,
            execution_profile=profile,
            primary_compiled_plan=compiled,
            baseline_world=seed_payload.world("baseline"),
            effective_world=seed_payload.world("effective"),
            scenario_operations=(operation,),
        )
        run = EvaluationRunV1(
            plan,
            profile,
            payload,
            self._side(
                name="baseline",
                plan=plan,
                world=payload.world("baseline"),
                profile=profile,
                age=35,
            ),
            self._side(
                name="effective",
                plan=plan,
                world=payload.world("effective"),
                profile=profile,
                age=22,
            ),
        )

        diff = diff_scenario_run_v1(run)

        self.assertEqual(diff.run_digest, run.run_digest)
        self.assertEqual(diff.plan_digest, plan.plan_digest)
        self.assertEqual(diff.scenario_request_digest, plan.scenario_request_digest)
        self.assertEqual(
            diff.baseline_world_capture_digest,
            payload.world("baseline").world_capture_digest,
        )
        self.assertEqual(
            diff.effective_world_capture_digest,
            payload.world("effective").world_capture_digest,
        )
        self.assertEqual(
            diff.input_difference_axes,
            ("semantic_world", "relation_snapshot", "resolution_evidence"),
        )
        self.assertEqual(diff.scenario_patch_capture, "captured")
        self.assertEqual(diff.scenario_patch_application, "applied")
        self.assertEqual(diff.scenario_operations, (operation,))
        self.assertEqual(diff.scenario_operation_digests, (operation.operation_digest,))
        self.assertEqual(diff.result_relation, "different")
        self.assertEqual(len(diff.baseline_only_semantic_row_digests), 1)
        self.assertEqual(len(diff.effective_only_semantic_row_digests), 1)
        self.assertEqual(diff.evidence_relation, "not_claimed")
        self.assertEqual(diff.causal_attribution, "not_claimed")
        self.assertTrue(diff.diff_digest.startswith("sha256:"))
        self.assertNotIn("store", inspect.signature(diff_scenario_run_v1).parameters)

    def test_scenario_diff_rejects_a_run_without_an_explicit_scenario_request(self) -> None:
        with self.assertRaisesRegex(EvaluationRunRuntimeErrorV1, "no explicit Scenario") as caught:
            diff_scenario_run_v1(self._run())
        self.assertEqual(caught.exception.code, "EVALUATION_RUN_V1_SCENARIO_DIFF_UNAVAILABLE")

    def test_replay_rejects_a_program_body_that_is_outer_pin_consistent_but_not_strictly_decodable(
        self,
    ) -> None:
        run = self._run()
        malformed_envelope = replace(
            run.replay_payload.program_envelope,
            compiled_program={
                "$type": "FactGraphEvaluationProgramV1",
                "primary": {},
                "candidate": None,
            },
        )
        malformed_payload = replace(
            run.replay_payload,
            compiled_program_bytes=malformed_envelope.to_bytes(),
        )
        malformed_run = EvaluationRunV1(
            run.plan,
            run.execution_profile,
            malformed_payload,
            run.baseline,
            run.effective,
        )

        with self.assertRaisesRegex(EvaluationRunRuntimeErrorV1, "unsupported or missing"):
            replay_evaluation_run_v1(malformed_run)

    def test_explicit_summary_explain_never_turns_empty_observation_into_negative_proof(
        self,
    ) -> None:
        run = self._run()
        empty_result = GoalResultV1(run.plan.plan_digest, "rows", "complete", ())
        empty_assessment = GoalTechnicalAssessmentV1(
            run.plan.plan_digest,
            empty_result.result_digest,
            "not_requested",
            "succeeded",
            "not_requested",
            "complete",
            "not_requested",
            "available",
            "available",
        )
        empty_effective = EvaluationRunSideV1(
            "effective",
            run.plan.plan_digest,
            "effective",
            run.replay_payload.world("effective").world_capture_digest,
            empty_result,
            (EvaluationEngineResultV1("native", empty_result),),
            empty_assessment,
        )
        empty_run = EvaluationRunV1(
            run.plan,
            run.execution_profile,
            run.replay_payload,
            run.baseline,
            empty_effective,
        )
        summary = empty_run.effective.canonical_result.summary_anchor
        assert summary is not None

        explanation = explain_evaluation_run_v1(
            empty_run, ExplainTargetV1("effective", "summary", summary.summary_anchor_digest)
        )

        self.assertEqual(explanation.observation, "result_summary_observed")
        self.assertEqual(explanation.logical_conclusion, "not_claimed")
        self.assertEqual(explanation.negative_proof, "not_claimed")
        with self.assertRaises(EvaluationRunRuntimeErrorV1):
            explain_evaluation_run_v1(empty_run, ExplainTargetV1("effective", "row", _token("9")))

    def test_variant_comparison_is_descriptive_and_non_causal(self) -> None:
        run = self._variant_run()

        comparison = compare_policy_variants_v1(run)

        self.assertEqual(comparison.result_relation, "equivalent")
        self.assertEqual(comparison.causal_attribution, "not_claimed")
        self.assertTrue(comparison.compiled_body_equal)
        self.assertEqual(comparison.authored_structure_relation, "not_captured")
        self.assertIsNone(comparison.primary_policy_structure_digest)
        self.assertIsNone(comparison.candidate_policy_structure_digest)

    def test_variant_comparison_describes_captured_authored_topology_without_causality(
        self,
    ) -> None:
        primary = self._single_occurrence_structure("primary")
        equivalent = self._single_occurrence_structure("primary")
        different = self._single_occurrence_structure("candidate")

        equal_comparison = compare_policy_variants_v1(
            self._variant_run(
                primary_policy_structure=primary,
                candidate_policy_structure=equivalent,
            )
        )
        self.assertEqual(equal_comparison.authored_structure_relation, "equivalent")
        self.assertEqual(
            equal_comparison.primary_policy_structure_digest,
            equal_comparison.candidate_policy_structure_digest,
        )
        self.assertEqual(equal_comparison.causal_attribution, "not_claimed")

        different_comparison = compare_policy_variants_v1(
            self._variant_run(
                primary_policy_structure=primary,
                candidate_policy_structure=different,
            )
        )
        self.assertEqual(different_comparison.authored_structure_relation, "different")
        self.assertNotEqual(
            different_comparison.primary_policy_structure_digest,
            different_comparison.candidate_policy_structure_digest,
        )
        # The compiled program and selected rows are still equal: topology is
        # descriptive context, never a causal explanation for either fact.
        self.assertTrue(different_comparison.compiled_body_equal)
        self.assertEqual(different_comparison.result_relation, "equivalent")
        self.assertEqual(different_comparison.causal_attribution, "not_claimed")

        partial_comparison = compare_policy_variants_v1(
            self._variant_run(primary_policy_structure=primary)
        )
        self.assertEqual(partial_comparison.authored_structure_relation, "captured")
        self.assertIsNotNone(partial_comparison.primary_policy_structure_digest)
        self.assertIsNone(partial_comparison.candidate_policy_structure_digest)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
