from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.adapters.souffle.runner import find_souffle_binary, run_package
from factpy_kernel.core.store.api import Store


class SouffleViewMultiEnd2EndV1Tests(unittest.TestCase):
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
                    "pred_id": "person:tag",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "tag", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "multi",
                }
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:tag"],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }

    def test_multi_outputs_all_active_claims(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:multi"

        set_field(
            store.ledger,
            pred_id="person:tag",
            e_ref=e_ref,
            rest_terms=[("string", "a")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:tag",
            e_ref=e_ref,
            rest_terms=[("string", "b")],
            meta={"source": "test", "source_loc": "row-2"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            export_package(store, out_dir, ExportOptions())
            run_manifest_path = run_package(out_dir, ["person:tag"], engine="souffle")

            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["engine_mode"], "souffle")
            self.assertEqual(run_manifest["exit_code"], 0)

            out_file = out_dir / "outputs" / "p_person_tag.out.facts"
            self.assertTrue(out_file.exists())
            lines = [line for line in out_file.read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(
                lines,
                [
                    f"{e_ref}\ta",
                    f"{e_ref}\tb",
                ],
            )


if __name__ == "__main__":
    unittest.main()
