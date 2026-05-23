from __future__ import annotations

import unittest

from factgraph.core.rules.where_eval import evaluate_where


class AggregateEvalTests(unittest.TestCase):
    def test_count_runs_per_outer_env_not_global_reduce(self) -> None:
        view_facts = {
            "User:exists": [("u-1",), ("u-2",)],
            "Order": [
                ("o-1", "u-1"),
                ("o-2", "u-1"),
                ("o-3", "u-1"),
                ("o-4", "u-2"),
                ("o-5", "u-2"),
                ("o-6", "u-2"),
                ("o-7", "u-2"),
                ("o-8", "u-2"),
            ],
        }
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$order_count", ("count", None, [("pred", "Order", ["$o", "$u"])])),
        ]

        rows = evaluate_where(view_facts, where)

        self.assertEqual(
            rows,
            [
                {"$order_count": 3, "$u": "u-1"},
                {"$order_count": 5, "$u": "u-2"},
            ],
        )

    def test_sum_mean_min_max_and_result_binding(self) -> None:
        view_facts = {
            "User:exists": [("u-1",)],
            "OrderAmount": [
                ("o-1", "u-1", 10),
                ("o-2", "u-1", 20),
                ("o-3", "u-1", 30),
            ],
        }

        self.assertEqual(
            evaluate_where(
                view_facts,
                [
                    ("pred", "User:exists", ["$u"]),
                    (
                        "eq",
                        "$total",
                        ("sum", "$amount", [("pred", "OrderAmount", ["$o", "$u", "$amount"])]),
                    ),
                    (
                        "eq",
                        "$mean",
                        ("mean", "$amount", [("pred", "OrderAmount", ["$o", "$u", "$amount"])]),
                    ),
                    (
                        "eq",
                        "$min",
                        ("min", "$amount", [("pred", "OrderAmount", ["$o", "$u", "$amount"])]),
                    ),
                    (
                        "eq",
                        "$max",
                        ("max", "$amount", [("pred", "OrderAmount", ["$o", "$u", "$amount"])]),
                    ),
                ],
            ),
            [{"$max": 30, "$mean": 20.0, "$min": 10, "$total": 60, "$u": "u-1"}],
        )

    def test_empty_min_no_value_violates_atom_without_exception(self) -> None:
        view_facts = {"User:exists": [("u-1",)], "OrderAmount": []}
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$min", ("min", "$amount", [("pred", "OrderAmount", ["$o", "$u", "$amount"])])),
        ]

        self.assertEqual(evaluate_where(view_facts, where), [])

    def test_no_value_arith_operand_excludes_env_without_exception(self) -> None:
        view_facts = {"User:exists": [("u-1",)], "OrderAmount": []}
        where = [
            ("pred", "User:exists", ["$u"]),
            ("addc", "$z", ("min", "$amount", [("pred", "OrderAmount", ["$o", "$u", "$amount"])]), 1),
            ("gt", "$z", 5),
        ]

        self.assertEqual(evaluate_where(view_facts, where), [])

    def test_runtime_non_numeric_sum_target_yields_no_value(self) -> None:
        view_facts = {
            "User:exists": [("u-1",)],
            "OrderAmount": [("o-1", "u-1", "bad")],
        }
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$total", ("sum", "$amount", [("pred", "OrderAmount", ["$o", "$u", "$amount"])])),
        ]

        self.assertEqual(evaluate_where(view_facts, where), [])


if __name__ == "__main__":
    unittest.main()
