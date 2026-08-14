"""SDK-level product outcome facade coverage for one sealed V2 run."""

from __future__ import annotations

import unittest

from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.semantic_port import entity_identity, field_endpoint
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import (
    AssetMeta,
    Entity,
    Field,
    Identity,
    ProductEvaluationOutcomeErrorV2,
    ProductEvaluationOutcomeV2,
    SDKStore,
    outcome_from_run_v2,
)


class Person(Entity):
    person_id: str = Identity()
    age: int = Field()


def _rule(graph: SDKStore):
    person, age = Var("$person"), Var("$age")
    return graph.build_rule(
        id="person_values",
        version="1",
        meta=AssetMeta(name="Person values"),
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
        ),
        ports={"person": person, "age": age},
        semantic_ports={
            "person": entity_identity("Person"),
            "age": field_endpoint("Person", "age"),
        },
    )


def _sealed_run():
    graph = SDKStore([Person])
    alice = graph.entities.create(Person, person_id="alice")
    set_field(graph.ledger, "person:age", alice, [("int", 20)])
    rule = _rule(graph)
    profile = graph.execution.native_deterministic(target=rule).build()
    scenario = graph.scenario().set(Person.age, alice, 34, premise_id="adjusted-age").build()
    return (
        graph.query(rule)
        .select("age", SemanticPortAddress("target", "age"))
        .plan(profile=profile, scenario=scenario)
        .run()
    )


class ProductEvaluationOutcomeV2Tests(unittest.TestCase):
    def test_raw_run_factory_exposes_named_views_explicit_explain_and_replay(self) -> None:
        run = _sealed_run()
        outcome = outcome_from_run_v2(run)

        self.assertIsInstance(outcome, ProductEvaluationOutcomeV2)
        self.assertIs(outcome.run, run)
        self.assertEqual(outcome.baseline.rows[0].values[0].value, 20)
        self.assertEqual(outcome.effective.rows[0].values[0].value, 34)
        self.assertIsNone(outcome.candidate_effective)
        self.assertFalse(hasattr(outcome.effective.rows[0], "close"))

        data_from_row = outcome.explain(outcome.effective.rows[0])
        data_from_target = outcome.explain(outcome.effective.rows[0].to_explain_target())
        self.assertEqual(
            data_from_row.identity.target_observation_digest,
            data_from_target.identity.target_observation_digest,
        )
        self.assertEqual(data_from_row.outcome.logical_conclusion, "not_claimed")
        self.assertEqual(data_from_row.evidence.state, "not_available")
        self.assertEqual(outcome.replay().status, "matched")

    def test_facade_rejects_boolean_and_implicit_or_foreign_explain_requests(self) -> None:
        outcome = ProductEvaluationOutcomeV2.from_run(_sealed_run())

        with self.assertRaises(ProductEvaluationOutcomeErrorV2) as boolean:
            bool(outcome)
        self.assertEqual(boolean.exception.code, "PRODUCT_OUTCOME_V2_BOOLEAN_UNSUPPORTED")

        with self.assertRaises(ProductEvaluationOutcomeErrorV2) as implicit:
            outcome.explain("first")  # type: ignore[arg-type]
        self.assertEqual(implicit.exception.code, "PRODUCT_OUTCOME_V2_EXPLAIN_TARGET_INVALID")

        other = ProductEvaluationOutcomeV2.from_run(_sealed_run())
        with self.assertRaises(ProductEvaluationOutcomeErrorV2) as foreign:
            outcome.explain(other.effective.rows[0])
        self.assertEqual(foreign.exception.code, "PRODUCT_OUTCOME_V2_EXPLAIN_TARGET_INVALID")

    def test_facade_rejects_nested_frame_row_mutation_under_stale_run_seal(self) -> None:
        run = _sealed_run()
        observation = run.effective.engine_frames[0].observations[0]
        object.__setattr__(observation, "values", ())

        with self.assertRaises(ProductEvaluationOutcomeErrorV2) as caught:
            outcome_from_run_v2(run)
        self.assertEqual(caught.exception.code, "PRODUCT_OUTCOME_V2_RUN_INVALID")


if __name__ == "__main__":
    unittest.main()
