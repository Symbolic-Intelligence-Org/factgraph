from __future__ import annotations

import unittest

from factgraph.adapters.pyreason.provenance import (
    PyReasonTraceEventV0,
    PyReasonTraceV0,
    pyreason_trace_to_evidence_graph,
)
from factgraph.application.explain.evidence_tree import EvidenceTimeline, LAYOUT_TIMELINE
from factgraph.core.store._support import PYREASON_PROVENANCE_KIND


class PyReasonEvidenceGraphTests(unittest.TestCase):
    def test_converter_builds_timeline_graph_for_node_candidate(self) -> None:
        trace = PyReasonTraceV0(
            timesteps=3,
            node_events=(
                PyReasonTraceEventV0(
                    time=0,
                    fixpoint_op=1,
                    component="Mary",
                    component_type="node",
                    label="popular",
                    old_bound=(0.0, 1.0),
                    new_bound=(0.85, 0.95),
                    occurred_due_to="seed_fact",
                    clause_groundings=(),
                ),
                PyReasonTraceEventV0(
                    time=1,
                    fixpoint_op=2,
                    component="Justin",
                    component_type="node",
                    label="popular",
                    old_bound=(0.0, 1.0),
                    new_bound=(1.0, 1.0),
                    occurred_due_to="spread_rule",
                    clause_groundings=("[Mary]", "[(Justin, Mary)]"),
                ),
                PyReasonTraceEventV0(
                    time=2,
                    fixpoint_op=3,
                    component="Justin",
                    component_type="node",
                    label="popular",
                    old_bound=(1.0, 1.0),
                    new_bound=(1.0, 1.0),
                    occurred_due_to="converged_rule",
                    clause_groundings=("[Mary]",),
                ),
            ),
            edge_events=(
                PyReasonTraceEventV0(
                    time=0,
                    fixpoint_op=1,
                    component="(Justin, Mary)",
                    component_type="edge",
                    label="friends",
                    old_bound=(0.0, 1.0),
                    new_bound=(1.0, 1.0),
                    occurred_due_to="friends_fact",
                    clause_groundings=(),
                ),
            ),
        )

        graph = pyreason_trace_to_evidence_graph(
            trace,
            candidate_id="cand_v2:test",
            candidate_payload={
                "pred_id": "user:popular",
                "terms": [
                    {"kind": "entity_ref", "value": "Justin"},
                ],
            },
        )

        self.assertEqual(graph.engine, "pyreason")
        self.assertEqual(graph.layout_hint, LAYOUT_TIMELINE)
        self.assertEqual(graph.metadata["support_kind"], PYREASON_PROVENANCE_KIND)
        self.assertEqual(graph.metadata["timesteps"], 3)
        self.assertEqual(graph.metadata["node_event_count"], 3)
        self.assertEqual(graph.metadata["edge_event_count"], 1)
        self.assertEqual(len(graph.paths), 1)
        timeline = graph.paths[0]
        self.assertIsInstance(timeline, EvidenceTimeline)
        self.assertEqual(len(timeline.events), 4)
        self.assertEqual(timeline.metadata["root_component"], "Justin")
        self.assertEqual(timeline.metadata["root_label"], "popular")
        self.assertEqual(timeline.metadata["root_event_index"], 3)

        root = timeline.events[timeline.metadata["root_event_index"]]
        self.assertEqual(root.form.terms[0].value, "Justin")
        self.assertEqual(root.form.predicate, "popular")
        self.assertEqual(root.timestep, 2)
        self.assertEqual(root.verdict.support[0].meta["occurred_due_to"], "converged_rule")

        mary = next(event for event in timeline.events if event.form.terms[0].value == "Mary")
        self.assertEqual(mary.repr_text, "popular(Mary) = [0.85, 0.95]")
        self.assertEqual(mary.verdict.support[0].meta["seed_event"], True)

        self.assertTrue(
            any(event.verdict.support[0].meta["clause_groundings"] == ("[Mary]",) for event in timeline.events)
        )

    def test_converter_normalizes_edge_components_for_edge_candidate(self) -> None:
        trace = PyReasonTraceV0(
            timesteps=2,
            node_events=(),
            edge_events=(
                PyReasonTraceEventV0(
                    time=0,
                    fixpoint_op=1,
                    component="(Alice, Bob)",
                    component_type="edge",
                    label="trust_score",
                    old_bound=(0.0, 1.0),
                    new_bound=(0.4, 0.6),
                    occurred_due_to="friendship_fact",
                    clause_groundings=(),
                ),
                PyReasonTraceEventV0(
                    time=1,
                    fixpoint_op=2,
                    component="Alice-Bob",
                    component_type="edge",
                    label="trust_score",
                    old_bound=(0.4, 0.6),
                    new_bound=(0.9, 0.9),
                    occurred_due_to="trust_rule",
                    clause_groundings=(),
                ),
            ),
        )

        graph = pyreason_trace_to_evidence_graph(
            trace,
            candidate_id="cand_v2:edge",
            candidate_payload={
                "pred_id": "friends:trust_score",
                "terms": [
                    {"kind": "entity_ref", "value": "Alice"},
                    {"kind": "entity_ref", "value": "Bob"},
                    {"kind": "literal", "tag": "float64", "value": 0.9},
                ],
            },
        )

        self.assertEqual(len(graph.paths), 1)
        timeline = graph.paths[0]
        self.assertEqual(len(timeline.events), 2)
        self.assertTrue(all(event.form.terms[0].value == "Alice" for event in timeline.events))
        self.assertTrue(all(event.form.terms[1].value == "Bob" for event in timeline.events))
        root = timeline.events[timeline.metadata["root_event_index"]]
        self.assertEqual(root.timestep, 1)
        self.assertEqual(root.repr_text, "trust_score(Alice->Bob) = [0.9, 0.9]")

    def test_converter_rejects_missing_candidate_anchor(self) -> None:
        trace = PyReasonTraceV0(
            timesteps=1,
            node_events=(
                PyReasonTraceEventV0(
                    time=0,
                    fixpoint_op=1,
                    component="Alice",
                    component_type="node",
                    label="popular",
                    old_bound=(0.0, 1.0),
                    new_bound=(1.0, 1.0),
                    occurred_due_to="seed_fact",
                    clause_groundings=(),
                ),
            ),
            edge_events=(),
        )

        with self.assertRaisesRegex(ValueError, "candidate anchor not found"):
            pyreason_trace_to_evidence_graph(
                trace,
                candidate_id="cand_v2:missing",
                candidate_payload={
                    "pred_id": "user:popular",
                    "terms": [
                        {"kind": "entity_ref", "value": "Bob"},
                        {"kind": "literal", "tag": "string", "value": "true"},
                    ],
                },
            )


if __name__ == "__main__":
    unittest.main()
