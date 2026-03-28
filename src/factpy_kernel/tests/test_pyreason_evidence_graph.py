from __future__ import annotations

import unittest

from factpy_kernel.adapters.pyreason.provenance import (
    PyReasonTraceEventV0,
    PyReasonTraceV0,
    pyreason_trace_to_evidence_graph,
)
from factpy_kernel.audit import EDGE_UPDATES, LAYOUT_TIMELINE
from factpy_kernel.core.store._support import PYREASON_PROVENANCE_KIND


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
                    {"kind": "literal", "tag": "string", "value": "true"},
                ],
            },
        )

        self.assertEqual(graph.engine, "pyreason")
        self.assertEqual(graph.layout_hint, LAYOUT_TIMELINE)
        self.assertEqual(graph.support_kind, PYREASON_PROVENANCE_KIND)
        self.assertEqual(graph.metadata["timesteps"], 3)
        self.assertEqual(graph.metadata["node_event_count"], 3)
        self.assertEqual(graph.metadata["edge_event_count"], 1)
        self.assertEqual(len(graph.nodes), 4)
        self.assertEqual(len(graph.edges), 1)

        root = next(node for node in graph.nodes if node.node_id == graph.root_node_id)
        self.assertEqual(root.component, "Justin")
        self.assertEqual(root.label, "popular")
        self.assertEqual(root.timestamp, 2)
        self.assertEqual(root.node_kind, "conclusion")
        self.assertEqual(root.engine_meta["occurred_due_to"], "converged_rule")

        mary = next(node for node in graph.nodes if node.component == "Mary")
        self.assertEqual(mary.node_kind, "seed")
        self.assertEqual(mary.value_summary, "[0.85, 0.95]")

        update_edge = graph.edges[0]
        self.assertEqual(update_edge.edge_kind, EDGE_UPDATES)
        self.assertEqual(update_edge.rule_label, "converged_rule")
        self.assertEqual(update_edge.engine_meta["clause_groundings"], ("[Mary]",))

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

        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(len(graph.edges), 1)
        self.assertTrue(all(node.component == "Alice->Bob" for node in graph.nodes))
        root = next(node for node in graph.nodes if node.node_id == graph.root_node_id)
        self.assertEqual(root.timestamp, 1)
        self.assertEqual(root.value_summary, "[0.9, 0.9]")

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
