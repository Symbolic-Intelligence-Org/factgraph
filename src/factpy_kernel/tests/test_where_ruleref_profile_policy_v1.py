from __future__ import annotations

import unittest

from factpy_kernel.core.rules.backend_profile import BackendProfile
from factpy_kernel.core.rules.where_ast import parse_where_ir_to_ast
from factpy_kernel.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast


class WhereRuleRefProfilePolicyV1Tests(unittest.TestCase):
    def test_souffle_profile_require_resolved_rejects_ruleref(self) -> None:
        ast = parse_where_ir_to_ast([("ruleref", "q_rank", "1.0.0", ["$E", "$R"])])

        with self.assertRaises(WhereASTValidationError) as ctx:
            validate_where_ast(
                ast,
                mode="souffle",
                profile=BackendProfile(capabilities={"ruleref_policy": "require_resolved"}),
            )
        self.assertIn("RuleRefAtom is not allowed in this mode", str(ctx.exception))

    def test_default_profile_keeps_souffle_behavior(self) -> None:
        ast = parse_where_ir_to_ast([("ruleref", "q_rank", "1.0.0", ["$E", "$R"])])
        validate_where_ast(ast, mode="souffle")

    def test_python_mode_ignores_ruleref_policy(self) -> None:
        ast = parse_where_ir_to_ast([("ruleref", "q_rank", "1.0.0", ["$E", "$R"])])
        validate_where_ast(
            ast,
            mode="python",
            profile=BackendProfile(capabilities={"ruleref_policy": "forbid"}),
        )


if __name__ == "__main__":
    unittest.main()
