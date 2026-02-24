from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from factpy_kernel.adapters.souffle.where_compile import compile_where_to_query_dl
from factpy_kernel.core.rules.where_eval import WhereValidationError


class WhereCompileASTGateV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {"predicates": []}

    def test_gate_enabled_adapts_ast_validator_error(self) -> None:
        where = [("not", [("pred", "x:local", ["$x"]), ("eq", "$x", 1)])]
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "1"}):
            with self.assertRaises(WhereValidationError) as ctx:
                compile_where_to_query_dl(
                    schema_ir=self.schema_ir,
                    where=where,
                    query_rel="q_bad",
                )
        err = ctx.exception
        self.assertEqual(getattr(err, "kind", None), "where_ast_validate")
        self.assertTrue(hasattr(err, "details"))
        self.assertIn("message", err.details)

    def test_gate_enabled_routes_structural_error_to_ast_gate(self) -> None:
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "1"}):
            with self.assertRaises(WhereValidationError) as ctx:
                compile_where_to_query_dl(
                    schema_ir=self.schema_ir,
                    where=[[]],
                    query_rel="q_bad",
                )
        self.assertEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")
        self.assertIn("message", getattr(ctx.exception, "details", {}))

    def test_gate_enabled_routes_shape_error_to_ast_gate(self) -> None:
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "1"}):
            with self.assertRaises(WhereValidationError) as ctx:
                compile_where_to_query_dl(
                    schema_ir=self.schema_ir,
                    where=[("pred",)],
                    query_rel="q_bad",
                )
        self.assertEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")

    def test_gate_disabled_uses_legacy_compile_validation(self) -> None:
        where = [[]]
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "OFF"}):
            with self.assertRaises(WhereValidationError) as ctx:
                compile_where_to_query_dl(
                    schema_ir=self.schema_ir,
                    where=where,
                    query_rel="q_bad",
                )
        self.assertNotEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")

    def test_gate_disabled_shape_error_uses_legacy_compile_guard(self) -> None:
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "0"}):
            with self.assertRaises(WhereValidationError) as ctx:
                compile_where_to_query_dl(
                    schema_ir=self.schema_ir,
                    where=[("pred",)],
                    query_rel="q_bad",
                )
        self.assertNotEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")

    def test_dataflow_error_routes_to_ast_gate_when_enabled(self) -> None:
        where = [("eq", "$x", "$y")]
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "1"}):
            with self.assertRaises(WhereValidationError) as ctx:
                compile_where_to_query_dl(
                    schema_ir=self.schema_ir,
                    where=where,
                    query_rel="q_bad",
                )
        self.assertEqual(getattr(ctx.exception, "kind", None), "where_ast_validate")

        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "0"}):
            with self.assertRaises(WhereValidationError) as ctx2:
                compile_where_to_query_dl(
                    schema_ir=self.schema_ir,
                    where=where,
                    query_rel="q_bad",
                )
        self.assertNotEqual(getattr(ctx2.exception, "kind", None), "where_ast_validate")


if __name__ == "__main__":
    unittest.main()
