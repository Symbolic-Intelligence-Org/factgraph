from __future__ import annotations

import unittest

from factpy_kernel.core.rules.where_ast import WhereASTError
from factpy_kernel.core.rules.where_ast_validate import WhereASTValidationError
from factpy_kernel.tests.where_golden_v1 import (
    assert_error_category,
    iter_cases,
    run_ast_validate_case,
)


class WhereGoldenASTValidateV1Tests(unittest.TestCase):
    def test_ast_validator_golden_cases(self) -> None:
        for case in iter_cases(target="ast"):
            with self.subTest(case_id=case.case_id):
                if case.expect == "ok":
                    run_ast_validate_case(case)
                    continue
                with self.assertRaises((WhereASTError, WhereASTValidationError)) as ctx:
                    run_ast_validate_case(case)
                if case.error_kind:
                    assert_error_category(ctx.exception, case.error_kind)


if __name__ == "__main__":
    unittest.main()
