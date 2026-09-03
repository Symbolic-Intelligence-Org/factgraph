from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from factgraph.application.goal_plan_v2_runtime import ProductEvaluationRuntimeErrorV2
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.semantic_port import entity_identity, field_endpoint
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import (
    AssetMeta,
    Entity,
    Field,
    Identity,
    SDKStore,
    SemanticCandidateRuntimeError,
    SemanticCandidateShapeError,
    SemanticValueCandidateBatchRequestV1,
    SemanticValueCandidateRequestV1,
)


class Person(Entity):
    person_id: str = Identity()
    name: str = Field()
    age: int = Field()
    score: float = Field()
    enabled: bool = Field()
    labels: list[str] = Field()


class Composite(Entity):
    first: str = Identity()
    second: str = Identity()


def _graph():
    graph = SDKStore([Person, Composite])
    alice = graph.entities.create(Person, person_id="Alice")
    for name, domain, value in (
        ("name", "string", "Alice"),
        ("age", "int", 20),
        ("score", "float64", 1.5),
        ("enabled", "bool", True),
    ):
        set_field(graph.ledger, f"person:{name}", alice, [(domain, value)])
    return graph, alice


def _request(value="alice", endpoint=None, mode="unicode_casefold_v1"):
    return SemanticValueCandidateBatchRequestV1(
        (
            SemanticValueCandidateRequestV1(
                "person", endpoint or entity_identity("Person"), value, mode
            ),
        )
    )


class SemanticCandidateTests(unittest.TestCase):
    def test_exact_and_normalized_and_evidence_are_deterministic(self):
        graph, _ = _graph()
        request = _request("  ALICE  ")
        result = graph.resolve_semantic_candidates(request)
        self.assertEqual(result.items[0].normalized_matches, ("Alice",))
        self.assertEqual(result, graph.resolve_semantic_candidates(request))
        self.assertEqual(result.request_digest, request.request_digest)
        self.assertEqual(len(result.evidence_digest), 71)
        self.assertEqual(
            graph.resolve_semantic_candidates(_request("Alice")).items[0].exact_matches, ("Alice",)
        )

    def test_ambiguous_and_exact_priority(self):
        graph, _ = _graph()
        graph.entities.create(Person, person_id="ALICE")
        result = graph.resolve_semantic_candidates(_request())
        self.assertEqual(result.items[0].normalized_matches, ("ALICE", "Alice"))
        exact = graph.resolve_semantic_candidates(_request("Alice")).items[0]
        self.assertEqual(exact.exact_matches, ("Alice",))
        self.assertEqual(exact.normalized_matches, ())

    def test_prefix_suggestions_are_not_matches_and_are_bounded(self):
        graph, _ = _graph()
        for value in ("Alicia", "Alina", "Alison", "Alistair", "Alix", "Alma"):
            graph.entities.create(Person, person_id=value)
        result = graph.resolve_semantic_candidates(_request("ali")).items[0]
        self.assertEqual(result.exact_matches, ())
        self.assertEqual(result.normalized_matches, ())
        self.assertEqual(len(result.suggestions), 5)
        self.assertTrue(result.suggestions_truncated)
        missing = graph.resolve_semantic_candidates(_request("missing")).items[0]
        self.assertEqual(missing.suggestions, ())

    def test_unicode_normalization(self):
        graph, _ = _graph()
        graph.entities.create(Person, person_id="Élodie")
        self.assertEqual(
            graph.resolve_semantic_candidates(_request(" E\u0301LODIE "))
            .items[0]
            .normalized_matches,
            ("Élodie",),
        )

    def test_batch_uses_one_view_and_distinct_scalar_values(self):
        graph, _ = _graph()
        other = graph.entities.create(Person, person_id="Bob")
        set_field(graph.ledger, "person:name", other, [("string", "Alice")])
        items = tuple(
            SemanticValueCandidateRequestV1(name, field_endpoint("Person", name), value, mode)
            for name, value, mode in (
                ("name", "alice", "unicode_casefold_v1"),
                ("age", 20, "exact"),
                ("score", 1.5, "exact"),
                ("enabled", True, "exact"),
            )
        )
        result = graph.resolve_semantic_candidates(SemanticValueCandidateBatchRequestV1(items))
        self.assertEqual(result.items[0].normalized_matches, ("Alice",))
        self.assertEqual(result.items[1].exact_matches, (20,))
        self.assertEqual(result.items[2].exact_matches, (1.5,))
        self.assertEqual(result.items[3].exact_matches, (True,))
        self.assertNotIn("idref_v1:", repr(result))

    def test_type_and_endpoint_validation(self):
        graph, _ = _graph()
        for request in (
            _request(True, field_endpoint("Person", "age"), "exact"),
            _request("a", entity_identity("Composite")),
            _request("a", field_endpoint("Person", "labels")),
        ):
            with self.subTest(request=request), self.assertRaises(SemanticCandidateRuntimeError):
                graph.resolve_semantic_candidates(request)
        with self.assertRaises(SemanticCandidateShapeError):
            SemanticValueCandidateBatchRequestV1((_request().items[0], _request().items[0]))

    def test_view_change_during_capture_fails(self):
        graph, _ = _graph()
        with (
            patch.object(
                graph,
                "_view_snapshot_digest",
                side_effect=["sha256:" + "a" * 64, "sha256:" + "b" * 64],
            ),
            self.assertRaises(SemanticCandidateRuntimeError) as raised,
        ):
            graph.resolve_semantic_candidates(_request())
        self.assertEqual(raised.exception.code, "VIEW_CHANGED_DURING_CANDIDATE_CAPTURE")

    def test_expected_view_guard_stops_before_world_capture(self):
        graph, alice = _graph()
        candidates = graph.resolve_semantic_candidates(_request())
        person, age = Var("$person"), Var("$age")
        rule = graph.build_rule(
            id="ages",
            version="1",
            meta=AssetMeta(name="Ages"),
            when=(PredAtom("Person:exists", [person]), PredAtom("person:age", [person, age])),
            ports={"person": person, "age": age},
            semantic_ports={
                "person": entity_identity("Person"),
                "age": field_endpoint("Person", "age"),
            },
        )
        profile = graph.execution.native_deterministic(target=rule).build()
        invocation = (
            graph.query(rule)
            .select("age", SemanticPortAddress("target", "age"))
            .plan_v2(profile=profile, expected_view_snapshot_digest=candidates.view_snapshot_digest)
        )
        run = invocation.run()
        self.assertEqual(
            run.replay_payload.worlds[0].world.base_view_digest, candidates.view_snapshot_digest
        )
        set_field(graph.ledger, "person:age", alice, [("int", 21)])
        with (
            patch(
                "factgraph.application.goal_plan_v2_runtime.project_view_facts_with_witness",
                side_effect=AssertionError("must not capture"),
            ),
            self.assertRaises(ProductEvaluationRuntimeErrorV2) as raised,
        ):
            invocation.run()
        self.assertEqual(raised.exception.code, "V2_EXPECTED_VIEW_MISMATCH")
        with self.assertRaises(ProductEvaluationRuntimeErrorV2):
            replace(invocation, expected_view_snapshot_digest="bad").run()


if __name__ == "__main__":
    unittest.main()
