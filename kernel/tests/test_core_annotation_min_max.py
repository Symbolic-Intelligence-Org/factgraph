from __future__ import annotations

import unittest

from kernel.core.annotation import (
    build_min_max_provenance_entries,
    derive_min_max_path_confidence,
    serialize_min_max_conclusions,
)


class MinMaxAnnotationKernelTests(unittest.TestCase):
    def test_prefers_higher_confidence_path_over_direct_edge(self) -> None:
        edge_facts = [
            {"source_id": "e000", "target_id": "e001", "confidence": 0.9},
            {"source_id": "e001", "target_id": "e002", "confidence": 0.8},
            {"source_id": "e000", "target_id": "e002", "confidence": 0.5},
        ]

        conclusions = derive_min_max_path_confidence(edge_facts)
        rows = {(row["source"], row["target"]): row for row in serialize_min_max_conclusions(conclusions)}
        provenance = {
            (entry["candidate"]["source"], entry["candidate"]["target"]): entry
            for entry in build_min_max_provenance_entries(conclusions)
        }

        self.assertEqual(rows[("e000", "e002")]["confidence"], 0.8)
        self.assertEqual(rows[("e000", "e002")]["min_support_depth"], 1)
        self.assertEqual(
            provenance[("e000", "e002")]["support_path"],
            [
                "e000 -[0.900000]-> e001",
                "e001 -[0.800000]-> e002",
            ],
        )

    def test_prefers_shorter_path_on_confidence_tie(self) -> None:
        edge_facts = [
            {"source_id": "e000", "target_id": "e001", "confidence": 0.8},
            {"source_id": "e001", "target_id": "e003", "confidence": 0.9},
            {"source_id": "e000", "target_id": "e002", "confidence": 0.8},
            {"source_id": "e002", "target_id": "e004", "confidence": 0.9},
            {"source_id": "e004", "target_id": "e003", "confidence": 0.95},
        ]

        conclusions = derive_min_max_path_confidence(edge_facts)
        provenance = {
            (entry["candidate"]["source"], entry["candidate"]["target"]): entry
            for entry in build_min_max_provenance_entries(conclusions)
        }

        self.assertEqual(
            provenance[("e000", "e003")]["support_path"],
            [
                "e000 -[0.800000]-> e001",
                "e001 -[0.900000]-> e003",
            ],
        )


if __name__ == "__main__":
    unittest.main()
