from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from factpy_kernel.core.rules.where_eval import WhereValidationError, evaluate_where


class WhereEvalASTGateV1Tests(unittest.TestCase):
    def test_gate_enabled_adapts_ast_validator_error_with_compat_attrs(self) -> None:
        where = [
            ("pred", "x:v", ["$e", "$x"]),
            ("add", "$z", "$missing", 1),
        ]
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "1"}):
            with self.assertRaises(WhereValidationError) as ctx:
                evaluate_where({"x:v": [("e1", 3)]}, where)
        err = ctx.exception
        self.assertIsInstance(err, WhereValidationError)
        self.assertEqual(getattr(err, "kind", None), "where_ast_validate")
        self.assertTrue(hasattr(err, "path"))
        self.assertTrue(hasattr(err, "details"))
        self.assertIsInstance(err.details, dict)
        self.assertIn("message", err.details)
        self.assertIn("ast_error_code", err.details)
        self.assertEqual(getattr(err, "path", None), "$.where[1]")

    def test_gate_enabled_rejects_not_without_outer_correlation(self) -> None:
        where = [("not", [("pred", "x:local", ["$x"]), ("eq", "$x", 1)])]
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "1"}):
            with self.assertRaises(WhereValidationError) as ctx:
                evaluate_where({"x:local": [("e1",)]}, where)
        self.assertEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")

    def test_gate_enabled_routes_structural_error_to_ast_gate(self) -> None:
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "1"}):
            with self.assertRaises(WhereValidationError) as ctx:
                evaluate_where({}, [[]])
        self.assertEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")
        self.assertIn("message", getattr(ctx.exception, "details", {}))

    def test_gate_enabled_routes_shape_error_to_ast_gate(self) -> None:
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "1"}):
            with self.assertRaises(WhereValidationError) as ctx:
                evaluate_where({}, [("pred",)])
        self.assertEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")
        self.assertEqual(getattr(ctx.exception, "path", None), "$.where[0]")

    def test_gate_enabled_rejects_ruleref_for_python_runtime(self) -> None:
        where = [("ruleref", "q_x", "1.0.0", ["$e"])]
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "1"}):
            with self.assertRaises(WhereValidationError) as ctx:
                evaluate_where({}, where)
        self.assertEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")
        self.assertEqual(getattr(ctx.exception, "path", None), "$.where[0]")

    def test_gate_disabled_falls_back_to_legacy_error_path(self) -> None:
        where = [[]]
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "0"}):
            with self.assertRaises(WhereValidationError) as ctx:
                evaluate_where({}, where)
        self.assertNotEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")

    def test_gate_disabled_shape_error_uses_legacy_guard(self) -> None:
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "0"}):
            with self.assertRaises(WhereValidationError) as ctx:
                evaluate_where({}, [("pred",)])
        self.assertNotEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")

    def test_gate_disabled_accepts_false_variants(self) -> None:
        where = [[]]
        for raw in ("false", "False", "off", "OFF"):
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": raw}):
                    with self.assertRaises(WhereValidationError) as ctx:
                        evaluate_where({}, where)
                self.assertNotEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")


if __name__ == "__main__":
    unittest.main()
