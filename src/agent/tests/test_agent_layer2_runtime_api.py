"""Layer 2 runtime API extension tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agent import (
    AgentScope,
    AgentSession,
    CandidatePayloadCache,
    EvaluateRequest,
    EvaluateTools,
    RuntimeBootstrapSpec,
)
from agent.tools._runtime_api import HttpRuntimeAPI, LocalRuntimeAPI
from agent.tools.explain import ExplainTools


class _FakeRuntimeAPI:
    def __init__(self, response: dict):
        self.response = response
        self.last_payload: dict | None = None

    def evaluate_derivation(self, session_id: str, dto: dict) -> dict:
        self.last_payload = {"session_id": session_id, "dto": dto}
        return self.response


class AgentLayer2RuntimeAPITests(unittest.TestCase):
    def test_local_runtime_api_evaluate_derivation_dispatches_to_runtime(self) -> None:
        api = LocalRuntimeAPI()
        payload = {"inference": {"derivation_id": "drv.x"}}
        expected = {"ok": True, "evaluation": {"rows": []}}
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
        payload = {"inference": {"derivation_id": "drv.x"}}
        with patch.object(api, "_post_json", return_value={"ok": True}) as mocked:
            api.evaluate_derivation("rt_123", payload)
        mocked.assert_called_once_with("/sessions/rt_123/inferences/evaluate", payload)

    def test_http_runtime_api_accept_derivation_uses_expected_route(self) -> None:
        api = HttpRuntimeAPI("http://localhost:8000/v1/runtime")
        payload = {"candidate": {"candidate_id": "cand_1"}}
        with patch.object(api, "_post_json", return_value={"ok": True}) as mocked:
            api.accept_derivation("rt_123", payload)
        mocked.assert_called_once_with("/sessions/rt_123/inferences/accept", payload)

    def test_evaluate_tools_consumes_evaluate_result_rows_without_candidate_cache(self) -> None:
        runtime = _FakeRuntimeAPI(
            {
                "ok": True,
                "meta": {
                    "mode": "native",
                    "row_count": 1,
                    "returned_count": 1,
                    "truncated": False,
                },
                "evaluation": {
                    "inference_id": "drv.x",
                    "version": "1.0.0",
                    "target_pred_id": "user:tag",
                    "result_id": "evalr_v1:" + ("a" * 64),
                    "run_id": "run_v1:" + ("b" * 64),
                    "rows": [
                        {
                            "row_id": "run_v1:" + ("b" * 64) + ":0123456789abcdef",
                            "bindings": {"$u": "idref_v1:User:u1"},
                        }
                    ],
                },
            }
        )
        session = AgentSession(scope=AgentScope(agent_id="agent-layer2"))
        session.bind_runtime_session(
            "rt_123",
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto({}),
        )
        with TemporaryDirectory() as tmp:
            cache = CandidatePayloadCache(Path(tmp) / "cache.sqlite3")
            try:
                tools = EvaluateTools(
                    runtime_api=runtime,  # type: ignore[arg-type]
                    candidate_cache=cache,
                    explain_tools=ExplainTools(runtime_api=runtime),  # type: ignore[arg-type]
                    session=session,
                )

                result = tools.evaluate(
                    EvaluateRequest(
                        inference={"derivation_id": "drv.x", "target": "user:tag"},
                        engine="native",
                    )
                )

                self.assertEqual(result.row_count, 1)
                self.assertEqual(result.rows[0]["bindings"]["$u"], "idref_v1:User:u1")
                self.assertEqual(cache.lookup_active_by_runtime("rt_123"), [])
            finally:
                cache.close()


if __name__ == "__main__":
    unittest.main()
