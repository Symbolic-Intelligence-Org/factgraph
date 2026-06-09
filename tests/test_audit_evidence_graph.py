from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factgraph.audit import (
    BoundVar,
    Const,
    EvidenceAtom,
    EvidenceGraph,
    EvidenceRule,
    EvidenceTimeline,
    EvidenceTree,
    Fact,
    Holds,
    LAYOUT_TIMELINE,
    LAYOUT_TREE,
    Source,
    evidence_graph_from_dict,
    evidence_graph_to_dict,
)
from factgraph.audit.reader import AuditReadError, _read_evidence_graphs
from factgraph.application.protocol import BOOLEAN_CERTAINTY, Certainty


class AuditEvidenceGraphTests(unittest.TestCase):
    def test_audit_facade_reexports_paths_model_graph(self) -> None:
        graph = EvidenceGraph(
            graph_id="eg:candidate-1",
            engine="souffle",
            layout_hint=LAYOUT_TREE,
            subject_binding={"person": "alice"},
            paths=(
                EvidenceTree(
                    tree_id="row-1",
                    status="holds",
                    rules=(
                        EvidenceRule(
                            occurrence_alias="head",
                            rule_id="popular",
                            role="head",
                            status="holds",
                            ports={"person": "alice"},
                            atoms=(
                                EvidenceAtom(
                                    form=Fact("popular", (BoundVar("$person", "alice"),)),
                                    verdict=Holds(
                                        certainty=BOOLEAN_CERTAINTY,
                                        support=(Source(ref="asrt-1", value="popular(alice)"),),
                                    ),
                                    atom_id="atom-1",
                                    repr_text="popular(alice)",
                                ),
                            ),
                        ),
                    ),
                    metadata={"support_kind": "souffle_witness_v1"},
                ),
            ),
            certainty=BOOLEAN_CERTAINTY,
            metadata={"row_id": "row-1"},
        )

        rebuilt = evidence_graph_from_dict(evidence_graph_to_dict(graph))

        self.assertEqual(rebuilt, graph)
        self.assertEqual(rebuilt.paths[0].rules[0].atoms[0].repr_text, "popular(alice)")
        self.assertFalse(hasattr(rebuilt, "nodes"))

    def test_timeline_graph_round_trips_through_json_friendly_dict(self) -> None:
        graph = EvidenceGraph(
            graph_id="eg:timeline",
            engine="pyreason",
            layout_hint=LAYOUT_TIMELINE,
            subject_binding={"term_0": "alice"},
            paths=(
                EvidenceTimeline(
                    timeline_id="timeline-1",
                    status="holds",
                    events=(
                        EvidenceAtom(
                            form=Fact("popular", (Const("alice"),)),
                            verdict=Holds(
                                certainty=Certainty(0.8, 0.9, "possibilistic"),
                                support=(Source(ref="trace:1", meta={"clause_groundings": ("seed",)}),),
                            ),
                            atom_id="event-1",
                            repr_text="popular(alice) = [0.8, 0.9]",
                            timestep=1,
                        ),
                    ),
                    certainty=Certainty(0.8, 0.9, "possibilistic"),
                    metadata={"timesteps": 2},
                ),
            ),
            certainty=Certainty(0.8, 0.9, "possibilistic"),
            metadata={"support_kind": "pyreason_provenance_v1"},
        )

        row = evidence_graph_to_dict(graph)
        rebuilt = evidence_graph_from_dict(json.loads(json.dumps(row)))

        self.assertEqual(rebuilt, graph)
        timeline = rebuilt.paths[0]
        self.assertIsInstance(timeline, EvidenceTimeline)
        self.assertEqual(timeline.events[0].timestep, 1)
        self.assertEqual(timeline.events[0].verdict.support[0].meta["clause_groundings"], ("seed",))

    def test_from_dict_rejects_missing_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "row.paths must be list"):
            evidence_graph_from_dict(
                {
                    "graph_id": "eg:bad",
                    "engine": "native",
                    "layout_hint": LAYOUT_TREE,
                    "subject_binding": {},
                }
            )

    def test_read_evidence_graphs_rejects_duplicate_candidate_id(self) -> None:
        graph_dict = evidence_graph_to_dict(
            EvidenceGraph(
                graph_id="eg:dup",
                engine="test",
                layout_hint=LAYOUT_TREE,
                subject_binding={},
                paths=(
                    EvidenceTree(
                        tree_id="row-1",
                        status="holds",
                        rules=(
                            EvidenceRule(
                                occurrence_alias="head",
                                rule_id="rule",
                                role="head",
                                status="holds",
                            ),
                        ),
                    ),
                ),
            )
        )
        rows = [
            {"candidate_id": "cand-1", "evidence_graph": graph_dict},
            {"candidate_id": "cand-1", "evidence_graph": graph_dict},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "evidence_graphs.jsonl"
            jsonl_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            mapping = {"evidence_graphs": "evidence_graphs.jsonl"}
            with self.assertRaises(AuditReadError) as ctx:
                _read_evidence_graphs(Path(tmp), mapping)
            self.assertIn("duplicate candidate_id", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
