from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.runner import find_souffle_binary
from factpy_kernel.core.store.api import Store


class WherePushdownEnd2EndV1Tests(unittest.TestCase):
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
                },
                {
                    "pred_id": "person:rank",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "rank", "type_domain": "int"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "person:flag",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "flag", "type_domain": "bool"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "person:seen_at",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "ts", "type_domain": "time"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "person:blob",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "blob", "type_domain": "bytes"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "person:uid",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "uid", "type_domain": "uuid"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "person:score",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "score", "type_domain": "float64"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
            ],
            "projection": {
                "entities": [],
                "predicates": [
                    "person:country",
                    "person:rank",
                    "person:flag",
                    "person:seen_at",
                    "person:blob",
                    "person:uid",
                    "person:score",
                ],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }

    def test_where_pushdown_produces_candidates(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:pushdown"
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref=e_ref,
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )

        candidates = store.evaluate_engine(
            derivation_id="drv.where.pushdown",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=[
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "de"),
            ],
        )

        self.assertTrue(candidates)
        candidate = candidates[0]
        self.assertEqual(candidate.payload["e_ref"], e_ref)
        self.assertEqual(candidate.payload["rest_terms"], [("string", "de")])
        self.assertTrue(candidate.key_tuple_digest.startswith("sha256:"))

    def test_where_pushdown_int_roundtrip(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:pushdown-int"
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref=e_ref,
            rest_terms=[("int", 3)],
            meta={"source": "test", "source_loc": "row-1"},
        )

        candidates = store.evaluate_engine(
            derivation_id="drv.where.pushdown.int",
            version="v1",
            target_pred_id="person:rank",
            head_vars=["$E", "$rank"],
            where=[
                ("pred", "person:rank", ["$E", "$rank"]),
                ("eq", "$rank", 3),
            ],
        )

        self.assertTrue(candidates)
        candidate = candidates[0]
        self.assertEqual(candidate.payload["e_ref"], e_ref)
        self.assertEqual(candidate.payload["rest_terms"], [("int", 3)])
        self.assertTrue(candidate.key_tuple_digest.startswith("sha256:"))

    def test_where_pushdown_bool_roundtrip(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:pushdown-bool"
        set_field(
            store.ledger,
            pred_id="person:flag",
            e_ref=e_ref,
            rest_terms=[("bool", True)],
            meta={"source": "test", "source_loc": "row-1"},
        )

        candidates = store.evaluate_engine(
            derivation_id="drv.where.pushdown.bool",
            version="v1",
            target_pred_id="person:flag",
            head_vars=["$E", "$flag"],
            where=[
                ("pred", "person:flag", ["$E", "$flag"]),
                ("eq", "$flag", True),
            ],
        )

        self.assertTrue(candidates)
        candidate = candidates[0]
        self.assertEqual(candidate.payload["e_ref"], e_ref)
        self.assertEqual(candidate.payload["rest_terms"], [("bool", True)])
        self.assertTrue(candidate.key_tuple_digest.startswith("sha256:"))

    def test_where_pushdown_time_roundtrip(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:pushdown-time"
        ts = 1772446272123456789
        set_field(
            store.ledger,
            pred_id="person:seen_at",
            e_ref=e_ref,
            rest_terms=[("time", ts)],
            meta={"source": "test", "source_loc": "row-1"},
        )

        candidates = store.evaluate_engine(
            derivation_id="drv.where.pushdown.time",
            version="v1",
            target_pred_id="person:seen_at",
            head_vars=["$E", "$ts"],
            where=[
                ("pred", "person:seen_at", ["$E", "$ts"]),
                ("eq", "$ts", ts),
            ],
        )

        self.assertTrue(candidates)
        candidate = candidates[0]
        self.assertEqual(candidate.payload["e_ref"], e_ref)
        self.assertEqual(candidate.payload["rest_terms"], [("time", ts)])
        self.assertTrue(candidate.key_tuple_digest.startswith("sha256:"))

    def test_where_pushdown_bytes_roundtrip(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:pushdown-bytes"
        blob = b"\x01\x02\x03"
        set_field(
            store.ledger,
            pred_id="person:blob",
            e_ref=e_ref,
            rest_terms=[("bytes", blob)],
            meta={"source": "test", "source_loc": "row-1"},
        )

        candidates = store.evaluate_engine(
            derivation_id="drv.where.pushdown.bytes",
            version="v1",
            target_pred_id="person:blob",
            head_vars=["$E", "$blob"],
            where=[
                ("pred", "person:blob", ["$E", "$blob"]),
                ("eq", "$blob", "AQID"),
            ],
        )

        self.assertTrue(candidates)
        candidate = candidates[0]
        self.assertEqual(candidate.payload["e_ref"], e_ref)
        self.assertEqual(candidate.payload["rest_terms"], [("bytes", blob)])
        self.assertTrue(candidate.key_tuple_digest.startswith("sha256:"))

    def test_where_pushdown_uuid_roundtrip(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:pushdown-uuid"
        uid = "123e4567-e89b-12d3-a456-426614174000"
        set_field(
            store.ledger,
            pred_id="person:uid",
            e_ref=e_ref,
            rest_terms=[("uuid", uid)],
            meta={"source": "test", "source_loc": "row-1"},
        )

        candidates = store.evaluate_engine(
            derivation_id="drv.where.pushdown.uuid",
            version="v1",
            target_pred_id="person:uid",
            head_vars=["$E", "$uid"],
            where=[
                ("pred", "person:uid", ["$E", "$uid"]),
                ("eq", "$uid", uid),
            ],
        )

        self.assertTrue(candidates)
        candidate = candidates[0]
        self.assertEqual(candidate.payload["e_ref"], e_ref)
        self.assertEqual(candidate.payload["rest_terms"], [("uuid", uid)])
        self.assertTrue(candidate.key_tuple_digest.startswith("sha256:"))

    def test_where_pushdown_float64_roundtrip(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        e_ref = "idref_v1:Person:pushdown-float64"
        score_bits = "0x3ff0000000000000"
        set_field(
            store.ledger,
            pred_id="person:score",
            e_ref=e_ref,
            rest_terms=[("float64", score_bits)],
            meta={"source": "test", "source_loc": "row-1"},
        )

        candidates = store.evaluate_engine(
            derivation_id="drv.where.pushdown.float64",
            version="v1",
            target_pred_id="person:score",
            head_vars=["$E", "$score"],
            where=[
                ("pred", "person:score", ["$E", "$score"]),
                ("eq", "$score", score_bits),
            ],
        )

        self.assertTrue(candidates)
        candidate = candidates[0]
        self.assertEqual(candidate.payload["e_ref"], e_ref)
        self.assertEqual(candidate.payload["rest_terms"], [("float64", score_bits)])
        self.assertTrue(candidate.key_tuple_digest.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
