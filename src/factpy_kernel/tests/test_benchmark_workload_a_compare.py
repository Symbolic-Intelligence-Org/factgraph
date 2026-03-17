from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = REPO_ROOT / "tools" / "benchmarks"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from workload_a_reference import (  # noqa: E402
    build_provenance_entries,
    build_workload_a_golden,
    compare_result_to_golden,
    derive_workload_a_minmax,
    generate_workload_a,
)


class WorkloadACompareHarnessTests(unittest.TestCase):
    def test_reference_result_matches_golden(self) -> None:
        payload = generate_workload_a(n_nodes=12, n_edges=24, seed=42)
        results = derive_workload_a_minmax(payload)
        golden = build_workload_a_golden(payload)
        result = {
            "baseline": "reference",
            "results": [
                {
                    "source": row["source"],
                    "target": row["target"],
                    "confidence": row["confidence"],
                    "min_support_depth": row["min_support_depth"],
                }
                for row in results
            ],
            "provenance_entries": build_provenance_entries(results),
            "unsupported_features": [],
            "notes": "",
        }

        report = compare_result_to_golden(result, golden, payload)
        self.assertTrue(report["golden_diff"]["matches_golden"])
        self.assertEqual(report["provenance_check"]["complete_rate"], 1.0)
        self.assertEqual(report["provenance_check"]["gaps"], [])

    def test_compare_detects_semantic_confidence_deltas(self) -> None:
        payload = {
            "workload": "A",
            "seed": 42,
            "edge_facts": [
                {"source_id": "e000", "target_id": "e001", "confidence": 0.9},
                {"source_id": "e001", "target_id": "e002", "confidence": 0.8},
                {"source_id": "e000", "target_id": "e002", "confidence": 0.5},
            ],
        }
        results = derive_workload_a_minmax(payload)
        golden = build_workload_a_golden(payload)
        broken = {
            "baseline": "problog_like",
            "results": [
                {
                    "source": row["source"],
                    "target": row["target"],
                    "confidence": 0.72 if (row["source"], row["target"]) == ("e000", "e002") else row["confidence"],
                    "min_support_depth": row["min_support_depth"],
                }
                for row in results
            ],
            "provenance_entries": build_provenance_entries(results),
            "unsupported_features": ["semantic_mismatch:min_max_vs_possible_world"],
            "notes": "",
        }

        report = compare_result_to_golden(broken, golden, payload)
        self.assertFalse(report["golden_diff"]["matches_golden"])
        deltas = [row for row in report["golden_diff"]["confidence_deltas"] if row["absolute_delta"] > 0.0]
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0]["candidate"], {"source": "e000", "target": "e002"})


if __name__ == "__main__":
    unittest.main()
