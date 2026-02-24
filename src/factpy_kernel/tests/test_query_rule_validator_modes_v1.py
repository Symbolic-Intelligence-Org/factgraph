from __future__ import annotations

import unittest

from factpy_kernel.core.rules.rule_ast import parse_query_rule_ir_to_ast
from factpy_kernel.core.rules.rule_ast_validate import RuleASTValidationError, validate_query_rule_ast


class QueryRuleValidatorModesV1Tests(unittest.TestCase):
    def test_python_and_souffle_modes_are_equivalent_for_query_rule_validator(self) -> None:
        for case_id, rule_ir, expect_ok in _CASES:
            with self.subTest(case_id=case_id):
                ast = parse_query_rule_ir_to_ast(rule_ir)
                py = _run_validate(ast, mode="python")
                sf = _run_validate(ast, mode="souffle")
                self.assertEqual(py, sf)
                self.assertEqual(py[0], "ok" if expect_ok else "error")


def _run_validate(ast: object, *, mode: str) -> tuple[str, str | None]:
    try:
        validate_query_rule_ast(ast, mode=mode)  # type: ignore[arg-type]
        return ("ok", None)
    except RuleASTValidationError as exc:
        return ("error", _classify_rule_ast_validation_error(exc))


def _classify_rule_ast_validation_error(exc: RuleASTValidationError) -> str:
    path = str(getattr(exc, "path", "") or "")
    text = str(exc).lower()
    if path.startswith("$.query_rule.select_vars"):
        return "select_vars_shape"
    if path.startswith("$.query_rule.where") or text.startswith("where validation failed:"):
        return "where_shape"
    if path.startswith("$.query_rule"):
        return "shape"
    return "unknown"


_CASES: tuple[tuple[str, dict[str, object], bool], ...] = (
    (
        "ok-eq-bind-select",
        {
            "rule_id": "rules.eq_binds",
            "version": "v1",
            "select_vars": ["$Y"],
            "where": [("pred", "x:v", ["$E", "$X"]), ("eq", "$Y", "$X")],
        },
        True,
    ),
    (
        "ok-builtin-bind-select",
        {
            "rule_id": "rules.addc_binds",
            "version": "v1",
            "select_vars": ["$Y"],
            "where": [("pred", "x:v", ["$E", "$X"]), ("addc", "$Y", "$X", 1)],
        },
        True,
    ),
    (
        "ok-or-of-and",
        {
            "rule_id": "rules.country_or",
            "version": "v1",
            "select_vars": ["$E"],
            "where": [
                [("pred", "person:country", ["$E", "de"])],
                [("pred", "person:country", ["$E", "fr"])],
            ],
        },
        True,
    ),
    (
        "ok-not-local-vars",
        {
            "rule_id": "rules.country_without_ban",
            "version": "v1",
            "select_vars": ["$P", "$C"],
            "where": [
                ("pred", "person:country", ["$P", "$C"]),
                ("not", [("pred", "person:block_reason", ["$P", "$R"]), ("eq", "$R", "ban")]),
            ],
        },
        True,
    ),
    (
        "ok-ruleref-query-contract",
        {
            "rule_id": "rules.rank_rows",
            "version": "v1",
            "select_vars": ["$E", "$R"],
            "where": [("ruleref", "q_rank", "1.0.0", ["$E", "$R"])],
        },
        True,
    ),
    (
        "err-where-dataflow-eq",
        {
            "rule_id": "rules.bad_eq",
            "version": "v1",
            "select_vars": ["$X"],
            "where": [("eq", "$X", "$Y")],
        },
        False,
    ),
    (
        "err-where-not-correlation",
        {
            "rule_id": "rules.bad_not",
            "version": "v1",
            "select_vars": ["$P", "$C"],
            "where": [
                ("pred", "person:country", ["$P", "$C"]),
                ("not", [("pred", "x:local", ["$X"]), ("eq", "$X", 1)]),
            ],
        },
        False,
    ),
    (
        "err-select-vars-or-branch-missing",
        {
            "rule_id": "rules.bad_select_or",
            "version": "v1",
            "select_vars": ["$C"],
            "where": [
                [("pred", "person:country", ["$E", "$C"])],
                [("pred", "person:country", ["$E", "de"])],
            ],
        },
        False,
    ),
    (
        "err-select-vars-not-local-only",
        {
            "rule_id": "rules.bad_select_not_local",
            "version": "v1",
            "select_vars": ["$R"],
            "where": [
                ("pred", "person:country", ["$P", "$C"]),
                ("not", [("pred", "person:block_reason", ["$P", "$R"])]),
            ],
        },
        False,
    ),
)


if __name__ == "__main__":
    unittest.main()
