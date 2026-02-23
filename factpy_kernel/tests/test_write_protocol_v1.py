from __future__ import annotations

import unittest

from factpy_kernel.evidence.write_protocol import WriteProtocolError, retract_by_asrt, set_field
from factpy_kernel.store.ledger import Ledger


class WriteProtocolV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = Ledger()
        self.pred_id = "person:country"
        self.e_ref = (
            "idref_v1:Person:irk4tcjz3wzyl4ja6245k5duzqd3vn5dypm4rr5s7glkdulef4ha"
        )

    def test_set_field_append_only_for_different_values(self) -> None:
        asrt_1 = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "de")],
            {"source": "test", "source_loc": "row-1"},
        )
        asrt_2 = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "fr")],
            {"source": "test", "source_loc": "row-2"},
        )

        self.assertNotEqual(asrt_1, asrt_2)
        claims = self.ledger.find_claims(pred_id=self.pred_id, e_ref=self.e_ref)
        self.assertEqual(len(claims), 2)
        self.assertFalse(self.ledger.has_active_revocation(asrt_1))
        self.assertFalse(self.ledger.has_active_revocation(asrt_2))

    def test_retract_by_asrt_is_idempotent(self) -> None:
        asrt_id = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "de")],
            {"source": "test", "source_loc": "row-1"},
        )

        revoker_1 = retract_by_asrt(self.ledger, asrt_id, {"source": "review"})
        self.assertIsNotNone(revoker_1)
        self.assertTrue(self.ledger.has_active_revocation(asrt_id))
        revokes_count_after_first = len(self.ledger.revokes)

        revoker_2 = retract_by_asrt(self.ledger, asrt_id, {"source": "review"})
        self.assertEqual(revoker_2, revoker_1)
        self.assertEqual(len(self.ledger.revokes), revokes_count_after_first)

    def test_ingest_key_idempotency_noop_on_duplicate(self) -> None:
        meta = {"source": "test", "source_loc": "row-1", "trace_id": "t-1"}
        asrt_1 = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "de")],
            meta,
        )
        claim_count_1 = len(self.ledger.find_claims(pred_id=self.pred_id, e_ref=self.e_ref))

        asrt_2 = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "de")],
            meta,
        )
        claim_count_2 = len(self.ledger.find_claims(pred_id=self.pred_id, e_ref=self.e_ref))

        self.assertEqual(asrt_2, asrt_1)
        self.assertEqual(claim_count_1, 1)
        self.assertEqual(claim_count_2, 1)

    def test_ingested_at_written_as_meta_time_epoch_nanos(self) -> None:
        asrt_id = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "de")],
            {"source": "test", "source_loc": "row-1"},
        )
        ingested_rows = self.ledger.find_meta(
            asrt_id=asrt_id,
            key="ingested_at",
            kind="time",
        )
        self.assertEqual(len(ingested_rows), 1)
        self.assertIsInstance(ingested_rows[0].value, int)

    def test_reject_user_supplied_system_managed_meta_keys(self) -> None:
        with self.assertRaises(WriteProtocolError):
            set_field(
                self.ledger,
                self.pred_id,
                self.e_ref,
                [("string", "de")],
                {"source": "test", "ingested_at": 123},
            )

        asrt_id = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "fr")],
            {"source": "test"},
        )
        with self.assertRaises(WriteProtocolError):
            retract_by_asrt(
                self.ledger,
                asrt_id,
                {"source": "test", "revoked_asrt_id": asrt_id},
            )


if __name__ == "__main__":
    unittest.main()
