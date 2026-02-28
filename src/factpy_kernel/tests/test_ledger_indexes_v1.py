from __future__ import annotations

import unittest

from factpy_kernel.core.store.ledger import Claim, ClaimArg, Idempotency, Ledger, MetaRow, Revokes


class LedgerIndexesV1Tests(unittest.TestCase):
    def test_find_claims_and_meta_and_claim_args_use_same_observable_semantics(self) -> None:
        ledger = Ledger()
        result_1 = ledger.append_assertion(
            claim=Claim("a1", "p:x", "idref_v1:E:1", [("string", "v1")]),
            claim_args=[ClaimArg("a1", 0, "v1", "string")],
            meta_rows=[
                MetaRow("a1", "ingested_at", "time", 1),
                MetaRow("a1", "source", "str", "s1"),
            ],
            asrt_id="a1",
        )
        result_2 = ledger.append_assertion(
            claim=Claim("a2", "p:x", "idref_v1:E:1", [("string", "v2")]),
            claim_args=[ClaimArg("a2", 0, "v2", "string")],
            meta_rows=[MetaRow("a2", "ingested_at", "time", 2)],
            asrt_id="a2",
        )
        result_3 = ledger.append_assertion(
            claim=Claim("a3", "p:y", "idref_v1:E:2", [("int", 3)]),
            claim_args=[ClaimArg("a3", 0, 3, "int")],
            meta_rows=[MetaRow("a3", "source", "str", "s3")],
            asrt_id="a3",
        )

        self.assertTrue(result_1.written)
        self.assertTrue(result_2.written)
        self.assertTrue(result_3.written)

        self.assertEqual([c.asrt_id for c in ledger.find_claims()], ["a1", "a2", "a3"])
        self.assertEqual([c.asrt_id for c in ledger.find_claims(pred_id="p:x")], ["a1", "a2"])
        self.assertEqual([c.asrt_id for c in ledger.find_claims(e_ref="idref_v1:E:1")], ["a1", "a2"])
        self.assertEqual(
            [c.asrt_id for c in ledger.find_claims(pred_id="p:x", e_ref="idref_v1:E:1")],
            ["a1", "a2"],
        )

        self.assertEqual([r.value for r in ledger.find_meta(asrt_id="a1")], [1, "s1"])
        self.assertEqual([r.value for r in ledger.find_meta(kind="time")], [1, 2])
        self.assertEqual([r.value for r in ledger.find_meta(key="source")], ["s1", "s3"])
        self.assertEqual([r.value for r in ledger.find_meta(asrt_id="a1", key="source")], ["s1"])
        self.assertEqual([r.value for r in ledger.find_meta(asrt_id="a1", key="ingested_at", kind="time")], [1])

        self.assertEqual([r.asrt_id for r in ledger.find_claim_args()], ["a1", "a2", "a3"])
        self.assertEqual([r.asrt_id for r in ledger.find_claim_args(asrt_id="a2")], ["a2"])
        self.assertEqual([r.asrt_id for r in ledger.find_claim_args(tag="string")], ["a1", "a2"])
        self.assertEqual([r.asrt_id for r in ledger.find_claim_args(idx=0, tag="int")], ["a3"])

    def test_find_revoker_preserves_first_match_semantics(self) -> None:
        ledger = Ledger()
        result_1 = ledger.append_revocation(
            revokes=Revokes("r1", "x"),
            meta_rows=[MetaRow("r1", "ingested_at", "time", 1)],
            revoker_asrt_id="r1",
        )
        result_2 = ledger.append_revocation(
            revokes=Revokes("r2", "x"),
            meta_rows=[MetaRow("r2", "ingested_at", "time", 2)],
            revoker_asrt_id="r2",
        )
        self.assertTrue(result_1.written)
        self.assertTrue(result_2.written)
        self.assertTrue(ledger.has_active_revocation("x"))
        self.assertEqual(ledger.find_revoker("x"), "r1")

    def test_append_assertion_idempotency_reports_written_flag(self) -> None:
        ledger = Ledger()
        first = ledger.append_assertion(
            claim=Claim("a1", "p:x", "idref_v1:E:1", [("string", "v1")]),
            claim_args=[ClaimArg("a1", 0, "v1", "string")],
            meta_rows=[
                MetaRow("a1", "ingested_at", "time", 1),
                MetaRow("a1", "ingest_key", "str", "k-1"),
            ],
            idempotency=Idempotency("k-1"),
            asrt_id="a1",
        )
        second = ledger.append_assertion(
            claim=Claim("a2", "p:x", "idref_v1:E:1", [("string", "v1")]),
            claim_args=[ClaimArg("a2", 0, "v1", "string")],
            meta_rows=[
                MetaRow("a2", "ingested_at", "time", 2),
                MetaRow("a2", "ingest_key", "str", "k-1"),
            ],
            idempotency=Idempotency("k-1"),
            asrt_id="a2",
        )

        self.assertTrue(first.written)
        self.assertFalse(second.written)
        self.assertEqual(second.asrt_id, "a1")
        self.assertEqual([c.asrt_id for c in ledger.find_claims()], ["a1"])

    def test_append_revocation_idempotency_reports_written_flag(self) -> None:
        ledger = Ledger()
        ledger.append_assertion(
            claim=Claim("a1", "p:x", "idref_v1:E:1", [("string", "v1")]),
            claim_args=[ClaimArg("a1", 0, "v1", "string")],
            meta_rows=[MetaRow("a1", "ingested_at", "time", 1)],
            asrt_id="a1",
        )

        first = ledger.append_revocation(
            revokes=Revokes("r1", "a1"),
            meta_rows=[
                MetaRow("r1", "ingested_at", "time", 2),
                MetaRow("r1", "ingest_key", "str", "revoke-a1"),
            ],
            idempotency=Idempotency("revoke-a1"),
            revoker_asrt_id="r1",
        )
        second = ledger.append_revocation(
            revokes=Revokes("r2", "a1"),
            meta_rows=[
                MetaRow("r2", "ingested_at", "time", 3),
                MetaRow("r2", "ingest_key", "str", "revoke-a1"),
            ],
            idempotency=Idempotency("revoke-a1"),
            revoker_asrt_id="r2",
        )

        self.assertTrue(first.written)
        self.assertFalse(second.written)
        self.assertEqual(second.asrt_id, "r1")
        self.assertEqual([row.revoker_asrt_id for row in ledger.revokes], ["r1"])
        self.assertTrue(ledger.has_active_revocation("a1"))
        self.assertEqual(ledger.find_revoker("a1"), "r1")


if __name__ == "__main__":
    unittest.main()
