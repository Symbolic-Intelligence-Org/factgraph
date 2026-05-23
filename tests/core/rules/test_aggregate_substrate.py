from __future__ import annotations

import unittest

from factgraph.core.rules.where_ast import (
    AggregateAtom,
    CmpAtom,
    lower_ast_to_where_ir,
    parse_where_ir_to_ast,
)
from factgraph.core.rules.where_ast_validate import (
    AggregateValidationError,
    AggregateVariableScopeError,
    validate_where_ast,
)


class AggregateIRTests(unittest.TestCase):
    def test_parse_and_lower_aggregate_term(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$order_count", ("count", None, [("pred", "Order", ["$o", "$u"])])),
        ]

        expr = parse_where_ir_to_ast(where)
        atom = expr.atoms[1]

        self.assertIsInstance(atom, CmpAtom)
        self.assertIsInstance(atom.rhs, AggregateAtom)
        self.assertEqual(atom.rhs.kind, "count")
        self.assertIsNone(atom.rhs.target)
        self.assertEqual(lower_ast_to_where_ir(expr), where)


class AggregateValidationTests(unittest.TestCase):
    def test_filter_rejects_nested_aggregate(self) -> None:
        expr = parse_where_ir_to_ast(
            [
                (
                    "eq",
                    "$n",
                    (
                        "count",
                        None,
                        [
                            (
                                "eq",
                                "$inner",
                                ("count", None, [("pred", "Order", ["$o"])]),
                            )
                        ],
                    ),
                )
            ]
        )

        with self.assertRaises(AggregateValidationError):
            validate_where_ast(expr, mode="python", capabilities={"allow_ruleref": False})

    def test_target_var_must_be_bound_by_outer_or_filter(self) -> None:
        expr = parse_where_ir_to_ast(
            [
                ("pred", "User:exists", ["$u"]),
                ("eq", "$total", ("sum", "$amount", [("pred", "Order", ["$o", "$u"])])),
            ]
        )

        with self.assertRaises(AggregateVariableScopeError):
            validate_where_ast(expr, mode="python", capabilities={"allow_ruleref": False})

    def test_filter_local_var_must_not_leak_to_outer_atoms(self) -> None:
        expr = parse_where_ir_to_ast(
            [
                ("pred", "User:exists", ["$u"]),
                ("eq", "$order_count", ("count", None, [("pred", "Order", ["$o", "$u"])])),
                ("eq", "$o", "o-1"),
            ]
        )

        with self.assertRaises(AggregateVariableScopeError):
            validate_where_ast(expr, mode="python", capabilities={"allow_ruleref": False})

    def test_sum_const_target_rejects_non_numeric_literal(self) -> None:
        expr = parse_where_ir_to_ast(
            [
                ("pred", "User:exists", ["$u"]),
                ("eq", "$total", ("sum", "not-numeric", [("pred", "Order", ["$o", "$u"])])),
            ]
        )

        with self.assertRaises(AggregateValidationError):
            validate_where_ast(expr, mode="python", capabilities={"allow_ruleref": False})


if __name__ == "__main__":
    unittest.main()
