from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.export.package import ExportOptions
from factpy_kernel.sdk import Entity, Field, Identity, SDKStore, SDKStoreError


class Company(Entity):
    source_id: str = Identity()
    sector: str = Field(cardinality="functional")


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    name_by_lang: str = Field(
        cardinality="functional",
        dims=[("lang", "string")],
        fact_key=["lang"],
        pred_id="person:name_by_lang",
    )
    tag: str = Field(cardinality="multi", pred_id="person:tag")
    works_at: Company = Field(cardinality="multi", pred_id="person:works_at")


class SDKStoreV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.sdk = SDKStore.from_schema_classes([Person, Company])
        self.p_ref = self.sdk.ref(Person, source_id="u1")
        self.c_ref = self.sdk.ref(Company, source_id="c1")

    def test_ref_set_add_retract_flow(self) -> None:
        a1 = self.sdk.set(
            Person.country,
            self.p_ref,
            "de",
            meta={"source": "sdk", "source_loc": "test", "trace_id": "t1"},
        )
        a2 = self.sdk.add(
            Person.works_at,
            self.p_ref,
            self.c_ref,
            meta={"source": "sdk", "source_loc": "test", "trace_id": "t2"},
        )
        self.assertNotEqual(a1, a2)

        fact = self.sdk.explain_fact("person:country", self.p_ref, "de")
        self.assertEqual(fact["pred_id"], "person:country")
        self.assertEqual(fact["chosen_asrt_id"], a1)

        revoker = self.sdk.retract(a2, meta={"source": "sdk", "source_loc": "test", "trace_id": "t3"})
        self.assertIsInstance(revoker, str)
        self.assertTrue(self.sdk.ledger.has_active_revocation(a2))

    def test_dims_are_encoded_from_named_or_positional_inputs(self) -> None:
        a_named = self.sdk.set(Person.name_by_lang, self.p_ref, "Alice", dims={"lang": "en"})
        a_pos = self.sdk.set(
            Person.name_by_lang,
            self.p_ref,
            "Alicia",
            dims=["es"],
            meta={"source": "sdk", "source_loc": "test", "trace_id": "t4"},
        )
        claims = {c.asrt_id: c for c in self.sdk.ledger.find_claims(pred_id="person:name_by_lang", e_ref=self.p_ref)}
        self.assertEqual(claims[a_named].rest_terms, [("string", "en"), ("string", "Alice")])
        self.assertEqual(claims[a_pos].rest_terms, [("string", "es"), ("string", "Alicia")])

    def test_dims_validation_rejects_missing_or_extra(self) -> None:
        with self.assertRaises(SDKStoreError):
            self.sdk.set(Person.name_by_lang, self.p_ref, "Alice")
        with self.assertRaises(SDKStoreError):
            self.sdk.set(Person.name_by_lang, self.p_ref, "Alice", dims={"lang": "en", "x": "y"})

    def test_export_and_run_passthrough(self) -> None:
        self.sdk.set(Person.country, self.p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t5"})
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            manifest_path = self.sdk.export_package(pkg_dir, ExportOptions(package_kind="inference"))
            self.assertTrue(manifest_path.exists())
            run_manifest_path = self.sdk.run_package(pkg_dir, entrypoints=["person:country"], engine="noop")
            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["engine_mode"], "noop")


if __name__ == "__main__":
    unittest.main()
