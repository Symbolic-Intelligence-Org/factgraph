"""Layer 3A runtime API extension tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.tools._runtime_api import HttpRuntimeAPI, LocalRuntimeAPI


class AgentLayer3ARuntimeAPITests(unittest.TestCase):
    def test_local_runtime_api_write_fact_dispatches_to_runtime(self) -> None:
        api = LocalRuntimeAPI()
        payload = {"pred_id": "user:name", "e_ref": "idref_v1:User:x", "rest_terms": [["string", "Alice"]]}
        expected = {"ok": True, "write": {"kind": "set", "assertion_id": "asrt_1"}}
        with patch(
            "service.runtime_v1.write_runtime_fact",
            return_value=expected,
        ) as mocked:
            resp = api.write_fact("rt_123", payload, kind="set")
        self.assertEqual(resp, expected)
        mocked.assert_called_once_with("rt_123", payload, kind="set")

    def test_http_runtime_api_write_fact_uses_expected_route(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime")
        payload = {"pred_id": "user:name", "e_ref": "idref_v1:User:x", "rest_terms": [["string", "Alice"]]}
        with patch.object(api, "_post_json", return_value={"ok": True}) as mocked:
            api.write_fact("rt_123", payload, kind="add")
        mocked.assert_called_once_with("/sessions/rt_123/writes/add", payload)

if __name__ == "__main__":
    unittest.main()
