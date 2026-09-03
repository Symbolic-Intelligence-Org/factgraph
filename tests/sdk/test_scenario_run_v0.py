from __future__ import annotations

import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    manage_rule_occurrence,
)
from factgraph.application.protocol import (
    EntityRef,
    EntitySelector,
    FieldPath,
    Policy,
    PolicyAll,
    PolicyCompare,
    PolicyFieldNavigation,
    PolicyOccurrence,
    ProtocolShapeError,
    ScenarioFieldSubstitutionSetV0,
    ScenarioFieldSubstitutionV0,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.schema_runtime import (
    entity_info,
    field_predicate,
    resolve_selector,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.store.premise_filter import MetaExclusion
from factgraph.sdk import Entity, Field, Identity, SDKStore
from factgraph.sdk.errors import SDKStoreError


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    score: int = Field()


def _address(alias: str, port: str) -> SemanticPortAddress:
    return SemanticPortAddress(alias, port)


def _bundle(graph: SDKStore):
    index = build_schema_index(graph.schema_ir)
    person, age, score = Var("$person"), Var("$age"), Var("$score")
    return build_resolved_rule(
        id="person_values",
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


def _seed(graph: SDKStore, employee_id: str, *, age: int, score: int) -> str:
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
    set_field(graph.ledger, field_predicate(index, "Person", "age").pred_id, encoded, [("int", age)])
    set_field(
        graph.ledger,
        field_predicate(index, "Person", "score").pred_id,
        encoded,
        [("int", score)],
    )
    return encoded


def _scenario(employee_id: str, field: str, value: object, premise_id: str) -> ScenarioFieldSubstitutionV0:
    return ScenarioFieldSubstitutionV0(
        EntityRef("Person", {"employee_id": employee_id}),
        FieldPath("Person", field),
        value,
        premise_id,
    )


def _support_state(graph: SDKStore) -> tuple[object, ...]:
    store = graph._store
    return (
        dict(store._support_artifacts),
        dict(store._candidate_support_index),
        dict(store._candidate_support_kind_index),
        dict(store._candidate_confidence_kind_index),
        dict(store._candidate_pred_index),
    )


def _all_sources(explanation: object) -> list[object]:
    evidence = explanation.evidence
    return [
        source
        for tree in evidence.paths
        for rule in tree.rules
        for atom in rule.atoms
        for source in getattr(atom.verdict, "support", ())
    ]


class ScenarioRunV0Tests(unittest.TestCase):
    def test_rule_builder_captures_detached_evidence_and_never_writes_store_support(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        query = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
        )
        claims_before = tuple(graph.ledger.find_claims())
        support_before = _support_state(graph)

        import factgraph.sdk.store as store_module

        with patch(
            "factgraph.sdk.store._evaluate_derivation_plans_with_native_effective_relation_capture",
            wraps=store_module._evaluate_derivation_plans_with_native_effective_relation_capture,
        ) as evaluator, patch.object(
            graph._store,
            "_remember_support_artifact",
            wraps=graph._store._remember_support_artifact,
        ) as remember_artifact, patch.object(
            graph._store,
            "_remember_candidate_support",
            wraps=graph._store._remember_candidate_support,
        ) as remember_candidate:
            run = query.what_if(_scenario("alice", "age", 35, "alice-age")).run()

        self.assertEqual(evaluator.call_count, 2)
        self.assertIs(evaluator.call_args_list[0].args[0].plans[0], evaluator.call_args_list[1].args[0].plans[0])
        remember_artifact.assert_not_called()
        remember_candidate.assert_not_called()
        self.assertEqual(tuple(graph.ledger.find_claims()), claims_before)
        self.assertEqual(_support_state(graph), support_before)
        self.assertEqual(run.plan.scenario_kind, "single_field_replacement")
        self.assertEqual(run.plan.premise_bindings[0].baseline_value.value, 22)
        self.assertEqual(run.plan.premise_bindings[0].effective_value.value, 35)
        self.assertTrue(run.diff().result_changed)
        self.assertEqual(dict(run.baseline.rows[0].values)["age"].value, 22)
        self.assertEqual(dict(run.effective.rows[0].values)["age"].value, 35)
        self.assertTrue(run.verify().matched)

        explanation = run.explain(
            side="effective", row_capture_digest=run.effective.rows[0].row_capture_digest
        )
        self.assertEqual(explanation.policy_projection.evaluation.root_state, "holds")
        sources = _all_sources(explanation)
        self.assertIn("scenario_hypothesis", {item.meta["role"] for item in sources})
        hypothesis = next(item for item in sources if item.meta["role"] == "scenario_hypothesis")
        self.assertFalse(hypothesis.meta["ledger_backed_at_capture"])
        self.assertEqual(hypothesis.meta["premise_id"], "alice-age")
        self.assertNotIn("captured_witness", {item.meta["role"] for item in sources})

        baseline = run.explain(
            side="baseline", row_capture_digest=run.baseline.rows[0].row_capture_digest
        )
        baseline_roles = {item.meta["role"] for item in _all_sources(baseline)}
        self.assertIn("captured_baseline_relation_witness", baseline_roles)
        self.assertNotIn("scenario_hypothesis", baseline_roles)

    def test_codec_roundtrip_is_detached_and_rejects_f4_decode_and_cross_run_splice(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        builder = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
        )
        run = builder.what_if(_scenario("alice", "age", 35, "first")).run()
        decoded = type(run).from_bytes(run.to_bytes())
        self.assertEqual(decoded, run)
        self.assertTrue(decoded.verify().matched)
        self.assertEqual(decoded.diff(), run.diff())
        with self.assertRaises(ProtocolShapeError):
            from factgraph.application import evaluation_run_bundle_from_bytes

            evaluation_run_bundle_from_bytes(run._effective_capture_bytes)

        other = builder.what_if(_scenario("alice", "age", 36, "second")).run()
        with self.assertRaisesRegex(ProtocolShapeError, "capture bytes"):
            replace(run, _effective_capture_bytes=other._effective_capture_bytes)

        forged_diff = replace(run, result_diff=other.result_diff)
        with self.assertRaisesRegex(ProtocolShapeError, "result diff"):
            forged_diff.diff()

        # The strict outer codec must reject a byte-level hybrid too, rather
        # than relying only on in-process dataclass construction checks.
        raw_fields = json.loads(run.to_bytes())
        other_fields = json.loads(other.to_bytes())
        raw_fields["fields"]["effective_capture"] = other_fields["fields"]["effective_capture"]
        hybrid = json.dumps(
            raw_fields,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        with self.assertRaises(ProtocolShapeError):
            type(run).from_bytes(hybrid)
        with self.assertRaises(ProtocolShapeError):
            type(run).from_bytes(b"{")

    def test_detached_explain_and_verify_do_not_consult_live_store_after_capture(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        run = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .what_if(_scenario("alice", "age", 35, "alice-age"))
            .run()
        )
        payload = run.to_bytes()
        decoded = type(run).from_bytes(payload)
        _seed(graph, "bob", age=19, score=7)
        with patch.object(graph._store, "evaluate_engine") as evaluator:
            self.assertTrue(decoded.verify().matched)
            explanation = decoded.explain(
                side="effective", row_capture_digest=decoded.effective.rows[0].row_capture_digest
            )
        evaluator.assert_not_called()
        self.assertEqual(explanation.policy_projection.evaluation.root_state, "holds")

    def test_view_change_between_captured_sides_fails_closed_before_effective_execution(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        query = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
        )

        import factgraph.sdk.store as store_module

        original = store_module._evaluate_derivation_plans_with_native_effective_relation_capture
        calls = 0

        def mutate_after_baseline(*args: object, **kwargs: object) -> object:
            nonlocal calls
            value = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                _seed(graph, "alice", age=22, score=10)
            return value

        with patch(
            "factgraph.sdk.store._evaluate_derivation_plans_with_native_effective_relation_capture",
            side_effect=mutate_after_baseline,
        ) as evaluator, self.assertRaisesRegex(SDKStoreError, "view changed"):
            query.what_if(_scenario("alice", "age", 35, "alice-age")).run()

        self.assertEqual(evaluator.call_count, 1)

    def test_run_scenario_rejects_a_restored_premise_policy(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        query = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
        )
        exclusion = MetaExclusion("provenance_class", frozenset({"untrusted"}))
        import factgraph.sdk.store as store_module

        original = store_module.build_scenario_run_v0

        def restore_policy_after_run_build(*args, **kwargs):
            run = original(*args, **kwargs)
            graph.set_premise_exclusions(exclusion)
            graph.set_premise_exclusions(None)
            return run

        with patch(
            "factgraph.sdk.store.build_scenario_run_v0",
            side_effect=restore_policy_after_run_build,
        ), self.assertRaisesRegex(SDKStoreError, "premise policy changed"):
            query.what_if(_scenario("alice", "age", 35, "alice-age")).run()

    def test_run_scenario_entry_pin_rejects_preflight_aba_before_capture(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        query = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
        )
        exclusion = MetaExclusion("provenance_class", frozenset({"untrusted"}))
        original = graph._assert_evaluation_query_artifact_current

        def restore_policy_after_artifact_check(compiled_query):
            original(compiled_query)
            graph.set_premise_exclusions(exclusion)
            graph.set_premise_exclusions(None)

        with patch.object(
            graph,
            "_assert_evaluation_query_artifact_current",
            side_effect=restore_policy_after_artifact_check,
        ), patch(
            "factgraph.sdk.store._evaluate_derivation_plans_with_native_effective_relation_capture"
        ) as evaluator, self.assertRaisesRegex(SDKStoreError, "premise policy changed"):
            query.what_if(_scenario("alice", "age", 35, "alice-age")).run()
        evaluator.assert_not_called()

    def test_targeted_run_scenario_rechecks_after_final_target_integrity_check(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        targeted = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .compile()
        )
        exclusion = MetaExclusion("provenance_class", frozenset({"untrusted"}))
        import factgraph.sdk.store as store_module

        original_target_check = store_module.assert_targeted_evaluation_query_current
        target_check_calls = 0

        def restore_policy_after_final_target_check(value):
            nonlocal target_check_calls
            original_target_check(value)
            target_check_calls += 1
            if target_check_calls == 5:
                graph.set_premise_exclusions(exclusion)
                graph.set_premise_exclusions(None)

        with patch(
            "factgraph.sdk.store.assert_targeted_evaluation_query_current",
            side_effect=restore_policy_after_final_target_check,
        ), self.assertRaisesRegex(SDKStoreError, "premise policy changed"):
            graph.eval.run_scenario(targeted, _scenario("alice", "age", 35, "alice-age"))
        self.assertEqual(target_check_calls, 5)

    def test_atomic_set_same_value_and_zero_result_remain_explicit(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        _seed(graph, "bob", age=19, score=7)
        builder = (
            graph.query(_bundle(graph))
            .select("person", _address("target", "person"))
            .select("age", _address("target", "age"))
            .select("score", _address("target", "score"))
        )
        run = builder.what_if(
            ScenarioFieldSubstitutionSetV0(
                (
                    _scenario("alice", "age", 22, "same-age"),
                    _scenario("bob", "score", 11, "bob-score"),
                )
            )
        ).run()
        self.assertEqual(run.plan.scenario_kind, "atomic_field_replacement_set")
        self.assertFalse(run.plan.premise_bindings[0].semantic_value_changed)
        self.assertTrue(run.diff().result_changed)
        self.assertTrue(run.verify().matched)

        zero = (
            graph.query(_bundle(graph))
            .bind(_address("target", "score"), 999)
            .select("age", _address("target", "age"))
            .what_if(_scenario("alice", "age", 35, "zero-age"))
            .run()
        )
        self.assertEqual((len(zero.baseline.rows), len(zero.effective.rows)), (0, 0))
        self.assertFalse(zero.diff().result_changed)
        self.assertTrue(zero.verify().matched)
        with self.assertRaisesRegex(ProtocolShapeError, "row_capture_digest"):
            zero.explain(side="effective", row_capture_digest="sha256:" + "0" * 64)

    def test_direct_policy_navigation_and_comparison_share_scenario_run_path(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        _seed(graph, "bob", age=19, score=7)
        bundle = _bundle(graph)
        space = SemanticAddressSpace(
            (manage_rule_occurrence(bundle, "older"), manage_rule_occurrence(bundle, "younger"))
        )
        policy = Policy(
            "older_pair",
            PolicyAll(
                (
                    PolicyOccurrence("older"),
                    PolicyOccurrence("younger"),
                    PolicyCompare.gt(
                        PolicyFieldNavigation(_address("older", "person"), FieldPath("Person", "age")),
                        PolicyFieldNavigation(_address("younger", "person"), FieldPath("Person", "age")),
                    ),
                )
            ),
        )
        run = (
            graph.query(policy, address_space=space)
            .select("older_age", _address("older", "age"))
            .select("younger_age", _address("younger", "age"))
            .what_if(_scenario("alice", "age", 10, "alice-age"))
            .run()
        )
        self.assertEqual(
            {(dict(row.values)["older_age"].value, dict(row.values)["younger_age"].value) for row in run.baseline.rows},
            {(22, 19)},
        )
        self.assertEqual(
            {(dict(row.values)["older_age"].value, dict(row.values)["younger_age"].value) for row in run.effective.rows},
            {(19, 10)},
        )
        projection = run.explain(
            side="baseline", row_capture_digest=run.baseline.rows[0].row_capture_digest
        ).policy_projection
        comparison = next(node for node in projection.evaluation.nodes if node.kind == "compare")
        self.assertEqual(comparison.state, "holds")

    def test_run_scenario_rejects_expectations_and_unsupported_execution_contexts(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        scenario = _scenario("alice", "age", 35, "alice-age")
        expected = (
            graph.query(_bundle(graph))
            .select("age", _address("target", "age"))
            .expect_contains("age", age=22)
            .compile()
        )
        with self.assertRaisesRegex(SDKStoreError, "does not support expectations"):
            graph.eval.run_scenario(expected, scenario)
        with self.assertRaisesRegex(SDKStoreError, "does not support expect_contains"):
            (
                graph.query(_bundle(graph))
                .select("age", _address("target", "age"))
                .expect_contains("age", age=22)
                .what_if(scenario)
            )


if __name__ == "__main__":
    unittest.main()
