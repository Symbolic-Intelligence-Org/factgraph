"""Native where evaluator disabled-locator primitive tests."""

from __future__ import annotations

import unittest

from kernel.core.rules.where_eval import (
    WhereLiteralReplacement,
    WhereValidationError,
    evaluate_where,
)


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


class WhereEvalLiteralReplacementTests(unittest.TestCase):
    def test_literal_replacement_updates_eq_filter(self) -> None:
        view_facts = {
            "Person:exists": [("alice",), ("bob",)],
            "Person:region": [("alice", "us"), ("bob", "eu")],
        }
        where = [
            ("pred", "Person:exists", ["$p"]),
            ("pred", "Person:region", ["$p", "$region"]),
            ("eq", "$region", "us"),
        ]

        result = evaluate_where(
            view_facts,
            where,
            literal_replacements=frozenset(
                {
                    WhereLiteralReplacement(
                        branch_index=0,
                        atom_index=2,
                        literal_path=("rhs", None),
                        old_literal="us",
                        new_literal="eu",
                    )
                }
            ),
        )

        self.assertEqual(result, [{"$p": "bob", "$region": "eu"}])

    def test_literal_replacement_updates_pred_constant_and_in_member(self) -> None:
        view_facts = {
            "Person:region": [("alice", "us"), ("bob", "eu")],
        }

        pred_result = evaluate_where(
            view_facts,
            [("pred", "Person:region", ["$p", "us"])],
            literal_replacements=frozenset(
                {
                    WhereLiteralReplacement(
                        branch_index=0,
                        atom_index=0,
                        literal_path=("pred_term", 1),
                        old_literal="us",
                        new_literal="eu",
                    )
                }
            ),
        )
        in_result = evaluate_where(
            view_facts,
            [
                ("pred", "Person:region", ["$p", "$region"]),
                ("in", "$region", ["us"]),
            ],
            literal_replacements=frozenset(
                {
                    WhereLiteralReplacement(
                        branch_index=0,
                        atom_index=1,
                        literal_path=("in_value", 0),
                        old_literal="us",
                        new_literal="eu",
                    )
                }
            ),
        )

        self.assertEqual(pred_result, [{"$p": "bob"}])
        self.assertEqual(in_result, [{"$p": "bob", "$region": "eu"}])

    def test_literal_replacement_updates_addc_constant(self) -> None:
        result = evaluate_where(
            {"Score:base": [("alice", 7)]},
            [
                ("pred", "Score:base", ["$p", "$base"]),
                ("addc", "$score", "$base", 5),
                ("eq", "$score", 12),
            ],
            literal_replacements=frozenset(
                {
                    WhereLiteralReplacement(
                        branch_index=0,
                        atom_index=1,
                        literal_path=("const_operand", None),
                        old_literal=5,
                        new_literal=6,
                    )
                }
            ),
        )

        self.assertEqual(result, [])

    def test_literal_replacement_rejects_variable_new_literal_and_stale_old_literal(self) -> None:
        where = [("eq", "$region", "us")]
        with self.assertRaises(WhereValidationError):
            evaluate_where(
                {},
                where,
                literal_replacements=frozenset(
                    {
                        WhereLiteralReplacement(
                            branch_index=0,
                            atom_index=0,
                            literal_path=("rhs", None),
                            old_literal="us",
                            new_literal="$other",
                        )
                    }
                ),
            )
        with self.assertRaises(WhereValidationError):
            evaluate_where(
                {},
                where,
                literal_replacements=frozenset(
                    {
                        WhereLiteralReplacement(
                            branch_index=0,
                            atom_index=0,
                            literal_path=("rhs", None),
                            old_literal="eu",
                            new_literal="ca",
                        )
                    }
                ),
            )


if __name__ == "__main__":
    unittest.main()
