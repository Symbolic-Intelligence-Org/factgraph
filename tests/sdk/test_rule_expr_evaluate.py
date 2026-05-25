from __future__ import annotations

import unittest
import warnings
from unittest.mock import patch

import factgraph.sdk as sdk
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.protocol import EntitySelector, EvaluateResult, Explanation, Rule, RuleExprError, RuleExprInspect
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import AggregateAtom, CmpAtom, Const, PredAtom, Var
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
    def test_ruleexpr_native_evaluate_returns_evaluate_result(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "alice")
        rule = _person_exists_rule()
        region = _person_region_rule()
        expr = (rule.as_("exists") & region.as_("region")).join_by_ports("person")

        result = graph.eval.evaluate(expr, head=rule, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertIn(encoded, str(result[0].bindings))
        self.assertNotIn("occurrence_map", result[0].bindings)
        self.assertNotIn("join_materializations", result[0].bindings)
        self.assertRegex(result.result_id, r"^evalr_v1:[0-9a-f]{64}$")
        self.assertRegex(result.view_snapshot_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(result.result_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertIsNone(result.semantics_digest)
        self.assertFalse(hasattr(result[0], "candidate_id"))
        self.assertFalse(hasattr(result[0], "support_digest"))
        self.assertIsInstance(result[0].explain(), Explanation)
        self.assertFalse(hasattr(result[0], "close"))

    def test_application_rule_input_uses_c35_single_rule_coercion(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "bob")
        rule = _person_exists_rule()

        result = graph.eval.evaluate(rule, head=rule, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertIn(encoded, str(result[0].bindings))
        self.assertEqual(result.view_snapshot_digest, graph.eval.evaluate(rule, head=rule, engine="native").view_snapshot_digest)

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

    def test_external_head_filters_rows_and_evaluates(self) -> None:
        graph = _store()
        alice = _seed_person(graph, "alice", region="eu")
        _seed_person(graph, "bob", region="us")
        body = _person_region_rule("body_region")
        person = Var("$person")
        region = Var("$region")
        external_head = Rule(
            id="person:region",
            where=(
                PredAtom("Person:exists", [person]),
                PredAtom("person:region", [person, region]),
                CmpAtom("eq", region, Const("eu")),
            ),
            ports={"person": person, "region": region},
        )

        result = graph.eval.evaluate(body, head=external_head, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertIn(alice, str(result[0].bindings))
        self.assertNotIn("bob", str(result[0].bindings))

    def test_projection_head_evaluates_and_preserves_argument_order(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "erin", region="apac")
        rule = _person_region_rule()

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(rule, head=Rule.projection("region", "person"), engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertEqual(result.count(), 0)
        request = evaluate.call_args.args[0]
        self.assertEqual(request.plans[0].heads[0].head_var_names, ("$__projection_0", "$__projection_1"))
        self.assertIn("$__projection_0", repr(request.plans[0].body_ir))
        self.assertNotIn("__factgraph_projection_placeholder", repr(request.plans[0].body_ir))

        self.assertTrue(encoded)

    def test_projection_undeclared_port_uses_ruleexpr_error(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with self.assertRaisesRegex(RuleExprError, "is not declared by the RuleExpr"):
            graph.eval.evaluate(rule, head=Rule.projection("unknown"), engine="native")

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
            result = graph.eval.evaluate(rule, head=head, engine="native")

        self.assertTrue(result)
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
                    result = graph.eval.evaluate(rule, head=rule, engine=engine)

                self.assertIsInstance(result, EvaluateResult)
                self.assertEqual(result.count(), 0)
                request = evaluate.call_args.args[0]
                self.assertEqual(request.engine, engine)
                self.assertEqual(request.plans[0].engine_options, {})

    def test_evaluate_rejects_public_engine_options_and_registry(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with self.assertRaisesRegex(SDKStoreError, "engine_options"):
            graph.eval.evaluate(rule, head=rule, engine="native", engine_options={"timeout": 1})
        with self.assertRaisesRegex(SDKStoreError, "registry"):
            graph.eval.evaluate(rule, head=rule, engine="native", registry=object())

    def test_pyreason_pred_only_path_preflights_and_evaluates_when_supported(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(rule, head=rule, engine="pyreason")

        self.assertIsInstance(result, EvaluateResult)
        self.assertEqual(result.count(), 0)
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

    def test_legacy_inference_evaluation_returns_evaluate_result(self) -> None:
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

        result = graph.eval.evaluate(inference, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertTrue(all(not isinstance(row, CandidateSet) for row in result))

    def test_structured_derivation_dict_returns_evaluate_result(self) -> None:
        graph = _store()
        _seed_person(graph, "frank")
        with sdk.vars("p") as (p,):
            derivation = sdk.Inference(
                id="dict_inference",
                version="v1",
                where=[sdk.Pred("Person:exists", p)],
                target="Person:exists",
                head_vars=[p],
            ).to_authoring_payload()

        result = graph.eval.evaluate(derivation, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertEqual(result.head.id, "Person:exists")

    def test_direct_store_style_evaluate_fallback_is_rejected(self) -> None:
        graph = _store()

        with self.assertRaisesRegex(SDKStoreError, "direct Store.evaluate-style calls"):
            graph.eval.evaluate(
                derivation_id="legacy",
                version="v1",
                target_pred_id="Person:exists",
                head_vars=["$person"],
                where=[],
            )


if __name__ == "__main__":
    unittest.main()
