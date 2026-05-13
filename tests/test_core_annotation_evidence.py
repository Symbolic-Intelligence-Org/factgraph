from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from factgraph.core.annotation import (  # noqa: E402
    apply_max_evidence_aggregation,
    build_direct_evidence_candidates_proto,
    build_max_evidence_provenance,
    derive_struct_candidates_proto,
)


class EvidenceAnnotationfactgraphTests(unittest.TestCase):
    def test_derive_struct_candidates_proto_handles_both_rule_shapes(self) -> None:
        struct_facts = [
            {"subject_id": "ent001", "relation": "depends_on", "object_id": "ent002"},
            {"subject_id": "ent002", "relation": "depends_on", "object_id": "ent003"},
            {"subject_id": "ent010", "relation": "monitors", "object_id": "ent020"},
            {"subject_id": "ent020", "relation": "is_component_of", "object_id": "ent030"},
        ]

        rows = derive_struct_candidates_proto(struct_facts)
        triples = {(row["subject"], row["relation"], row["object"]) for row in rows}
        self.assertEqual(
            triples,
            {
                ("ent001", "indirect_dependency", "ent003"),
                ("ent010", "reachable_monitor", "ent030"),
            },
        )

    def test_derive_struct_candidates_proto_returns_empty_for_irrelevant_input(self) -> None:
        rows = derive_struct_candidates_proto(
            [{"subject_id": "ent001", "relation": "supports", "object_id": "ent002"}]
        )
        self.assertEqual(rows, [])

    def test_build_direct_evidence_candidates_proto_preserves_claim_fields(self) -> None:
        evidence_facts = [
            {
                "claim_id": "claim0000",
                "subject_id": "ent050",
                "relation": "supports",
                "object_id": "ent060",
                "confidence": 0.9,
                "source": "sensor",
            },
            {
                "claim_id": "claim0001",
                "subject_id": "ent050",
                "relation": "supports",
                "object_id": "ent060",
                "confidence": 0.7,
                "source": "llm_extraction",
            },
        ]

        rows = build_direct_evidence_candidates_proto(evidence_facts)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["claim_id"], "claim0000")
        self.assertEqual(rows[0]["confidence"], 0.9)
        self.assertEqual(rows[0]["source_type"], "direct_evidence")

    def test_build_max_evidence_provenance_emits_struct_and_direct_support(self) -> None:
        struct_facts = [
            {"subject_id": "ent001", "relation": "depends_on", "object_id": "ent002"},
            {"subject_id": "ent002", "relation": "depends_on", "object_id": "ent003"},
        ]
        evidence_facts = [
            {
                "claim_id": "claim0000",
                "subject_id": "ent050",
                "relation": "supports",
                "object_id": "ent060",
                "confidence": 0.9,
                "source": "sensor",
            }
        ]
        raw_candidates = [
            {
                "subject": "ent001",
                "relation": "indirect_dependency",
                "object": "ent003",
                "confidence": 1.0,
                "source_type": "derived",
                "claim_id": None,
            },
            {
                "subject": "ent050",
                "relation": "supports",
                "object": "ent060",
                "confidence": 0.9,
                "source_type": "direct_evidence",
                "claim_id": "claim0000",
            },
        ]

        entries = build_max_evidence_provenance(struct_facts, evidence_facts, raw_candidates)
        by_triple = {
            (entry["candidate"]["subject"], entry["candidate"]["relation"], entry["candidate"]["object"]): entry
            for entry in entries
        }
        self.assertEqual(
            by_triple[("ent001", "indirect_dependency", "ent003")]["struct_support"],
            [
                "ent001 -[depends_on]-> ent002",
                "ent002 -[depends_on]-> ent003",
            ],
        )
        self.assertEqual(
            by_triple[("ent050", "supports", "ent060")]["direct_evidence"],
            ["claim0000"],
        )

    def test_apply_max_evidence_aggregation_prefers_higher_confidence(self) -> None:
        raw_candidates = [
            {
                "subject": "ent050",
                "relation": "supports",
                "object": "ent060",
                "confidence": 0.7,
                "source_type": "direct_evidence",
                "claim_id": "claim0001",
            },
            {
                "subject": "ent050",
                "relation": "supports",
                "object": "ent060",
                "confidence": 0.9,
                "source_type": "direct_evidence",
                "claim_id": "claim0000",
            },
        ]

        aggregated = apply_max_evidence_aggregation(raw_candidates)
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(aggregated[0]["confidence"], 0.9)
        self.assertEqual(aggregated[0]["claim_id"], "claim0000")


if __name__ == "__main__":
    unittest.main()
