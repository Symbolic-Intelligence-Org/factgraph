"""W2a retract runtime API extension tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from factpy.agent.tools._runtime_api import HttpRuntimeAPI, LocalRuntimeAPI


class AgentW2ARuntimeAPITests(unittest.TestCase):
    def test_local_runtime_api_retract_fact_dispatches_to_runtime(self) -> None:
        api = LocalRuntimeAPI()
        payload = {"asrt_id": "asrt_1", "meta": {"note": "duplicate"}}
        expected = {"ok": True, "write": {"kind": "retract", "assertion_id": "rev_1"}}
        with patch(
            "service.runtime_v1.retract_runtime_fact",
            return_value=expected,
        ) as mocked:
            resp = api.retract_fact("rt_123", payload)
        self.assertEqual(resp, expected)
        mocked.assert_called_once_with("rt_123", payload)

    def test_http_runtime_api_retract_fact_uses_expected_route(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime")
        payload = {"asrt_id": "asrt_1", "meta": {"note": "duplicate"}}
        with patch.object(api, "_post_json", return_value={"ok": True}) as mocked:
            api.retract_fact("rt_123", payload)
        mocked.assert_called_once_with("/sessions/rt_123/writes/retract", payload)


if __name__ == "__main__":
    unittest.main()
