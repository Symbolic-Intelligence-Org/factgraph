from __future__ import annotations

import inspect
import unittest

from factgraph.application.explain.evidence_tree import (
    LAYOUT_TREE,
    Const,
    EvidenceAtom,
    EvidenceGraph,
    EvidenceJoin,
    EvidenceRule,
    EvidenceTimeline,
    EvidenceTree,
    Fact,
    Fails,
    Holds,
    PortRef,
)
from factgraph.application.protocol import BOOLEAN_CERTAINTY, ErrorDTO, EvaluateRow, Explanation
from factgraph.application.protocol.certainty import Certainty
from factgraph.application.protocol.explanation_render import narrate_evidence
from factgraph.application.protocol.rule import _PROJECTION_ID_PREFIX
from factgraph.core.protocol.digests import sha256_token


def _row(*, certainty: Certainty = BOOLEAN_CERTAINTY) -> EvaluateRow:
    return EvaluateRow(
        row_id="row-1",
        bindings={"person": "alice", "age": 25},
        kind="fact_triple",
        digest=sha256_token(b"row-digest"),
        closed_head_digest=sha256_token(b"closed-head"),
        certainty=certainty,
    )


def _paths_graph(*, status: str = "holds") -> EvidenceGraph:
    return EvidenceGraph(
        graph_id="graph-1",
        engine="native",
        layout_hint=LAYOUT_TREE,
        subject_binding={"person": "alice", "age": 25},
        paths=(
            EvidenceTree(
                tree_id="row-1",
                status=status,
                rules=(
                    EvidenceRule(
                        occurrence_alias="adult_rule",
                        rule_id="adult_rule",
                        role="head",
                        status=status,
                        repr_text="adult alice",
                        ports={"person": "alice", "age": 25},
                        atoms=(),
                    ),
                ),
            ),
        ),
        certainty=BOOLEAN_CERTAINTY,
    )


def _joined_paths_graph() -> EvidenceGraph:
    return EvidenceGraph(
        graph_id="graph-join",
        engine="native",
        layout_hint=LAYOUT_TREE,
        subject_binding={"speaker": "Carol", "language": "German"},
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
                        repr_text="Carol speaks German",
                        ports={"speaker": "Carol", "language": "German"},
                        atoms=(
                            EvidenceAtom(
                                form=Fact("User:exists", (Const("u-3"),)),
                                verdict=Holds(),
                                atom_id="c0:atom:11",
                                repr_text="User:exists(User u-3)",
                            ),
                        ),
                    ),
                    EvidenceRule(
                        occurrence_alias="speaks",
                        rule_id="speaks_language",
                        role="body",
                        status="holds",
                        repr_text="Carol speaks German",
                        ports={"speaker": "Carol", "language": "German"},
                        atoms=(),
                    ),
                    EvidenceRule(
                        occurrence_alias="age",
                        rule_id="age_filter",
                        role="body",
                        status="holds",
                        repr_text="Carol is older than 5",
                        ports={"speaker": "Carol"},
                        atoms=(),
                    ),
                ),
                joins=(
                    EvidenceJoin(
                        left=PortRef("speaks", "speaker"),
                        right=PortRef("age", "speaker"),
                        status="holds",
                        join_id="j0",
                    ),
                ),
            ),
        ),
        certainty=BOOLEAN_CERTAINTY,
        metadata={"run_id": "run_v1:647d604d99999999"},
    )


def _or_paths_graph() -> EvidenceGraph:
    first = _paths_graph(status="fails").paths[0]
    second = _paths_graph(status="holds").paths[0]
    return EvidenceGraph(
        graph_id="graph-or",
        engine="native",
        layout_hint=LAYOUT_TREE,
        subject_binding={"person": "alice", "age": 25},
        paths=(
            EvidenceTree(tree_id="c0", status="fails", rules=first.rules),
            EvidenceTree(tree_id="c1", status="holds", rules=second.rules),
        ),
        certainty=BOOLEAN_CERTAINTY,
    )


def _timeline_graph() -> EvidenceGraph:
    return EvidenceGraph(
        graph_id="graph-timeline",
        engine="pyreason",
        layout_hint="timeline",
        subject_binding={"person": "alice"},
        paths=(
            EvidenceTimeline(
                timeline_id="tl0",
                status="holds",
                certainty=Certainty(0.2, 0.8, "possibilistic"),
                events=(
                    EvidenceAtom(
                        form=Fact("popular", (Const("alice"),)),
                        verdict=Holds(certainty=Certainty(0.4, 0.6, "possibilistic")),
                        atom_id="event-1",
                        repr_text="alice is popular",
                        timestep=2,
                    ),
                    EvidenceAtom(
                        form=Fact("seed", (Const("alice"),)),
                        verdict=Fails(certainty=Certainty(0.1, 0.2, "possibilistic")),
                        atom_id="event-0",
                        repr_text="alice seed failed",
                        timestep=1,
                    ),
                ),
            ),
        ),
        certainty=Certainty(0.2, 0.8, "possibilistic"),
        metadata={"run_id": "run_v1:abcdef012345"},
    )


def _headless_graph() -> EvidenceGraph:
    return EvidenceGraph(
        graph_id="headless-graph",
        engine="native",
        layout_hint=LAYOUT_TREE,
        subject_binding={"b": 2, "a": 1},
        paths=(
            EvidenceTree(
                tree_id="c0",
                status="holds",
                rules=(),
            ),
        ),
        certainty=BOOLEAN_CERTAINTY,
        metadata={"run_id": "run_v1:deadbeef9999"},
    )


class ExplanationRenderTests(unittest.TestCase):
    def test_explanation_repr_is_computed_property_and_cached(self) -> None:
        self.assertNotIn("repr", inspect.signature(Explanation).parameters)
        explanation = Explanation(
            status="passed",
            evidence=_paths_graph(),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
        )

        first = explanation.repr
        second = explanation.repr

        self.assertIs(first, second)
        assert first is not None
        self.assertEqual(first[0], "Conclusion: row-1 [row-1]")

    def test_failed_explanation_repr_uses_paths_evidence(self) -> None:
        explanation = Explanation(
            status="failed",
            evidence=_paths_graph(status="fails"),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
            failure_class="closed_head_false",
            suggested_next_steps=("Retry with a row returned by evaluate().",),
        )

        self.assertEqual(
            explanation.repr,
            (
                "NOT concluded: row-1 [row-1] (closed_head_false)",
                '  Rule "adult_rule": fails',
            ),
        )

    def test_unsupported_and_invalid_request_repr_is_none(self) -> None:
        unsupported = Explanation(
            status="unsupported",
            evidence=None,
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
            errors=(ErrorDTO(code="UNSUPPORTED", message="unsupported"),),
        )
        invalid = Explanation(
            status="invalid_request",
            evidence=None,
            row=None,
            result_id=None,
            errors=(ErrorDTO(code="INVALID_REQUEST", message="bad request"),),
        )

        self.assertIsNone(unsupported.repr)
        self.assertIsNone(invalid.repr)

    def test_explanation_narrate_is_independent_cached_surface(self) -> None:
        explanation = Explanation(
            status="passed",
            evidence=_paths_graph(),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
        )

        first = explanation.narrate()
        second = explanation.narrate()

        self.assertIs(first, second)
        assert first is not None
        self.assertEqual(first[0], "Conclusion ── adult alice")
        self.assertIn("              [adult_rule · row-1 · row-1]  holds", first)
        self.assertIn("      produces:  person = alice,  age = 25", first)
        self.assertNotIn("> Path row-1 [holds]", first)
        self.assertTrue(any('  adult_rule [head] ── "adult alice"  [holds]' == line for line in first))

    def test_narrate_uses_rule_ids_for_derivation_and_joins(self) -> None:
        explanation = Explanation(
            status="passed",
            evidence=_joined_paths_graph(),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
        )

        narrative = explanation.narrate()

        assert narrative is not None
        self.assertEqual(narrative[0], "Conclusion ── Carol speaks German")
        self.assertIn("              [head · run_v1:647d604d… · c0]  holds", narrative)
        self.assertIn("  Derivation:  head <= ( speaks_language AND age_filter )", narrative)
        self.assertIn("               join:  speaks_language.speaker = age_filter.speaker  [holds]", narrative)
        self.assertIn('  speaks_language ── "Carol speaks German"  [holds]', narrative)
        self.assertIn('  age_filter ── "Carol is older than 5"  [holds]', narrative)

    def test_narrate_uses_path_lines_only_for_or_trees(self) -> None:
        explanation = Explanation(
            status="passed",
            evidence=_or_paths_graph(),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
        )

        narrative = explanation.narrate()

        assert narrative is not None
        self.assertIn("              [adult_rule · row-1 · c0|c1 (concluded via c1)]  holds", narrative)
        self.assertNotIn("concluded via c1", narrative)
        self.assertIn("▸ Path c0  [fails]", narrative)
        self.assertIn("▸ Path c1  [holds]", narrative)

    def test_narrate_labels_projection_head_with_port_list(self) -> None:
        graph = EvidenceGraph(
            graph_id="projection-graph",
            engine="native",
            layout_hint=LAYOUT_TREE,
            subject_binding={"user": "User u-1"},
            paths=(
                EvidenceTree(
                    tree_id="c0",
                    status="holds",
                    rules=(
                        EvidenceRule(
                            occurrence_alias="head",
                            rule_id=f"{_PROJECTION_ID_PREFIX}abc123",
                            role="head",
                            status="holds",
                            ports={"user": "User u-1"},
                            atoms=(),
                        ),
                        EvidenceRule(
                            occurrence_alias="body",
                            rule_id="source_rule",
                            role="body",
                            status="holds",
                            repr_text="source",
                        ),
                    ),
                ),
            ),
            certainty=BOOLEAN_CERTAINTY,
            metadata={"run_id": "run_v1:abcdef012345"},
        )

        narrative = narrate_evidence(graph, status="passed")

        self.assertEqual(narrative[0], "Conclusion ── projection(user)")
        self.assertIn("              [projection(user) · run_v1:abcdef01… · c0]  holds", narrative)
        self.assertIn("  Derivation:  projection(user) <= ( source_rule )", narrative)
        self.assertIn('  projection(user) [head] ── "projection(user)"  [holds]', narrative)

    def test_narrate_marks_non_boolean_certainty_at_summary_path_and_atom_levels(self) -> None:
        explanation = Explanation(
            status="passed",
            evidence=_or_paths_graph(),
            row=_row(certainty=Certainty(0.4, 0.4, "probabilistic")),
            result_id="evalr_v1:" + "1" * 64,
        )

        narrative = explanation.narrate()

        assert narrative is not None
        self.assertIn(
            "              [adult_rule · row-1 · c0|c1 (concluded via c1)]  holds with probability 0.4",
            narrative,
        )

    def test_narrate_expands_timeline_events_with_bounds(self) -> None:
        explanation = Explanation(
            status="passed",
            evidence=_timeline_graph(),
            row=_row(certainty=Certainty(0.2, 0.8, "possibilistic")),
            result_id="evalr_v1:" + "1" * 64,
        )

        narrative = explanation.narrate()

        assert narrative is not None
        self.assertIn("Conclusion ── graph-timeline", narrative)
        self.assertIn("              [head · run_v1:abcdef01… · c0]  holds with bound [0.2, 0.8]", narrative)
        self.assertIn("▸ Timeline tl0  [holds] with bound [0.2, 0.8]", narrative)
        self.assertLess(narrative.index("    t=1  alice seed failed  [event-0]  fails [0.1, 0.2]"), narrative.index("    t=2  alice is popular  [event-1]  holds [0.4, 0.6]"))

    def test_narrate_headless_graph_keeps_reference_tail_and_produces(self) -> None:
        explanation = Explanation(
            status="passed",
            evidence=_headless_graph(),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
        )

        narrative = explanation.narrate()

        assert narrative is not None
        self.assertEqual(narrative[0], "Conclusion ── headless-graph")
        self.assertIn("              [head · run_v1:deadbeef… · c0]  holds", narrative)
        self.assertIn("      produces:  a = 1,  b = 2", narrative)

    def test_failed_narrate_uses_not_concluded_and_failed_tail(self) -> None:
        explanation = Explanation(
            status="failed",
            evidence=_paths_graph(status="fails"),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
            failure_class="closed_head_false",
        )

        narrative = explanation.narrate()

        assert narrative is not None
        self.assertEqual(narrative[0], "NOT concluded ── adult alice (closed_head_false)")
        self.assertIn("              [adult_rule · row-1 · row-1]  fails", narrative)

    def test_unsupported_and_invalid_request_narrate_is_none(self) -> None:
        unsupported = Explanation(
            status="unsupported",
            evidence=None,
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
            errors=(ErrorDTO(code="UNSUPPORTED", message="unsupported"),),
        )
        invalid = Explanation(
            status="invalid_request",
            evidence=None,
            row=None,
            result_id=None,
            errors=(ErrorDTO(code="INVALID_REQUEST", message="bad request"),),
        )

        self.assertIsNone(unsupported.narrate())
        self.assertIsNone(invalid.narrate())


if __name__ == "__main__":
    unittest.main()
