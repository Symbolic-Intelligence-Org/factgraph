from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class WorkloadCSmokeRunnerTests(unittest.TestCase):
    def test_pyreason_baseline_reports_bridge_status(self) -> None:
        result = self._run_runner("pyreason")
        self.assertEqual(result["workload"], "C")
        self.assertEqual(result["baseline"], "pyreason")
        self.assertEqual(result["raw_candidates"], [])
        self.assertIn("pyreason_bridge_v0_not_implemented", result["unsupported_features"])

    def test_problog_baseline_emits_normalized_workload_c_shape(self) -> None:
        result = self._run_runner("problog")
        self.assertEqual(result["workload"], "C")
        self.assertEqual(result["baseline"], "problog")
        self.assertEqual(result["aggregation"], "max")
        self.assertIn("raw_candidates", result)
        self.assertIn("provenance_entries", result)
        self.assertIn("unsupported_features", result)
        if result["unsupported_features"]:
            self.assertTrue(any(item.startswith("engine_unavailable:") for item in result["unsupported_features"]))
            return

        self.assertEqual(len(result["raw_candidates"]), 4)
        self.assertEqual(len(result["provenance_entries"]), 3)
        triples = {
            (row["subject"], row["relation"], row["object"])
            for row in result["raw_candidates"]
        }
        self.assertEqual(
            triples,
            {
                ("ent001", "indirect_dependency", "ent003"),
                ("ent010", "reachable_monitor", "ent030"),
                ("ent050", "supports", "ent060"),
            },
        )

    def test_souffle_proto_baseline_emits_normalized_workload_c_shape(self) -> None:
        result = self._run_runner("souffle_proto")
        self.assertEqual(result["workload"], "C")
        self.assertEqual(result["baseline"], "souffle_proto")
        self.assertEqual(result["aggregation"], "max")
        self.assertIn("raw_candidates", result)
        self.assertIn("provenance_entries", result)
        self.assertIn("unsupported_features", result)
        if result["unsupported_features"]:
            self.assertTrue(any(item.startswith("engine_unavailable:") for item in result["unsupported_features"]))
            return

        self.assertEqual(len(result["raw_candidates"]), 4)
        self.assertEqual(len(result["provenance_entries"]), 3)
        support_rows = {
            tuple(entry["struct_support"])
            for entry in result["provenance_entries"]
            if entry["struct_support"]
        }
        self.assertEqual(
            support_rows,
            {
                ("ent001 -[depends_on]-> ent002", "ent002 -[depends_on]-> ent003"),
                ("ent010 -[monitors]-> ent020", "ent020 -[is_component_of]-> ent030"),
            },
        )

    def _run_runner(self, baseline: str) -> dict[str, object]:
        repo_root = Path(__file__).resolve().parents[3]
        runner_path = repo_root / "tools" / "benchmarks" / "bench_runner.py"
        payload = {
            "workload": "C",
            "seed": 42,
            "struct_facts": [
                {"subject_id": "ent001", "relation": "depends_on", "object_id": "ent002"},
                {"subject_id": "ent002", "relation": "depends_on", "object_id": "ent003"},
                {"subject_id": "ent010", "relation": "monitors", "object_id": "ent020"},
                {"subject_id": "ent020", "relation": "is_component_of", "object_id": "ent030"},
            ],
            "evidence_facts": [
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
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            input_path = tmp_root / "workload_c_input.json"
            output_path = tmp_root / f"result_{baseline}.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(runner_path),
                    "--workload",
                    "C",
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
