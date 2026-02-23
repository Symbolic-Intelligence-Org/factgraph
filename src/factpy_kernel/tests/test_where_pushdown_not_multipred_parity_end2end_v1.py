from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.runner import find_souffle_binary
from factpy_kernel.core.store.api import Store


class WherePushdownNotMultiPredParityEnd2EndV1Tests(unittest.TestCase):
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
                    "pred_id": "person:ban",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "country", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "multi",
                },
            ],
            "projection": {
                "entities": [],
                "predicates": [
                    "person:country",
                    "person:blacklist",
                    "person:rank",
                    "person:ban",
                ],
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
            e_ref="idref_v1:Person:mp-e1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:mp-e1",
            rest_terms=[("int", 6)],
            meta={"source": "test", "source_loc": "row-2"},
        )
        set_field(
            store.ledger,
            pred_id="person:blacklist",
            e_ref="idref_v1:Person:mp-e1",
            rest_terms=[("string", "x")],
            meta={"source": "test", "source_loc": "row-3"},
        )
        set_field(
            store.ledger,
            pred_id="person:ban",
            e_ref="idref_v1:Person:mp-e1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-4"},
        )

        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:mp-e2",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-5"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:mp-e2",
            rest_terms=[("int", 6)],
            meta={"source": "test", "source_loc": "row-6"},
        )
        set_field(
            store.ledger,
            pred_id="person:blacklist",
            e_ref="idref_v1:Person:mp-e2",
            rest_terms=[("string", "x")],
            meta={"source": "test", "source_loc": "row-7"},
        )
        set_field(
            store.ledger,
            pred_id="person:ban",
            e_ref="idref_v1:Person:mp-e2",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-8"},
        )

        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:mp-e3",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-9"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:mp-e3",
            rest_terms=[("int", 3)],
            meta={"source": "test", "source_loc": "row-10"},
        )
        set_field(
            store.ledger,
            pred_id="person:blacklist",
            e_ref="idref_v1:Person:mp-e3",
            rest_terms=[("string", "x")],
            meta={"source": "test", "source_loc": "row-11"},
        )
        set_field(
            store.ledger,
            pred_id="person:ban",
            e_ref="idref_v1:Person:mp-e3",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-12"},
        )

        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:mp-e4",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-13"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:mp-e4",
            rest_terms=[("int", 8)],
            meta={"source": "test", "source_loc": "row-14"},
        )
        set_field(
            store.ledger,
            pred_id="person:blacklist",
            e_ref="idref_v1:Person:mp-e4",
            rest_terms=[("string", "x")],
            meta={"source": "test", "source_loc": "row-15"},
        )
        set_field(
            store.ledger,
            pred_id="person:ban",
            e_ref="idref_v1:Person:mp-e4",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-16"},
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

    def test_not_multipred_filters_expected_rows(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("eq", "$country", "de"),
            ("pred", "person:rank", ["$E", "$rank"]),
            (
                "not",
                [
                    ("pred", "person:blacklist", ["$E", "x"]),
                    ("pred", "person:ban", ["$E", "$country"]),
                    ("in", "$rank", [6]),
                    ("ge", "$rank", 5),
                ],
            ),
        ]

        py, en = self._evaluate_pair(store, where, "drv.where.not.mp.hit")
        expected = {
            ("idref_v1:Person:mp-e2", (("string", "de"),)),
            ("idref_v1:Person:mp-e3", (("string", "de"),)),
        }

        self.assertEqual(self._payload_set(py), expected)
        self.assertEqual(self._payload_set(en), expected)
        self.assertEqual(
            {cand.key_tuple_digest for cand in py},
            {cand.key_tuple_digest for cand in en},
        )

    def test_not_multipred_unsat_does_not_filter(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("eq", "$country", "de"),
            ("pred", "person:rank", ["$E", "$rank"]),
            (
                "not",
                [
                    ("pred", "person:blacklist", ["$E", "x"]),
                    ("pred", "person:ban", ["$E", "zz"]),
                ],
            ),
        ]

        py, en = self._evaluate_pair(store, where, "drv.where.not.mp.unsat")
        expected = {
            ("idref_v1:Person:mp-e1", (("string", "de"),)),
            ("idref_v1:Person:mp-e2", (("string", "de"),)),
            ("idref_v1:Person:mp-e3", (("string", "de"),)),
        }

        self.assertEqual(self._payload_set(py), expected)
        self.assertEqual(self._payload_set(en), expected)
        self.assertEqual(
            {cand.key_tuple_digest for cand in py},
            {cand.key_tuple_digest for cand in en},
        )

    def test_or_with_not_multipred_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "de"),
                ("pred", "person:rank", ["$E", "$rank"]),
                (
                    "not",
                    [
                        ("pred", "person:blacklist", ["$E", "x"]),
                        ("pred", "person:ban", ["$E", "$country"]),
                        ("in", "$rank", [6]),
                        ("ge", "$rank", 5),
                    ],
                ),
            ],
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "fr"),
                ("pred", "person:rank", ["$E", "$rank"]),
            ],
        ]

        py, en = self._evaluate_pair(store, where, "drv.where.not.mp.or")
        expected = {
            ("idref_v1:Person:mp-e2", (("string", "de"),)),
            ("idref_v1:Person:mp-e3", (("string", "de"),)),
            ("idref_v1:Person:mp-e4", (("string", "fr"),)),
        }

        self.assertEqual(self._payload_set(py), expected)
        self.assertEqual(self._payload_set(en), expected)
        self.assertEqual(
            {cand.key_tuple_digest for cand in py},
            {cand.key_tuple_digest for cand in en},
        )


if __name__ == "__main__":
    unittest.main()
