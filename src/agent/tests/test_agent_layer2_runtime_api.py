"""Layer 2 runtime API extension tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.tools._runtime_api import HttpRuntimeAPI, LocalRuntimeAPI


class AgentLayer2RuntimeAPITests(unittest.TestCase):
    def test_local_runtime_api_evaluate_derivation_dispatches_to_runtime(self) -> None:
        api = LocalRuntimeAPI()
        payload = {"derivation": {"derivation_id": "drv.x"}}
        expected = {"ok": True, "evaluation": {"candidates": []}}
        with patch(
            "service.runtime_v1.evaluate_runtime_derivation",
            return_value=expected,
        ) as mocked:
            resp = api.evaluate_derivation("rt_123", payload)
        self.assertEqual(resp, expected)
        mocked.assert_called_once_with("rt_123", payload)

    def test_local_runtime_api_accept_derivation_dispatches_to_runtime(self) -> None:
        api = LocalRuntimeAPI()
        payload = {"candidate": {"candidate_id": "cand_1"}}
        expected = {"ok": True, "accept": {"accepted": []}}
        with patch(
            "service.runtime_v1.accept_runtime_derivation",
            return_value=expected,
        ) as mocked:
            resp = api.accept_derivation("rt_123", payload)
        self.assertEqual(resp, expected)
        mocked.assert_called_once_with("rt_123", payload)

    def test_http_runtime_api_evaluate_derivation_uses_expected_route(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime")
        payload = {"derivation": {"derivation_id": "drv.x"}}
        with patch.object(api, "_post_json", return_value={"ok": True}) as mocked:
            api.evaluate_derivation("rt_123", payload)
        mocked.assert_called_once_with("/sessions/rt_123/derivations/evaluate", payload)

    def test_http_runtime_api_accept_derivation_uses_expected_route(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime")
        payload = {"candidate": {"candidate_id": "cand_1"}}
        with patch.object(api, "_post_json", return_value={"ok": True}) as mocked:
            api.accept_derivation("rt_123", payload)
        mocked.assert_called_once_with("/sessions/rt_123/derivations/accept", payload)


if __name__ == "__main__":
    unittest.main()
