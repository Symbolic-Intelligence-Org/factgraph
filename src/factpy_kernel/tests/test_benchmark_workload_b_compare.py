from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = REPO_ROOT / "tools" / "benchmarks"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from workload_b_reference import (  # noqa: E402
    build_workload_b_golden,
    compare_result_to_golden,
    generate_workload_b,
    simulate_workload_b,
)


class WorkloadBCompareHarnessTests(unittest.TestCase):
    def test_reference_result_matches_golden(self) -> None:
        payload = generate_workload_b(n_entities=12, t_max=5, seed=42)
        simulation = simulate_workload_b(payload)
        golden = build_workload_b_golden(payload)
        result = {
            "baseline": "reference",
            "results": simulation["results"],
            "provenance_entries": simulation["provenance_entries"],
            "unsupported_features": [],
            "notes": "",
        }

        report = compare_result_to_golden(result, golden, payload)
        self.assertTrue(report["golden_diff"]["matches_golden"])
        self.assertEqual(report["provenance_check"]["complete_rate"], 1.0)
        self.assertEqual(report["provenance_check"]["gaps"], [])

    def test_compare_detects_missing_provenance_entries(self) -> None:
        payload = generate_workload_b(n_entities=12, t_max=5, seed=42)
        simulation = simulate_workload_b(payload)
        golden = build_workload_b_golden(payload)
        result = {
            "baseline": "broken",
            "results": simulation["results"],
            "provenance_entries": [],
            "unsupported_features": [],
            "notes": "",
        }

        report = compare_result_to_golden(result, golden, payload)
        self.assertTrue(report["golden_diff"]["matches_golden"])
        self.assertLess(report["provenance_check"]["complete_rate"], 1.0)
        self.assertTrue(report["provenance_check"]["gaps"])
        self.assertTrue(
            all(gap["gap_type"] == "missing_event_provenance" for gap in report["provenance_check"]["gaps"])
        )


if __name__ == "__main__":
    unittest.main()
