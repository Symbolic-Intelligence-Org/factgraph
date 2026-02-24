from __future__ import annotations

import unittest

from factpy_kernel.core.rules.rule_ast import parse_query_rule_ir_to_ast
from factpy_kernel.core.rules.rule_ast_validate import RuleASTValidationError, validate_query_rule_ast


class QueryRuleSelectVarsAvailableV1Tests(unittest.TestCase):
    def _validate_ok(self, rule_ir: dict[str, object]) -> None:
        ast = parse_query_rule_ir_to_ast(rule_ir)
        validate_query_rule_ast(ast, mode="python")

    def _assert_select_vars_rejected(self, rule_ir: dict[str, object]) -> RuleASTValidationError:
        ast = parse_query_rule_ir_to_ast(rule_ir)
        with self.assertRaises(RuleASTValidationError) as ctx:
            validate_query_rule_ast(ast, mode="python")
        err = ctx.exception
        self.assertEqual(getattr(err, "path", None), "$.query_rule.select_vars")
        self.assertIn("guaranteed bound", str(err))
        return err

    def test_and_eq_can_conditionally_bind_select_var(self) -> None:
        self._validate_ok(
            {
                "rule_id": "rules.eq_binds_select",
                "version": "v1",
                "select_vars": ["$Y"],
                "where": [("pred", "x:v", ["$E", "$X"]), ("eq", "$Y", "$X")],
            }
        )

    def test_arith_builtin_output_can_bind_select_var(self) -> None:
        self._validate_ok(
            {
                "rule_id": "rules.builtin_binds_select",
                "version": "v1",
                "select_vars": ["$Y"],
                "where": [("pred", "x:v", ["$E", "$X"]), ("addc", "$Y", "$X", 1)],
            }
        )

    def test_or_branches_must_all_bind_select_vars(self) -> None:
        self._assert_select_vars_rejected(
            {
                "rule_id": "rules.or_missing_select",
                "version": "v1",
                "select_vars": ["$C"],
                "where": [
                    [("pred", "person:country", ["$E", "$C"])],
                    [("pred", "person:country", ["$E", "de"])],
                ],
            }
        )

    def test_select_var_only_in_not_local_is_not_considered_bound(self) -> None:
        self._assert_select_vars_rejected(
            {
                "rule_id": "rules.not_local_not_bound",
                "version": "v1",
                "select_vars": ["$R"],
                "where": [
                    ("pred", "person:country", ["$P", "$C"]),
                    ("not", [("pred", "person:block_reason", ["$P", "$R"])]),
                ],
            }
        )

    def test_ruleref_terms_are_treated_as_binders_for_query_contract(self) -> None:
        self._validate_ok(
            {
                "rule_id": "rules.ruleref_binds_select",
                "version": "v1",
                "select_vars": ["$E", "$R"],
                # Query-level select-vars contract treats ruleref terms as binders.
                # (where_ast_validate still models ruleref dataflow conservatively.)
                "where": [("ruleref", "q_rank", "1.0.0", ["$E", "$R"])],
            }
        )

    def test_left_to_right_order_still_rejected_by_where_dataflow(self) -> None:
        ast = parse_query_rule_ir_to_ast(
            {
                "rule_id": "rules.order_bad",
                "version": "v1",
                "select_vars": ["$X"],
                "where": [("in", "$X", [1, 2]), ("pred", "x:v", ["$E", "$X"])],
            }
        )
        with self.assertRaises(RuleASTValidationError) as ctx:
            validate_query_rule_ast(ast, mode="python")
        self.assertTrue(
            (getattr(ctx.exception, "path", None) or "").startswith("$.query_rule.where")
        )
        self.assertIn("where validation failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
