from __future__ import annotations

import unittest

from factpy_kernel.adapters.souffle.where_compile import (
    build_query_witness_layout,
    compile_where_to_query_dl,
)


class SouffleWitnessWhereCompileV1Tests(unittest.TestCase):
    def test_build_query_witness_layout_collects_pred_atoms_in_branch_order(self) -> None:
        where = [
            [("pred", "user:name", ["$e", "$value"])],
            [("pred", "user:status", ["$e", "$value"])],
        ]

        layout = build_query_witness_layout(where)

        self.assertEqual(layout.query_variables, ("$e", "$value"))
        self.assertEqual(
            [row.pred_atom_key for row in layout.pred_witness_columns],
            ["b0.a0:user:name", "b1.a0:user:status"],
        )

    def test_compile_where_to_query_dl_with_witness_columns_uses_w_relations(self) -> None:
        where = [
            [("pred", "user:name", ["$e", "$value"])],
            [("pred", "user:status", ["$e", "$value"])],
        ]

        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=where,
            query_rel="query__test",
            include_pred_witness_columns=True,
        )

        self.assertIn(".decl query__test(C0:symbol, C1:symbol, W0:symbol, W1:symbol)", dl)
        self.assertIn(".output query__test", dl)
        self.assertIn('query__test(C0, C1, W0, W1) :- p_user_name_w(C0, C1, W0), W1 = "".', dl)
        self.assertIn('query__test(C0, C1, W0, W1) :- p_user_status_w(C0, C1, W1), W0 = "".', dl)

    def test_compile_where_to_query_dl_keeps_legacy_shape_by_default(self) -> None:
        where = [
            ("pred", "user:name", ["$e", "$name"]),
            ("pred", "user:status", ["$e", "$status"]),
        ]

        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=where,
            query_rel="query__legacy",
        )

        self.assertIn(".decl query__legacy(C0:symbol, C1:symbol, C2:symbol)", dl)
        self.assertNotIn("W0:symbol", dl)
        self.assertIn("p_user_name(C0, C1)", dl)
        self.assertIn("p_user_status(C0, C2)", dl)
        self.assertNotIn("p_user_name_w(", dl)


def _schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {
                "pred_id": "user:name",
                "cardinality": "multi",
                "arg_specs": [
                    {"name": "e_ref", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            },
            {
                "pred_id": "user:status",
                "cardinality": "single",
                "arg_specs": [
                    {"name": "e_ref", "type_domain": "entity_ref"},
                    {"name": "status", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            },
        ]
    }


if __name__ == "__main__":
    unittest.main()
