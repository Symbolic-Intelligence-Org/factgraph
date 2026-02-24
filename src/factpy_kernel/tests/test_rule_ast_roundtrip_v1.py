from __future__ import annotations

import unittest

from factpy_kernel.core.rules.rule_ast import (
    lower_program_ast_to_ir,
    lower_rule_ast_to_ir,
    parse_program_ir_to_ast,
    parse_rule_ir_to_ast,
)


class RuleASTRoundTripV1Tests(unittest.TestCase):
    def _assert_rule_roundtrip(self, rule_ir: dict[str, object]) -> None:
        ast = parse_rule_ir_to_ast(rule_ir)
        lowered = lower_rule_ast_to_ir(ast)
        self.assertEqual(lowered, rule_ir)

    def test_roundtrip_rule_with_or_where_and_meta(self) -> None:
        self._assert_rule_roundtrip(
            {
                "rule_id": "q_country_or",
                "version": "v1",
                "head": ("pred", "query:country_or", ["$E"]),
                "where": [
                    [("pred", "person:country", ["$E", "de"])],
                    [("pred", "person:country", ["$E", "fr"]), ("eq", "$tag", "ok")],
                ],
                "meta": {"owner": "tests", "priority": 1},
            }
        )

    def test_roundtrip_rule_preserves_nested_not_where(self) -> None:
        self._assert_rule_roundtrip(
            {
                "rule_id": "q_country_safe",
                "version": "1.0.0",
                "head": ("pred", "query:country_safe", ["$P", "$C"]),
                "where": [
                    ("pred", "person:country", ["$P", "$C"]),
                    ("not", [("pred", "person:block_reason", ["$P", "$R"]), ("eq", "$R", "ban")]),
                ],
            }
        )

    def test_roundtrip_program_with_multiple_rules(self) -> None:
        program_ir = {
            "rules": [
                {
                    "rule_id": "q_country_rows",
                    "version": "v1",
                    "head": ("pred", "query:country_rows", ["$E", "$C"]),
                    "where": [("pred", "person:country", ["$E", "$C"])],
                },
                {
                    "rule_id": "q_country_de",
                    "version": "v1",
                    "head": ("pred", "query:country_de", ["$E"]),
                    "where": [("pred", "person:country", ["$E", "de"])],
                },
            ],
            "meta": {"program_id": "demo"},
        }
        ast = parse_program_ir_to_ast(program_ir)
        lowered = lower_program_ast_to_ir(ast)
        self.assertEqual(lowered, program_ir)


if __name__ == "__main__":
    unittest.main()
