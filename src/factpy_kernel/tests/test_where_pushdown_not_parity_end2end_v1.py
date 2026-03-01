from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.runner import find_souffle_binary
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store.api import Store


class WherePushdownNotParityEnd2EndV1Tests(unittest.TestCase):
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
                    "pred_id": "person:blacklist",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "reason", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "multi",
                },
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:country", "person:blacklist"],
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
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:not-e1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:blacklist",
            e_ref="idref_v1:Person:not-e1",
            rest_terms=[("string", "x")],
            meta={"source": "test", "source_loc": "row-2"},
        )

        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:not-e2",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-3"},
        )

        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:not-e3",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-4"},
        )
        set_field(
            store.ledger,
            pred_id="person:blacklist",
            e_ref="idref_v1:Person:not-e3",
            rest_terms=[("string", "y")],
            meta={"source": "test", "source_loc": "row-5"},
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

    def _payload_set(self, candidates) -> set[tuple[str, tuple[tuple[str, object], ...]]]:
        return {
            (
                cand.payload["terms"][0]["value"],
                tuple(
                    (term["tag"], term["value"])
                    if term["kind"] == "literal"
                    else ("entity_ref", term["value"])
                    for term in cand.payload["terms"][1:]
                ),
            )
            for cand in candidates
        }

    def test_not_filters_blacklisted_de(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("eq", "$country", "de"),
            ("not", [("pred", "person:blacklist", ["$E", "x"])]),
        ]

        py, en = self._evaluate_pair(store, where, "drv.where.not.hit")
        expected = {("idref_v1:Person:not-e2", (("string", "de"),))}

        self.assertEqual(self._payload_set(py), expected)
        self.assertEqual(self._payload_set(en), expected)
        self.assertEqual(
            {cand.key_tuple_digest for cand in py},
            {cand.key_tuple_digest for cand in en},
        )

    def test_not_empty_result_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("eq", "$country", "de"),
            ("not", [("pred", "person:country", ["$E", "$country"])]),
        ]

        py, en = self._evaluate_pair(store, where, "drv.where.not.empty")
        self.assertEqual(py, [])
        self.assertEqual(en, [])

    def test_not_rejects_unbound_variables(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("not", [("pred", "person:blacklist", ["$X", "$r"])]),
        ]

        with self.assertRaises(WhereValidationError):
            store.evaluate(
                derivation_id="drv.where.not.unbound.py",
                version="v1",
                target_pred_id="person:country",
                head_vars=["$E", "$country"],
                where=where,
                mode="python",
            )

        with self.assertRaises(WhereValidationError):
            store.evaluate(
                derivation_id="drv.where.not.unbound.en",
                version="v1",
                target_pred_id="person:country",
                head_vars=["$E", "$country"],
                where=where,
                mode="engine",
            )

    def test_or_with_not_branch_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "de"),
                ("not", [("pred", "person:blacklist", ["$E", "x"])]),
            ],
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "fr"),
            ],
        ]

        py, en = self._evaluate_pair(store, where, "drv.where.not.or")
        expected = {
            ("idref_v1:Person:not-e2", (("string", "de"),)),
            ("idref_v1:Person:not-e3", (("string", "fr"),)),
        }

        self.assertEqual(self._payload_set(py), expected)
        self.assertEqual(self._payload_set(en), expected)
        self.assertEqual(
            {cand.key_tuple_digest for cand in py},
            {cand.key_tuple_digest for cand in en},
        )


if __name__ == "__main__":
    unittest.main()
