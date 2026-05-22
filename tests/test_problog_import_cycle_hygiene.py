from __future__ import annotations

import os
import subprocess
import sys
import unittest


class ProbLogImportCycleHygieneTests(unittest.TestCase):
    def _run_fresh_import(self, statement: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-c", statement],
            check=False,
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
        )

    def test_problog_export_import_does_not_hit_round_event_cycle(self) -> None:
        result = self._run_fresh_import(
            "from factgraph.adapters.problog.problog_export import export_problog; "
            "print(export_problog.__name__)"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "export_problog")

    def test_audit_evidence_graph_import_does_not_hit_round_event_cycle(self) -> None:
        result = self._run_fresh_import("import factgraph.audit.evidence_graph; print('ok')")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ok")


if __name__ == "__main__":
    unittest.main()
