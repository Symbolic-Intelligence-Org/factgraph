from __future__ import annotations

import unittest

from factgraph.core.evidence.write_protocol import WriteProtocolError, add_field, set_field
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.protocol.tup_v1 import (
    TUP_V1_PREFIX,
    canonical_bytes_tup_v1,
    claim_args_from_rest_terms,
    encode_value_bytes,
)
from factgraph.core.store.ledger import Ledger

_INVALID_TYPED_VALUES = (
    ("string", 12, "string value must be str"),
    ("entity_ref", 12, "entity_ref value must be str"),
    ("int", True, "int must be int64"),
    ("int", 1.5, "int must be int64"),
    ("time", False, "time must be int64"),
    ("float64", 12, "float64 value must be float or 0x<16hex> string"),
    ("bool", 1, "bool value must be bool"),
    ("bytes", "abc", "bytes value must be bytes-like"),
    ("uuid", 12, "uuid value must be canonical lowercase string"),
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
            "idref_v1:Person:irk4tcjz3wzyl4ja6245k5duzqd3vn5dypm4rr5s7glkdulef4ha",
        )

    def test_tup_v1_example_a_claim_args_and_digest(self) -> None:
        entity_ref = "idref_v1:Person:irk4tcjz3wzyl4ja6245k5duzqd3vn5dypm4rr5s7glkdulef4ha"
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
            "sha256:5a02dcfdd201f292bd4175e543657b17f1d549b42cb2864a9208b54bdafe793e",
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

    def test_typed_encoding_errors_preserve_value_error_contract(self) -> None:
        for tag, supplied, message in _INVALID_TYPED_VALUES:
            with self.subTest(tag=tag, supplied=supplied), self.assertRaises(ValueError) as caught:
                encode_value_bytes(tag, supplied)
            self.assertIs(type(caught.exception), ValueError)
            self.assertEqual(str(caught.exception), message)

    def test_tuple_and_claim_encoders_preserve_value_errors(self) -> None:
        for encoder in (canonical_bytes_tup_v1, claim_args_from_rest_terms):
            for tag, supplied, _message in _INVALID_TYPED_VALUES:
                with self.subTest(encoder=encoder.__name__, tag=tag, supplied=supplied):
                    with self.assertRaises(ValueError) as caught:
                        encoder([(tag, supplied)])
                    self.assertIs(type(caught.exception), ValueError)

    def test_non_string_tag_remains_value_error(self) -> None:
        for encoder in (canonical_bytes_tup_v1, claim_args_from_rest_terms):
            with self.subTest(encoder=encoder.__name__), self.assertRaises(ValueError) as caught:
                encoder([(1, "Alice")])
            self.assertIs(type(caught.exception), ValueError)
            self.assertEqual(str(caught.exception), "tag must be str")

    def test_non_string_identity_type_remains_value_error(self) -> None:
        with self.assertRaises(ValueError) as caught:
            encode_idref_v1(1, [("name", "string", "Alice")])
        self.assertIs(type(caught.exception), ValueError)
        self.assertEqual(str(caught.exception), "entity_type must be str")

    def test_write_boundary_wraps_encoding_error_without_writing(self) -> None:
        ledger = Ledger()
        try:
            for writer in (set_field, add_field):
                for tag, supplied, message in _INVALID_TYPED_VALUES:
                    with self.subTest(writer=writer.__name__, tag=tag, supplied=supplied):
                        with self.assertRaises(WriteProtocolError) as caught:
                            writer(ledger, "Person:value", "idref_v1:Person:test", [(tag, supplied)])
                        self.assertIs(type(caught.exception.__cause__), ValueError)
                        self.assertEqual(str(caught.exception), message)
            self.assertEqual(ledger.find_claims(pred_id="Person:value"), [])
        finally:
            ledger.close()

    def test_hex_and_float_forms_have_identical_canonical_bytes(self) -> None:
        for value, encoded in ((0.0, "0x0000000000000000"), (-0.0, "0x8000000000000000"),
                               (1.0, "0x3ff0000000000000"), (-1.0, "0xbff0000000000000")):
            with self.subTest(encoded=encoded):
                self.assertEqual(encode_value_bytes("float64", value), encode_value_bytes("float64", encoded))


if __name__ == "__main__":
    unittest.main()
