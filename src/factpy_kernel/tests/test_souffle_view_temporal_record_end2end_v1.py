from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.adapters.souffle.pred_norm import normalize_pred_id
from factpy_kernel.adapters.souffle.runner import find_souffle_binary, run_package
from factpy_kernel.core.store.api import Store


class SouffleViewTemporalRecordEnd2EndV1Tests(unittest.TestCase):
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
                    "pred_id": "person:salary_history",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "year", "type_domain": "string"},
                        {"name": "amount", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0, 1],
                    "cardinality": "temporal",
                }
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:salary_history"],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }

    def test_temporal_record_outputs_all_active_history(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:temporal"

        set_field(
            store.ledger,
            pred_id="person:salary_history",
            e_ref=e_ref,
            rest_terms=[("string", "2024"), ("string", "100")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:salary_history",
            e_ref=e_ref,
            rest_terms=[("string", "2024"), ("string", "200")],
            meta={"source": "test", "source_loc": "row-2"},
        )
        set_field(
            store.ledger,
            pred_id="person:salary_history",
            e_ref=e_ref,
            rest_terms=[("string", "2025"), ("string", "300")],
            meta={"source": "test", "source_loc": "row-3"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            export_package(store, out_dir, ExportOptions())
            run_manifest_path = run_package(
                out_dir,
                ["person:salary_history"],
                engine="souffle",
            )

            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["engine_mode"], "souffle")
            self.assertEqual(run_manifest["exit_code"], 0)

            out_file = out_dir / "outputs" / f"{normalize_pred_id('person:salary_history')}.out.facts"
            self.assertTrue(out_file.exists())
            lines = [line for line in out_file.read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(
                lines,
                [
                    f"{e_ref}\t2024\t100",
                    f"{e_ref}\t2024\t200",
                    f"{e_ref}\t2025\t300",
                ],
            )


if __name__ == "__main__":
    unittest.main()
