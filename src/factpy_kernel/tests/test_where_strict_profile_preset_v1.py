from __future__ import annotations

import unittest

from factpy_kernel.core.rules.backend_profile import PROFILE_DEFAULT, PROFILE_SOUFFLE_STRICT
from factpy_kernel.core.rules.where_ast import parse_where_ir_to_ast
from factpy_kernel.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast


class WhereStrictProfilePresetV1Tests(unittest.TestCase):
    def test_strict_profile_rejects_ruleref_in_souffle_mode(self) -> None:
        ast = parse_where_ir_to_ast([("ruleref", "q_rank", "1.0.0", ["$E", "$R"])])
        with self.assertRaises(WhereASTValidationError):
            validate_where_ast(ast, mode="souffle", profile=PROFILE_SOUFFLE_STRICT)

    def test_default_profile_keeps_ruleref_behavior(self) -> None:
        ast = parse_where_ir_to_ast([("ruleref", "q_rank", "1.0.0", ["$E", "$R"])])
        validate_where_ast(ast, mode="souffle", profile=PROFILE_DEFAULT)

    def test_strict_profile_rejects_not_or_body_in_souffle_mode(self) -> None:
        ast = parse_where_ir_to_ast(
            [
                ("pred", "person:country", ["$P", "$C"]),
                (
                    "not",
                    [
                        [("pred", "person:block_reason", ["$P", "ban"])],
                        [("pred", "person:block_reason", ["$P", "warning"])],
                    ],
                ),
            ]
        )
        with self.assertRaises(WhereASTValidationError):
            validate_where_ast(ast, mode="souffle", profile=PROFILE_SOUFFLE_STRICT)

    def test_default_profile_keeps_not_or_behavior(self) -> None:
        ast = parse_where_ir_to_ast(
            [
                ("pred", "person:country", ["$P", "$C"]),
                (
                    "not",
                    [
                        [("pred", "person:block_reason", ["$P", "ban"])],
                        [("pred", "person:block_reason", ["$P", "warning"])],
                    ],
                ),
            ]
        )
        validate_where_ast(ast, mode="souffle")


if __name__ == "__main__":
    unittest.main()
