"""Layer 4A runtime API extension tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from factpy_kernel.agent.tools._runtime_api import HttpRuntimeAPI, LocalRuntimeAPI


class AgentLayer4ARuntimeAPITests(unittest.TestCase):
    def test_local_runtime_api_validate_rule_dispatches_to_rules_v1(self) -> None:
        api = LocalRuntimeAPI()
        payload = {"rule": {"rule_id": "q.ok", "select_vars": ["$u"], "where": []}}
        expected = {"ok": True, "errors": [], "meta": {"mode": "souffle", "profile_effective": "default"}}
        with patch("factpy_kernel.service.rules_v1.validate_rule", return_value=expected) as mocked:
            resp = api.validate_rule(payload)
        self.assertEqual(resp, expected)
        mocked.assert_called_once_with(payload)

    def test_local_runtime_api_compile_rule_preview_dispatches_to_rules_v1(self) -> None:
        api = LocalRuntimeAPI()
        payload = {"rule": {"rule_id": "q.ok", "select_vars": ["$u"], "where": []}}
        expected = {"ok": True, "errors": [], "preview": {"compiled_payload": {"rule_id": "q.ok"}}}
        with patch("factpy_kernel.service.rules_v1.compile_rule_preview", return_value=expected) as mocked:
            resp = api.compile_rule_preview(payload)
        self.assertEqual(resp, expected)
        mocked.assert_called_once_with(payload)

    def test_local_runtime_api_ephemeral_rule_methods_dispatch_to_runtime(self) -> None:
        api = LocalRuntimeAPI()
        register_payload = {"rule": {"rule_id": "q.ok", "select_vars": ["$u"], "where": []}}
        with patch(
            "factpy_kernel.service.runtime_v1.register_ephemeral_rule",
            return_value={"ok": True},
        ) as register_mock:
            api.register_ephemeral_rule("rt_123", register_payload)
        register_mock.assert_called_once_with("rt_123", register_payload)

        with patch(
            "factpy_kernel.service.runtime_v1.list_ephemeral_rules",
            return_value={"ok": True},
        ) as list_mock:
            api.list_ephemeral_rules("rt_123")
        list_mock.assert_called_once_with("rt_123")

        with patch(
            "factpy_kernel.service.runtime_v1.clear_ephemeral_rules",
            return_value={"ok": True},
        ) as clear_mock:
            api.clear_ephemeral_rules("rt_123")
        clear_mock.assert_called_once_with("rt_123")

    def test_http_runtime_api_validate_and_preview_use_rules_base(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime")
        payload = {"rule": {"rule_id": "q.ok", "select_vars": ["$u"], "where": []}}
        with patch.object(api, "_post_json_to_base", return_value={"ok": True}) as mocked:
            api.validate_rule(payload)
            api.compile_rule_preview(payload)
        self.assertEqual(mocked.call_args_list[0].args, ("http://localhost:8000/v1", "/rules/validate", payload))
        self.assertEqual(
            mocked.call_args_list[1].args,
            ("http://localhost:8000/v1", "/rules/compile-preview", payload),
        )

    def test_http_runtime_api_ephemeral_rule_routes_use_session_paths(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime")
        payload = {"rule": {"rule_id": "q.ok", "select_vars": ["$u"], "where": []}}
        with patch.object(api, "_post_json", return_value={"ok": True}) as post_mock:
            api.register_ephemeral_rule("rt_123", payload)
        post_mock.assert_called_once_with("/sessions/rt_123/ephemeral-rules", payload)

        with patch.object(api, "_get_json", return_value={"ok": True}) as get_mock:
            api.list_ephemeral_rules("rt_123")
        get_mock.assert_called_once_with("/sessions/rt_123/ephemeral-rules")

        with patch.object(api, "_delete_json", return_value={"ok": True}) as delete_mock:
            api.clear_ephemeral_rules("rt_123")
        delete_mock.assert_called_once_with("/sessions/rt_123/ephemeral-rules")


if __name__ == "__main__":
    unittest.main()
