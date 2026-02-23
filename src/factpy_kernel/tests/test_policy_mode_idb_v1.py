from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.core.evidence.write_protocol import retract_by_asrt, set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.adapters.souffle.pred_norm import normalize_pred_id
from factpy_kernel.adapters.souffle.runner import find_souffle_binary, run_package
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.store.ledger import MetaRow


class PolicyModeIDBV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.pred_id = "person:country"
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
                    "pred_id": self.pred_id,
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
                "predicates": [self.pred_id],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }

    def test_export_idb_policy_rules_are_executable(self) -> None:
        store = Store(schema_ir=self.schema_ir)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            manifest_path = export_package(
                store,
                out_dir,
                ExportOptions(policy_mode="idb"),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            policy_rules_text = (out_dir / "policy" / "policy_rules.dl").read_text(encoding="utf-8")
            view_text = (out_dir / "rules" / "view.dl").read_text(encoding="utf-8")

        self.assertEqual(manifest["policy_mode"], "idb")
        self.assertIn(".decl active(A:symbol)", policy_rules_text)
        self.assertIn("active(A) :- claim(A,_,_,_), !revokes(_,A).", policy_rules_text)
        self.assertNotIn(".decl active(A:symbol)", view_text)

    def test_edb_and_idb_policy_modes_produce_same_outputs(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:policy-mode-e1"
        asrt_de = set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        asrt_fr = set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-2"},
        )
        asrt_es = set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "es")],
            meta={"source": "test", "source_loc": "row-3"},
        )
        self._set_ingested_at(store, asrt_de, 100)
        self._set_ingested_at(store, asrt_fr, 200)
        self._set_ingested_at(store, asrt_es, 300)
        retract_by_asrt(store.ledger, asrt_es, meta={"source": "test", "source_loc": "row-4"})

        engine_pred = normalize_pred_id(self.pred_id)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edb_dir = root / "pkg_edb"
            idb_dir = root / "pkg_idb"

            export_package(store, edb_dir, ExportOptions(policy_mode="edb"))
            export_package(store, idb_dir, ExportOptions(policy_mode="idb"))

            run_package(edb_dir, [self.pred_id], engine="souffle")
            run_package(idb_dir, [self.pred_id], engine="souffle")

            edb_lines = self._read_lines(edb_dir / "outputs" / f"{engine_pred}.out.facts")
            idb_lines = self._read_lines(idb_dir / "outputs" / f"{engine_pred}.out.facts")

        self.assertEqual(edb_lines, idb_lines)
        self.assertEqual(edb_lines, [f"{e_ref}\tfr"])

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
    @staticmethod
    def _read_lines(path: Path) -> list[str]:
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


if __name__ == "__main__":
    unittest.main()
