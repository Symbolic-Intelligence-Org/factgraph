from __future__ import annotations

import unittest

from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.tests.where_golden_v1 import (
    assert_error_category,
    iter_cases,
    run_compile_case,
)


class WhereGoldenCompileGateV1Tests(unittest.TestCase):
    def test_compile_golden_cases_gate_on(self) -> None:
        for case in iter_cases(target="compile"):
            with self.subTest(case_id=case.case_id, gate="on"):
                if case.expect == "ok":
                    run_compile_case(case, gate_enabled=True)
                    continue
                with self.assertRaises(WhereValidationError) as ctx:
                    run_compile_case(case, gate_enabled=True)
                self.assertEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")
                if case.error_kind:
                    assert_error_category(ctx.exception, case.error_kind)

    def test_compile_golden_cases_gate_off(self) -> None:
        for case in iter_cases(target="compile"):
            with self.subTest(case_id=case.case_id, gate="off"):
                if case.expect == "ok":
                    run_compile_case(case, gate_enabled=False)
                    continue
                with self.assertRaises(WhereValidationError) as ctx:
                    run_compile_case(case, gate_enabled=False)
                self.assertNotEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")
                if case.error_kind:
                    assert_error_category(ctx.exception, case.error_kind)


if __name__ == "__main__":
    unittest.main()
