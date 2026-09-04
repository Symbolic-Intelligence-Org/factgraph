from __future__ import annotations

import unittest

from factgraph.application.explain.evidence_tree import (
    LAYOUT_TREE,
    BoundVar,
    Const,
    EvidenceAtom,
    EvidenceGraph,
    EvidenceRule,
    EvidenceTree,
    Fact,
    Holds,
)
from factgraph.application.protocol.certainty import Certainty
from factgraph.application.protocol.explanation_render import narrate_evidence


class ExplanationNarrateProbabilityTests(unittest.TestCase):
    def test_narrate_renders_inline_probability_formula_for_rule(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={"sensor": "Sensor s-2"},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(
                        EvidenceRule(
                            occurrence_alias="head",
                            rule_id="online_m1_sensor",
                            role="head",
                            status="holds",
                            repr_text="sensor Sensor s-2 is an online m1 sensor",
                        ),
                        EvidenceRule(
                            occurrence_alias="status_rule",
                            rule_id="online_m1_sensor",
                            role="body",
                            status="holds",
                            repr_text="sensor Sensor s-2 is an online m1 sensor",
                            atoms=(
                                EvidenceAtom(
                                    form=Fact("sensor:status", (BoundVar("sensor", "Sensor s-2"), Const("online"))),
                                    verdict=Holds(certainty=Certainty(0.4, 0.4, "probabilistic")),
                                    atom_id="c0:atom:0",
                                    repr_text="Sensor s-2 has status online",
                                ),
                                EvidenceAtom(
                                    form=Fact("sensor:model", (BoundVar("sensor", "Sensor s-2"), Const("m1"))),
                                    verdict=Holds(),
                                    atom_id="c0:atom:1",
                                    repr_text="Sensor s-2 has model m1",
                                ),
                            ),
                        ),
                    ),
                    certainty=Certainty(0.4, 0.4, "probabilistic"),
                    metadata={
                        "branch_probability": 0.4,
                        "occ_probabilities": {"status_rule": 0.4},
                    },
                ),
            ),
            certainty=Certainty(0.4, 0.4, "probabilistic"),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertNotIn("      probability:  0.4", lines)
        self.assertIn(
            "  online_m1_sensor  [holds]  (p = 0.4 × 1 = 0.4)",
            lines,
        )
        self.assertNotIn("  Derivation:  online_m1_sensor <= ( online_m1_sensor )", lines)
        self.assertFalse(any('online_m1_sensor [head] ── "sensor Sensor s-2 is an online m1 sensor"' in line for line in lines))
        self.assertFalse(any('online_m1_sensor ── "sensor Sensor s-2 is an online m1 sensor"' in line for line in lines))
        self.assertIn("       ✓ Sensor s-2 has status online  [c0:atom:0]  holds (p = 0.4)", lines)

    def test_narrate_keeps_label_for_degenerate_tree_when_body_text_differs(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(
                        EvidenceRule(
                            occurrence_alias="head",
                            rule_id="same_rule",
                            role="head",
                            status="holds",
                            repr_text="head title",
                        ),
                        EvidenceRule(
                            occurrence_alias="body",
                            rule_id="same_rule",
                            role="body",
                            status="holds",
                            repr_text="body title",
                        ),
                    ),
                    metadata={"branch_probability": 0.4, "occ_probabilities": {"body": 0.4}},
                ),
            ),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertNotIn("  Derivation:  same_rule <= ( same_rule )", lines)
        self.assertIn('  same_rule ── "body title"  [holds]  (p = 0.4)', lines)

    def test_narrate_keeps_derivation_with_pure_probability_for_non_degenerate_single_body(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(
                        EvidenceRule(
                            occurrence_alias="head",
                            rule_id="head_rule",
                            role="head",
                            status="holds",
                            repr_text="head",
                        ),
                        EvidenceRule(
                            occurrence_alias="body",
                            rule_id="body_rule",
                            role="body",
                            status="holds",
                            repr_text="body",
                            atoms=(
                                EvidenceAtom(
                                    form=Fact("p", (Const("x"),)),
                                    verdict=Holds(certainty=Certainty(0.4, 0.4, "probabilistic")),
                                    atom_id="c0:atom:0",
                                    repr_text="p(x)",
                                ),
                            ),
                        ),
                    ),
                    metadata={"branch_probability": 0.4, "occ_probabilities": {"body": 0.4}},
                ),
            ),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn("  Derivation:  head_rule <= ( body_rule )  (p = 0.4)", lines)
        self.assertIn('  head_rule [head] ── "head"  [holds]', lines)
        self.assertIn('  body_rule ── "body"  [holds]  (p = 0.4)', lines)

    def test_narrate_degrades_to_pure_probability_when_formula_does_not_match(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={"sensor": "Sensor s-2"},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(
                        EvidenceRule(
                            occurrence_alias="body",
                            rule_id="body_rule",
                            role="body",
                            status="holds",
                            repr_text="body",
                            atoms=(
                                EvidenceAtom(
                                    form=Fact("p", (Const("x"),)),
                                    verdict=Holds(certainty=Certainty(0.4, 0.4, "probabilistic")),
                                    atom_id="c0:atom:0",
                                    repr_text="p(x)",
                                ),
                                EvidenceAtom(
                                    form=Fact("q", (Const("x"),)),
                                    verdict=Holds(certainty=Certainty(0.5, 0.5, "probabilistic")),
                                    atom_id="c0:atom:1",
                                    repr_text="q(x)",
                                ),
                            ),
                        ),
                    ),
                    metadata={"occ_probabilities": {"body": 0.4}},
                ),
            ),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn('  body_rule ── "body"  [holds]  (p = 0.4)', lines)

    def test_narrate_renders_derivation_probability_formula_for_multiple_rules(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(
                        EvidenceRule(
                            occurrence_alias="head",
                            rule_id="head",
                            role="head",
                            status="holds",
                            repr_text="head",
                        ),
                        EvidenceRule(
                            occurrence_alias="geo",
                            rule_id="geo",
                            role="body",
                            status="holds",
                            repr_text="geo",
                            atoms=(
                                EvidenceAtom(
                                    form=Fact("geo", (Const("x"),)),
                                    verdict=Holds(certainty=Certainty(0.8, 0.8, "probabilistic")),
                                    atom_id="c0:atom:0",
                                    repr_text="geo",
                                ),
                            ),
                        ),
                        EvidenceRule(
                            occurrence_alias="age",
                            rule_id="age",
                            role="body",
                            status="holds",
                            repr_text="age",
                            atoms=(
                                EvidenceAtom(
                                    form=Fact("age", (Const("x"),)),
                                    verdict=Holds(certainty=Certainty(0.5, 0.5, "probabilistic")),
                                    atom_id="c0:atom:1",
                                    repr_text="age",
                                ),
                            ),
                        ),
                    ),
                    metadata={"branch_probability": 0.4, "occ_probabilities": {"geo": 0.8, "age": 0.5}},
                ),
            ),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn("  Derivation:  head <= ( geo AND age )  (p = 0.8 × 0.5 = 0.4)", lines)

    def test_narrate_uses_head_probability_candidate_for_derivation_formula(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(
                        EvidenceRule(
                            occurrence_alias="head",
                            rule_id="head",
                            role="head",
                            status="holds",
                            repr_text="head",
                        ),
                        EvidenceRule(
                            occurrence_alias="geo",
                            rule_id="geo",
                            role="body",
                            status="holds",
                            repr_text="geo",
                        ),
                        EvidenceRule(
                            occurrence_alias="age",
                            rule_id="age",
                            role="body",
                            status="holds",
                            repr_text="age",
                        ),
                    ),
                    metadata={
                        "branch_probability": 0.36,
                        "head_probability": 0.9,
                        "occ_probabilities": {"geo": 0.5, "age": 0.8},
                    },
                ),
            ),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn("  Derivation:  head <= ( geo AND age )  (p = 0.9 × 0.5 × 0.8 = 0.36)", lines)

    def test_narrate_renders_global_derivation_for_multiple_paths(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(
                        EvidenceRule("head", "head", "head", "holds", repr_text="head"),
                        EvidenceRule("geo", "geo", "body", "holds", repr_text="geo"),
                        EvidenceRule("age", "age", "body", "holds", repr_text="age"),
                    ),
                    metadata={"branch_probability": 0.7},
                ),
                EvidenceTree(
                    tree_id="c1",
                    status="fails",
                    rules=(
                        EvidenceRule("head", "head", "head", "fails", repr_text="head"),
                        EvidenceRule("country", "country", "body", "fails", repr_text="country"),
                        EvidenceRule("language", "language", "body", "fails", repr_text="language"),
                    ),
                    metadata={"branch_probability": 0.4},
                ),
            ),
            certainty=Certainty(0.82, 0.82, "probabilistic"),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn("  Derivation:  head <= ( geo AND age ) OR ( country AND language )", lines)
        self.assertEqual(1, sum(1 for line in lines if line.startswith("  Derivation:")))
        self.assertIn("▸ Path c0  [holds] (p = 0.7)", lines)
        self.assertIn("▸ Path c1  [fails] (p = 0.4)", lines)

    def test_narrate_renders_noisy_or_formula_for_multiple_holding_paths(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(),
                    certainty=Certainty(0.7, 0.7, "probabilistic"),
                    metadata={"branch_probability": 0.7},
                ),
                EvidenceTree(
                    tree_id="c1",
                    status="holds",
                    rules=(),
                    certainty=Certainty(0.4, 0.4, "probabilistic"),
                    metadata={"branch_probability": 0.4},
                ),
            ),
            certainty=Certainty(0.82, 0.82, "probabilistic"),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn("      probability:  1 − (1−0.7) × (1−0.4) = 0.82", lines)
        self.assertIn("▸ Path c0  [holds] (p = 0.7)", lines)

    def test_narrate_renders_noisy_or_formula_over_holding_paths_only(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(),
                    certainty=Certainty(0.8, 0.8, "probabilistic"),
                    metadata={"branch_probability": 0.8},
                ),
                EvidenceTree(
                    tree_id="c1",
                    status="holds",
                    rules=(),
                    certainty=Certainty(0.63, 0.63, "probabilistic"),
                    metadata={"branch_probability": 0.63},
                ),
                EvidenceTree(
                    tree_id="c2",
                    status="fails",
                    rules=(),
                    metadata={},
                ),
            ),
            certainty=Certainty(0.926, 0.926, "probabilistic"),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn("      probability:  1 − (1−0.8) × (1−0.63) = 0.926", lines)
        self.assertIn("▸ Path c2  [fails]", lines)

    def test_narrate_keeps_pure_probability_for_single_holding_path(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph-1",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(),
                    certainty=Certainty(0.7, 0.7, "probabilistic"),
                    metadata={"branch_probability": 0.7},
                ),
                EvidenceTree(
                    tree_id="c1",
                    status="fails",
                    rules=(),
                    metadata={},
                ),
            ),
            certainty=Certainty(0.7, 0.7, "probabilistic"),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn("      probability:  0.7", lines)
        self.assertFalse(any("1 −" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
