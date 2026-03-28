from __future__ import annotations

import unittest

from factpy_kernel.audit import (
    EDGE_SUPPORTS,
    LAYOUT_TREE,
    NODE_CONCLUSION,
    NODE_PREMISE,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    evidence_graph_from_dict,
    evidence_graph_to_dict,
)


class AuditEvidenceGraphTests(unittest.TestCase):
    def test_graph_accepts_valid_tree_graph(self) -> None:
        graph = EvidenceGraph(
            graph_id="eg:candidate-1",
            engine="souffle",
            root_node_id="n:root",
            nodes=(
                EvidenceNode(
                    node_id="n:root",
                    node_kind=NODE_CONCLUSION,
                    component="bob",
                    label="popular",
                    value_summary="true",
                    engine_meta={"rule_number": "R1"},
                ),
                EvidenceNode(
                    node_id="n:p1",
                    node_kind=NODE_PREMISE,
                    component="alice",
                    label="popular",
                    value_summary="true",
                ),
            ),
            edges=(
                EvidenceEdge(
                    edge_id="e:1",
                    from_node_id="n:p1",
                    to_node_id="n:root",
                    edge_kind=EDGE_SUPPORTS,
                    rule_label="popular propagation",
                ),
            ),
            support_kind="souffle_witness_v1",
            layout_hint=LAYOUT_TREE,
            metadata={"confidence": 1.0},
        )

        self.assertEqual(graph.root_node_id, "n:root")
        self.assertEqual(graph.nodes[0].engine_meta["rule_number"], "R1")
        self.assertEqual(graph.edges[0].rule_label, "popular propagation")
        self.assertEqual(graph.metadata["confidence"], 1.0)

    def test_graph_rejects_duplicate_node_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate node_id"):
            EvidenceGraph(
                graph_id="eg:dup-node",
                engine="souffle",
                root_node_id="n:root",
                nodes=(
                    EvidenceNode("n:root", NODE_CONCLUSION, "bob", "popular", "true"),
                    EvidenceNode("n:root", NODE_PREMISE, "alice", "popular", "true"),
                ),
                edges=(),
                support_kind="souffle_witness_v1",
            )

    def test_graph_rejects_duplicate_edge_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate edge_id"):
            EvidenceGraph(
                graph_id="eg:dup-edge",
                engine="souffle",
                root_node_id="n:root",
                nodes=(
                    EvidenceNode("n:root", NODE_CONCLUSION, "bob", "popular", "true"),
                    EvidenceNode("n:p1", NODE_PREMISE, "alice", "popular", "true"),
                ),
                edges=(
                    EvidenceEdge("e:1", "n:p1", "n:root", EDGE_SUPPORTS),
                    EvidenceEdge("e:1", "n:p1", "n:root", EDGE_SUPPORTS),
                ),
                support_kind="souffle_witness_v1",
            )

    def test_graph_rejects_missing_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "root_node_id 'n:missing' not in nodes"):
            EvidenceGraph(
                graph_id="eg:missing-root",
                engine="souffle",
                root_node_id="n:missing",
                nodes=(EvidenceNode("n:root", NODE_CONCLUSION, "bob", "popular", "true"),),
                edges=(),
                support_kind="souffle_witness_v1",
            )

    def test_graph_rejects_edge_endpoint_not_in_nodes(self) -> None:
        with self.assertRaisesRegex(ValueError, "edge from_node_id 'n:p1' not in nodes"):
            EvidenceGraph(
                graph_id="eg:bad-edge",
                engine="souffle",
                root_node_id="n:root",
                nodes=(EvidenceNode("n:root", NODE_CONCLUSION, "bob", "popular", "true"),),
                edges=(EvidenceEdge("e:1", "n:p1", "n:root", EDGE_SUPPORTS),),
                support_kind="souffle_witness_v1",
            )

    def test_graph_rejects_unsupported_layout(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported layout_hint: dag"):
            EvidenceGraph(
                graph_id="eg:bad-layout",
                engine="souffle",
                root_node_id="n:root",
                nodes=(EvidenceNode("n:root", NODE_CONCLUSION, "bob", "popular", "true"),),
                edges=(),
                support_kind="souffle_witness_v1",
                layout_hint="dag",
            )

    def test_node_rejects_unsupported_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported node_kind: rule_fire"):
            EvidenceNode("n:1", "rule_fire", "Mary", "popular", "[0.85, 0.95]")

    def test_edge_rejects_unsupported_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported edge_kind: propagates"):
            EvidenceEdge("e:1", "n:1", "n:2", "propagates")

    def test_shallow_freeze_wraps_mapping_fields(self) -> None:
        graph = EvidenceGraph(
            graph_id="eg:freeze",
            engine="pyreason",
            root_node_id="n:root",
            nodes=(
                EvidenceNode(
                    node_id="n:root",
                    node_kind=NODE_CONCLUSION,
                    component="Justin",
                    label="popular",
                    value_summary="[1.0, 1.0]",
                    engine_meta={"old_bound": [0, 1]},
                ),
            ),
            edges=(),
            support_kind="pyreason_provenance_v1",
            metadata={"timesteps": 2},
        )

        with self.assertRaises(TypeError):
            graph.metadata["timesteps"] = 3  # type: ignore[index]
        with self.assertRaises(TypeError):
            graph.nodes[0].engine_meta["old_bound"] = [1, 1]  # type: ignore[index]

    def test_graph_round_trips_through_json_friendly_dict(self) -> None:
        graph = EvidenceGraph(
            graph_id="eg:roundtrip",
            engine="pyreason",
            root_node_id="n:root",
            nodes=(
                EvidenceNode(
                    node_id="n:root",
                    node_kind=NODE_CONCLUSION,
                    component="Alice",
                    label="popular",
                    value_summary="[0.8, 0.9]",
                    engine_meta={"old_bound": (0.0, 0.0), "clause_groundings": ("seed",)},
                ),
                EvidenceNode(
                    node_id="n:p1",
                    node_kind=NODE_PREMISE,
                    component="Alice",
                    label="name",
                    value_summary="Alice",
                ),
            ),
            edges=(
                EvidenceEdge(
                    edge_id="e:1",
                    from_node_id="n:p1",
                    to_node_id="n:root",
                    edge_kind=EDGE_SUPPORTS,
                    engine_meta={"groundings": ("g1", "g2")},
                ),
            ),
            support_kind="pyreason_provenance_v1",
            metadata={"timesteps": 2, "anchor": ("Alice",)},
        )

        rebuilt = evidence_graph_from_dict(evidence_graph_to_dict(graph))

        self.assertEqual(rebuilt, graph)
        self.assertEqual(rebuilt.nodes[0].engine_meta["clause_groundings"], ("seed",))
        self.assertEqual(rebuilt.metadata["anchor"], ("Alice",))


if __name__ == "__main__":
    unittest.main()
