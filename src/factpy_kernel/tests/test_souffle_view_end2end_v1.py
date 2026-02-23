from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.adapters.souffle.runner import find_souffle_binary, run_package
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.store.ledger import MetaRow


class SouffleViewEnd2EndV1Tests(unittest.TestCase):
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

    def test_exported_view_rules_choose_latest_country(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:abc"

        asrt_old = set_field(
            store.ledger,
            pred_id="person:country",
            e_ref=e_ref,
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        asrt_new = set_field(
            store.ledger,
            pred_id="person:country",
            e_ref=e_ref,
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-2"},
        )

        self._set_ingested_at(store, asrt_old, 100)
        self._set_ingested_at(store, asrt_new, 200)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            export_package(store, out_dir, ExportOptions())
            run_manifest_path = run_package(out_dir, ["person:country"], engine="souffle")

            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["engine_mode"], "souffle")
            self.assertEqual(run_manifest["exit_code"], 0)

            out_file = out_dir / "outputs" / "p_person_country.out.facts"
            self.assertTrue(out_file.exists())

            lines = [line for line in out_file.read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(lines, [f"{e_ref}\tfr"])

    def _set_ingested_at(self, store: Store, asrt_id: str, epoch_nanos: int) -> None:
        replaced = False
        updated: list[MetaRow] = []
        for row in store.ledger._meta_rows:
            if row.asrt_id == asrt_id and row.key == "ingested_at":
                updated.append(
                    MetaRow(
                        asrt_id=row.asrt_id,
                        key=row.key,
                        kind="time",
                        value=epoch_nanos,
                    )
                )
                replaced = True
            else:
                updated.append(row)
        if not replaced:
            raise AssertionError(f"missing ingested_at for asrt_id={asrt_id}")
        store.ledger._meta_rows = updated
        store.ledger.rebuild_indexes()
if __name__ == "__main__":
    unittest.main()
