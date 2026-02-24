from __future__ import annotations

import unittest

from factpy_kernel.tests.rule_golden_v1 import (
    RuleASTError,
    RuleASTValidationError,
    assert_error_category,
    iter_cases,
    run_rule_ast_validate_case,
)


class RuleGoldenASTValidateV1Tests(unittest.TestCase):
    def test_rule_ast_validator_golden_cases(self) -> None:
        for case in iter_cases():
            with self.subTest(case_id=case.case_id):
                if case.expect == "ok":
                    run_rule_ast_validate_case(case)
                    continue
                with self.assertRaises((RuleASTError, RuleASTValidationError)) as ctx:
                    run_rule_ast_validate_case(case)
                if case.error_kind:
                    assert_error_category(ctx.exception, case.error_kind)


if __name__ == "__main__":
    unittest.main()
