from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    manage_rule_occurrence,
)
from factgraph.application.goal_plan_v1_runtime import (
    GoalPlanFailureV1,
    GoalPlanRunV1,
    portable_deterministic_profile_v1,
    provider_binding_slot_v1,
)
from factgraph.application.portable_evaluation_runtime import (
    PortableEngineDiagnosticV1,
    PortableEngineObservationFrameV1,
    observe_portable_deterministic_v1,
)
from factgraph.application.evaluation_run_v1_runtime import (
    EvaluationRunRuntimeErrorV1,
    ScenarioDiffV1,
    replay_evaluation_run_v1,
)
from factgraph.application.protocol import (
    EntityRef,
    EvaluationQueryFieldNavigationV0,
    FieldPath,
    Policy,
    PolicyOccurrence,
    SemanticPortAddress,
    SemanticRulePort,
)
from factgraph.application.protocol.evaluation_run_v1 import (
    EvaluationRunV1,
    ExplainTargetV1,
)
from factgraph.application.protocol.scenario_v1 import (
    EvidenceScopeV1,
    ExactLocalClosureTargetV1,
    ScenarioCreateEphemeralEntityV1,
    ScenarioSetEffectiveValueV1,
    ScenarioSpecV1,
    ScenarioWithoutAssertionV1,
    ScenarioWithoutFieldV1,
    ScenarioValueV1,
)
from factgraph.application.protocol.goal_plan_v1 import (
    ContainsRowExpectationV1,
    CountEqExpectationV1,
    ExactLocalAbsenceExpectationV1,
    ExistsExpectationV1,
    GoalRowExpectationV1,
    GoalValueV1,
    SetEqualsExpectationV1,
)
from factgraph.application.protocol.relation_provider_v1 import (
    ProviderMaterializationV1,
    ProviderRelationRowV1,
    RelationProviderV1,
)
from factgraph.application.schema_runtime import entity_info, field_predicate, resolve_selector
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, SDKStore
from factgraph.sdk.errors import SDKStoreError
from factgraph.sdk.evaluation_query_builder import ProviderQueryTargetV1


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    score: int = Field()


def _address(alias: str, port: str) -> SemanticPortAddress:
    return SemanticPortAddress(alias, port)


def _bundle(graph: SDKStore):
    from factgraph.application.protocol import entity_identity, field_endpoint

    index = build_schema_index(graph.schema_ir)
    person, age, score = Var("$person"), Var("$age"), Var("$score")
    return build_resolved_rule(
        id="goal_person_values",
        version="1",
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
            PredAtom("person:score", [person, score]),
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
            "score": SemanticRulePort(score, field_endpoint("Person", "score")),
        },
        schema_index=index,
    )


def _age_only_bundle(graph: SDKStore):
    from factgraph.application.protocol import entity_identity, field_endpoint

    index = build_schema_index(graph.schema_ir)
    person, age = Var("$person"), Var("$age")
    return build_resolved_rule(
        id="goal_person_age_only",
        version="1",
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
        },
        schema_index=index,
    )


def _age_with_score_guard_bundle(graph: SDKStore):
    from factgraph.application.protocol import entity_identity, field_endpoint

    index = build_schema_index(graph.schema_ir)
    person, age, score = Var("$person"), Var("$age"), Var("$score")
    return build_resolved_rule(
        id="goal_person_age_with_score_guard",
        version="1",
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
            PredAtom("person:score", [person, score]),
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
        },
        schema_index=index,
    )


def _identity_bundle(graph: SDKStore):
    from factgraph.application.protocol import entity_identity

    index = build_schema_index(graph.schema_ir)
    person = Var("$person")
    return build_resolved_rule(
        id="goal_person_identity_only",
        version="1",
        when=(PredAtom("Person:exists", [person]),),
        ports={"person": SemanticRulePort(person, entity_identity("Person"))},
        schema_index=index,
    )


def _seed(graph: SDKStore, employee_id: str, *, age: int, score: int) -> str:
    from factgraph.application.protocol import EntitySelector

    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"employee_id": employee_id}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        graph.ledger,
        info.identity_predicates["employee_id"].pred_id,
        encoded,
        [("string", employee_id)],
    )
    set_field(
        graph.ledger,
        field_predicate(index, "Person", "age").pred_id,
        encoded,
        [("int", age)],
    )
    set_field(
        graph.ledger,
        field_predicate(index, "Person", "score").pred_id,
        encoded,
        [("int", score)],
    )
    return encoded


class GoalPlanV1SDKTests(unittest.TestCase):
    def test_rule_query_plan_runs_and_replays_from_detached_capture(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        invocation = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .plan()
        )

        outcome = invocation.run()
        self.assertIsInstance(outcome, GoalPlanRunV1)
        assert isinstance(outcome, GoalPlanRunV1)
        self.assertEqual(len(outcome.run.baseline.canonical_result.rows), 1)
        self.assertEqual(
            dict(outcome.run.effective.canonical_result.rows[0].values)["age"].value,
            22,
        )
        row = outcome.run.effective.canonical_result.rows[0]
        assert row.anchor is not None
        row_explanation = outcome.explain(
            ExplainTargetV1("effective", "row", row.anchor.anchor_digest)
        )
        self.assertEqual(row_explanation.logical_conclusion, "holds")
        self.assertEqual(row_explanation.policy_structure_capture, "captured")
        assert row_explanation.policy_structure is not None
        self.assertEqual(
            row_explanation.policy_structure,
            invocation.primary.target.compiled_policy.policy_structure,
        )
        summary = outcome.run.effective.canonical_result.summary_anchor
        assert summary is not None
        summary_explanation = outcome.explain(
            ExplainTargetV1("effective", "summary", summary.summary_anchor_digest)
        )
        self.assertEqual(summary_explanation.logical_conclusion, "not_claimed")
        replay = outcome.replay()
        self.assertEqual(replay.status, "matched")

    def test_scenario_without_is_exact_local_not_a_zero_row_negative_fact(self) -> None:
        graph = SDKStore([Person])
        alice = _seed(graph, "alice", age=22, score=9)
        index = build_schema_index(graph.schema_ir)
        age_predicate = field_predicate(index, "Person", "age").pred_id
        from factgraph.application.protocol import FieldPath

        scenario = ScenarioSpecV1(
            (
                ScenarioWithoutFieldV1(
                    "alice-age-removed",
                    EntityRef("Person", {"employee_id": "alice"}),
                    FieldPath("Person", "age"),
                ),
            )
        )
        absence = ExactLocalAbsenceExpectationV1(
            "age-is-scenario-empty",
            ExactLocalClosureTargetV1("field", alice, age_predicate),
        )
        outcome = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .what_if(scenario)
            .plan(expectations=(absence,))
            .run()
        )
        self.assertNotIsInstance(outcome, GoalPlanFailureV1)
        assert isinstance(outcome, GoalPlanRunV1)
        self.assertEqual(len(outcome.run.baseline.canonical_result.rows), 1)
        self.assertEqual(len(outcome.run.effective.canonical_result.rows), 0)
        self.assertEqual(
            outcome.run.baseline.canonical_result.expectation_outcomes[0].status,
            "underdetermined",
        )
        self.assertEqual(
            outcome.run.effective.canonical_result.expectation_outcomes[0].status,
            "satisfied",
        )
        summary = outcome.run.effective.canonical_result.summary_anchor
        assert summary is not None
        explanation = outcome.explain(
            ExplainTargetV1("effective", "summary", summary.summary_anchor_digest)
        )
        self.assertEqual(explanation.scenario_patch_capture, "captured")
        self.assertEqual(explanation.scenario_patch_application, "applied")
        assert explanation.scenario_operations is not None
        self.assertEqual(
            {operation.kind for operation in explanation.scenario_operations},
            {"without_field"},
        )
        self.assertEqual(outcome.replay().status, "matched")

        # A closure digest cannot by itself turn a forged world into absence:
        # restore the masked age relation while preserving the sealed closure
        # target, self-consistently reseal the outer payload/run, and require
        # detached replay to reject the contradiction before reporting success.
        baseline_world = outcome.run.replay_payload.world("baseline")
        effective_world = outcome.run.replay_payload.world("effective")
        baseline_age = next(
            relation
            for relation in baseline_world.relations
            if relation.predicate_id == age_predicate
        )
        forged_effective = replace(
            effective_world,
            relations=tuple(
                baseline_age if relation.predicate_id == age_predicate else relation
                for relation in effective_world.relations
            ),
        )
        forged_payload = replace(
            outcome.run.replay_payload,
            worlds=(baseline_world, forged_effective),
        )
        forged_effective_side = replace(
            outcome.run.effective,
            world_capture_digest=forged_effective.world_capture_digest,
        )
        forged_run = EvaluationRunV1(
            outcome.run.plan,
            outcome.run.execution_profile,
            forged_payload,
            outcome.run.baseline,
            forged_effective_side,
        )
        with self.assertRaisesRegex(
            EvaluationRunRuntimeErrorV1,
            "closure contradicts its captured relation",
        ):
            replay_evaluation_run_v1(forged_run)

    def test_scenario_scalar_replacement_keeps_baseline_and_effective_runs_separate(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        scenario = ScenarioSpecV1(
            (
                ScenarioSetEffectiveValueV1(
                    "alice-age-35",
                    EntityRef("Person", {"employee_id": "alice"}),
                    FieldPath("Person", "age"),
                    ScenarioValueV1("int", 35),
                    origin_refs=("fixture:what-if",),
                ),
            )
        )
        outcome = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .what_if(scenario)
            .run()
        )
        self.assertIsInstance(outcome, GoalPlanRunV1)
        assert isinstance(outcome, GoalPlanRunV1)
        self.assertEqual(
            dict(outcome.run.baseline.canonical_result.rows[0].values)["age"].value,
            22,
        )
        self.assertEqual(
            dict(outcome.run.effective.canonical_result.rows[0].values)["age"].value,
            35,
        )
        self.assertIsInstance(outcome.scenario_diff, ScenarioDiffV1)
        assert isinstance(outcome.scenario_diff, ScenarioDiffV1)
        self.assertEqual(outcome.scenario_diff.result_relation, "different")
        self.assertIn("semantic_world", outcome.scenario_diff.input_difference_axes)
        self.assertEqual(outcome.scenario_diff.evidence_relation, "not_claimed")
        self.assertEqual(outcome.scenario_diff.causal_attribution, "not_claimed")
        self.assertEqual(outcome.replay().status, "matched")

    def test_scenario_ephemeral_entity_augments_the_sealed_world_not_the_live_store(self) -> None:
        """An age-only Rule can still query a newly created entity safely.

        The Scenario resolver needs ``Person:exists`` plus every identity
        predicate even when the Rule itself does not read identity.  The V1
        runtime therefore adds those schema anchors to its one captured world
        before resolution; it never asks the Store for Bob afterwards.
        """

        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        info = entity_info(build_schema_index(graph.schema_ir), "Person")
        bob = EntityRef("Person", {"employee_id": "bob"})
        scenario = ScenarioSpecV1(
            (
                ScenarioCreateEphemeralEntityV1("create-bob", bob),
                ScenarioSetEffectiveValueV1(
                    "bob-age",
                    bob,
                    FieldPath("Person", "age"),
                    ScenarioValueV1("int", 19),
                ),
            )
        )
        outcome = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), bob)
            .select("age", _address("target", "age"))
            .what_if(scenario)
            .run()
        )
        self.assertIsInstance(outcome, GoalPlanRunV1)
        assert isinstance(outcome, GoalPlanRunV1)
        self.assertEqual(outcome.run.baseline.canonical_result.rows, ())
        self.assertEqual(
            dict(outcome.run.effective.canonical_result.rows[0].values)["age"].value,
            19,
        )
        # Identity support is visible in the sealed replay world, but Bob was
        # never written to the source graph.
        self.assertTrue(
            any(
                relation.predicate_id == info.identity_predicates["employee_id"].pred_id
                for relation in outcome.run.replay_payload.world("effective").relations
            )
        )
        self.assertEqual(outcome.replay().status, "matched")

    def test_without_assertion_is_scenario_closure_while_scope_ignore_is_not(self) -> None:
        """The SDK/debug assertion form is not silently downgraded to scope.ignore."""

        graph = SDKStore([Person])
        index = build_schema_index(graph.schema_ir)
        from factgraph.application.protocol import EntitySelector

        alice_ref = resolve_selector(
            EntitySelector(entity_type="Person", identity={"employee_id": "alice"}),
            index=index,
        ).encoded_ref
        assert alice_ref is not None
        info = entity_info(index, "Person")
        set_field(graph.ledger, info.exists_predicate_id, alice_ref, [])
        set_field(
            graph.ledger,
            info.identity_predicates["employee_id"].pred_id,
            alice_ref,
            [("string", "alice")],
        )
        age_predicate = field_predicate(index, "Person", "age").pred_id
        age_assertion = set_field(graph.ledger, age_predicate, alice_ref, [("int", 22)])
        scenario = ScenarioSpecV1(
            (ScenarioWithoutAssertionV1("remove-age-witness", age_assertion),)
        )
        absence = ExactLocalAbsenceExpectationV1(
            "the-exact-witness-is-absent",
            ExactLocalClosureTargetV1("assertion", None, age_predicate, assertion_id=age_assertion),
        )
        outcome = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .what_if(scenario)
            .plan(expectations=(absence,))
            .run()
        )
        self.assertIsInstance(outcome, GoalPlanRunV1)
        assert isinstance(outcome, GoalPlanRunV1)
        self.assertEqual(outcome.run.effective.canonical_result.rows, ())
        self.assertEqual(
            outcome.run.effective.canonical_result.expectation_outcomes[0].status,
            "satisfied",
        )
        self.assertEqual(outcome.replay().status, "matched")

        ignored = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .plan(
                expectations=(absence,),
                scenario=ScenarioSpecV1(()),
                evidence_scope=EvidenceScopeV1((age_assertion,)),
            )
            .run()
        )
        self.assertIsInstance(ignored, GoalPlanRunV1)
        assert isinstance(ignored, GoalPlanRunV1)
        self.assertEqual(ignored.run.effective.canonical_result.rows, ())
        self.assertEqual(
            ignored.run.effective.canonical_result.expectation_outcomes[0].status,
            "underdetermined",
        )

    def test_candidate_with_added_dependency_uses_one_union_world_and_replays(self) -> None:
        """Candidate policy changes may add a dependency without changing world identity.

        The primary Rule does not require ``person:score``; the immutable
        candidate does.  A comparison must capture their union once, then give
        each isolated evaluator exactly its own declared relation subset.
        """

        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        outcome = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .plan(candidate=_age_with_score_guard_bundle(graph))
            .run()
        )
        self.assertIsInstance(outcome, GoalPlanRunV1)
        assert isinstance(outcome, GoalPlanRunV1)
        self.assertIsNotNone(outcome.comparison)
        self.assertEqual(outcome.comparison.result_relation, "equivalent")
        captured_predicates = {
            relation.predicate_id
            for relation in outcome.run.replay_payload.world("effective").relations
        }
        self.assertIn("person:score", captured_predicates)
        self.assertEqual(outcome.replay().status, "matched")

    def test_provider_replaces_only_its_declared_relation_once_and_replay_never_calls_it(
        self,
    ) -> None:
        graph = SDKStore([Person])
        alice = _seed(graph, "alice", age=22, score=9)
        index = build_schema_index(graph.schema_ir)
        age_predicate = field_predicate(index, "Person", "age").pred_id
        calls: list[object] = []

        def materialize(request):
            calls.append(request)
            return ProviderMaterializationV1(
                request.provider_digest,
                request.request_digest,
                "fixture:age-lookup",
                sha256_token(b"fixture:age-lookup:receipt"),
                request.supplied_predicate_ids,
                (
                    ProviderRelationRowV1(
                        age_predicate,
                        (GoalValueV1("entity_ref", alice), GoalValueV1("int", 30)),
                        "fixture:age-lookup-row",
                    ),
                ),
            )

        person_slot = provider_binding_slot_v1("target", "person")
        provider = RelationProviderV1(
            "fixture.age-lookup",
            "1",
            "lookup",
            sha256_token(b"fixture:age-lookup:code"),
            (person_slot,),
            (age_predicate,),
            materialize,
        )
        builder = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .using(provider)
        )
        with self.assertRaisesRegex(SDKStoreError, r"requires query\.plan"):
            builder.compile()
        with self.assertRaisesRegex(SDKStoreError, r"requires query\.plan"):
            builder.evaluate()
        outcome = builder.plan().run()
        self.assertIsInstance(outcome, GoalPlanRunV1)
        assert isinstance(outcome, GoalPlanRunV1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            dict(outcome.run.effective.canonical_result.rows[0].values)["age"].value,
            30,
        )
        self.assertEqual(len(outcome.run.replay_payload.provider_receipts), 1)
        self.assertEqual(outcome.replay().status, "matched")
        self.assertEqual(len(calls), 1)
        with self.assertRaisesRegex(SDKStoreError, "candidate cannot carry RelationProviderV1"):
            graph.query(_age_only_bundle(graph)).select("age", _address("target", "age")).plan(
                candidate=ProviderQueryTargetV1(_age_with_score_guard_bundle(graph), provider)  # type: ignore[arg-type]
            )

    def test_portable_profile_uses_all_three_real_engines_for_one_query_plan(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        outcome = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .plan(profile=portable_deterministic_profile_v1())
            .run()
        )
        self.assertIsInstance(outcome, GoalPlanRunV1)
        assert isinstance(outcome, GoalPlanRunV1)
        self.assertEqual(
            tuple(frame.engine for frame in outcome.run.effective.engine_results),
            ("native", "souffle", "problog"),
        )
        self.assertEqual(outcome.run.effective.assessment.parity, "equivalent")
        self.assertEqual(outcome.replay().status, "matched")

    def test_provider_persistent_view_mutation_fails_closed_before_result_sealing(self) -> None:
        """A trusted in-process callback cannot silently mutate the source view.

        V1 cannot sandbox arbitrary Python closures or roll a mutation back,
        but it does pin the source view immediately before/after materializing
        the provider relation and refuses to seal a result if it changed.
        """

        graph = SDKStore([Person])
        alice = _seed(graph, "alice", age=22, score=9)
        index = build_schema_index(graph.schema_ir)
        age_predicate = field_predicate(index, "Person", "age").pred_id
        score_predicate = field_predicate(index, "Person", "score").pred_id

        def malicious_materialize(request):
            set_field(graph.ledger, score_predicate, alice, [("int", 999)])
            return ProviderMaterializationV1(
                request.provider_digest,
                request.request_digest,
                "fixture:mutating-provider",
                sha256_token(b"fixture:mutating-provider-receipt"),
                request.supplied_predicate_ids,
                (
                    ProviderRelationRowV1(
                        age_predicate,
                        (GoalValueV1("entity_ref", alice), GoalValueV1("int", 30)),
                        "fixture:mutating-provider-row",
                    ),
                ),
            )

        provider = RelationProviderV1(
            "fixture.mutating-provider",
            "1",
            "lookup",
            sha256_token(b"fixture:mutating-provider-code"),
            (),
            (age_predicate,),
            malicious_materialize,
        )
        outcome = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .using(provider)
            .plan()
            .run()
        )
        self.assertIsInstance(outcome, GoalPlanFailureV1)
        assert isinstance(outcome, GoalPlanFailureV1)
        self.assertEqual(outcome.code, "GOAL_VIEW_CHANGED_DURING_PROVIDER")
        self.assertIsNone(outcome.assessment.result_digest)

    def test_portable_adapter_absence_is_a_typed_frame_not_a_native_fallback(self) -> None:
        """A missing noncanonical adapter remains visible in Run and Replay.

        The Native frame remains the canonical selected-row result, but the
        profile cannot silently be described as parity-equivalent.  Patching
        the observation seam models an unavailable Soufflé installation while
        retaining the same isolated relation and the actual Native/ProbLog
        results.
        """

        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)

        def missing_souffle(*args, **kwargs):
            observed = observe_portable_deterministic_v1(*args, **kwargs)
            unavailable = PortableEngineObservationFrameV1(
                engine="souffle",
                status="unsupported",
                diagnostic=PortableEngineDiagnosticV1(
                    "PORTABLE_ENGINE_UNAVAILABLE",
                    '{"component":"fixture","engine":"souffle"}',
                ),
            )
            return replace(observed, frames=(observed.frames[0], unavailable, observed.frames[2]))

        with (
            patch(
                "factgraph.application.goal_plan_v1_runtime.observe_portable_deterministic_v1",
                side_effect=missing_souffle,
            ),
            patch(
                "factgraph.application.evaluation_run_v1_runtime.observe_portable_deterministic_v1",
                side_effect=missing_souffle,
            ),
        ):
            outcome = (
                graph.query(_age_only_bundle(graph))
                .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
                .select("age", _address("target", "age"))
                .plan(profile=portable_deterministic_profile_v1())
                .run()
            )
            self.assertIsInstance(outcome, GoalPlanRunV1)
            assert isinstance(outcome, GoalPlanRunV1)
            frames = outcome.run.effective.engine_results
            self.assertEqual(
                tuple(frame.status for frame in frames), ("succeeded", "unsupported", "succeeded")
            )
            self.assertEqual(outcome.run.effective.assessment.parity, "unsupported")
            self.assertEqual(outcome.run.effective.assessment.capability, "unresolved")
            self.assertEqual(outcome.replay().status, "matched")

    def test_direct_policy_and_field_navigation_share_the_v1_goal_plan_path(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        bundle = _identity_bundle(graph)
        space = SemanticAddressSpace((manage_rule_occurrence(bundle, "person"),))
        policy = Policy("goal_people", PolicyOccurrence("person"), version="1")
        outcome = (
            graph.query(policy, address_space=space)
            .bind(_address("person", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select(
                "age",
                EvaluationQueryFieldNavigationV0(
                    _address("person", "person"), FieldPath("Person", "age")
                ),
            )
            .plan()
            .run()
        )
        self.assertIsInstance(outcome, GoalPlanRunV1)
        assert isinstance(outcome, GoalPlanRunV1)
        self.assertEqual(outcome.run.plan.target.kind, "policy")
        self.assertEqual(
            dict(outcome.run.effective.canonical_result.rows[0].values)["age"].value,
            22,
        )
        self.assertEqual(outcome.replay().status, "matched")

    def test_result_modes_and_expectations_keep_zero_distinct_from_false(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        _seed(graph, "bob", age=19, score=7)
        age_19 = GoalValueV1("int", 19)
        age_22 = GoalValueV1("int", 22)
        row_19 = GoalRowExpectationV1((("age", age_19),))
        row_22 = GoalRowExpectationV1((("age", age_22),))
        rows_outcome = (
            graph.query(_age_only_bundle(graph))
            .select("age", _address("target", "age"))
            .plan(
                expectations=(
                    ContainsRowExpectationV1("has-bob", row_19),
                    ContainsRowExpectationV1(
                        "does-not-have-44", GoalRowExpectationV1((("age", GoalValueV1("int", 44)),))
                    ),
                    ExistsExpectationV1("any-person", True),
                    CountEqExpectationV1("two-people", 2),
                    SetEqualsExpectationV1("exact-ages", (row_19, row_22)),
                ),
            )
            .run()
        )
        self.assertIsInstance(rows_outcome, GoalPlanRunV1)
        assert isinstance(rows_outcome, GoalPlanRunV1)
        statuses = {
            item.expectation_id: item.status
            for item in rows_outcome.run.effective.canonical_result.expectation_outcomes
        }
        self.assertEqual(
            statuses,
            {
                "has-bob": "satisfied",
                "does-not-have-44": "not_satisfied",
                "any-person": "satisfied",
                "two-people": "satisfied",
                "exact-ages": "satisfied",
            },
        )
        count_outcome = (
            graph.query(_age_only_bundle(graph))
            .select("age", _address("target", "age"))
            .plan(result_mode="count")
            .run()
        )
        exists_outcome = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "nobody"}))
            .select("age", _address("target", "age"))
            .plan(result_mode="exists")
            .run()
        )
        self.assertIsInstance(count_outcome, GoalPlanRunV1)
        self.assertIsInstance(exists_outcome, GoalPlanRunV1)
        assert isinstance(count_outcome, GoalPlanRunV1)
        assert isinstance(exists_outcome, GoalPlanRunV1)
        self.assertEqual(count_outcome.run.effective.canonical_result.count_value, 2)
        self.assertEqual(exists_outcome.run.effective.canonical_result.exists_value, "false")
        self.assertEqual(
            exists_outcome.run.effective.canonical_result.summary_anchor.completeness,
            "complete",
        )
        self.assertEqual(rows_outcome.replay().status, "matched")
        self.assertEqual(count_outcome.replay().status, "matched")
        self.assertEqual(exists_outcome.replay().status, "matched")

    def test_invocation_splices_are_rejected_before_view_capture(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        _seed(graph, "bob", age=35, score=7)
        invocation = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .plan()
        )
        bob_compiled = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "bob"}))
            .select("age", _address("target", "age"))
            .compile()
        )
        outcome = replace(invocation, primary=bob_compiled).run()
        self.assertIsInstance(outcome, GoalPlanFailureV1)
        assert isinstance(outcome, GoalPlanFailureV1)
        self.assertEqual(outcome.code, "GOAL_INVOCATION_QUERY_SPLICE")
        self.assertEqual(outcome.assessment.contract_validity, "invalid")

        scope_outcome = replace(invocation, evidence_scope=EvidenceScopeV1(("asrt:ignored",))).run()
        self.assertIsInstance(scope_outcome, GoalPlanFailureV1)
        assert isinstance(scope_outcome, GoalPlanFailureV1)
        self.assertEqual(scope_outcome.code, "GOAL_INVOCATION_SCOPE_SPLICE")

        scenario = ScenarioSpecV1(
            (
                ScenarioSetEffectiveValueV1(
                    "alice-age-35",
                    EntityRef("Person", {"employee_id": "alice"}),
                    FieldPath("Person", "age"),
                    ScenarioValueV1("int", 35),
                ),
            )
        )
        scenario_invocation = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .plan(scenario=scenario)
        )
        changed_scenario = ScenarioSpecV1(
            (
                ScenarioSetEffectiveValueV1(
                    "alice-age-99",
                    EntityRef("Person", {"employee_id": "alice"}),
                    FieldPath("Person", "age"),
                    ScenarioValueV1("int", 99),
                ),
            )
        )
        scenario_outcome = replace(scenario_invocation, scenario=changed_scenario).run()
        self.assertIsInstance(scenario_outcome, GoalPlanFailureV1)
        assert isinstance(scenario_outcome, GoalPlanFailureV1)
        self.assertEqual(scenario_outcome.code, "GOAL_INVOCATION_SCENARIO_SPLICE")
        self.assertEqual(scenario_outcome.assessment.contract_validity, "invalid")

    def test_rejected_identity_mutation_is_a_typed_capability_failure(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        rejected = ScenarioSpecV1(
            (
                ScenarioSetEffectiveValueV1(
                    "cannot-rewrite-identity",
                    EntityRef("Person", {"employee_id": "alice"}),
                    FieldPath("Person", "employee_id"),
                    ScenarioValueV1("string", "eve"),
                ),
            )
        )
        outcome = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .plan(scenario=rejected)
            .run()
        )
        self.assertIsInstance(outcome, GoalPlanFailureV1)
        assert isinstance(outcome, GoalPlanFailureV1)
        self.assertEqual(outcome.code, "SCENARIO_PROTECTED_FIELD")
        self.assertEqual(outcome.assessment.scenario_resolution, "unsupported")
        self.assertEqual(outcome.assessment.execution, "unsupported")
        self.assertEqual(outcome.assessment.capability, "rejected")

    def test_view_change_during_capture_fails_closed_without_sealing_mixed_world(self) -> None:
        graph = SDKStore([Person])
        alice = _seed(graph, "alice", age=22, score=9)
        index = build_schema_index(graph.schema_ir)
        age_predicate = field_predicate(index, "Person", "age").pred_id
        invocation = (
            graph.query(_age_only_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .plan()
        )
        from factgraph.application.goal_plan_v1_runtime import project_view_facts_with_witness

        def capture_then_mutate(*args, **kwargs):
            captured = project_view_facts_with_witness(*args, **kwargs)
            set_field(graph.ledger, age_predicate, alice, [("int", 99)])
            return captured

        with patch(
            "factgraph.application.goal_plan_v1_runtime.project_view_facts_with_witness",
            side_effect=capture_then_mutate,
        ):
            outcome = invocation.run()
        self.assertIsInstance(outcome, GoalPlanFailureV1)
        assert isinstance(outcome, GoalPlanFailureV1)
        self.assertEqual(outcome.code, "GOAL_VIEW_CHANGED_DURING_CAPTURE")
