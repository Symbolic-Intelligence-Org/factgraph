from __future__ import annotations

from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from factgraph.application import build_resolved_rule, build_schema_index
from factgraph.application.protocol import (
    CompiledContainsRowExpectationV0,
    EntityRef,
    EntitySelector,
    EvaluationQueryFieldNavigationV0,
    FieldPath,
    Policy,
    PolicyAll,
    PolicyOccurrence,
    ProtocolShapeError,
    ResolvedExpectationValueV0,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.evaluation_query_runtime import _canonical_value
from factgraph.application.evaluation_query_target_runtime import (
    targeted_evaluation_query_wrapper_digest_v0,
)
from factgraph.application.captured_evaluation_query_run_runtime import (
    build_captured_evaluation_query_run_v0,
)
from factgraph.application.semantic_address_runtime import (
    SemanticAddressSpace,
    manage_rule_occurrence,
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


def _address(alias: str, port: str) -> SemanticPortAddress:
    return SemanticPortAddress(alias, port)


def _bundle(graph: SDKStore):
    index = build_schema_index(graph.schema_ir)
    person, age = Var("$person"), Var("$age")
    return build_resolved_rule(
        id="person_age_capture",
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


def _seed(graph: SDKStore, employee_id: str, age: int) -> str:
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
    return encoded


class CapturedEvaluationQueryRunV0Tests(unittest.TestCase):
    def _builder(self, graph: SDKStore):
        return (
            graph.query(_bundle(graph))
            .select("person", _address("target", "person"))
            .select("age", _address("target", "age"))
        )

    def test_capture_positive_roundtrip_verify_explain_and_live_compatibility(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", 22)
        _seed(graph, "bob", 22)
        query = (
            self._builder(graph)
            .expect_contains("both_ages", age=22)
            .expect_contains("alice", person=EntityRef("Person", {"employee_id": "alice"}))
        )
        targeted = query.compile()
        with self.assertRaisesRegex(SDKStoreError, "expectations do not support capture"):
            graph.eval.evaluate(targeted, capture="run_bundle_v0")

        captured = query.capture()
        self.assertEqual(
            tuple(item.status for item in captured.expectation_results),
            ("satisfied", "satisfied"),
        )
        self.assertEqual(len(captured.expectation_results[0].matched_row_ids), 2)
        self.assertNotIn("alice", repr(captured))
        decoded = type(captured).from_bytes(captured.to_bytes())
        self.assertEqual(decoded, captured)
        self.assertTrue(decoded.verify().matched)
        explanation = decoded.explain(row_capture_digest=decoded.bundle.rows[0].row_capture_digest)
        self.assertEqual(explanation.policy_projection.evaluation.root_state, "holds")

        _seed(graph, "carol", 19)
        with patch.object(graph._store, "evaluate_engine") as evaluator:
            self.assertTrue(decoded.verify().matched)
            decoded.explain(row_capture_digest=decoded.bundle.rows[0].row_capture_digest)
        evaluator.assert_not_called()

    def test_zero_row_and_nonmatching_expectation_have_no_negative_explain(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", 22)
        captured = (
            self._builder(graph)
            .bind(_address("target", "age"), 999)
            .expect_contains("missing", age=999)
            .capture()
        )
        self.assertEqual(captured.bundle.rows, ())
        self.assertEqual(captured.expectation_results[0].status, "not_satisfied")
        self.assertFalse(captured.expectation_results[0].matched_row_ids)
        with self.assertRaisesRegex(ProtocolShapeError, "row_capture_digest"):
            captured.explain(row_capture_digest="sha256:" + "0" * 64)

        observed = self._builder(graph).expect_contains("wrong", age=99).capture()
        self.assertEqual(observed.expectation_results[0].status, "not_satisfied")
        self.assertTrue(observed.bundle.rows)
        # A real positive row remains explainable; it is not evidence for the
        # failed observation.
        observed.explain(row_capture_digest=observed.bundle.rows[0].row_capture_digest)

    def test_navigation_and_direct_policy_retain_target_identity(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", 22)
        bundle = _bundle(graph)
        navigation = (
            graph.query(bundle)
            .bind(_address("target", "person"), EntityRef("Person", {"employee_id": "alice"}))
            .select(
                "age",
                EvaluationQueryFieldNavigationV0(
                    _address("target", "person"), FieldPath("Person", "age")
                ),
            )
            .expect_contains("age", age=22)
            .capture()
        )
        self.assertEqual(navigation.bundle.run_anchor.target.original_target_kind, "rule")
        self.assertEqual(navigation.expectation_results[0].status, "satisfied")

        space = SemanticAddressSpace((manage_rule_occurrence(bundle, "person"),))
        policy = Policy("person_policy", PolicyAll((PolicyOccurrence("person"),)))
        direct = (
            graph.query(policy, address_space=space)
            .select("age", _address("person", "age"))
            .expect_contains("age", age=22)
            .capture()
        )
        self.assertEqual(direct.bundle.run_anchor.target.original_target_kind, "policy")
        self.assertEqual(direct.bundle.run_anchor.target.target_id, "person_policy")

    def test_splices_and_codec_edges_fail_closed(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", 22)
        first = self._builder(graph).expect_contains("first", age=22).capture()
        second = self._builder(graph).expect_contains("second", age=22).capture()
        with self.assertRaisesRegex(ProtocolShapeError, "wrapper|outcome"):
            replace(first, expectations=second.expectations).verify()
        with self.assertRaisesRegex(ProtocolShapeError, "outcome"):
            replace(first, expectation_results=second.expectation_results).verify()
        with self.assertRaisesRegex(ProtocolShapeError, "outcomes|bundle"):
            replace(first, bundle=second.bundle).verify()

        raw = first.to_bytes()
        with self.assertRaises(ProtocolShapeError):
            type(first).from_bytes(raw.replace(b'"$type"', b'"$type","$type"', 1))
        with self.assertRaises(ProtocolShapeError):
            type(first).from_bytes(raw.replace(b'"unverified"', b"NaN", 1))
        payload = json.loads(raw)
        payload["fields"]["unexpected"] = True
        forged = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        with self.assertRaises(ProtocolShapeError):
            type(first).from_bytes(forged)

    def test_self_consistent_unselected_or_wrongly_typed_inventory_fails_closed(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", 22)
        captured = self._builder(graph).expect_contains("age", age=22).capture()
        for alias, value_type, raw_value in (
            ("ghost", "int", 22),
            ("age", "string", "22"),
        ):
            with self.subTest(alias=alias, value_type=value_type):
                canonical, value_digest = _canonical_value(value_type, raw_value)
                forged_expectation = CompiledContainsRowExpectationV0(
                    "forged",
                    captured.bundle.query_digest,
                    (ResolvedExpectationValueV0(alias, value_type, canonical, value_digest),),
                )
                wrapper = targeted_evaluation_query_wrapper_digest_v0(
                    captured.bundle.query_digest,
                    captured.bundle.run_anchor.target.target_digest,
                    (forged_expectation,),
                )
                with self.assertRaisesRegex(ProtocolShapeError, "aliases|type"):
                    build_captured_evaluation_query_run_v0(
                        bundle=captured.bundle,
                        targeted_query_wrapper_digest=wrapper,
                        expectations=(forged_expectation,),
                    )
                payload = json.loads(captured.to_bytes())
                payload["fields"]["expectations"] = [
                    {
                        "expectation_id": forged_expectation.expectation_id,
                        "query_digest": forged_expectation.query_digest,
                        "values": [
                            [
                                item.alias,
                                item.value_type,
                                item.normalized_value,
                                item.value_digest,
                            ]
                            for item in forged_expectation.values
                        ],
                        "kind": forged_expectation.kind,
                        "expectation_digest": forged_expectation.expectation_digest,
                    }
                ]
                payload["fields"]["targeted_query_wrapper_digest"] = wrapper
                payload["fields"]["expectation_results"] = []
                payload["fields"]["captured_query_run_digest"] = "sha256:" + "0" * 64
                forged_wire = json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
                with self.assertRaises(ProtocolShapeError):
                    type(captured).from_bytes(forged_wire)

    def test_capture_inventory_limit_rejects_before_execution_without_changing_evaluate(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", 22)
        query = self._builder(graph)
        for index in range(65):
            query = query.expect_contains(f"age-{index}", age=22)
        import factgraph.sdk.store as store_module

        ordinary = query.evaluate()
        self.assertEqual(len(ordinary.expectation_results), 65)
        with patch("factgraph.sdk.store.evaluate_derivation_plans", wraps=store_module.evaluate_derivation_plans) as evaluator:
            with self.assertRaisesRegex(SDKStoreError, "inventory exceeds"):
                query.capture()
        evaluator.assert_not_called()

    def test_capture_rejects_an_inventory_that_cannot_fit_its_durable_codec(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", 22)
        query = self._builder(graph)
        oversized_id = "x" * 20_000
        for index in range(64):
            query = query.expect_contains(f"{index}-{oversized_id}", age=22)
        with self.assertRaisesRegex(SDKStoreError, "maximum encoded size"):
            query.capture()

    def test_targeted_evaluate_and_capture_reject_a_restored_premise_policy(self) -> None:
        exclusion = MetaExclusion("provenance_class", frozenset({"untrusted"}))
        import factgraph.sdk.store as store_module

        ordinary = SDKStore([Person])
        _seed(ordinary, "alice", 22)
        targeted = self._builder(ordinary).compile()
        original_evaluate = store_module.evaluate_derivation_plans

        def restore_policy_after_evaluate(*args, **kwargs):
            outputs = original_evaluate(*args, **kwargs)
            ordinary.set_premise_exclusions(exclusion)
            ordinary.set_premise_exclusions(None)
            return outputs

        with patch(
            "factgraph.sdk.store.evaluate_derivation_plans",
            side_effect=restore_policy_after_evaluate,
        ), self.assertRaisesRegex(SDKStoreError, "premise policy changed"):
            ordinary.eval.evaluate(targeted)

        preflight = SDKStore([Person])
        _seed(preflight, "alice", 22)
        targeted = self._builder(preflight).compile()
        original_target_check = store_module.assert_targeted_evaluation_query_current
        target_check_calls = 0

        def restore_policy_after_first_target_check(value):
            nonlocal target_check_calls
            original_target_check(value)
            target_check_calls += 1
            if target_check_calls == 1:
                preflight.set_premise_exclusions(exclusion)
                preflight.set_premise_exclusions(None)

        with patch(
            "factgraph.sdk.store.assert_targeted_evaluation_query_current",
            side_effect=restore_policy_after_first_target_check,
        ), patch("factgraph.sdk.store.evaluate_derivation_plans") as evaluator, self.assertRaisesRegex(
            SDKStoreError,
            "premise policy changed",
        ):
            preflight.eval.evaluate(targeted)
        evaluator.assert_not_called()

        captured = SDKStore([Person])
        _seed(captured, "alice", 22)
        original_capture = store_module.build_captured_evaluation_query_run_v0

        def restore_policy_after_targeted_capture(*args, **kwargs):
            run = original_capture(*args, **kwargs)
            captured.set_premise_exclusions(exclusion)
            captured.set_premise_exclusions(None)
            return run

        with patch(
            "factgraph.sdk.store.build_captured_evaluation_query_run_v0",
            side_effect=restore_policy_after_targeted_capture,
        ), self.assertRaisesRegex(SDKStoreError, "premise policy changed"):
            self._builder(captured).capture()

    def test_targeted_evaluate_rechecks_after_final_target_integrity_check(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", 22)
        targeted = self._builder(graph).compile()
        exclusion = MetaExclusion("provenance_class", frozenset({"untrusted"}))
        import factgraph.sdk.store as store_module

        original_target_check = store_module.assert_targeted_evaluation_query_current
        target_check_calls = 0

        def restore_policy_after_final_target_check(value):
            nonlocal target_check_calls
            original_target_check(value)
            target_check_calls += 1
            if target_check_calls == 3:
                graph.set_premise_exclusions(exclusion)
                graph.set_premise_exclusions(None)

        with patch(
            "factgraph.sdk.store.assert_targeted_evaluation_query_current",
            side_effect=restore_policy_after_final_target_check,
        ), self.assertRaisesRegex(SDKStoreError, "premise policy changed"):
            graph.eval.evaluate(targeted)
        self.assertEqual(target_check_calls, 3)


if __name__ == "__main__":
    unittest.main()
