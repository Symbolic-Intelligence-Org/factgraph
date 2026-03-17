from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class WorkloadASmokeRunnerTests(unittest.TestCase):
    def test_pyreason_baseline_reports_bridge_status(self) -> None:
        result = self._run_runner("pyreason")
        self.assertEqual(result["workload"], "A")
        self.assertEqual(result["baseline"], "pyreason")
        self.assertEqual(result["results"], [])
        self.assertIn("pyreason_bridge_v0_not_implemented", result["unsupported_features"])

    def test_problog_baseline_emits_result_shape_and_semantic_mismatch_marker(self) -> None:
        result = self._run_runner("problog")
        self.assertEqual(result["workload"], "A")
        self.assertEqual(result["baseline"], "problog")
        self.assertEqual(result["algebra"], "min_max")
        self.assertIn("results", result)
        self.assertIn("provenance_entries", result)
        self.assertIn("unsupported_features", result)
        if result["unsupported_features"] == ["engine_unavailable:problog_cli"]:
            return

        self.assertIn("semantic_mismatch:min_max_vs_possible_world", result["unsupported_features"])
        self.assertTrue(result["results"])
        pairs = {(row["source"], row["target"]) for row in result["results"]}
        self.assertIn(("e000", "e002"), pairs)
        self.assertIn(("e001", "e000"), pairs)

    def test_souffle_proto_baseline_emits_result_shape(self) -> None:
        result = self._run_runner("souffle_proto")
        self.assertEqual(result["workload"], "A")
        self.assertEqual(result["baseline"], "souffle_proto")
        self.assertEqual(result["algebra"], "min_max")
        self.assertIn("results", result)
        self.assertIn("provenance_entries", result)
        self.assertIn("unsupported_features", result)
        if result["unsupported_features"]:
            self.assertEqual(result["unsupported_features"], ["engine_unavailable:souffle_cli"])
            return

        self.assertTrue(result["results"])
        pairs = {(row["source"], row["target"]) for row in result["results"]}
        self.assertIn(("e000", "e002"), pairs)
        self.assertIn(("e001", "e000"), pairs)

    def test_souffle_full_a_baseline_emits_result_shape(self) -> None:
        result = self._run_runner("souffle_full_a")
        self.assertEqual(result["workload"], "A")
        self.assertEqual(result["baseline"], "souffle_full_a")
        self.assertEqual(result["algebra"], "min_max")
        self.assertIn("results", result)
        self.assertIn("provenance_entries", result)
        self.assertIn("unsupported_features", result)
        if result["unsupported_features"] == ["engine_unavailable:souffle_cli"]:
            return

        self.assertIn("provenance_reconstructed_from_reference", result["unsupported_features"])
        self.assertTrue(result["results"])
        pairs = {(row["source"], row["target"]) for row in result["results"]}
        self.assertIn(("e000", "e002"), pairs)
        self.assertIn(("e001", "e000"), pairs)

    def _run_runner(self, baseline: str) -> dict[str, object]:
        repo_root = Path(__file__).resolve().parents[3]
        runner_path = repo_root / "tools" / "benchmarks" / "bench_runner.py"
        payload = {
            "workload": "A",
            "seed": 42,
            "edge_facts": [
                {"source_id": "e000", "target_id": "e001", "confidence": 0.9},
                {"source_id": "e001", "target_id": "e002", "confidence": 0.8},
                {"source_id": "e000", "target_id": "e002", "confidence": 0.5},
                {"source_id": "e002", "target_id": "e000", "confidence": 0.7},
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            input_path = tmp_root / "workload_a_input.json"
            output_path = tmp_root / f"result_{baseline}.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(runner_path),
                    "--workload",
                    "A",
                    "--baseline",
                    baseline,
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            return json.loads(output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
