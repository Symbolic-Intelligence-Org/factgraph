from __future__ import annotations

import unittest

from factpy.application._derivation_match_helpers import (
    _all_body_vars,
    _binding_matches,
)


class DerivationBindingMatchHelperTests(unittest.TestCase):
    def test_binding_matches_requested_subset(self) -> None:
        self.assertTrue(
            _binding_matches(
                {"$person": "alice", "$city": "Paris"},
                (("$person", "alice"),),
            )
        )

    def test_binding_mismatch_rejects(self) -> None:
        self.assertFalse(
            _binding_matches(
                {"$person": "alice", "$city": "Paris"},
                (("$person", "bob"),),
            )
        )

    def test_empty_requested_binding_matches_any_final_binding(self) -> None:
        self.assertTrue(_binding_matches({"$person": "alice"}, ()))


class DerivationBodyVarHelperTests(unittest.TestCase):
    def test_all_body_vars_collects_plain_atoms(self) -> None:
        self.assertEqual(
            _all_body_vars([
                ("pred", "parent", ["$parent", "$child"]),
                ("pred", "lives_in", ["$child", "Paris"]),
            ]),
            {"$parent", "$child"},
        )

    def test_all_body_vars_collects_not_body_vars(self) -> None:
        self.assertEqual(
            _all_body_vars([
                ("pred", "parent", ["$parent", "$child"]),
                ("not", [("pred", "blocked", ["$child", "$reason"])]),
            ]),
            {"$parent", "$child", "$reason"},
        )

    def test_all_body_vars_collects_ruleref_terms(self) -> None:
        self.assertEqual(
            _all_body_vars([
                ("ruleref", "eligible", None, ["$person", "literal", "$status"]),
            ]),
            {"$person", "$status"},
        )


if __name__ == "__main__":
    unittest.main()
