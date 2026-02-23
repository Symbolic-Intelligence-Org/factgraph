from __future__ import annotations

import unittest

from factpy_kernel.core.store.ledger import Claim, ClaimArg, Ledger, MetaRow, Revokes


class LedgerIndexesV1Tests(unittest.TestCase):
    def test_find_claims_and_meta_and_claim_args_use_same_observable_semantics(self) -> None:
        ledger = Ledger()
        c1 = Claim("a1", "p:x", "idref_v1:E:1", [("string", "v1")])
        c2 = Claim("a2", "p:x", "idref_v1:E:1", [("string", "v2")])
        c3 = Claim("a3", "p:y", "idref_v1:E:2", [("int", 3)])
        for claim in [c1, c2, c3]:
            ledger.append_claim(claim)

        ledger.append_claim_args(
            [
                ClaimArg("a1", 0, "v1", "string"),
                ClaimArg("a2", 0, "v2", "string"),
                ClaimArg("a3", 0, 3, "int"),
            ]
        )
        ledger.append_meta(
            [
                MetaRow("a1", "ingested_at", "time", 1),
                MetaRow("a1", "source", "str", "s1"),
                MetaRow("a2", "ingested_at", "time", 2),
                MetaRow("a3", "source", "str", "s3"),
            ]
        )

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
        ledger.append_revokes(Revokes("r1", "x"))
        ledger.append_revokes(Revokes("r2", "x"))
        self.assertTrue(ledger.has_active_revocation("x"))
        self.assertEqual(ledger.find_revoker("x"), "r1")


if __name__ == "__main__":
    unittest.main()
