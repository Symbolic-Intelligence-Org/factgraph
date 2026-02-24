from __future__ import annotations

import unittest

from factpy_kernel.core.rules.backend_profile import PROFILE_DEFAULT
from factpy_kernel.core.rules.where_ast import WhereASTError, parse_where_ir_to_ast
from factpy_kernel.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast
from factpy_kernel.tests.where_golden_v1 import classify_error_category, iter_cases


class WhereProfileEquivalenceV1Tests(unittest.TestCase):
    def test_default_profile_is_equivalent_to_no_profile(self) -> None:
        for case in iter_cases(target="ast"):
            modes = [case.mode] if case.mode is not None else ["python", "souffle"]
            for mode in modes:
                with self.subTest(case_id=case.case_id, mode=mode):
                    baseline = _run_where_validate(case.where_ir, mode=mode, use_profile=False)
                    profiled = _run_where_validate(case.where_ir, mode=mode, use_profile=True)
                    self.assertEqual(baseline, profiled)


def _run_where_validate(where_ir: object, *, mode: str, use_profile: bool) -> tuple[str, str | None]:
    try:
        ast = parse_where_ir_to_ast(where_ir)
        kwargs = {"mode": mode}
        if use_profile:
            kwargs["profile"] = PROFILE_DEFAULT
        validate_where_ast(ast, **kwargs)
        return ("ok", None)
    except (WhereASTError, WhereASTValidationError) as exc:
        return ("error", classify_error_category(exc))


if __name__ == "__main__":
    unittest.main()
