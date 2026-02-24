from __future__ import annotations

import unittest

from factpy_kernel.core.rules.backend_profile import BackendProfile
from factpy_kernel.core.rules.where_ast import parse_where_ir_to_ast
from factpy_kernel.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast


_WHERE_WITH_NOT_AND = [
    ("pred", "person:country", ["$P", "$C"]),
    ("not", [("pred", "person:block_reason", ["$P", "ban"])]),
]

_WHERE_WITH_NOT_OR = [
    ("pred", "person:country", ["$P", "$C"]),
    (
        "not",
        [
            [("pred", "person:block_reason", ["$P", "ban"])],
            [("pred", "person:block_reason", ["$P", "warning"])],
        ],
    ),
]


class WhereNotBodyProfilePolicyV1Tests(unittest.TestCase):
    def test_souffle_profile_forbid_rejects_not_atom(self) -> None:
        ast = parse_where_ir_to_ast(_WHERE_WITH_NOT_AND)
        with self.assertRaises(WhereASTValidationError) as ctx:
            validate_where_ast(
                ast,
                mode="souffle",
                profile=BackendProfile(capabilities={"not_body_policy": "forbid"}),
            )
        self.assertIn("not_body_policy=forbid", str(ctx.exception))

    def test_souffle_profile_forbid_or_rejects_not_or_body(self) -> None:
        ast = parse_where_ir_to_ast(_WHERE_WITH_NOT_OR)
        with self.assertRaises(WhereASTValidationError) as ctx:
            validate_where_ast(
                ast,
                mode="souffle",
                profile=BackendProfile(capabilities={"not_body_policy": "forbid_or"}),
            )
        self.assertIn("not_body_policy=forbid_or", str(ctx.exception))

    def test_souffle_profile_forbid_or_still_allows_not_and_body(self) -> None:
        ast = parse_where_ir_to_ast(_WHERE_WITH_NOT_AND)
        validate_where_ast(
            ast,
            mode="souffle",
            profile=BackendProfile(capabilities={"not_body_policy": "forbid_or"}),
        )

    def test_souffle_default_profile_keeps_not_or_behavior(self) -> None:
        ast = parse_where_ir_to_ast(_WHERE_WITH_NOT_OR)
        validate_where_ast(ast, mode="souffle")

    def test_python_mode_ignores_not_body_policy(self) -> None:
        ast = parse_where_ir_to_ast(_WHERE_WITH_NOT_OR)
        validate_where_ast(
            ast,
            mode="python",
            profile=BackendProfile(capabilities={"not_body_policy": "forbid_or"}),
        )


if __name__ == "__main__":
    unittest.main()
