"""Layer 4B conservative engine routing workflow tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agent import (
    AgentCheckpointStore,
    AgentScope,
    AgentSession,
    CandidatePayloadCache,
    DraftManager,
    EvaluateOutcome,
    EvaluateTools,
    ReadReviewOrchestrator,
    RegisterResult,
    RuleSpec,
    RuleTools,
    RuntimeBootstrapSpec,
    build_layer3a_tool_registry,
)
from agent.tools._runtime_api import LocalRuntimeAPI
from agent.tools.explain import ExplainTools
from agent.tools.kg_read import KGReadTools
from service.runtime_v1 import (
    close_runtime_session,
    get_runtime_session,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)
from factgraph.tests._test_helpers import User, _schema_ir, _seed_users_for_syntax_matrix
from factgraph.sdk import SDKStore


def _open_session(open_dto: dict[str, object]) -> str:
    resp = open_runtime_session(open_dto)
    assert resp["ok"], resp
    return resp["session"]["session_id"]


def _rule_spec(
    *,
    rule_id: str = "q.user_tag_rows",
    version: str = "1.0.0",
    where: list[object] | None = None,
    tags: list[str] | None = None,
) -> RuleSpec:
    return RuleSpec(
        rule_id=rule_id,
        version=version,
        select_vars=["$u", "$tag"],
        where=where or [["pred", "user:tag", ["$u", "$tag"]]],
        expose=True,
        tags=tags,
    )


class AgentLayer4BWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_l4b.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.schema_ir = _schema_ir()
        self.open_dto = {"schema_ir": self.schema_ir, "ledger_path": self.ledger_path}
        self.runtime_session_id = _open_session(self.open_dto)

        self.agent_session = AgentSession(scope=AgentScope(agent_id="agent-l4b"))
        self.agent_session.bind_runtime_session(
            self.runtime_session_id,
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto(self.open_dto),
            burr_db_path=str(self.db_path),
        )
        self.draft_manager = DraftManager()
        self.cache = CandidatePayloadCache(self.db_path)
        self.checkpoint = AgentCheckpointStore(self.db_path)
        self.runtime_api = LocalRuntimeAPI()
        self.kg = KGReadTools(runtime_api=self.runtime_api)
        self.explain = ExplainTools(runtime_api=self.runtime_api)
        self.evaluate_tools = EvaluateTools(
            runtime_api=self.runtime_api,
            candidate_cache=self.cache,
            explain_tools=self.explain,
            session=self.agent_session,
        )
        self.rule_tools = RuleTools(runtime_api=self.runtime_api, session=self.agent_session)
        self.orchestrator = ReadReviewOrchestrator(
            session=self.agent_session,
            draft_manager=self.draft_manager,
            kg_read_tools=self.kg,
            explain_tools=self.explain,
            evaluate_tools=self.evaluate_tools,
            candidate_cache=self.cache,
            checkpoint_store=self.checkpoint,
            rule_tools=self.rule_tools,
        )

        self.sdk = SDKStore([User])
        self.refs = _seed_users_for_syntax_matrix(self.sdk)
        self._write_rows()

    def tearDown(self) -> None:
        self.cache.close()
        self.checkpoint.close()
        if get_runtime_session(self.runtime_session_id).get("ok") is True:
            close_runtime_session(self.runtime_session_id)
        reset_runtime_sessions_for_tests()

    def _write_rows(self) -> None:
        for pred_id, e_ref, rest_terms in (
            ("user:tag", self.refs["u1"], [["string", "vip"]]),
            ("user:tag", self.refs["u2"], [["string", "staff"]]),
            ("user:name", self.refs["u1"], [["string", "Alice"]]),
            ("user:name", self.refs["u2"], [["string", "Bob"]]),
        ):
            resp = write_runtime_fact(
                self.runtime_session_id,
                {
                    "pred_id": pred_id,
                    "e_ref": e_ref,
                    "rest_terms": rest_terms,
                },
                kind="add",
            )
            self.assertTrue(resp["ok"], resp)

    def test_non_native_route_skips_without_ephemeral_registration(self) -> None:
        register, outcome, hint = self.orchestrator.register_and_evaluate_rule_with_routing(
            _rule_spec(rule_id="q.problog_only", tags=["engine:problog"]),
            evaluate_target_pred_id="user:tag",
        )
        self.assertIsNone(register)
        self.assertIsInstance(outcome, EvaluateOutcome)
        self.assertEqual(outcome.status, "skipped")
        self.assertEqual(hint.suggested_engine, "problog")
        self.assertEqual(self.orchestrator.list_ephemeral_rules(), [])

    def test_override_to_native_registers_and_evaluates(self) -> None:
        register, outcome, hint = self.orchestrator.register_and_evaluate_rule_with_routing(
            _rule_spec(rule_id="q.native_override", tags=["engine:problog"]),
            evaluate_target_pred_id="user:tag",
            override_engine="native",
        )
        self.assertIsInstance(register, RegisterResult)
        self.assertEqual(register.status, "registered")
        self.assertEqual(outcome.status, "ok")
        assert outcome.result is not None
        self.assertEqual(outcome.result.mode, "native")
        self.assertEqual(hint.suggested_engine, "native")
        ephemeral = self.orchestrator.list_ephemeral_rules()
        self.assertEqual(ephemeral[0].rule_id, "q.native_override")

    def test_consistency_warning_is_appended_to_hint_reason(self) -> None:
        seed_register, seed_outcome = self.orchestrator.register_and_evaluate_rule(
            _rule_spec(rule_id="q.seed_history"),
            evaluate_target_pred_id="user:tag",
        )
        self.assertIsInstance(seed_register, RegisterResult)
        self.assertEqual(seed_outcome.status, "ok")

        register, outcome, hint = self.orchestrator.register_and_evaluate_rule_with_routing(
            _rule_spec(rule_id="q.route_conflict", tags=["engine:problog"]),
            evaluate_target_pred_id="user:tag",
        )
        self.assertIsNone(register)
        self.assertEqual(outcome.status, "skipped")
        self.assertIn("consistency warning", hint.reason)
        self.assertIn("historical candidates for user:tag used native", hint.reason)

    def test_build_layer3a_tool_registry_exposes_forty_five_tools(self) -> None:
        tool_registry = build_layer3a_tool_registry(orchestrator=self.orchestrator)
        self.assertEqual(len(tool_registry), 45)
        self.assertIn("create_document_bundle", tool_registry)
        self.assertIn("commit_bundle", tool_registry)
        self.assertIn("extract_from_segment", tool_registry)
        self.assertIn("extract_and_create_bundle", tool_registry)


if __name__ == "__main__":
    unittest.main()
