from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.rules.where_eval import WhereValidationError, evaluate_where
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.view.projector import project_view_facts


class WhereEvalV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {
            "schema_ir_version": "v1",
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [{"name": "source_id", "type_domain": "string"}],
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
                    "pred_id": "person:lang",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "lang", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
            ],
            "projection": {"entities": [], "predicates": ["person:country", "person:lang"]},
            "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
            "generated_at": "2026-01-01T00:00:00Z",
        }
        self.store = Store(schema_ir=self.schema_ir)

        self.e1 = "idref_v1:Person:e1"
        self.e2 = "idref_v1:Person:e2"

        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.e1,
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            self.store.ledger,
            pred_id="person:lang",
            e_ref=self.e1,
            rest_terms=[("string", "en")],
            meta={"source": "test", "source_loc": "row-2"},
        )
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.e2,
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-3"},
        )

    def test_and_join_returns_one_binding(self) -> None:
        view_facts = project_view_facts(self.store.ledger, self.schema_ir)
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("pred", "person:lang", ["$E", "$lang"]),
        ]

        bindings = evaluate_where(view_facts, where)
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0]["$E"], self.e1)
        self.assertEqual(bindings[0]["$country"], "de")
        self.assertEqual(bindings[0]["$lang"], "en")

    def test_or_branches_return_two_bindings(self) -> None:
        view_facts = project_view_facts(self.store.ledger, self.schema_ir)
        where = [
            [("pred", "person:country", ["$E", "de"])],
            [("pred", "person:country", ["$E", "fr"])],
        ]

        bindings = evaluate_where(view_facts, where)
        self.assertEqual(len(bindings), 2)
        self.assertEqual({row["$E"] for row in bindings}, {self.e1, self.e2})

    def test_invalid_where_dsl_raises(self) -> None:
        view_facts = project_view_facts(self.store.ledger, self.schema_ir)

        with self.assertRaises(WhereValidationError):
            evaluate_where(
                view_facts,
                [[[ ("pred", "person:country", ["$E", "$country"]) ]]],
            )

        with self.assertRaises(WhereValidationError):
            evaluate_where(
                view_facts,
                [("gt", "$x", 1)],
            )

    def test_evaluate_key_tuple_digest_stable(self) -> None:
        where = [("pred", "person:country", ["$E", "$country"])]
        head_vars = ["$E", "$country"]

        result_1 = self.store.evaluate(
            derivation_id="derive_country",
            version="v1",
            target_pred_id="person:country",
            head_vars=head_vars,
            where=where,
        )
        result_2 = self.store.evaluate(
            derivation_id="derive_country",
            version="v1",
            target_pred_id="person:country",
            head_vars=head_vars,
            where=where,
        )

        digests_1 = {candidate.key_tuple_digest for candidate in result_1}
        digests_2 = {candidate.key_tuple_digest for candidate in result_2}

        self.assertEqual(digests_1, digests_2)
        self.assertGreater(len(digests_1), 0)

    def test_arithmetic_builtins_bind_and_filter(self) -> None:
        view_facts = {
            "person:birth_year": [
                (self.e1, 2000),
                (self.e2, 2012),
            ]
        }
        where = [
            ("pred", "person:birth_year", ["$E", "$by"]),
            ("sub", "$age", 2026, "$by"),
            ("ge", "$age", 18),
        ]
        bindings = evaluate_where(view_facts, where)
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0]["$E"], self.e1)
        self.assertEqual(bindings[0]["$age"], 26)

    def test_arithmetic_builtins_support_addc_mulc_neg(self) -> None:
        bindings = evaluate_where(
            {"x:v": [("e1", 3)]},
            [
                ("pred", "x:v", ["$E", "$x"]),
                ("mulc", "$y", "$x", 2),
                ("addc", "$z", "$y", 1),
                ("neg", "$n", "$z"),
                ("eq", "$n", -7),
            ],
        )
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0]["$n"], -7)

    def test_arithmetic_input_must_be_bound(self) -> None:
        with self.assertRaises(WhereValidationError):
            evaluate_where({"x:v": [("e1", 3)]}, [("add", "$z", "$x", 1)])


if __name__ == "__main__":
    unittest.main()
