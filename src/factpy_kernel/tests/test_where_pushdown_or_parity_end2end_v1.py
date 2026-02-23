from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.runner import find_souffle_binary
from factpy_kernel.core.store.api import Store


class WherePushdownOrParityEnd2EndV1Tests(unittest.TestCase):
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
                }
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:country"],
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
            e_ref="idref_v1:Person:or-e1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:or-e2",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-2"},
        )
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:or-e3",
            rest_terms=[("string", "us")],
            meta={"source": "test", "source_loc": "row-3"},
        )
        return store

    def _assert_parity(
        self,
        *,
        store: Store,
        where: list[tuple[str, object, object] | tuple[str, object, list[object]] | list[tuple]],
        expected: set[tuple[str, tuple[tuple[str, object], ...]]],
        derivation_id: str,
    ) -> None:
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

        py_payload = {
            (cand.payload["e_ref"], tuple(cand.payload["rest_terms"])) for cand in py
        }
        en_payload = {
            (cand.payload["e_ref"], tuple(cand.payload["rest_terms"])) for cand in en
        }

        self.assertEqual(py_payload, expected)
        self.assertEqual(en_payload, expected)
        self.assertEqual(py_payload, en_payload)

    def test_or_eq_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "de"),
            ],
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "fr"),
            ],
        ]

        self._assert_parity(
            store=store,
            where=where,
            expected={
                ("idref_v1:Person:or-e1", (("string", "de"),)),
                ("idref_v1:Person:or-e2", (("string", "fr"),)),
            },
            derivation_id="drv.where.or.eq",
        )

    def test_or_in_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("in", "$country", ["de", "us"]),
            ],
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "fr"),
            ],
        ]

        self._assert_parity(
            store=store,
            where=where,
            expected={
                ("idref_v1:Person:or-e1", (("string", "de"),)),
                ("idref_v1:Person:or-e2", (("string", "fr"),)),
                ("idref_v1:Person:or-e3", (("string", "us"),)),
            },
            derivation_id="drv.where.or.in",
        )

    def test_or_empty_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = self._seed_store()
        where = [
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("eq", "$country", "zz"),
            ],
            [
                ("pred", "person:country", ["$E", "$country"]),
                ("in", "$country", ["yy"]),
            ],
        ]

        py = store.evaluate(
            derivation_id="drv.where.or.empty",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=where,
            mode="python",
        )
        en = store.evaluate(
            derivation_id="drv.where.or.empty",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=where,
            mode="engine",
        )

        self.assertEqual(py, [])
        self.assertEqual(en, [])


if __name__ == "__main__":
    unittest.main()
