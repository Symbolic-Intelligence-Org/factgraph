from __future__ import annotations

import unittest

from kernel.audit import (
    EDGE_DERIVES,
    EDGE_UPDATES,
    LAYOUT_TIMELINE,
    LAYOUT_TREE,
    NODE_CONCLUSION,
    NODE_PREMISE,
    NODE_SEED,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    render_evidence_graph_html,
)


class AuditEvidenceGraphRenderTests(unittest.TestCase):
    def test_tree_renderer_outputs_root_and_child_branches(self) -> None:
        graph = EvidenceGraph(
            graph_id="eg:tree",
            engine="problog",
            root_node_id="n:root",
            nodes=(
                EvidenceNode(
                    node_id="n:root",
                    node_kind=NODE_CONCLUSION,
                    component="alice",
                    label="c",
                    value_summary="0.35",
                    engine_meta={"goal": "c(alice)", "event_status": "result"},
                ),
                EvidenceNode(
                    node_id="n:a",
                    node_kind=NODE_SEED,
                    component="alice",
                    label="a",
                    value_summary="true",
                ),
                EvidenceNode(
                    node_id="n:b",
                    node_kind=NODE_SEED,
                    component="alice",
                    label="b",
                    value_summary="true",
                ),
            ),
            edges=(
                EvidenceEdge("e:1", "n:a", "n:root", EDGE_DERIVES, rule_label="rule_a"),
                EvidenceEdge("e:2", "n:b", "n:root", EDGE_DERIVES, rule_label="rule_b"),
            ),
            support_kind="problog_provenance_v1",
            layout_hint=LAYOUT_TREE,
        )

        html = render_evidence_graph_html(graph)

        self.assertIn("evidence-graph-tree", html)
        self.assertIn("Unified Evidence Graph", html)
        self.assertIn(">Tree Layout<", html)
        self.assertIn("c", html)
        self.assertIn("alice", html)
        self.assertIn("rule_a", html)
        self.assertIn("rule_b", html)
        self.assertIn("ROOT", html)
        self.assertIn("data-node-id='n:root'", html)

    def test_timeline_renderer_uses_css_grid_and_groups_by_component_and_timestep(self) -> None:
        graph = EvidenceGraph(
            graph_id="eg:timeline",
            engine="pyreason",
            root_node_id="n:t1",
            nodes=(
                EvidenceNode(
                    node_id="n:t0",
                    node_kind=NODE_SEED,
                    component="Mary",
                    label="popular",
                    value_summary="[0.85, 0.95]",
                    timestamp=0,
                    engine_meta={"occurred_due_to": "seed_fact"},
                ),
                EvidenceNode(
                    node_id="n:t1",
                    node_kind=NODE_CONCLUSION,
                    component="Justin",
                    label="popular",
                    value_summary="[1.0, 1.0]",
                    timestamp=1,
                    engine_meta={"occurred_due_to": "spread_rule"},
                ),
                EvidenceNode(
                    node_id="n:t2",
                    node_kind=NODE_PREMISE,
                    component="Justin",
                    label="popular",
                    value_summary="[1.0, 1.0]",
                    timestamp=2,
                    engine_meta={"occurred_due_to": "converged_rule"},
                ),
            ),
            edges=(EvidenceEdge("e:1", "n:t1", "n:t2", EDGE_UPDATES, rule_label="converged_rule"),),
            support_kind="pyreason_provenance_v1",
            layout_hint=LAYOUT_TIMELINE,
            metadata={"timesteps": 3},
        )

        html = render_evidence_graph_html(graph)

        self.assertIn("evidence-graph-timeline", html)
        self.assertIn("display:grid", html)
        self.assertIn("grid-template-columns:180px repeat(3, minmax(180px, 1fr))", html)
        self.assertIn("Timestep 0", html)
        self.assertIn("Timestep 1", html)
        self.assertIn("Mary", html)
        self.assertIn("Justin", html)
        self.assertIn("spread_rule", html)
        self.assertIn("ROOT", html)
        self.assertIn("data-component='Justin' data-timestep='1'", html)
        # F-EG-2: edge annotations must be visible in timeline
        self.assertIn("evidence-timeline-edge-note", html)
        self.assertIn("updates", html)  # edge_kind
        self.assertIn("converged_rule", html)  # rule_label
        self.assertIn("from popular", html)  # source node label

    def test_timeline_renderer_no_edges_produces_no_edge_notes(self) -> None:
        """F-EG-2: timeline with no edges must not produce edge-note divs."""
        graph = EvidenceGraph(
            graph_id="eg:no-edges",
            engine="test",
            root_node_id="n:a",
            nodes=(
                EvidenceNode(
                    node_id="n:a",
                    node_kind=NODE_CONCLUSION,
                    component="X",
                    label="fact",
                    value_summary="v",
                    timestamp=0,
                ),
            ),
            edges=(),
            support_kind="test",
            layout_hint=LAYOUT_TIMELINE,
        )
        html = render_evidence_graph_html(graph)
        self.assertIn("evidence-graph-timeline", html)
        self.assertNotIn("evidence-timeline-edge-note", html)

    def test_renderer_dispatch_rejects_unknown_layout(self) -> None:
        class BadGraph:
            layout_hint = "dag"

        with self.assertRaisesRegex(ValueError, "unsupported layout_hint: dag"):
            render_evidence_graph_html(BadGraph())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
