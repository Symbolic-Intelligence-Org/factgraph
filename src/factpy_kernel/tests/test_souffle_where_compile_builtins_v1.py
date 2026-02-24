from __future__ import annotations

import unittest

from factpy_kernel.adapters.souffle.where_compile import compile_where_to_query_dl
from factpy_kernel.core.rules.where_eval import WhereValidationError


class SouffleWhereCompileBuiltinsV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {
            "predicates": [
                {
                    "pred_id": "person:birth_year",
                    "cardinality": "functional",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "birth_year", "type_domain": "int"},
                    ],
                }
            ]
        }

    def test_compile_where_supports_linear_arithmetic_builtins(self) -> None:
        dl = compile_where_to_query_dl(
            schema_ir=self.schema_ir,
            where=[
                ("pred", "person:birth_year", ["$p", "$by"]),
                ("sub", "$age", 2026, "$by"),
                ("ge", "$age", 18),
            ],
            query_rel="q_adults",
        )
        self.assertIn(".decl q_adults(", dl)
        self.assertIn("p_person_birth__year(", dl)
        self.assertIn("= to_string((2026 - to_number(", dl)
        self.assertIn("to_number(", dl)
        self.assertIn(">= 18", dl)

    def test_compile_where_rejects_unbound_arithmetic_input(self) -> None:
        with self.assertRaises(WhereValidationError):
            compile_where_to_query_dl(
                schema_ir=self.schema_ir,
                where=[("add", "$z", "$x", 1)],
                query_rel="q_bad",
            )


if __name__ == "__main__":
    unittest.main()
