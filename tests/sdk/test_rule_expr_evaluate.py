from __future__ import annotations

import unittest
import warnings
from unittest.mock import patch

import factgraph.sdk as sdk
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.protocol import EntitySelector, Rule, RuleExprError, RuleExprInspect
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import AggregateAtom, CmpAtom, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity
from factgraph.sdk.store import SDKStoreError


class Person(Entity):
    name: str = Identity(primary_key=True)
    region: str = Field(cardinality="single")


def _store() -> sdk.SDKStore:
    return sdk.SDKStore([Person])


def _seed_person(graph: sdk.SDKStore, name: str, region: str = "us") -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(EntitySelector(entity_type="Person", identity={"name": name}), index=index)
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates["name"].pred_id, encoded, [("string", name)])
    set_field(graph.ledger, field_predicate(index, "Person", "region").pred_id, encoded, [("string", region)])
    return encoded


def _person_exists_rule(rule_id: str = "Person:exists") -> Rule:
    person = Var("$person")
    return Rule(id=rule_id, where=(PredAtom("Person:exists", [person]),), ports={"person": person})


def _person_region_rule(rule_id: str = "person_region") -> Rule:
    person = Var("$person")
    region = Var("$region")
    return Rule(
        id=rule_id,
        where=(PredAtom("Person:exists", [person]), PredAtom("person:region", [person, region])),
        ports={"person": person, "region": region},
    )


def _aggregate_rule() -> Rule:
    total = Var("$total")
    amount = Var("$amount")
    order = Var("$order")
    aggregate = AggregateAtom("sum", amount, [PredAtom("OrderAmount", [order, amount])])
    return Rule(id="amount_sum", where=(CmpAtom("eq", total, aggregate),), ports={"total": total})


class RuleExprEvaluatePublicDispatchTests(unittest.TestCase):
    def test_ruleexpr_native_evaluate_returns_candidate_sets(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "alice")
        rule = _person_exists_rule()
        region = _person_region_rule()
        expr = (rule.as_("exists") & region.as_("region")).join_by_ports("person")

        candidates = graph.eval.evaluate(expr, head=rule, engine="native")

        self.assertTrue(candidates)
        self.assertTrue(all(isinstance(candidate, CandidateSet) for candidate in candidates))
        self.assertIn(encoded, str(candidates[0].payload))
        self.assertNotIn("occurrence_map", candidates[0].payload)
        self.assertNotIn("join_materializations", candidates[0].payload)

    def test_application_rule_input_uses_c35_single_rule_coercion(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "bob")
        rule = _person_exists_rule()

        candidates = graph.eval.evaluate(rule, head=rule, engine="native")

        self.assertTrue(candidates)
        self.assertIn(encoded, str(candidates[0].payload))

    def test_missing_head_uses_sdk_store_error(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with self.assertRaisesRegex(SDKStoreError, "requires head="):
            graph.eval.evaluate(rule)

    def test_invalid_head_types_use_sdk_store_error(self) -> None:
        graph = _store()
        rule = _person_exists_rule()
        with sdk.vars("p") as (p,):
            legacy_rule = sdk.Rule(id="legacy", version="v1", select=[p], where=[sdk.Pred("Person:exists", p)])
            inference = sdk.Inference(
                id="legacy_inference",
                version="v1",
                where=[sdk.Pred("Person:exists", p)],
                target="Person:exists",
                head_vars=[p],
            )
        inspected = RuleExprInspect(ast=(), occurrences=(), joins=(), unjoined_same_name_ports=())

        for invalid in (legacy_rule, inference, {"head": "dict"}, "Person:exists", inspected):
            with self.subTest(invalid=type(invalid).__name__):
                with self.assertRaisesRegex(SDKStoreError, "head= must be application Rule"):
                    graph.eval.evaluate(rule, head=invalid)

    def test_external_head_rejects_with_guidance(self) -> None:
        graph = _store()
        body = _person_region_rule()
        external_head = _person_exists_rule()

        with self.assertRaisesRegex(SDKStoreError, "include the head rule as an expression occurrence"):
            graph.eval.evaluate(body, head=external_head)

    def test_same_id_version_mismatch_warns_and_evaluates(self) -> None:
        graph = _store()
        _seed_person(graph, "dana")
        person = Var("$person")
        rule = Rule(
            id="Person:exists",
            version="v1",
            where=(PredAtom("Person:exists", [person]),),
            ports={"person": person},
        )
        head = Rule(id=rule.id, version="v2", where=rule.where, ports=rule.ports)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            candidates = graph.eval.evaluate(rule, head=head, engine="native")

        self.assertTrue(candidates)
        self.assertEqual(len(caught), 1)
        self.assertIn("different version", str(caught[0].message))

    def test_same_id_different_digest_uses_ruleexpr_error(self) -> None:
        graph = _store()
        body = _person_exists_rule("same_id")
        head = _person_region_rule("same_id")

        with self.assertRaisesRegex(RuleExprError, "different content digest"):
            graph.eval.evaluate(body, head=head, engine="native")

    def test_same_name_ambiguity_uses_ruleexpr_error_before_evaluation(self) -> None:
        graph = _store()
        left = _person_exists_rule("left")
        right = _person_exists_rule("right")
        expr = left.as_("left") & right.as_("right")

        with self.assertRaisesRegex(RuleExprError, "ambiguous across occurrences"):
            graph.eval.evaluate(expr, head=left, engine="native")

    def test_souffle_and_problog_paths_use_existing_request_shape(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        for engine in ("souffle", "problog"):
            with self.subTest(engine=engine):
                with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
                    candidates = graph.eval.evaluate(rule, head=rule, engine=engine, engine_options={"timeout": 1})

                self.assertEqual(candidates, [])
                request = evaluate.call_args.args[0]
                self.assertEqual(request.engine, engine)
                self.assertEqual(request.plans[0].engine_options, {"timeout": 1})

    def test_pyreason_pred_only_path_preflights_and_evaluates_when_supported(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            candidates = graph.eval.evaluate(rule, head=rule, engine="pyreason")

        self.assertEqual(candidates, [])
        request = evaluate.call_args.args[0]
        self.assertEqual(request.engine, "pyreason")

    def test_pyreason_ruleexpr_join_rejection_uses_d9_message_fields(self) -> None:
        graph = _store()
        left = _person_region_rule("left_region")
        right = _person_region_rule("right_region")
        expr = (left.as_("left") & right.as_("right")).join_by_ports("person", "region")

        with self.assertRaises(SDKStoreError) as ctx:
            graph.eval.evaluate(expr, head=left, engine="pyreason")

        message = str(ctx.exception)
        self.assertIn("engine='pyreason'", message)
        self.assertIn("unsupported feature 'eq'", message)
        self.assertIn("ruleexpr-join", message)
        self.assertIn("native, souffle, problog", message)

    def test_pyreason_aggregate_rejection_uses_sdk_store_error(self) -> None:
        graph = _store()
        rule = _aggregate_rule()

        with self.assertRaisesRegex(SDKStoreError, "unsupported feature 'aggregate'"):
            graph.eval.evaluate(rule, head=rule, engine="pyreason")

    def test_legacy_inference_evaluation_still_uses_existing_path(self) -> None:
        graph = _store()
        _seed_person(graph, "carol")
        with sdk.vars("p") as (p,):
            inference = sdk.Inference(
                id="legacy_inference",
                version="v1",
                where=[sdk.Pred("Person:exists", p)],
                target="Person:exists",
                head_vars=[p],
            )

        candidates = graph.eval.evaluate(inference, engine="native")

        self.assertTrue(candidates)
        self.assertTrue(all(isinstance(candidate, CandidateSet) for candidate in candidates))


if __name__ == "__main__":
    unittest.main()
