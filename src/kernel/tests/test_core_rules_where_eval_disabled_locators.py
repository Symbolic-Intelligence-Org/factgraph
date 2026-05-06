"""Native where evaluator disabled-locator primitive tests."""

from __future__ import annotations

import unittest

from kernel.core.rules.where_eval import WhereValidationError, evaluate_where


class WhereEvalDisabledLocatorTests(unittest.TestCase):
    def test_disabled_locator_skips_atom_without_shifting_later_semantics(self) -> None:
        view_facts = {
            "Person:exists": [("alice",), ("bob",)],
            "Person:region": [("alice", "us"), ("bob", "eu")],
        }
        where = [
            ("pred", "Person:exists", ["$p"]),
            ("pred", "Person:region", ["$p", "$region"]),
            ("eq", "$region", "us"),
        ]

        baseline = evaluate_where(view_facts, where)
        variant = evaluate_where(
            view_facts,
            where,
            disabled_locators=frozenset({(0, 2)}),
        )

        self.assertEqual(baseline, [{"$p": "alice", "$region": "us"}])
        self.assertEqual(
            variant,
            [
                {"$p": "alice", "$region": "us"},
                {"$p": "bob", "$region": "eu"},
            ],
        )

    def test_disabled_locator_supports_or_branch_coordinates(self) -> None:
        view_facts = {
            "Person:exists": [("alice",), ("bob",)],
        }
        where = [
            [("pred", "Person:exists", ["$p"]), ("eq", "$p", "alice")],
            [("pred", "Person:exists", ["$p"]), ("eq", "$p", "bob")],
        ]

        result = evaluate_where(
            view_facts,
            where,
            disabled_locators=frozenset({(1, 1)}),
        )

        self.assertEqual(result, [{"$p": "alice"}, {"$p": "bob"}])

    def test_disabled_locator_rejects_out_of_range_coordinates(self) -> None:
        with self.assertRaises(WhereValidationError):
            evaluate_where(
                {"Person:exists": [("alice",)]},
                [("pred", "Person:exists", ["$p"])],
                disabled_locators=frozenset({(1, 0)}),
            )
        with self.assertRaises(WhereValidationError):
            evaluate_where(
                {"Person:exists": [("alice",)]},
                [("pred", "Person:exists", ["$p"])],
                disabled_locators=frozenset({(0, 2)}),
            )

    def test_disabled_locator_rejects_bad_shape(self) -> None:
        with self.assertRaises(WhereValidationError):
            evaluate_where(
                {"Person:exists": [("alice",)]},
                [("pred", "Person:exists", ["$p"])],
                disabled_locators={(0, 0)},  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
