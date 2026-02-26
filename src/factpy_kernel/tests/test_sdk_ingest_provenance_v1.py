from __future__ import annotations

import unittest

import factpy_kernel.tests._warnings as test_warnings
from factpy_kernel.sdk import Entity, Field, Identity, SDKStore, SDKStoreError


def setUpModule() -> None:
    test_warnings.install_test_warning_filters()


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    tag: str = Field(cardinality="multi", pred_id="person:tag")


class SDKIngestProvenanceV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.sdk = SDKStore.from_schema_classes([Person])
        self.p_ref = self.sdk.ref(Person, source_id="u1")

    def test_validate_provenance_accepts_candidate_set(self) -> None:
        cand = self.sdk.store.evaluate_dummy(
            derivation_id="drv.copy_country",
            version="1.0.0",
            target="person:country",
            e_ref=self.p_ref,
            rest_terms=[("string", "de")],
            dims_terms=[],
        )
        report = self.sdk.validate_provenance(cand)
        self.assertTrue(report.ok)
        self.assertEqual(report.errors, [])

    def test_validate_provenance_reports_invalid_meta_dict(self) -> None:
        report = self.sdk.validate_provenance(
            {
                "derived_rule_id": "drv.x",
                "derived_rule_version": "",
                "run_id": "run-1",
                "support_digest": "sha256:nothex",
                "support_kind": 123,
            }
        )
        self.assertFalse(report.ok)
        codes = {row["code"] for row in report.errors}
        self.assertIn("provenance_required_field_missing_or_invalid", codes)
        self.assertIn("provenance_required_digest_missing_or_invalid", codes)

    def test_ingest_writes_fact_items_and_tracks_duplicates(self) -> None:
        item = {
            "kind": "set",
            "field": Person.country,
            "e_ref": self.p_ref,
            "value": "de",
        }
        res1 = self.sdk.ingest([item], meta={"source": "csv", "trace_id": "t1"})
        self.assertEqual(res1.duplicate_count, 0)
        self.assertEqual(res1.skipped_count, 0)
        self.assertEqual(len(res1.written_assertion_ids), 1)

        # Same write + same dedup-affecting meta -> duplicate
        res2 = self.sdk.ingest([item], meta={"source": "csv", "trace_id": "t1"})
        self.assertEqual(res2.duplicate_count, 1)
        self.assertEqual(res2.skipped_count, 1)
        self.assertEqual(res2.written_assertion_ids, [])

        # Different trace_id changes ingest_key -> new assertion
        res3 = self.sdk.ingest([item], meta={"source": "csv", "trace_id": "t2"})
        self.assertEqual(res3.duplicate_count, 0)
        self.assertEqual(len(res3.written_assertion_ids), 1)

    def test_ingest_supports_add_and_retract_and_sensitive_meta_warning(self) -> None:
        add_item = {
            "kind": "add",
            "field": Person.tag,
            "e_ref": self.p_ref,
            "value": "x",
        }
        res_add = self.sdk.ingest(
            [add_item],
            meta={"source": "etl", "derived_rule_id": "manual_override"},
        )
        # Warning should not block write.
        self.assertEqual(len(res_add.written_assertion_ids), 1)
        self.assertEqual(res_add.skipped_count, 0)
        self.assertFalse(any(row["severity"] == "error" for row in res_add.diagnostics))
        warning_codes = {row["code"] for row in res_add.warnings}
        self.assertIn("ingest_sensitive_meta_key_present", warning_codes)

        asrt_id = res_add.written_assertion_ids[0]
        retract_item = {
            "kind": "retract",
            "asrt_id": asrt_id,
        }
        res_retract_1 = self.sdk.ingest([retract_item], meta={"source": "etl"})
        self.assertEqual(len(res_retract_1.written_assertion_ids), 1)
        res_retract_2 = self.sdk.ingest([retract_item], meta={"source": "etl"})
        self.assertEqual(res_retract_2.duplicate_count, 1)
        self.assertEqual(res_retract_2.skipped_count, 1)

    def test_ingest_rejects_reserved_meta_keys(self) -> None:
        with self.assertRaises(SDKStoreError):
            self.sdk.ingest(
                [
                    {
                        "kind": "set",
                        "field": Person.country,
                        "e_ref": self.p_ref,
                        "value": "de",
                    }
                ],
                meta={"ingested_at": 1},
            )

    def test_ingest_collects_per_item_diagnostics_and_does_not_write(self) -> None:
        items = [
            {
                "kind": "set",
                "field": Person.country,
                "e_ref": self.p_ref,
                "value": "de",
                "meta": {"ingested_at": 1},  # item-level reserved key -> diagnostics, not raise
            },
            {
                "kind": "retract",
                "asrt_id": "missing-asrt-id",
            },
            {
                "kind": "unknown",
            },
        ]
        res = self.sdk.ingest(items, meta={"source": "etl"})
        self.assertEqual(res.written_assertion_ids, [])
        self.assertEqual(self.sdk.ledger.find_claims(pred_id="person:country", e_ref=self.p_ref), [])

        by_path = {row["path"]: row for row in res.diagnostics}
        self.assertIn("items[0].meta", by_path)
        self.assertIn("items[1].asrt_id", by_path)
        self.assertIn("items[2].kind", by_path)
        for path in by_path:
            self.assertTrue(path.startswith("items["))
        self.assertTrue(any(row["severity"] == "error" for row in res.diagnostics))


if __name__ == "__main__":
    unittest.main()
