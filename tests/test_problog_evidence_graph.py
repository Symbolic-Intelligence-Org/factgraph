"""Tests for ProbLog -> EvidenceGraph conversion."""

from __future__ import annotations

import unittest

from factgraph.adapters.problog.provenance import (
    parse_problog_trace,
    problog_trace_to_evidence_graph,
)
from factgraph.application.explain.evidence_tree import EvidenceGraph, LAYOUT_TREE
from factgraph.core.store._support import PROBLOG_PROVENANCE_KIND


_SUCCESS_TRACE = """
 call query(X1) {0.00000} []
  result query(X1) (c(alice),) {{}} {0.00012} []
 complete query(X1) {0.00013} {0.00013} []
 call c(alice) {0.00019} [at 4:7]
  call a(alice) {0.00026} [at 3:9]
   result a(alice) (alice,) {{}} {0.00038} [at 3:9]
  complete a(alice) {0.00039} {0.00013} []
  call b(alice) {0.00041} [at 3:15]
   result b(alice) (alice,) {{}} {0.00053} [at 3:15]
  complete b(alice) {0.00055} {0.00014} []
  result c(alice) (alice,) {{}} {0.00060} []
 complete c(alice) {0.00061} {0.00042} []

c(alice):\t0.35
""".strip()

_ANSWER_TRACE = """
 call query(X1,X2) {0.00000} []
  result query(X1,X2) ("vip","idref_v1:User:Alice") {{}} {0.00012} []
 complete query(X1,X2) {0.00013} {0.00013} []
 call answer("vip","idref_v1:User:Alice") {0.00019} [at 4:7]
  result answer("vip","idref_v1:User:Alice") ("vip","idref_v1:User:Alice") {{}} {0.00060} []
 complete answer("vip","idref_v1:User:Alice") {0.00061} {0.00042} []

answer("vip","idref_v1:User:Alice"):\t0.42
""".strip()

_MULTI_ANSWER_TRACE = """
 call d(alice) {0.00010} []
  result d(alice) (alice,) {{}} {0.00012} []
 complete d(alice) {0.00013} {0.00003} []
 call d(bob) {0.00020} []
  result d(bob) (bob,) {{}} {0.00022} []
 complete d(bob) {0.00023} {0.00003} []

d(alice):\t0.2
d(bob):\t0.7
""".strip()


class ProbLogEvidenceGraphTests(unittest.TestCase):
    def test_converter_builds_tree_from_nested_call_trace(self) -> None:
        graph = problog_trace_to_evidence_graph(
            parse_problog_trace(_SUCCESS_TRACE),
            candidate_id="cand_v2:problog",
            candidate_payload={
                "pred_id": "c",
                "terms": [{"kind": "entity_ref", "value": "alice"}],
            },
        )

        self.assertIsInstance(graph, EvidenceGraph)
        self.assertEqual(graph.engine, "problog")
        self.assertEqual(graph.layout_hint, LAYOUT_TREE)
        self.assertEqual(graph.metadata["support_kind"], PROBLOG_PROVENANCE_KIND)
        self.assertEqual(graph.metadata["answer_probability"], 0.35)
        self.assertEqual(graph.certainty.kind, "probabilistic")
        self.assertEqual(graph.certainty.lo, 0.35)
        self.assertEqual(len(graph.paths), 1)

        tree = graph.paths[0]
        self.assertEqual(tree.certainty.kind, "probabilistic")
        self.assertEqual(tree.certainty.lo, 0.35)
        self.assertEqual(tree.metadata["answer_probability"], 0.35)
        self.assertEqual({rule.role for rule in tree.rules}, {"head", "body"})
        head = next(rule for rule in tree.rules if rule.role == "head")
        self.assertEqual(head.rule_id, "c")
        self.assertEqual(head.atoms[0].repr_text, "c(alice)")
        body_atoms = tuple(atom for rule in tree.rules if rule.role == "body" for atom in rule.atoms)
        self.assertEqual({atom.form.predicate for atom in body_atoms}, {"a", "b"})
        self.assertTrue(all(type(atom.verdict).__name__ == "Holds" for atom in body_atoms))

    def test_converter_anchors_synthetic_answer_goal_with_reordered_terms(self) -> None:
        graph = problog_trace_to_evidence_graph(
            parse_problog_trace(_ANSWER_TRACE),
            candidate_id="cand_v2:answer",
            candidate_payload={
                "pred_id": "user:tag",
                "terms": [
                    {"kind": "entity_ref", "value": "idref_v1:User:Alice"},
                    {"kind": "literal", "tag": "string", "value": "vip"},
                ],
            },
        )

        self.assertEqual(len(graph.paths), 1)
        tree = graph.paths[0]
        head = next(rule for rule in tree.rules if rule.role == "head")
        atom = head.atoms[0]
        self.assertEqual(atom.form.predicate, "answer")
        self.assertEqual(atom.repr_text, 'answer("vip","idref_v1:User:Alice")')
        self.assertTrue(atom.verdict.support[0].meta["synthetic_goal"])
        self.assertEqual(tree.certainty.lo, 0.42)

    def test_converter_maps_multiple_answers_to_multiple_trees(self) -> None:
        graph = problog_trace_to_evidence_graph(
            parse_problog_trace(_MULTI_ANSWER_TRACE),
            candidate_id="cand_v2:multi",
            candidate_payload={
                "pred_id": "d",
                "terms": [{"kind": "literal", "tag": "string", "value": "alice"}],
            },
        )

        self.assertEqual(len(graph.paths), 2)
        self.assertEqual(graph.certainty.kind, "probabilistic")
        self.assertEqual(graph.certainty.lo, 0.7)
        self.assertEqual([tree.certainty.lo for tree in graph.paths], [0.2, 0.7])
        self.assertEqual([tree.metadata["answer_query"] for tree in graph.paths], ["d(alice)", "d(bob)"])

    def test_converter_rejects_missing_candidate_anchor(self) -> None:
        with self.assertRaisesRegex(ValueError, "candidate anchor not found"):
            problog_trace_to_evidence_graph(
                parse_problog_trace(_SUCCESS_TRACE),
                candidate_id="cand_v2:missing",
                candidate_payload={
                    "pred_id": "c",
                    "terms": [{"kind": "entity_ref", "value": "bob"}],
                },
            )


if __name__ == "__main__":
    unittest.main()
