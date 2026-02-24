from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from factpy_kernel.authoring import AuthoringRuleCompileError, compile_authoring_rule_v1
from factpy_kernel.core.rules.backend_profile import PROFILE_DEFAULT, PROFILE_SOUFFLE_STRICT


class AuthoringRuleCompileStrictV1Tests(unittest.TestCase):
    def test_default_compile_keeps_ruleref_behavior(self) -> None:
        with patch.dict(os.environ, {"FACTPY_RULE_AST_VALIDATE": "1"}):
            payload = compile_authoring_rule_v1(_authoring_rule_with_ruleref())
        self.assertEqual(payload["rule_id"], "rules.rank_rows")
        self.assertEqual(payload["where"], [("ruleref", "q_rank", "1.0.0", ["$E", "$R"])])

    def test_strict_true_rejects_ruleref_via_rule_ast_gate(self) -> None:
        with patch.dict(os.environ, {"FACTPY_RULE_AST_VALIDATE": "1"}):
            with self.assertRaises(AuthoringRuleCompileError) as ctx:
                compile_authoring_rule_v1(_authoring_rule_with_ruleref(), strict=True)
        err = ctx.exception
        self.assertEqual(getattr(err, "kind", None), "rule_ast_validate")
        self.assertTrue((err.path or "").startswith("$.query_rule.where"))
        self.assertIn("message", getattr(err, "details", {}))

    def test_profile_argument_overrides_strict_flag(self) -> None:
        with patch.dict(os.environ, {"FACTPY_RULE_AST_VALIDATE": "1"}):
            payload = compile_authoring_rule_v1(
                _authoring_rule_with_ruleref(),
                strict=True,
                profile=PROFILE_DEFAULT,
            )
        self.assertEqual(payload["rule_id"], "rules.rank_rows")

    def test_explicit_strict_profile_can_enable_strict_without_flag(self) -> None:
        with patch.dict(os.environ, {"FACTPY_RULE_AST_VALIDATE": "1"}):
            with self.assertRaises(AuthoringRuleCompileError):
                compile_authoring_rule_v1(
                    _authoring_rule_with_not_or(),
                    strict=False,
                    profile=PROFILE_SOUFFLE_STRICT,
                )


def _authoring_rule_with_ruleref() -> dict[str, object]:
    return {
        "rule_id": "rules.rank_rows",
        "version": "v1",
        "select": ["E", "R"],
        "where": [("ruleref", "q_rank", "1.0.0", ["$E", "$R"])],
    }


def _authoring_rule_with_not_or() -> dict[str, object]:
    return {
        "rule_id": "rules.country_without_ban_or_warning",
        "version": "v1",
        "select": ["P", "C"],
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


if __name__ == "__main__":
    unittest.main()
