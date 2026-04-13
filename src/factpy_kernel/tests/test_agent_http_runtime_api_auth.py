from __future__ import annotations

import unittest
from unittest.mock import patch

from factpy_kernel.agent.tools._runtime_api import HttpRuntimeAPI


class AgentHttpRuntimeAPIAuthTests(unittest.TestCase):
    def test_get_request_includes_api_key_header_when_configured(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime", api_key="secret")
        captured = []

        with patch.object(api, "_load", side_effect=lambda req: captured.append(req) or {"ok": True}):
            api.get_session("rt_123")

        self.assertEqual(captured[0].headers["X-factpy-api-key"], "secret")

    def test_post_request_includes_api_key_header_when_configured(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime", api_key="secret")
        captured = []

        with patch.object(api, "_load", side_effect=lambda req: captured.append(req) or {"ok": True}):
            api.write_fact("rt_123", {"pred_id": "x", "e_ref": "y", "rest_terms": []}, kind="set")

        self.assertEqual(captured[0].headers["X-factpy-api-key"], "secret")

    def test_delete_request_includes_api_key_header_when_configured(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime", api_key="secret")
        captured = []

        with patch.object(api, "_load", side_effect=lambda req: captured.append(req) or {"ok": True}):
            api.close_session("rt_123")

        self.assertEqual(captured[0].headers["X-factpy-api-key"], "secret")

    def test_request_omits_api_key_header_when_not_configured(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime")
        captured = []

        with patch.object(api, "_load", side_effect=lambda req: captured.append(req) or {"ok": True}):
            api.get_session("rt_123")

        self.assertNotIn("X-factpy-api-key", captured[0].headers)

    def test_invalid_api_key_argument_is_rejected(self) -> None:
        with self.assertRaisesRegex(Exception, "api_key must be non-empty string"):
            HttpRuntimeAPI("http://localhost:8000/v1/runtime", api_key="")
