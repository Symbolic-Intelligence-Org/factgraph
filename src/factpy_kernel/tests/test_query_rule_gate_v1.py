from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from factpy_kernel.authoring import AuthoringRuleCompileError, compile_authoring_rule_v1


class QueryRuleGateV1Tests(unittest.TestCase):
    def test_gate_enabled_routes_where_dataflow_error_to_rule_ast_gate(self) -> None:
        # Old authoring compile path accepts this shape; query-rule AST gate rejects the where dataflow.
        authoring_rule = {
            "rule_id": "rules.bad_where_flow",
            "version": "v1",
            "select": ["X"],
            "where": [("eq", "$X", "$Y")],
        }
        with patch.dict(os.environ, {"FACTPY_RULE_AST_VALIDATE": "1"}):
            with self.assertRaises(AuthoringRuleCompileError) as ctx:
                compile_authoring_rule_v1(authoring_rule)
        err = ctx.exception
        self.assertEqual(getattr(err, "kind", None), "rule_ast_validate")
        self.assertTrue(hasattr(err, "details"))
        self.assertIn("message", getattr(err, "details", {}))

    def test_gate_disabled_keeps_legacy_compile_behavior(self) -> None:
        authoring_rule = {
            "rule_id": "rules.bad_where_flow",
            "version": "v1",
            "select": ["X"],
            "where": [("eq", "$X", "$Y")],
        }
        with patch.dict(os.environ, {"FACTPY_RULE_AST_VALIDATE": "0"}):
            payload = compile_authoring_rule_v1(authoring_rule)
        self.assertEqual(payload["rule_id"], "rules.bad_where_flow")
        self.assertEqual(payload["select_vars"], ["$X"])
        self.assertEqual(payload["where"], [("eq", "$X", "$Y")])

    def test_valid_rule_passes_gate_on_and_off(self) -> None:
        authoring_rule = {
            "rule_id": "rules.country_rows",
            "version": "v1",
            "select": ["E", "C"],
            "where": [("pred", "person:country", ["$E", "$C"])],
            "public": True,
        }
        for gate in ("1", "0"):
            with self.subTest(gate=gate):
                with patch.dict(os.environ, {"FACTPY_RULE_AST_VALIDATE": gate}):
                    payload = compile_authoring_rule_v1(authoring_rule)
                self.assertEqual(payload["rule_id"], "rules.country_rows")
                self.assertEqual(payload["version"], "v1")
                self.assertEqual(payload["select_vars"], ["$E", "$C"])
                self.assertEqual(payload["where"], [("pred", "person:country", ["$E", "$C"])])
                self.assertTrue(payload["expose"])


if __name__ == "__main__":
    unittest.main()
