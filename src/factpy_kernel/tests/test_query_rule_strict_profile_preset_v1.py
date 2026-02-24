from __future__ import annotations

import unittest

from factpy_kernel.core.rules.backend_profile import PROFILE_DEFAULT, PROFILE_SOUFFLE_STRICT
from factpy_kernel.core.rules.rule_ast import parse_query_rule_ir_to_ast
from factpy_kernel.core.rules.rule_ast_validate import RuleASTValidationError, validate_query_rule_ast


class QueryRuleStrictProfilePresetV1Tests(unittest.TestCase):
    def test_strict_profile_rejects_query_rule_ruleref(self) -> None:
        ast = parse_query_rule_ir_to_ast(
            {
                "rule_id": "rules.rank_rows",
                "version": "v1",
                "select_vars": ["$E", "$R"],
                "where": [("ruleref", "q_rank", "1.0.0", ["$E", "$R"])],
            }
        )
        with self.assertRaises(RuleASTValidationError) as ctx:
            validate_query_rule_ast(ast, mode="souffle", profile=PROFILE_SOUFFLE_STRICT)
        self.assertEqual(getattr(ctx.exception, "path", None), "$.query_rule.where")

    def test_default_profile_keeps_query_rule_ruleref_behavior(self) -> None:
        ast = parse_query_rule_ir_to_ast(
            {
                "rule_id": "rules.rank_rows",
                "version": "v1",
                "select_vars": ["$E", "$R"],
                "where": [("ruleref", "q_rank", "1.0.0", ["$E", "$R"])],
            }
        )
        validate_query_rule_ast(ast, mode="souffle", profile=PROFILE_DEFAULT)

    def test_strict_profile_rejects_query_rule_not_or_body(self) -> None:
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
            validate_query_rule_ast(ast, mode="souffle", profile=PROFILE_SOUFFLE_STRICT)
        self.assertEqual(getattr(ctx.exception, "path", None), "$.query_rule.where")

    def test_default_profile_keeps_query_rule_not_or_behavior(self) -> None:
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
        validate_query_rule_ast(ast, mode="souffle", profile=PROFILE_DEFAULT)


if __name__ == "__main__":
    unittest.main()
