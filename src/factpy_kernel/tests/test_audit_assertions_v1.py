from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factpy_kernel.audit import load_assertion_index
from factpy_kernel.core.evidence.write_protocol import retract_by_asrt, set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.core.store.api import Store


class AuditAssertionsV1Tests(unittest.TestCase):
    def test_load_assertion_index_reads_claim_args_and_meta(self) -> None:
        store = Store(schema_ir=_simple_schema())
        asrt_id = set_field(
            store.ledger,
            pred_id="person:tag",
            e_ref="idref_v1:Person:audit-assertions-1",
            rest_terms=[("string", "vip")],
            meta={"source": "seed", "run_id": "run-aa-1", "materialize_id": "mat-aa-1"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            idx = load_assertion_index(pkg_dir)

        detail = idx.get_assertion_detail(asrt_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["claim"]["pred_id"], "person:tag")
        self.assertEqual(detail["claim"]["e_ref"], "idref_v1:Person:audit-assertions-1")
        self.assertEqual(detail["claim_args"], [{"asrt_id": asrt_id, "idx": 0, "val": "vip", "tag": "string"}])
        self.assertIn("str", detail["meta"])
        self.assertIn("time", detail["meta"])
        self.assertTrue(any(row["key"] == "source" and row["value"] == "seed" for row in detail["meta"]["str"]))
        self.assertTrue(any(row["key"] == "ingested_at" and isinstance(row["value"], int) for row in detail["meta"]["time"]))
        self.assertFalse(detail["is_revoked"])

    def test_load_assertion_index_links_revocations(self) -> None:
        store = Store(schema_ir=_simple_schema())
        original_asrt = set_field(
            store.ledger,
            pred_id="person:tag",
            e_ref="idref_v1:Person:audit-assertions-2",
            rest_terms=[("string", "old")],
            meta={"source": "seed", "run_id": "run-aa-2"},
        )
        revoker_asrt = retract_by_asrt(store.ledger, original_asrt, meta={"source": "user", "trace_id": "t-aa-2"})

        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            idx = load_assertion_index(pkg_dir)

        original = idx.get_assertion_detail(original_asrt)
        revoker = idx.get_assertion_detail(revoker_asrt)
        self.assertIsNotNone(original)
        self.assertIsNone(revoker)
        assert original is not None
        self.assertTrue(original["is_revoked"])
        self.assertEqual(original["revoked_by"], [revoker_asrt])
        self.assertEqual(idx.revokes.get(revoker_asrt), [original_asrt])


def _simple_schema() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [{"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]}],
        "predicates": [
            {
                "pred_id": "person:tag",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "tag", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "multi",
            }
        ],
        "projection": {"entities": [], "predicates": ["person:tag"]},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


if __name__ == "__main__":
    unittest.main()
