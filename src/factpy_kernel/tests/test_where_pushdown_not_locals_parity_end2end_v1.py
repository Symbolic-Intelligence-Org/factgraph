from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.runner import find_souffle_binary
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store.api import Store


class WherePushdownNotLocalsParityEnd2EndV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {
            "schema_ir_version": "v1",
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [
                        {"name": "source_id", "type_domain": "string"},
                    ],
                },
                {
                    "entity_type": "Reason",
                    "identity_fields": [
                        {"name": "source_id", "type_domain": "string"},
                    ],
                },
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
                    "pred_id": "person:ban",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "reason", "type_domain": "entity_ref"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "multi",
                },
                {
                    "pred_id": "reason:level",
                    "arg_specs": [
                        {"name": "R", "type_domain": "entity_ref"},
                        {"name": "level", "type_domain": "int"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:country", "person:ban", "reason:level"],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }

    def _seed_store(self) -> Store:
        store = Store(schema_ir=self.schema_ir)

        reason_high = "idref_v1:Reason:r-high"
        reason_low = "idref_v1:Reason:r-low"

        set_field(
            store.ledger,
            pred_id="reason:level",
            e_ref=reason_high,
            rest_terms=[("int", 10)],
            meta={"source": "test", "source_loc": "row-r1"},
        )
        set_field(
            store.ledger,
            pred_id="reason:level",
            e_ref=reason_low,
            rest_terms=[("int", 3)],
            meta={"source": "test", "source_loc": "row-r2"},
        )

        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:notlocals-e1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-p1"},
        )
        set_field(
            store.ledger,
            pred_id="person:ban",
            e_ref="idref_v1:Person:notlocals-e1",
            rest_terms=[("entity_ref", reason_high)],
            meta={"source": "test", "source_loc": "row-p2"},
        )

        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:notlocals-e2",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-p3"},
        )
        set_field(
            store.ledger,
            pred_id="person:ban",
            e_ref="idref_v1:Person:notlocals-e2",
            rest_terms=[("entity_ref", reason_low)],
            meta={"source": "test", "source_loc": "row-p4"},
        )

        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:notlocals-e3",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-p5"},
        )

        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:notlocals-e4",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-p6"},
        )
        set_field(
            store.ledger,
            pred_id="person:ban",
            e_ref="idref_v1:Person:notlocals-e4",
            rest_terms=[("entity_ref", reason_high)],
            meta={"source": "test", "source_loc": "row-p7"},
        )
        return store

    def _evaluate_pair(self, store: Store, where: list, derivation_id: str):
        py = store.evaluate(
            derivation_id=derivation_id,
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=where,
            mode="python",
        )
        en = store.evaluate(
            derivation_id=derivation_id,
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=where,
            mode="engine",
        )
        return py, en

    @staticmethod
    def _payload_set(candidates) -> set[tuple[str, tuple[tuple[str, object], ...]]]:
        return {
            (cand.payload["e_ref"], tuple(cand.payload["rest_terms"]))
            for cand in candidates
        }

    def test_not_local_vars_multipred_join_cmp_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("eq", "$country", "de"),
            (
                "not",
                [
                    ("pred", "person:ban", ["$E", "$R"]),
                    ("pred", "reason:level", ["$R", "$L"]),
                    ("ge", "$L", 5),
                ],
            ),
        ]

        py, en = self._evaluate_pair(store, where, "drv.where.notlocals.hit")
        expected = {
            ("idref_v1:Person:notlocals-e2", (("string", "de"),)),
            ("idref_v1:Person:notlocals-e3", (("string", "de"),)),
        }

        self.assertEqual(self._payload_set(py), expected)
        self.assertEqual(self._payload_set(en), expected)
        self.assertEqual(
            {cand.key_tuple_digest for cand in py},
            {cand.key_tuple_digest for cand in en},
        )

    def test_not_local_vars_uncorrelated_rejected(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("eq", "$country", "de"),
            ("not", [("pred", "reason:level", ["$R", "$L"]), ("ge", "$L", 5)]),
        ]

        with self.assertRaises(WhereValidationError):
            store.evaluate(
                derivation_id="drv.where.notlocals.reject.py",
                version="v1",
                target_pred_id="person:country",
                head_vars=["$E", "$country"],
                where=where,
                mode="python",
            )
        with self.assertRaises(WhereValidationError):
            store.evaluate(
                derivation_id="drv.where.notlocals.reject.en",
                version="v1",
                target_pred_id="person:country",
                head_vars=["$E", "$country"],
                where=where,
                mode="engine",
            )

    def test_or_with_not_local_vars_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "de"),
                (
                    "not",
                    [
                        ("pred", "person:ban", ["$E", "$R"]),
                        ("pred", "reason:level", ["$R", "$L"]),
                        ("ge", "$L", 5),
                    ],
                ),
            ],
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "fr"),
            ],
        ]

        py, en = self._evaluate_pair(store, where, "drv.where.notlocals.or")
        expected = {
            ("idref_v1:Person:notlocals-e2", (("string", "de"),)),
            ("idref_v1:Person:notlocals-e3", (("string", "de"),)),
            ("idref_v1:Person:notlocals-e4", (("string", "fr"),)),
        }
        self.assertEqual(self._payload_set(py), expected)
        self.assertEqual(self._payload_set(en), expected)
        self.assertEqual(
            {cand.key_tuple_digest for cand in py},
            {cand.key_tuple_digest for cand in en},
        )


if __name__ == "__main__":
    unittest.main()
