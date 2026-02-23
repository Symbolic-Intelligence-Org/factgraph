from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.adapters.souffle.runner import run_package
from factpy_kernel.core.store.api import Store


class OutputsMapV1Tests(unittest.TestCase):
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
        self.store = Store(schema_ir=self.schema_ir)
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:outputs-map",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )

    def test_manifest_contains_outputs_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            manifest_path = export_package(self.store, out_dir, ExportOptions())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertIn("outputs_map", manifest)
            self.assertEqual(
                manifest["outputs_map"]["person:country"],
                ["p_person_country"],
            )

    def test_runner_uses_outputs_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            manifest_path = export_package(self.store, out_dir, ExportOptions())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["outputs_map"] = {"person:country": ["p_custom_country"]}
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
                newline="\n",
            )

            run_manifest_path = run_package(out_dir, ["person:country"], engine="noop")
            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))

            self.assertIn("outputs/p_custom_country.out.facts", run_manifest["resolved_outputs"])
            self.assertTrue((out_dir / "outputs" / "p_custom_country.out.facts").exists())
            self.assertFalse((out_dir / "outputs" / "p_person_country.out.facts").exists())


if __name__ == "__main__":
    unittest.main()
