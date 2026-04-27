from __future__ import annotations

import json
import unittest

from kernel.adapters.souffle.provenance import (
    parse_souffle_proof_json,
    souffle_proof_tree_to_evidence_graph,
)
from kernel.audit import EDGE_SUPPORTS, LAYOUT_TREE, render_evidence_graph_html
from kernel.core.store._support import SOUFFLE_WITNESS_KIND


_PASSIVATION_JSON = r"""
{
  "proof": {
    "premises": "component_not_passivated(\"power_system\")",
    "rule-number": "(R3)",
    "children": [
      {"axiom": "has_sub_component(\"power_system\", \"battery_2\")"},
      {
        "premises": "component_not_passivated(\"battery_2\")",
        "rule-number": "(R2)",
        "children": [
          {"axiom": "has_sub_component(\"power_system\", \"battery_2\")"},
          {"axiom": "!component_passivated(\"battery_2\")"}
        ]
      }
    ]
  },
  "rules": [
    {"rule-number": "(R2)", "rule": "component_not_passivated(C) :- !component_passivated(C)."},
    {"rule-number": "(R3)", "rule": "component_not_passivated(P) :- has_sub_component(P, C), component_not_passivated(C)."}
  ]
}
"""


class SouffleEvidenceGraphTests(unittest.TestCase):
    def test_converter_builds_tree_from_recursive_proof(self) -> None:
        proof_tree = parse_souffle_proof_json(_PASSIVATION_JSON)[0]

        graph = souffle_proof_tree_to_evidence_graph(
            proof_tree,
            candidate_id="cand_v2:souffle",
        )

        self.assertEqual(graph.engine, "souffle")
        self.assertEqual(graph.layout_hint, LAYOUT_TREE)
        self.assertEqual(graph.support_kind, SOUFFLE_WITNESS_KIND)
        self.assertEqual(graph.metadata["query"], 'component_not_passivated("power_system")')
        self.assertEqual(graph.metadata["rule_count"], 2)
        self.assertEqual(graph.metadata["root_relation"], "component_not_passivated")
        self.assertEqual(graph.metadata["root_rule_number"], "(R3)")
        self.assertEqual(len(graph.nodes), 5)
        self.assertEqual(len(graph.edges), 4)

        root = next(node for node in graph.nodes if node.node_id == graph.root_node_id)
        self.assertEqual(root.node_kind, "conclusion")
        self.assertEqual(root.label, "component_not_passivated")
        self.assertEqual(root.component, "power_system")
        self.assertEqual(root.value_summary, "true")
        self.assertEqual(root.engine_meta["event_status"], "derived")
        self.assertEqual(
            root.engine_meta["occurred_due_to"],
            "component_not_passivated(P) :- has_sub_component(P, C), component_not_passivated(C).",
        )

        negation = next(
            node for node in graph.nodes if node.engine_meta["event_status"] == "negation"
        )
        self.assertEqual(negation.node_kind, "premise")
        self.assertEqual(negation.label, "component_passivated")
        self.assertEqual(negation.component, "battery_2")
        self.assertEqual(negation.value_summary, "true")
        self.assertEqual(negation.engine_meta["goal"], "!component_passivated(battery_2)")

        seed_nodes = [node for node in graph.nodes if node.node_kind == "seed"]
        self.assertEqual(len(seed_nodes), 2)
        self.assertTrue(all(node.label == "has_sub_component" for node in seed_nodes))
        self.assertTrue(all(node.value_summary == "battery_2" for node in seed_nodes))

        self.assertTrue(all(edge.edge_kind == EDGE_SUPPORTS for edge in graph.edges))
        negation_parent_edge = next(edge for edge in graph.edges if edge.from_node_id == negation.node_id)
        self.assertEqual(negation_parent_edge.rule_label, "(R2)")
        self.assertEqual(
            negation_parent_edge.engine_meta["parent_rule_text"],
            "component_not_passivated(C) :- !component_passivated(C).",
        )

    def test_converter_preserves_subproof_leaf_as_premise(self) -> None:
        json_text = json.dumps(
            {
                "proof": {
                    "premises": "top(1)",
                    "rule-number": "(R1)",
                    "children": [
                        {"axiom": "base(1)"},
                        {"axiom": "subproof mid(0)"},
                    ],
                },
                "rules": [
                    {"rule-number": "(R1)", "rule": "top(X) :- base(X), mid(X-1)."},
                ],
            }
        )
        proof_tree = parse_souffle_proof_json(json_text)[0]

        graph = souffle_proof_tree_to_evidence_graph(
            proof_tree,
            candidate_id="cand_v2:subproof",
        )

        self.assertEqual(len(graph.nodes), 3)
        self.assertEqual(len(graph.edges), 2)

        subproof = next(node for node in graph.nodes if node.engine_meta["event_status"] == "subproof")
        self.assertEqual(subproof.node_kind, "premise")
        self.assertEqual(subproof.label, "mid")
        self.assertEqual(subproof.component, "0")
        self.assertEqual(subproof.value_summary, "true")
        self.assertEqual(subproof.engine_meta["goal"], "subproof mid(0)")

    def test_rendered_tree_fragment_accepts_souffle_graph(self) -> None:
        proof_tree = parse_souffle_proof_json(_PASSIVATION_JSON)[0]
        graph = souffle_proof_tree_to_evidence_graph(
            proof_tree,
            candidate_id="cand_v2:render",
        )

        html = render_evidence_graph_html(graph)

        self.assertIn("data-layout='tree'", html)
        self.assertIn("component_not_passivated", html)
        self.assertIn("has_sub_component", html)
        self.assertIn("supports", html)
        self.assertIn("(R2)", html)


if __name__ == "__main__":
    unittest.main()
