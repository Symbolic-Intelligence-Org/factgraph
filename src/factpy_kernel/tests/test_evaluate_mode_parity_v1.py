from __future__ import annotations

import unittest
from unittest.mock import patch

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.runner import find_souffle_binary
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store.api import Store


class EvaluateModeParityV1Tests(unittest.TestCase):
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

    @staticmethod
    def _payload_sig(cand) -> tuple[str, tuple[tuple[str, object], ...]]:
        terms = cand.payload["terms"]
        return (
            terms[0]["value"],
            tuple(
                (term["tag"], term["value"])
                if term["kind"] == "literal"
                else ("entity_ref", term["value"])
                for term in terms[1:]
            ),
        )

    def test_evaluate_bad_mode_raises(self) -> None:
        store = Store(schema_ir=self.schema_ir)
        with self.assertRaises(ValueError):
            store.evaluate(
                derivation_id="drv.parity",
                version="v1",
                target_pred_id="person:country",
                head_vars=["$E", "$country"],
                where=[("pred", "person:country", ["$E", "$country"])],
                mode="bad",
            )

    def test_evaluate_python_engine_mode_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:parity-e1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:parity-e2",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-2"},
        )

        where = [("pred", "person:country", ["$E", "$country"])]

        py = store.evaluate(
            derivation_id="drv.parity",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=where,
            mode="python",
        )
        en = store.evaluate(
            derivation_id="drv.parity",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=where,
            mode="engine",
        )

        py_payload_set = {self._payload_sig(cand) for cand in py}
        en_payload_set = {self._payload_sig(cand) for cand in en}

        self.assertEqual(py_payload_set, en_payload_set)
        self.assertEqual(
            {cand.key_tuple_digest for cand in py},
            {cand.key_tuple_digest for cand in en},
        )
        self.assertEqual(
            {cand.target for cand in py},
            {"person:country"},
        )
        self.assertEqual(
            {cand.target for cand in en},
            {"person:country"},
        )

    def test_evaluate_python_engine_empty_result_parity(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:parity-empty-e1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:parity-empty-e2",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-2"},
        )

        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("eq", "$country", "zz"),
        ]

        py = store.evaluate(
            derivation_id="drv.parity.empty",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=where,
            mode="python",
        )
        en = store.evaluate(
            derivation_id="drv.parity.empty",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=where,
            mode="engine",
        )

        self.assertEqual(py, [])
        self.assertEqual(en, [])

    def test_evaluate_python_engine_parity_pred_in_cmp_int(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        schema_ir = {
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
                    "pred_id": "person:rank",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "rank", "type_domain": "int"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                }
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:rank"],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }
        store = Store(schema_ir=schema_ir)
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:parity-r1",
            rest_terms=[("int", 1)],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:parity-r3",
            rest_terms=[("int", 3)],
            meta={"source": "test", "source_loc": "row-2"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:parity-r5",
            rest_terms=[("int", 5)],
            meta={"source": "test", "source_loc": "row-3"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:parity-r7",
            rest_terms=[("int", 7)],
            meta={"source": "test", "source_loc": "row-4"},
        )

        where = [
            ("pred", "person:rank", ["$E", "$rank"]),
            ("in", "$rank", [3, 5, 9]),
            ("ge", "$rank", 4),
        ]

        py = store.evaluate(
            derivation_id="drv.parity.pred-in-cmp",
            version="v1",
            target_pred_id="person:rank",
            head_vars=["$E", "$rank"],
            where=where,
            mode="python",
        )
        en = store.evaluate(
            derivation_id="drv.parity.pred-in-cmp",
            version="v1",
            target_pred_id="person:rank",
            head_vars=["$E", "$rank"],
            where=where,
            mode="engine",
        )

        py_payload_set = {self._payload_sig(cand) for cand in py}
        en_payload_set = {self._payload_sig(cand) for cand in en}
        self.assertEqual(
            py_payload_set,
            {("idref_v1:Person:parity-r5", (("int", 5),))},
        )
        self.assertEqual(py_payload_set, en_payload_set)
        self.assertEqual(
            {cand.key_tuple_digest for cand in py},
            {cand.key_tuple_digest for cand in en},
        )
        self.assertEqual({cand.target for cand in py}, {"person:rank"})
        self.assertEqual({cand.target for cand in en}, {"person:rank"})

    def test_evaluate_python_engine_parity_pred_in_cmp_empty(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        schema_ir = {
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
                    "pred_id": "person:rank",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "rank", "type_domain": "int"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                }
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:rank"],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }
        store = Store(schema_ir=schema_ir)
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:parity-empty-r3",
            rest_terms=[("int", 3)],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:parity-empty-r5",
            rest_terms=[("int", 5)],
            meta={"source": "test", "source_loc": "row-2"},
        )

        where = [
            ("pred", "person:rank", ["$E", "$rank"]),
            ("in", "$rank", [3, 5]),
            ("gt", "$rank", 10),
        ]

        py = store.evaluate(
            derivation_id="drv.parity.pred-in-cmp-empty",
            version="v1",
            target_pred_id="person:rank",
            head_vars=["$E", "$rank"],
            where=where,
            mode="python",
        )
        en = store.evaluate(
            derivation_id="drv.parity.pred-in-cmp-empty",
            version="v1",
            target_pred_id="person:rank",
            head_vars=["$E", "$rank"],
            where=where,
            mode="engine",
        )
        self.assertEqual(py, [])
        self.assertEqual(en, [])

    def test_evaluate_engine_rejects_noop_fallback(self) -> None:
        store = Store(schema_ir=self.schema_ir)
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:parity-fallback-e1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )

        with patch("factpy_kernel.adapters.souffle.runner.find_souffle_binary", return_value=None):
            with self.assertRaisesRegex(
                WhereValidationError,
                r"runner fell back to noop",
            ):
                store.evaluate(
                    derivation_id="drv.parity.fallback",
                    version="v1",
                    target_pred_id="person:country",
                    head_vars=["$E", "$country"],
                    where=[("pred", "person:country", ["$E", "$country"])],
                    mode="engine",
                )


if __name__ == "__main__":
    unittest.main()
