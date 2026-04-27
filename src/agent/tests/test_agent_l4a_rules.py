"""Layer 4A rule tool tests."""

from __future__ import annotations

import unittest

from agent import (
    AgentScope,
    AgentSession,
    CompilePreviewResult,
    EphemeralRuleSummary,
    RegisterError,
    RegisterResult,
    RuleSpec,
    RuleTools,
    RuntimeBootstrapSpec,
    ValidateResult,
)
from kernel.tests._test_helpers import _schema_ir


class _FakeRuleRuntimeAPI:
    def __init__(self) -> None:
        self.validate_response = {"ok": True, "errors": [], "meta": {"profile_effective": "default", "mode": "souffle"}}
        self.preview_response = {
            "ok": True,
            "errors": [],
            "meta": {"profile_effective": "default", "mode": "souffle"},
            "preview": {"compiled_payload": {"rule_id": "q.ok", "version": "v1"}},
        }
        self.register_response = {
            "ok": True,
            "errors": [],
            "result": {"rule_id": "q.ok", "version": "v1", "status": "registered", "total_ephemeral": 1},
        }
        self.list_response = {
            "ok": True,
            "errors": [],
            "result": {"ephemeral_rules": [{"rule_id": "q.ok", "version": "v1"}], "total": 1},
        }
        self.clear_response = {"ok": True, "errors": [], "result": {"cleared": 1}}
        self.register_calls: list[tuple[str, dict[str, object]]] = []

    def validate_rule(self, dto: dict[str, object]) -> dict[str, object]:
        self.last_validate = dto
        return self.validate_response

    def compile_rule_preview(self, dto: dict[str, object]) -> dict[str, object]:
        self.last_preview = dto
        return self.preview_response

    def register_ephemeral_rule(self, session_id: str, dto: dict[str, object]) -> dict[str, object]:
        self.register_calls.append((session_id, dto))
        return self.register_response

    def list_ephemeral_rules(self, session_id: str) -> dict[str, object]:
        self.last_list = session_id
        return self.list_response

    def clear_ephemeral_rules(self, session_id: str) -> dict[str, object]:
        self.last_clear = session_id
        return self.clear_response


def _rule_spec(*, rule_id: str = "q.ok") -> RuleSpec:
    return RuleSpec(
        rule_id=rule_id,
        version="v1",
        select_vars=["$u", "$tag"],
        where=[["pred", "user:tag", ["$u", "$tag"]]],
        expose=True,
    )


class AgentLayer4ARuleToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = _FakeRuleRuntimeAPI()
        self.session = AgentSession(scope=AgentScope(agent_id="agent-l4a"))
        self.session.bind_runtime_session(
            "rt_123",
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto({"schema_ir": _schema_ir()}),
            burr_db_path="/tmp/agent-l4a.sqlite3",
        )
        self.tools = RuleTools(runtime_api=self.runtime, session=self.session)

    def test_validate_returns_valid_result(self) -> None:
        result = self.tools.validate(_rule_spec())
        self.assertIsInstance(result, ValidateResult)
        self.assertTrue(result.valid)
        self.assertEqual(result.profile_effective, "default")
        self.assertEqual(result.mode, "souffle")

    def test_validate_returns_errors_for_invalid_rule(self) -> None:
        self.runtime.validate_response = {
            "ok": False,
            "errors": [
                {
                    "kind": "rule_ast_validate",
                    "path": "$.rule.where",
                    "details": {"message": "bad atom"},
                }
            ],
            "meta": {"profile_effective": "default", "mode": "souffle"},
        }
        result = self.tools.validate(_rule_spec())
        self.assertFalse(result.valid)
        self.assertEqual(result.errors[0]["kind"], "rule_ast_validate")

    def test_compile_preview_returns_compiled_payload(self) -> None:
        result = self.tools.compile_preview(_rule_spec())
        self.assertIsInstance(result, CompilePreviewResult)
        self.assertTrue(result.valid)
        self.assertEqual(result.compiled_payload, {"rule_id": "q.ok", "version": "v1"})

    def test_register_ephemeral_returns_register_error_when_validate_fails(self) -> None:
        self.runtime.validate_response = {
            "ok": False,
            "errors": [
                {
                    "kind": "rule_ast_validate",
                    "path": "$.rule.where",
                    "details": {"message": "bad atom"},
                }
            ],
            "meta": {"profile_effective": "default", "mode": "souffle"},
        }
        result = self.tools.register_ephemeral(_rule_spec())
        self.assertIsInstance(result, RegisterError)
        self.assertEqual(result.error_kind, "rule_ast_validate")
        self.assertEqual(self.runtime.register_calls, [])

    def test_register_ephemeral_returns_register_result(self) -> None:
        result = self.tools.register_ephemeral(_rule_spec())
        self.assertIsInstance(result, RegisterResult)
        self.assertEqual(result.status, "registered")
        self.assertEqual(self.runtime.register_calls[0][0], "rt_123")

    def test_list_and_clear_ephemeral_rules(self) -> None:
        listed = self.tools.list_ephemeral()
        self.assertEqual(listed, [EphemeralRuleSummary(rule_id="q.ok", version="v1")])
        cleared = self.tools.clear_ephemeral()
        self.assertEqual(cleared, 1)


if __name__ == "__main__":
    unittest.main()
