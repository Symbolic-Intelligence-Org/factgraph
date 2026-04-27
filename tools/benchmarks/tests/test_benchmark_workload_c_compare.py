from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = REPO_ROOT / "tools" / "benchmarks"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from workload_c_reference import (  # noqa: E402
    build_provenance_entries,
    build_workload_c_golden,
    compare_result_to_golden,
    derive_workload_c_raw_candidates,
    generate_workload_c,
)


class WorkloadCCompareHarnessTests(unittest.TestCase):
    def test_reference_result_matches_golden(self) -> None:
        payload = generate_workload_c(n_struct=20, n_evidence=10, n_entities=10, seed=42)
        raw_candidates = derive_workload_c_raw_candidates(payload)
        golden = build_workload_c_golden(payload, top_k=10)
        provenance_entries = build_provenance_entries(
            payload["struct_facts"],
            payload["evidence_facts"],
            raw_candidates,
        )
        result = {
            "baseline": "reference",
            "raw_candidates": raw_candidates,
            "provenance_entries": provenance_entries,
            "unsupported_features": [],
            "notes": "",
        }

        report = compare_result_to_golden(result, golden, payload, top_k=10)
        self.assertTrue(report["golden_diff"]["matches_golden"])
        self.assertEqual(report["provenance_check"]["complete_rate"], 1.0)
        self.assertEqual(report["provenance_check"]["gaps"], [])

    def test_compare_detects_missing_provenance_entries(self) -> None:
        payload = generate_workload_c(n_struct=20, n_evidence=10, n_entities=10, seed=42)
        raw_candidates = derive_workload_c_raw_candidates(payload)
        golden = build_workload_c_golden(payload, top_k=5)
        result = {
            "baseline": "broken",
            "raw_candidates": raw_candidates,
            "provenance_entries": [],
            "unsupported_features": [],
            "notes": "",
        }

        report = compare_result_to_golden(result, golden, payload, top_k=5)
        self.assertFalse(report["golden_diff"]["missing"] or report["golden_diff"]["extra"])
        self.assertEqual(report["provenance_check"]["complete_rate"], 0.0)
        self.assertTrue(report["provenance_check"]["gaps"])
        self.assertTrue(
            all(gap["gap_type"] == "missing_provenance_entry" for gap in report["provenance_check"]["gaps"])
        )


if __name__ == "__main__":
    unittest.main()
