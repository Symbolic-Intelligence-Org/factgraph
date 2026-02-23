from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.adapters.souffle.runner import (
    RunnerCapabilityError,
    _parse_souffle_line,
    find_souffle_binary,
    run_package,
)
from factpy_kernel.core.store.api import Store


class RunnerSouffleV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {
            "schema_ir_version": "v1",
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [
                        {"name": "source_id", "type_domain": "string"},
                    ],
                }
            ],
            "predicates": [
                {
                    "pred_id": "person:country",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "country", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                }
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:country"],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }

    def test_souffle_runner_constant_output(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            export_package(store, out_dir, ExportOptions())

            (out_dir / "rules" / "idb.dl").write_text(
                """
p_person_country("x", "y").
""".lstrip(),
                encoding="utf-8",
                newline="\n",
            )

            run_manifest_path = run_package(out_dir, ["person:country"], engine="souffle")
            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(run_manifest["engine_mode"], "souffle")
            self.assertEqual(run_manifest["exit_code"], 0)

            out_file = out_dir / "outputs" / "p_person_country.out.facts"
            self.assertTrue(out_file.exists())
            self.assertEqual(out_file.read_text(encoding="utf-8").splitlines(), ["x\ty"])

    def test_noop_mode_bypasses_souffle(self) -> None:
        store = Store(schema_ir=self.schema_ir)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            export_package(store, out_dir, ExportOptions())

            (out_dir / "rules" / "idb.dl").write_text(
                "this is invalid souffle syntax",
                encoding="utf-8",
                newline="\n",
            )

            run_manifest_path = run_package(out_dir, ["person:country"], engine="noop")
            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(run_manifest["engine_mode"], "noop")
            self.assertEqual(run_manifest["exit_code"], 0)
            self.assertIn("outputs_digest", run_manifest["digests"])

            out_file = out_dir / "outputs" / "p_person_country.out.facts"
            self.assertTrue(out_file.exists())

    def test_parse_souffle_line_supports_quoted_csv(self) -> None:
        parsed = _parse_souffle_line('"x,y","z"', "sample.csv")
        self.assertEqual(parsed, ["x,y", "z"])

    def test_parse_souffle_line_rejects_invalid_quoted_csv(self) -> None:
        with self.assertRaises(RunnerCapabilityError):
            _parse_souffle_line('"x,y","z', "bad.csv")


if __name__ == "__main__":
    unittest.main()
