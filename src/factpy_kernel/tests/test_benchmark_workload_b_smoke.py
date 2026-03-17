from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class WorkloadBSmokeRunnerTests(unittest.TestCase):
    def test_pyreason_baseline_reports_bridge_status(self) -> None:
        result = self._run_runner("pyreason")
        self.assertEqual(result["workload"], "B")
        self.assertEqual(result["baseline"], "pyreason")
        self.assertEqual(result["results"], [])
        self.assertIn("pyreason_bridge_v0_not_implemented", result["unsupported_features"])

    def test_problog_baseline_reports_not_implemented(self) -> None:
        result = self._run_runner("problog")
        self.assertEqual(result["workload"], "B")
        self.assertEqual(result["baseline"], "problog")
        self.assertEqual(result["unsupported_features"], ["workload_b_problog_not_implemented"])

    def test_souffle_proto_baseline_emits_temporal_result_shape(self) -> None:
        result = self._run_runner("souffle_proto")
        self.assertEqual(result["workload"], "B")
        self.assertEqual(result["baseline"], "souffle_proto")
        self.assertEqual(result["T_max"], 3)
        self.assertTrue(result["annotation_kernel_noop"])
        self.assertFalse(result["native_temporal_advantage"])
        if result["unsupported_features"]:
            self.assertEqual(result["unsupported_features"], ["engine_unavailable:souffle_cli"])
            return

        by_entity = {row["entity"]: row for row in result["results"]}
        self.assertEqual(by_entity["ent000"]["final_status"], "active")
        self.assertEqual(by_entity["ent000"]["first_transition_at"], 1)
        self.assertEqual(by_entity["ent000"]["transition_count"], 1)
        self.assertEqual(by_entity["ent002"]["final_status"], "active")
        self.assertEqual(by_entity["ent002"]["first_transition_at"], 1)
        self.assertEqual(by_entity["ent002"]["transition_count"], 1)
        self.assertTrue(result["provenance_entries"])

    def _run_runner(self, baseline: str) -> dict[str, object]:
        repo_root = Path(__file__).resolve().parents[3]
        runner_path = repo_root / "tools" / "benchmarks" / "bench_runner.py"
        payload = {
            "workload": "B",
            "seed": 42,
            "t_max": 3,
            "init_state_facts": [
                {"entity_id": "ent000", "timestep": 0, "status": "degraded"},
                {"entity_id": "ent001", "timestep": 0, "status": "active"},
                {"entity_id": "ent002", "timestep": 0, "status": "inactive"},
                {"entity_id": "ent003", "timestep": 0, "status": "active"},
            ],
            "property_facts": [
                {"entity_id": "ent000", "prop_name": "class", "prop_value": "A"},
                {"entity_id": "ent001", "prop_name": "class", "prop_value": "B"},
                {"entity_id": "ent002", "prop_name": "class", "prop_value": "C"},
                {"entity_id": "ent003", "prop_name": "class", "prop_value": "A"},
            ],
            "rules": [
                {
                    "rule_id": 101,
                    "rule_label": "T2_101",
                    "template": "T2",
                    "source_status": "inactive",
                    "class_value": "C",
                    "target_status": "active",
                },
                {
                    "rule_id": 201,
                    "rule_label": "T3_201",
                    "template": "T3",
                    "source_status": "degraded",
                    "helper_class": "B",
                    "target_status": "active",
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            input_path = tmp_root / "workload_b_input.json"
            output_path = tmp_root / f"result_{baseline}.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(runner_path),
                    "--workload",
                    "B",
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
