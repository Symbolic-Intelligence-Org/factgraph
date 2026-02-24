from __future__ import annotations

import unittest

from factpy_kernel.core.rules.where_ast import (
    AndExpr,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    Origin,
    OrExpr,
    PredAtom,
    RuleRefAtom,
    Var,
    parse_where_ir_to_ast,
)
from factpy_kernel.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast


class WhereASTValidateV1Tests(unittest.TestCase):
    def test_valid_not_body_allows_local_vars_and_requires_outer_correlation(self) -> None:
        ast = parse_where_ir_to_ast(
            [
                ("pred", "person:country", ["$p", "$c"]),
                (
                    "not",
                    [
                        ("pred", "person:block_reason", ["$p", "$r"]),
                        ("eq", "$r", "ban"),
                    ],
                ),
            ]
        )
        validate_where_ast(ast, mode="python")

    def test_reject_not_body_without_outer_correlation(self) -> None:
        ast = parse_where_ir_to_ast(
            [
                (
                    "not",
                    [
                        ("pred", "x:local", ["$x"]),
                        ("eq", "$x", "v"),
                    ],
                )
            ]
        )
        with self.assertRaises(WhereASTValidationError) as ctx:
            validate_where_ast(ast, mode="python")
        self.assertIn("outer bound variable", str(ctx.exception))

    def test_reject_not_body_missing_required_var_in_branch(self) -> None:
        ast = parse_where_ir_to_ast(
            [
                ("pred", "person:country", ["$p", "$c"]),
                ("not", [("gt", "$age", 18)]),
            ]
        )
        with self.assertRaises(WhereASTValidationError):
            validate_where_ast(ast, mode="python")

    def test_builtin_output_binder_allows_following_compare(self) -> None:
        ast = parse_where_ir_to_ast(
            [
                ("pred", "x:v", ["$e", "$x"]),
                ("addc", "$y", "$x", 1),
                ("ge", "$y", 2),
            ]
        )
        validate_where_ast(ast, mode="souffle")

    def test_builtin_shape_error_uses_origin_path(self) -> None:
        bad = AndExpr(
            atoms=[
                BuiltinAtom(
                    op="mulc",
                    args=[Var("$z"), Var("$x"), Var("$k")],
                    origin=Origin(source="raw_ir", path="$.where[1]"),
                )
            ]
        )
        with self.assertRaises(WhereASTValidationError) as ctx:
            validate_where_ast(bad)
        self.assertEqual(ctx.exception.path, "$.where[1]")

    def test_rule_ref_is_shape_valid_but_not_used_for_binding_in_pr2(self) -> None:
        ast = AndExpr(
            atoms=[
                RuleRefAtom(rule_id="q_x", version="1.0.0", terms=[Var("$p"), Var("$x")]),
                CmpAtom(op="ge", lhs=Var("$x"), rhs=Const(1)),
            ]
        )
        with self.assertRaises(WhereASTValidationError):
            validate_where_ast(ast, mode="python")

    def test_not_body_rejects_ruleref_by_default_subset(self) -> None:
        ast = AndExpr(
            atoms=[
                PredAtom("p:exists", [Var("$p")]),
                NotAtom(body=AndExpr(atoms=[RuleRefAtom("q_x", "1.0.0", [Var("$p")])])),
            ]
        )
        with self.assertRaises(WhereASTValidationError):
            validate_where_ast(ast)

    def test_mode_capability_can_disable_builtin(self) -> None:
        ast = parse_where_ir_to_ast([("neg", "$y", "$x")])
        with self.assertRaises(WhereASTValidationError):
            validate_where_ast(ast, mode="souffle", capabilities={"builtin_allow": {"add"}})

    def test_or_in_not_uses_union_free_vars_without_branch_equality_requirement(self) -> None:
        ast = parse_where_ir_to_ast(
            [
                ("pred", "person:country", ["$p", "$c"]),
                (
                    "not",
                    [
                        [("pred", "person:block_reason", ["$p", "$r"]), ("eq", "$r", "ban")],
                        [("pred", "person:country", ["$p", "xx"])],
                    ],
                ),
            ]
        )
        validate_where_ast(ast)

    def test_or_branch_structure_non_empty(self) -> None:
        bad = OrExpr(branches=[])
        with self.assertRaises(WhereASTValidationError):
            validate_where_ast(bad)

    def test_in_atom_requires_bound_var(self) -> None:
        ast = parse_where_ir_to_ast([("in", "$x", [1, 2])])
        with self.assertRaises(WhereASTValidationError):
            validate_where_ast(ast)

    def test_eq_conditional_binder_respects_left_to_right_order(self) -> None:
        ast = parse_where_ir_to_ast([("eq", "$x", "$y"), ("pred", "x:v", ["$e", "$y"])])
        with self.assertRaises(WhereASTValidationError):
            validate_where_ast(ast)

    def test_eq_can_bind_from_constant(self) -> None:
        ast = parse_where_ir_to_ast([("eq", "$x", 1), ("ge", "$x", 1)])
        validate_where_ast(ast)


if __name__ == "__main__":
    unittest.main()
