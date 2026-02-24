from __future__ import annotations

import unittest

from factpy_kernel.core.rules.backend_profile import BackendProfile
from factpy_kernel.core.rules.rule_ast import parse_query_rule_ir_to_ast
from factpy_kernel.core.rules.rule_ast_validate import RuleASTValidationError, validate_query_rule_ast


class QueryRuleNotBodyProfilePolicyV1Tests(unittest.TestCase):
    def test_souffle_profile_forbid_or_rejects_query_rule_not_or_body(self) -> None:
        ast = parse_query_rule_ir_to_ast(
            {
                "rule_id": "rules.country_without_ban_or_warning",
                "version": "v1",
                "select_vars": ["$P", "$C"],
                "where": [
                    ("pred", "person:country", ["$P", "$C"]),
                    (
                        "not",
                        [
                            [("pred", "person:block_reason", ["$P", "ban"])],
                            [("pred", "person:block_reason", ["$P", "warning"])],
                        ],
                    ),
                ],
            }
        )
        with self.assertRaises(RuleASTValidationError) as ctx:
            validate_query_rule_ast(
                ast,
                mode="souffle",
                profile=BackendProfile(capabilities={"not_body_policy": "forbid_or"}),
            )
        self.assertTrue(
            (getattr(ctx.exception, "path", None) or "").startswith("$.query_rule.where")
        )
        self.assertIn("where validation failed", str(ctx.exception))

    def test_souffle_default_profile_still_allows_query_rule_not_or_body(self) -> None:
        ast = parse_query_rule_ir_to_ast(
            {
                "rule_id": "rules.country_without_ban_or_warning",
                "version": "v1",
                "select_vars": ["$P", "$C"],
                "where": [
                    ("pred", "person:country", ["$P", "$C"]),
                    (
                        "not",
                        [
                            [("pred", "person:block_reason", ["$P", "ban"])],
                            [("pred", "person:block_reason", ["$P", "warning"])],
                        ],
                    ),
                ],
            }
        )
        validate_query_rule_ast(ast, mode="souffle")


if __name__ == "__main__":
    unittest.main()
