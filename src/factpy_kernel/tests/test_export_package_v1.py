from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.adapters.souffle.pred_norm import denormalize_engine_pred, normalize_pred_id
from factpy_kernel.adapters.souffle.runner import run_package
from factpy_kernel.core.store.api import Store


class ExportPackageV1Tests(unittest.TestCase):
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
        self.e_ref = (
            "idref_v1:Person:irk4tcjz3wzyl4ja6245k5duzqd3vn5dypm4rr5s7glkdulef4ha"
        )
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )

    def test_export_minimal_package_and_pred_norm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            manifest_path = export_package(self.store, out_dir, ExportOptions())

            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("package_kind", manifest)
            self.assertIn("protocol_version", manifest)
            self.assertIn("generated_at", manifest)
            self.assertIn("target_engine", manifest)
            self.assertIn("dialect_version", manifest)
            self.assertIn("digests", manifest)
            self.assertIn("paths", manifest)
            self.assertIn("entrypoints", manifest)

            self.assertTrue((out_dir / "schema" / "schema_ir.json").exists())
            self.assertTrue((out_dir / "policy" / "policy_rules.dl").exists())
            self.assertTrue((out_dir / "facts" / "claim.facts").exists())
            self.assertTrue((out_dir / "facts" / "claim_arg.facts").exists())
            self.assertTrue((out_dir / "facts" / "meta_str.facts").exists())
            self.assertTrue((out_dir / "facts" / "meta_time.facts").exists())
            self.assertTrue((out_dir / "facts" / "revokes.facts").exists())
            self.assertTrue((out_dir / "rules" / "view.dl").exists())
            self.assertTrue((out_dir / "rules" / "idb.dl").exists())

            normalized = normalize_pred_id("person:country")
            self.assertEqual(normalized, "p_person_country")
            self.assertEqual(denormalize_engine_pred(normalized), "person:country")

    def test_export_digests_stable_across_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir_1 = Path(tmp) / "pkg1"
            out_dir_2 = Path(tmp) / "pkg2"

            manifest_1 = export_package(self.store, out_dir_1, ExportOptions())
            manifest_2 = export_package(self.store, out_dir_2, ExportOptions())

            data_1 = json.loads(manifest_1.read_text(encoding="utf-8"))
            data_2 = json.loads(manifest_2.read_text(encoding="utf-8"))

            self.assertEqual(
                data_1["digests"]["schema_digest"],
                data_2["digests"]["schema_digest"],
            )
            self.assertEqual(
                data_1["digests"]["edb_digest"],
                data_2["digests"]["edb_digest"],
            )

    def test_export_supports_unary_exists_predicate_views(self) -> None:
        schema_ir = {
            **self.schema_ir,
            "predicates": [
                *self.schema_ir["predicates"],
                {
                    "pred_id": "Person:exists",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
            ],
            "projection": {
                **self.schema_ir["projection"],
                "predicates": [*self.schema_ir["projection"]["predicates"], "Person:exists"],
            },
        }
        store = Store(schema_ir=schema_ir)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            export_package(store, out_dir, ExportOptions())

            view_dl = (out_dir / "rules" / "view.dl").read_text(encoding="utf-8")
            self.assertIn(".decl p_Person_exists(E:symbol)", view_dl)
            self.assertIn(".output p_Person_exists", view_dl)

    def test_runner_outputs_and_outputs_digest_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            export_package(self.store, out_dir, ExportOptions())

            run_manifest_1 = run_package(out_dir, ["person:country"])
            self.assertTrue(run_manifest_1.exists())
            run_data_1 = json.loads(run_manifest_1.read_text(encoding="utf-8"))
            outputs_digest_1 = run_data_1["digests"]["outputs_digest"]

            output_file = out_dir / "outputs" / "p_person_country.out.facts"
            self.assertTrue(output_file.exists())

            run_manifest_1.write_text(
                json.dumps(
                    {
                        **run_data_1,
                        "engine_stdout": "changed",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
                newline="\n",
            )

            run_manifest_2 = run_package(out_dir, ["person:country"])
            run_data_2 = json.loads(run_manifest_2.read_text(encoding="utf-8"))
            outputs_digest_2 = run_data_2["digests"]["outputs_digest"]

            self.assertEqual(outputs_digest_1, outputs_digest_2)


if __name__ == "__main__":
    unittest.main()
