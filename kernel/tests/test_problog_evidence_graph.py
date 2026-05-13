"""Tests for ProbLog -> EvidenceGraph conversion."""

from __future__ import annotations

import unittest

from kernel.adapters.problog.provenance import (
    parse_problog_trace,
    problog_trace_to_evidence_graph,
)
from kernel.audit import EDGE_DERIVES, LAYOUT_TREE
from kernel.core.store._support import PROBLOG_PROVENANCE_KIND


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

        self.assertEqual(graph.engine, "problog")
        self.assertEqual(graph.layout_hint, LAYOUT_TREE)
        self.assertEqual(graph.support_kind, PROBLOG_PROVENANCE_KIND)
        self.assertEqual(graph.metadata["answer_probability"], 0.35)
        self.assertEqual(len(graph.nodes), 3)
        self.assertEqual(len(graph.edges), 2)

        root = next(node for node in graph.nodes if node.node_id == graph.root_node_id)
        self.assertEqual(root.label, "c")
        self.assertEqual(root.component, "alice")
        self.assertEqual(root.value_summary, "0.35")
        self.assertEqual(root.node_kind, "conclusion")
        self.assertEqual(root.engine_meta["goal"], "c(alice)")
        self.assertEqual(root.engine_meta["event_status"], "result")

        leaf_labels = {node.label: node for node in graph.nodes if node.node_id != graph.root_node_id}
        self.assertEqual(leaf_labels["a"].node_kind, "seed")
        self.assertEqual(leaf_labels["b"].node_kind, "seed")
        self.assertEqual(leaf_labels["a"].value_summary, "true")

        self.assertTrue(all(edge.edge_kind == EDGE_DERIVES for edge in graph.edges))
        self.assertEqual({edge.to_node_id for edge in graph.edges}, {graph.root_node_id})

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

        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(len(graph.edges), 0)
        root = graph.nodes[0]
        self.assertEqual(root.node_id, graph.root_node_id)
        self.assertEqual(root.label, "tag")
        self.assertEqual(root.component, "idref_v1:User:Alice")
        self.assertEqual(root.value_summary, "0.42")
        self.assertTrue(root.engine_meta["synthetic_goal"])
        self.assertEqual(root.engine_meta["goal"], 'answer("vip","idref_v1:User:Alice")')

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
