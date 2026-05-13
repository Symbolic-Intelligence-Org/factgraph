"""Tests for runtime session schema readback."""

from __future__ import annotations

import unittest

from factpy.service.runtime_v1 import (
    close_runtime_session,
    get_runtime_session,
    get_runtime_session_schema,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
)
from tests._test_helpers import _schema_ir


class RuntimeSessionSchemaReadbackTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.schema_ir = _schema_ir()
        open_resp = open_runtime_session({"schema_ir": self.schema_ir})
        self.assertTrue(open_resp["ok"], open_resp)
        self.session_id = open_resp["session"]["session_id"]

    def tearDown(self) -> None:
        close_runtime_session(self.session_id)
        reset_runtime_sessions_for_tests()

    def test_get_runtime_session_schema_returns_digest_and_schema_ir(self) -> None:
        resp = get_runtime_session_schema(self.session_id)
        self.assertTrue(resp["ok"], resp)
        result = resp["result"]
        self.assertIn("schema_digest", result)
        self.assertEqual(result["schema_ir"], self.schema_ir)

    def test_schema_ir_predicates_include_pred_id_and_arg_specs(self) -> None:
        resp = get_runtime_session_schema(self.session_id)
        self.assertTrue(resp["ok"], resp)
        predicates = resp["result"]["schema_ir"].get("predicates", [])
        self.assertTrue(predicates)
        first = predicates[0]
        self.assertIn("pred_id", first)
        self.assertIn("arg_specs", first)

    def test_unknown_session_returns_runtime_session_not_found(self) -> None:
        resp = get_runtime_session_schema("rt_missing")
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["errors"][0]["kind"], "runtime_session_not_found")

    def test_get_runtime_session_shape_is_unchanged(self) -> None:
        resp = get_runtime_session(self.session_id)
        self.assertTrue(resp["ok"], resp)
        session = resp["session"]
        self.assertIn("schema_digest", session)
        self.assertNotIn("schema_ir", session)


if __name__ == "__main__":
    unittest.main()
