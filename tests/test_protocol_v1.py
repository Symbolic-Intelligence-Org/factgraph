from __future__ import annotations

import unittest

from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.protocol.tup_v1 import (
    TUP_V1_PREFIX,
    canonical_bytes_tup_v1,
    claim_args_from_rest_terms,
)


class ProtocolV1Tests(unittest.TestCase):
    def test_idref_v1_matches_doc_vector(self) -> None:
        identity_fields = [
            ("source_system", "string", "HR"),
            ("source_id", "string", "123"),
        ]
        token = encode_idref_v1("Person", identity_fields)
        self.assertEqual(
            token,
            "idref_v1:Person:ry37kwbswkbrb7mc72gdfc6skukkguim3cyjur4pwpuokf3rd4ga",
        )

    def test_tup_v1_example_a_claim_args_and_digest(self) -> None:
        entity_ref = "idref_v1:Person:ry37kwbswkbrb7mc72gdfc6skukkguim3cyjur4pwpuokf3rd4ga"
        rest_terms = [("entity_ref", entity_ref), ("string", "de"), ("int", 3)]
        claim_args = claim_args_from_rest_terms(rest_terms)
        self.assertEqual(
            claim_args,
            [
                (0, entity_ref, "entity_ref"),
                (1, "de", "string"),
                (2, 3, "int"),
            ],
        )
        canonical = canonical_bytes_tup_v1(rest_terms)
        self.assertTrue(canonical.startswith(TUP_V1_PREFIX))
        self.assertEqual(
            sha256_token(canonical),
            "sha256:a492bceedc8ca8ab66d114d3ab574f1c8d2920665dbb3d2d9101564dd1bcea65",
        )

    def test_tup_v1_example_b_time_and_bytes_val_atom(self) -> None:
        rest_terms = [("bytes", b"\x00\xff\x10"), ("time", 1772446272123456789)]
        claim_args = claim_args_from_rest_terms(rest_terms)
        self.assertEqual(
            claim_args,
            [
                (0, "AP8Q", "bytes"),
                (1, 1772446272123456789, "time"),
            ],
        )

    def test_reject_invalid_entity_ref_and_invalid_float64_hex(self) -> None:
        with self.assertRaises(ValueError):
            claim_args_from_rest_terms([("entity_ref", "Person__abc123")])

        with self.assertRaises(ValueError):
            canonical_bytes_tup_v1([("float64", "0x1234")])


if __name__ == "__main__":
    unittest.main()
