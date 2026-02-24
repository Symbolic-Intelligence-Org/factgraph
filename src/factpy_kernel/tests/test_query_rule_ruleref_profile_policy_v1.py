from __future__ import annotations

import unittest

from factpy_kernel.core.rules.backend_profile import BackendProfile
from factpy_kernel.core.rules.rule_ast import parse_query_rule_ir_to_ast
from factpy_kernel.core.rules.rule_ast_validate import RuleASTValidationError, validate_query_rule_ast


class QueryRuleRuleRefProfilePolicyV1Tests(unittest.TestCase):
    def test_souffle_profile_require_resolved_rejects_query_rule_ruleref(self) -> None:
        ast = parse_query_rule_ir_to_ast(
            {
                "rule_id": "rules.rank_rows",
                "version": "v1",
                "select_vars": ["$E", "$R"],
                "where": [("ruleref", "q_rank", "1.0.0", ["$E", "$R"])],
            }
        )
        with self.assertRaises(RuleASTValidationError) as ctx:
            validate_query_rule_ast(
                ast,
                mode="souffle",
                profile=BackendProfile(capabilities={"ruleref_policy": "require_resolved"}),
            )
        self.assertEqual(getattr(ctx.exception, "path", None), "$.query_rule.where")
        self.assertIn("where validation failed", str(ctx.exception))

    def test_souffle_default_profile_still_allows_query_rule_ruleref(self) -> None:
        ast = parse_query_rule_ir_to_ast(
            {
                "rule_id": "rules.rank_rows",
                "version": "v1",
                "select_vars": ["$E", "$R"],
                "where": [("ruleref", "q_rank", "1.0.0", ["$E", "$R"])],
            }
        )
        validate_query_rule_ast(ast, mode="souffle")


if __name__ == "__main__":
    unittest.main()
