from __future__ import annotations

import unittest

from factpy_kernel.core.rules.backend_profile import PROFILE_DEFAULT
from factpy_kernel.core.rules.rule_ast import parse_query_rule_ir_to_ast
from factpy_kernel.core.rules.rule_ast_validate import RuleASTValidationError, validate_query_rule_ast
from factpy_kernel.tests.test_query_rule_validator_modes_v1 import (
    _CASES,
    _classify_rule_ast_validation_error,
)


class QueryRuleProfileEquivalenceV1Tests(unittest.TestCase):
    def test_default_profile_is_equivalent_to_no_profile_in_both_modes(self) -> None:
        for case_id, rule_ir, _expect_ok in _CASES:
            ast = parse_query_rule_ir_to_ast(rule_ir)
            for mode in ("python", "souffle"):
                with self.subTest(case_id=case_id, mode=mode):
                    baseline = _run_query_validate(ast, mode=mode, use_profile=False)
                    profiled = _run_query_validate(ast, mode=mode, use_profile=True)
                    self.assertEqual(baseline, profiled)


def _run_query_validate(ast: object, *, mode: str, use_profile: bool) -> tuple[str, str | None]:
    try:
        kwargs = {"mode": mode}
        if use_profile:
            kwargs["profile"] = PROFILE_DEFAULT
        validate_query_rule_ast(ast, **kwargs)  # type: ignore[arg-type]
        return ("ok", None)
    except RuleASTValidationError as exc:
        return ("error", _classify_rule_ast_validation_error(exc))


if __name__ == "__main__":
    unittest.main()
