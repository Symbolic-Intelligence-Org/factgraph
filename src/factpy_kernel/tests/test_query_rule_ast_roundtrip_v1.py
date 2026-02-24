from __future__ import annotations

import unittest

from factpy_kernel.core.rules.rule_ast import (
    lower_query_rule_ast_to_ir,
    parse_query_rule_ir_to_ast,
)


class QueryRuleASTRoundTripV1Tests(unittest.TestCase):
    def _assert_roundtrip(self, rule_ir: dict[str, object]) -> None:
        ast = parse_query_rule_ir_to_ast(rule_ir)
        lowered = lower_query_rule_ast_to_ir(ast)
        self.assertEqual(lowered, rule_ir)

    def test_roundtrip_query_rule_payload_shape(self) -> None:
        self._assert_roundtrip(
            {
                "rule_id": "rules.country_rows",
                "version": "v1",
                "select_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "expose": True,
                "meta": {"owner": "tests"},
            }
        )

    def test_roundtrip_query_rule_or_where(self) -> None:
        self._assert_roundtrip(
            {
                "rule_id": "rules.country_or",
                "version": "v1",
                "select_vars": ["$E"],
                "where": [
                    [("pred", "person:country", ["$E", "de"])],
                    [("pred", "person:country", ["$E", "fr"])],
                ],
            }
        )


if __name__ == "__main__":
    unittest.main()
