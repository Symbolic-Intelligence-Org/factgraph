from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_evaluation_query,
    compile_policy,
    evaluation_run_bundle_evidence,
    manage_rule_occurrence,
    project_policy_explanation_v0,
    verify_evaluation_run_bundle,
)
from factgraph.application.evaluation_run_runtime import build_evaluation_run_anchor_v0
from factgraph.application.protocol import (
    EntityRef,
    EntitySelector,
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQuerySelection,
    FieldPath,
    Policy,
    PolicyOccurrence,
    ScenarioFieldSubstitutionV0,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.evaluate_result import DetachedRowError
from factgraph.application.schema_runtime import (
    entity_info,
    field_predicate,
    resolve_selector,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
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
    set_field(graph.ledger, info.identity_predicates["employee_id"].pred_id, encoded, [("string", employee_id)])
    set_field(graph.ledger, field_predicate(index, "Person", "age").pred_id, encoded, [("int", age)])
    set_field(graph.ledger, field_predicate(index, "Person", "score").pred_id, encoded, [("int", score)])
    return encoded


class UnifiedEvaluationQueryTests(unittest.TestCase):
    def test_rule_target_runs_captures_verifies_and_projects_evidence(self) -> None:
        graph = SDKStore([Person])
        alice = _seed(graph, "alice", age=22, score=9)
        bundle = _bundle(graph)
        compiled = (
            graph.query(bundle)
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("person", _address("target", "person"))
            .select("age", _address("target", "age"))
            .compile()
        )

        result = graph.eval.evaluate(compiled, capture="run_bundle_v0")
        self.assertEqual(dict(result[0].bindings)["person"], {"kind": "entity_ref", "value": alice})
        self.assertEqual(dict(result[0].bindings)["age"], {"kind": "literal", "tag": "int", "value": 22})
        assert result.run_anchor is not None and result.run_bundle is not None
        target = result.run_anchor.target
        self.assertEqual(target.original_target_kind, "rule")
        self.assertEqual(target.normalization_kind, "rule_lift_v0")
        self.assertEqual(target.target_id, bundle.rule.id)
        self.assertEqual(target.normalized_policy_id, "__factgraph_rule_lift__:person_values")
        self.assertEqual(tuple(pin.occurrence_alias for pin in target.rule_pins), ("target",))
        self.assertEqual(result.run_bundle.run_anchor, result.run_anchor)
        repeated = graph.eval.evaluate(compiled)
        assert repeated.run_anchor is not None
        self.assertEqual(
            repeated.run_anchor.target.target_digest,
            result.run_anchor.target.target_digest,
        )
        self.assertEqual(verify_evaluation_run_bundle(result.run_bundle).verdict, "matched_declared_runtime")

        capture_row = result.run_bundle.rows[0]
        evidence = evaluation_run_bundle_evidence(
            result.run_bundle,
            row_capture_digest=capture_row.row_capture_digest,
        )
        projection = project_policy_explanation_v0(
            result.run_anchor,
            evidence,
            semantic_row_anchor_digest=result.run_anchor.row_anchors[0].semantic_anchor_digest,
        )
        self.assertEqual(projection.policy_id, "__factgraph_rule_lift__:person_values")
        self.assertEqual(projection.evaluation.root_state, "holds")
        self.assertEqual(result[0].explain().status, "passed")

    def test_direct_policy_target_has_same_query_compiler_but_direct_anchor_identity(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        bundle = _bundle(graph)
        space = SemanticAddressSpace((manage_rule_occurrence(bundle, "person"),))
        policy = Policy("people", PolicyOccurrence("person"), version="3")
        from_builder = (
            graph.query(policy, address_space=space)
            .bind(_address("person", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("person", "age"))
            .compile()
        )
        direct_policy = compile_policy(policy, address_space=space)
        direct = compile_evaluation_query(
            EvaluationQuery(
                direct_policy.policy_digest,
                (EvaluationQuerySelection("age", _address("person", "age")),),
                (EvaluationQueryBinding(_address("person", "person"), EntityRef("Person", {"employee_id": "alice"})),),
            ),
            compiled_policy=direct_policy,
            address_space=space,
            schema_index=build_schema_index(graph.schema_ir),
        )
        self.assertEqual(from_builder.compiled_query.query_digest, direct.query_digest)
        self.assertEqual(from_builder.compiled_query._lowering_plan, direct._lowering_plan)
        result = graph.eval.evaluate(from_builder)
        assert result.run_anchor is not None
        self.assertEqual(result.run_anchor.target.original_target_kind, "policy")
        self.assertEqual(result.run_anchor.target.normalization_kind, "policy_direct_v0")
        self.assertEqual(result.run_anchor.target.target_id, "people")

    def test_builder_forwards_narrow_scenario_without_creating_evidence(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        compiled = (
            graph.query(_bundle(graph))
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select("age", _address("target", "age"))
            .compile()
        )
        scenario = ScenarioFieldSubstitutionV0(
            EntityRef("Person", {"employee_id": "alice"}),
            FieldPath("Person", "age"),
            35,
            "review-age-hypothesis",
        )
        result = graph.query(compiled.target).bind(
            _address("target", "person"), EntityRef("Person", {"employee_id": "alice"})
        ).select("age", _address("target", "age")).evaluate(scenario=scenario)
        self.assertEqual(dict(result[0].bindings)["age"]["value"], 35)
        self.assertIsNone(result.run_anchor)
        self.assertIsNone(result.run_bundle)
        assert result.scenario is not None
        with self.assertRaises(DetachedRowError):
            result[0].close()
        self.assertEqual(result[0].explain().status, "unsupported")
        with self.assertRaisesRegex(SDKStoreError, "does not support capture"):
            graph.eval.evaluate(compiled, scenario=scenario, capture="run_bundle_v0")

    def test_builder_contains_expectation_observes_rows_without_changing_query(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        base = (
            graph.query(_bundle(graph))
            .select("age", _address("target", "age"))
        )
        ordinary = base.compile()
        expected = base.expect_contains("alice_age", age=22).compile()
        self.assertEqual(ordinary.compiled_query.query_digest, expected.compiled_query.query_digest)
        self.assertEqual(ordinary.compiled_query._lowering_plan, expected.compiled_query._lowering_plan)
        self.assertNotEqual(ordinary.wrapper_digest, expected.wrapper_digest)

        result = graph.eval.evaluate(expected)
        self.assertEqual(len(result.expectation_results), 1)
        outcome = result.expectation_results[0]
        self.assertEqual(outcome.status, "satisfied")
        self.assertEqual(outcome.completeness_basis, "complete_native_enumeration_v0")
        self.assertEqual(outcome.matched_row_ids, (result[0].row_id,))
        self.assertIsNotNone(result.run_anchor)
        assert result.run_anchor is not None
        self.assertEqual(outcome.run_anchor_digest, result.run_anchor.anchor_digest)
        self.assertEqual(result.run_anchor.summary.completeness, "unknown")

    def test_builder_contains_expectation_complete_non_match_and_rejections(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        expected = (
            graph.query(_bundle(graph))
            .select("age", _address("target", "age"))
            .expect_contains("missing_age", age=19)
            .compile()
        )
        result = graph.eval.evaluate(expected)
        self.assertEqual(result.expectation_results[0].status, "not_satisfied")
        self.assertEqual(result.expectation_results[0].matched_row_ids, ())
        with self.assertRaisesRegex(SDKStoreError, "not support capture"):
            graph.eval.evaluate(expected, capture="run_bundle_v0")
        scenario = ScenarioFieldSubstitutionV0(
            EntityRef("Person", {"employee_id": "alice"}),
            FieldPath("Person", "age"),
            19,
            "hypothesis",
        )
        with self.assertRaisesRegex(SDKStoreError, "not support scenario"):
            graph.eval.evaluate(expected, scenario=scenario)
        with self.assertRaisesRegex(SDKStoreError, "selected"):
            graph.query(_bundle(graph)).select("age", _address("target", "age")).expect_contains(
                "bad-alias", missing=19
            ).compile()
        with self.assertRaisesRegex(SDKStoreError, "non-empty"):
            graph.query(_bundle(graph)).expect_contains("not-exists").compile()
        with self.assertRaisesRegex(SDKStoreError, "unique"):
            graph.query(_bundle(graph)).select("age", _address("target", "age")).expect_contains(
                "duplicate", age=22
            ).expect_contains("duplicate", age=19).compile()

    def test_expectation_wrapper_splice_fails_before_engine(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        expected = (
            graph.query(_bundle(graph))
            .select("age", _address("target", "age"))
            .expect_contains("alice_age", age=22)
            .compile()
        )
        object.__setattr__(expected.expectations[0], "query_digest", "0" * 64)
        with patch("factgraph.sdk.store.evaluate_derivation_plans") as evaluator:
            with self.assertRaisesRegex(SDKStoreError, "integrity check"):
                graph.eval.evaluate(expected)
        evaluator.assert_not_called()

    def test_expectation_outcome_splice_is_rejected_by_result_validation(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        expected = (
            graph.query(_bundle(graph))
            .select("age", _address("target", "age"))
            .expect_contains("alice_age", age=22)
            .compile()
        )
        result = graph.eval.evaluate(expected)
        outcome = result.expectation_results[0]
        object.__setattr__(outcome, "result_digest", "sha256:" + "0" * 64)
        with self.assertRaisesRegex(ValueError, "outcome_digest"):
            replace(result, expectation_results=(outcome,))

    def test_invalid_targets_and_addresses_fail_before_evaluator(self) -> None:
        graph = SDKStore([Person])
        bundle = _bundle(graph)
        with self.assertRaisesRegex(SDKStoreError, "bare Rules"):
            graph.query(bundle.rule)
        with self.assertRaisesRegex(SDKStoreError, "address_space"):
            graph.query(Policy("p", PolicyOccurrence("x")))
        builder = graph.query(bundle)
        with self.assertRaisesRegex(SDKStoreError, "binding address"):
            builder.bind("target.age", 22)  # type: ignore[arg-type]
        with patch("factgraph.sdk.store.evaluate_derivation_plans") as evaluator:
            with self.assertRaisesRegex(SDKStoreError, "compilation rejected"):
                builder.select("age", _address("target", "missing")).evaluate()
        evaluator.assert_not_called()

    def test_target_wrapper_integrity_is_checked_before_execution(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        compiled = (
            graph.query(_bundle(graph))
            .select("age", _address("target", "age"))
            .compile()
        )
        object.__setattr__(compiled, "wrapper_digest", "sha256:" + "0" * 64)
        with patch("factgraph.sdk.store.evaluate_derivation_plans") as evaluator:
            with self.assertRaisesRegex(SDKStoreError, "integrity check"):
                graph.eval.evaluate(compiled)
        evaluator.assert_not_called()
        with self.assertRaisesRegex(SDKStoreError, "does not accept TargetedCompiledEvaluationQueryV0"):
            graph.eval.evaluate_candidates(compiled)
        with self.assertRaisesRegex(SDKStoreError, "does not accept TargetedCompiledEvaluationQueryV0"):
            graph.eval.explain(compiled)

    def test_direct_anchor_helper_revalidates_source_target_seal(self) -> None:
        graph = SDKStore([Person])
        compiled = graph.query(_bundle(graph)).select("age", _address("target", "age")).compile()
        result = graph.eval.evaluate(compiled.compiled_query)
        object.__setattr__(compiled.target.run_target, "target_digest", "sha256:" + "0" * 64)
        with self.assertRaisesRegex(ValueError, "target_digest"):
            build_evaluation_run_anchor_v0(
                compiled.compiled_query,
                replace(result, run_anchor=None),
                source_target=compiled.target.run_target,
            )
