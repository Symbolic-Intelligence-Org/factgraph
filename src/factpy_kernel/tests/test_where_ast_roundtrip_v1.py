from __future__ import annotations

import unittest

from factpy_kernel.core.rules.where_ast import lower_ast_to_where_ir, parse_where_ir_to_ast


class WhereASTRoundTripV1Tests(unittest.TestCase):
    def _assert_roundtrip(self, where_ir: list[object]) -> None:
        ast = parse_where_ir_to_ast(where_ir)
        lowered = lower_ast_to_where_ir(ast)
        self.assertEqual(lowered, where_ir)

    def test_roundtrip_and_body_with_ruleref_and_builtins(self) -> None:
        self._assert_roundtrip(
            [
                ("pred", "person:birth_year", ["$p", "$by"]),
                ("ruleref", "q_country", "1.0.0", ["$p", "$c"]),
                ("sub", "$age", 2026, "$by"),
                ("ge", "$age", 18),
                ("in", "$c", ["de", "fr"]),
            ]
        )

    def test_roundtrip_or_of_and_preserves_branch_structure(self) -> None:
        self._assert_roundtrip(
            [
                [("pred", "person:country", ["$p", "de"])],
                [("pred", "person:country", ["$p", "fr"]), ("eq", "$x", "ok")],
            ]
        )

    def test_roundtrip_not_body_or_of_and_preserves_nested_where_expr(self) -> None:
        self._assert_roundtrip(
            [
                ("pred", "person:country", ["$p", "$c"]),
                (
                    "not",
                    [
                        [("pred", "person:block", ["$p", "$r"]), ("eq", "$r", "ban")],
                        [("pred", "person:suspended", ["$p", True])],
                    ],
                ),
            ]
        )

    def test_roundtrip_ruleref_version_none(self) -> None:
        self._assert_roundtrip([("ruleref", "q_any", None, ["$p"])])


if __name__ == "__main__":
    unittest.main()
