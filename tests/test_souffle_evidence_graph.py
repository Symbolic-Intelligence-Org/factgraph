from __future__ import annotations

import json
import unittest

from factgraph.adapters.souffle.provenance import (
    parse_souffle_proof_json,
    souffle_proof_tree_to_evidence_graph,
)
from factgraph.application.explain.evidence_tree import EvidenceGraph, LAYOUT_TREE
from factgraph.core.store._support import SOUFFLE_WITNESS_KIND


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

        self.assertIsInstance(graph, EvidenceGraph)
        self.assertEqual(graph.engine, "souffle")
        self.assertEqual(graph.layout_hint, LAYOUT_TREE)
        self.assertEqual(graph.metadata["support_kind"], SOUFFLE_WITNESS_KIND)
        self.assertEqual(graph.metadata["query"], 'component_not_passivated("power_system")')
        self.assertEqual(graph.metadata["rule_count"], 2)
        self.assertEqual(graph.metadata["root_relation"], "component_not_passivated")
        self.assertEqual(graph.metadata["root_rule_number"], "(R3)")
        self.assertEqual(len(graph.paths), 1)

        tree = graph.paths[0]
        self.assertEqual(tree.status, "holds")
        self.assertEqual(tree.metadata["support_kind"], SOUFFLE_WITNESS_KIND)
        self.assertEqual({rule.role for rule in tree.rules}, {"head", "body"})
        head = next(rule for rule in tree.rules if rule.role == "head")
        self.assertEqual(head.rule_id, "(R3)")
        self.assertEqual(head.atoms[0].repr_text, 'component_not_passivated(power_system)')
        body_atoms = tuple(atom for rule in tree.rules if rule.role == "body" for atom in rule.atoms)
        self.assertEqual(len(body_atoms), 4)
        self.assertTrue(any(atom.repr_text == "has_sub_component(power_system, battery_2)" for atom in body_atoms))
        negation = next(atom for atom in body_atoms if atom.negated)
        self.assertEqual(negation.repr_text, "!component_passivated(battery_2)")
        self.assertEqual(type(negation.verdict).__name__, "Holds")

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

        tree = graph.paths[0]
        atoms = tuple(atom for rule in tree.rules for atom in rule.atoms)
        subproof = next(atom for atom in atoms if atom.verdict.support[0].meta["event_status"] == "subproof")
        self.assertEqual(subproof.repr_text, "subproof mid(0)")
        self.assertEqual(subproof.form.predicate, "mid")
        self.assertEqual(subproof.form.terms[0].value, "0")


if __name__ == "__main__":
    unittest.main()
