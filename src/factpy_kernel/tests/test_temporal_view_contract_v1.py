from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.adapters.souffle.pred_norm import normalize_pred_id
from factpy_kernel.adapters.souffle.runner import find_souffle_binary
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.store.ledger import MetaRow


class TemporalViewContractV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.pred_id = "person:salary_history"
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
                        {"name": "year", "type_domain": "string"},
                        {"name": "amount", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0, 1],
                    "cardinality": "temporal",
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

    def test_evaluate_record_temporal_view_supported(self) -> None:
        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:temporal-contract-e1"
        set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "2024"), ("string", "100")],
            meta={"source": "test", "source_loc": "row-1"},
        )

        candidates = store.evaluate(
            derivation_id="drv.temporal.contract",
            version="v1",
            target_pred_id=self.pred_id,
            head_vars=["$E", "$year", "$amount"],
            where=[("pred", self.pred_id, ["$E", "$year", "$amount"])],
            mode="python",
            temporal_view="record",
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].payload["e_ref"], e_ref)
        self.assertEqual(candidates[0].payload["rest_terms"], [("string", "2024"), ("string", "100")])

    def test_evaluate_python_temporal_current_supported(self) -> None:
        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:temporal-current-eval-python"
        asrt_100 = set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "2024"), ("string", "100")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        asrt_200 = set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "2024"), ("string", "200")],
            meta={"source": "test", "source_loc": "row-2"},
        )
        self._set_ingested_at(store, asrt_100, 100)
        self._set_ingested_at(store, asrt_200, 200)

        candidates = store.evaluate(
            derivation_id="drv.temporal.contract.current.py",
            version="v1",
            target_pred_id=self.pred_id,
            head_vars=["$E", "$year", "$amount"],
            where=[("pred", self.pred_id, ["$E", "$year", "$amount"])],
            mode="python",
            temporal_view="current",
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].payload["e_ref"], e_ref)
        self.assertEqual(candidates[0].payload["rest_terms"], [("string", "2024"), ("string", "200")])

    def test_evaluate_temporal_current_python_engine_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:temporal-current-parity"
        asrt_100 = set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "2024"), ("string", "100")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        asrt_200 = set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "2024"), ("string", "200")],
            meta={"source": "test", "source_loc": "row-2"},
        )
        self._set_ingested_at(store, asrt_100, 100)
        self._set_ingested_at(store, asrt_200, 200)

        py = store.evaluate(
            derivation_id="drv.temporal.contract.current.parity",
            version="v1",
            target_pred_id=self.pred_id,
            head_vars=["$E", "$year", "$amount"],
            where=[("pred", self.pred_id, ["$E", "$year", "$amount"])],
            mode="python",
            temporal_view="current",
        )
        en = store.evaluate(
            derivation_id="drv.temporal.contract.current.parity",
            version="v1",
            target_pred_id=self.pred_id,
            head_vars=["$E", "$year", "$amount"],
            where=[("pred", self.pred_id, ["$E", "$year", "$amount"])],
            mode="engine",
            temporal_view="current",
        )
        self.assertEqual(
            {(c.payload["e_ref"], tuple(c.payload["rest_terms"])) for c in py},
            {(c.payload["e_ref"], tuple(c.payload["rest_terms"])) for c in en},
        )

    def test_evaluate_engine_temporal_current_supported(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:temporal-current-eval"

        asrt_100 = set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "2024"), ("string", "100")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        asrt_200 = set_field(
            store.ledger,
            pred_id=self.pred_id,
            e_ref=e_ref,
            rest_terms=[("string", "2024"), ("string", "200")],
            meta={"source": "test", "source_loc": "row-2"},
        )
        self._set_ingested_at(store, asrt_100, 100)
        self._set_ingested_at(store, asrt_200, 200)

        candidates = store.evaluate(
            derivation_id="drv.temporal.contract.current",
            version="v1",
            target_pred_id=self.pred_id,
            head_vars=["$E", "$year", "$amount"],
            where=[("pred", self.pred_id, ["$E", "$year", "$amount"])],
            mode="engine",
            temporal_view="current",
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].payload["e_ref"], e_ref)
        self.assertEqual(candidates[0].payload["rest_terms"], [("string", "2024"), ("string", "200")])

    def test_export_outputs_map_keeps_temporal_current_channel(self) -> None:
        store = Store(schema_ir=self.schema_ir)
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = export_package(store, Path(tmp) / "pkg", ExportOptions())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        engine_pred = normalize_pred_id(self.pred_id)
        self.assertEqual(
            manifest["outputs_map"][self.pred_id],
            [engine_pred, f"{engine_pred}__current"],
        )

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
