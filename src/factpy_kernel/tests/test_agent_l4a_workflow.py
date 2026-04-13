"""Layer 4A native-first rule authoring workflow tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from factpy_kernel.authoring import FileAuthoringRegistry
from factpy_kernel.agent import (
    AgentCheckpointStore,
    AgentScope,
    AgentSession,
    CandidatePayloadCache,
    CompilePreviewResult,
    DraftManager,
    EphemeralRuleSummary,
    EvaluateOutcome,
    EvaluateTools,
    ReadReviewOrchestrator,
    RegisterError,
    RegisterResult,
    RuleSpec,
    RuleTools,
    RuntimeBootstrapSpec,
    ValidateResult,
    build_layer3a_tool_registry,
)
from factpy_kernel.agent.tools._runtime_api import LocalRuntimeAPI
from factpy_kernel.agent.tools.explain import ExplainTools
from factpy_kernel.agent.tools.kg_read import KGReadTools
from factpy_kernel.service.runtime_v1 import (
    close_runtime_session,
    get_runtime_session,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)
from factpy_kernel.tests._test_helpers import (
    User,
    _register_exposed_user_tag_rule,
    _schema_ir,
    _seed_users_for_syntax_matrix,
)
from factpy_kernel.sdk import SDKStore


def _open_session(open_dto: dict[str, object]) -> str:
    resp = open_runtime_session(open_dto)
    assert resp["ok"], resp
    return resp["session"]["session_id"]


def _rule_spec(
    *,
    rule_id: str = "q.user_tag_rows",
    version: str = "1.0.0",
    where: list[object] | None = None,
    select_vars: list[str] | None = None,
) -> RuleSpec:
    return RuleSpec(
        rule_id=rule_id,
        version=version,
        select_vars=select_vars or ["$u", "$tag"],
        where=where or [["pred", "user:tag", ["$u", "$tag"]]],
        expose=True,
    )


class AgentLayer4AWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_l4a.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.schema_ir = _schema_ir()
        self.open_dto = {"schema_ir": self.schema_ir, "ledger_path": self.ledger_path}
        self.runtime_session_id = _open_session(self.open_dto)

        self.agent_session = AgentSession(scope=AgentScope(agent_id="agent-l4a"))
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

    def test_validate_and_preview_rule(self) -> None:
        validation = self.orchestrator.validate_rule(_rule_spec())
        self.assertIsInstance(validation, ValidateResult)
        self.assertTrue(validation.valid)
        preview = self.orchestrator.preview_rule(_rule_spec())
        self.assertIsInstance(preview, CompilePreviewResult)
        self.assertTrue(preview.valid)
        self.assertIsNotNone(preview.compiled_payload)
        assert preview.compiled_payload is not None
        self.assertEqual(preview.compiled_payload["rule_id"], "q.user_tag_rows")

    def test_register_and_evaluate_rule_returns_ok_outcome_and_supports_review_accept(self) -> None:
        register, outcome = self.orchestrator.register_and_evaluate_rule(
            _rule_spec(),
            evaluate_target_pred_id="user:tag",
        )
        self.assertIsInstance(register, RegisterResult)
        self.assertEqual(register.status, "registered")
        self.assertIsInstance(outcome, EvaluateOutcome)
        self.assertEqual(outcome.status, "ok")
        assert outcome.result is not None
        self.assertEqual(outcome.result.mode, "native")
        self.assertEqual(outcome.result.candidate_count, 2)

        candidate_id = outcome.result.candidates[0]["candidate_id"]
        review = self.orchestrator.review_candidate(candidate_id, include_steps=True)
        self.assertEqual(review.cache_status, "active")
        self.assertTrue(review.steps)
        accepted = self.orchestrator.accept(candidate_id, dry_run=True)
        self.assertEqual(accepted.candidate_id, candidate_id)
        restored_session, _, _ = self.checkpoint.load(self.agent_session.agent_session_id)
        self.assertEqual(restored_session.runtime_session_id, self.runtime_session_id)

    def test_register_and_evaluate_rule_not_requested_and_list_clear_ephemeral(self) -> None:
        register, outcome = self.orchestrator.register_and_evaluate_rule(_rule_spec(rule_id="q.no_eval"))
        self.assertIsInstance(register, RegisterResult)
        self.assertEqual(outcome.status, "not_requested")

        listed = self.orchestrator.list_ephemeral_rules()
        self.assertEqual(listed, [EphemeralRuleSummary(rule_id="q.no_eval", version="1.0.0")])
        cleared = self.orchestrator.clear_ephemeral_rules()
        self.assertEqual(cleared, 1)
        self.assertEqual(self.orchestrator.list_ephemeral_rules(), [])

    def test_register_and_evaluate_rule_skips_on_invalid_rule(self) -> None:
        register, outcome = self.orchestrator.register_and_evaluate_rule(
            _rule_spec(rule_id="q.bad", select_vars=["u"])
        )
        self.assertIsInstance(register, RegisterError)
        self.assertEqual(register.error_kind, "rule_ast_validate")
        self.assertEqual(outcome.status, "skipped")
        self.assertEqual(self.orchestrator.list_ephemeral_rules(), [])

    def test_register_and_evaluate_rule_returns_error_outcome_when_evaluate_fails(self) -> None:
        register, outcome = self.orchestrator.register_and_evaluate_rule(
            _rule_spec(rule_id="q.eval_error"),
            evaluate_target_pred_id="missing:pred",
        )
        self.assertIsInstance(register, RegisterResult)
        self.assertEqual(outcome.status, "error")
        self.assertIn("target predicate not found", outcome.error_message or "")

    def test_fs_shadowed_rule_still_evaluates_fs_version(self) -> None:
        close_runtime_session(self.runtime_session_id)
        self.cache.close()
        self.checkpoint.close()

        with TemporaryDirectory() as reg_dir:
            registry = FileAuthoringRegistry(Path(reg_dir))
            registry.upsert_schema_ir(self.sdk.schema_ir)
            _register_exposed_user_tag_rule(self.sdk, reg_dir, rule_id="q.shadow_test")

            self.runtime_session_id = _open_session({"registry_root": reg_dir, "ledger_path": self.ledger_path})
            self.agent_session.bind_runtime_session(
                self.runtime_session_id,
                bootstrap_spec=RuntimeBootstrapSpec.from_open_dto({"registry_root": reg_dir, "ledger_path": self.ledger_path}),
                burr_db_path=str(self.db_path),
            )
            self.cache = CandidatePayloadCache(self.db_path)
            self.checkpoint = AgentCheckpointStore(self.db_path)
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
            self._write_rows()

            shadowed_spec = _rule_spec(
                rule_id="q.shadow_test",
                where=[
                    ["pred", "user:tag", ["$u", "$tag"]],
                    ["eq", "$tag", "staff"],
                ],
            )
            register, outcome = self.orchestrator.register_and_evaluate_rule(
                shadowed_spec,
                evaluate_target_pred_id="user:tag",
            )
            self.assertIsInstance(register, RegisterResult)
            self.assertEqual(outcome.status, "ok")
            assert outcome.result is not None
            self.assertEqual(outcome.result.candidate_count, 2)
            rules = self.orchestrator.list_rules()
            shadowed = next(rule for rule in rules if rule.rule_id == "q.shadow_test")
            self.assertEqual(shadowed.source, "ephemeral_shadowed_by_fs")

    def test_build_layer3a_tool_registry_exposes_forty_five_tools(self) -> None:
        tool_registry = build_layer3a_tool_registry(orchestrator=self.orchestrator)
        self.assertEqual(len(tool_registry), 45)
        self.assertIn("create_document_bundle", tool_registry)
        self.assertIn("commit_bundle", tool_registry)
        self.assertIn("validate_rule", tool_registry)
        self.assertIn("preview_rule", tool_registry)
        self.assertIn("register_and_evaluate_rule", tool_registry)
        self.assertIn("list_ephemeral_rules", tool_registry)
        self.assertIn("clear_ephemeral_rules", tool_registry)
        self.assertIn("extract_from_segment", tool_registry)
        self.assertIn("extract_and_create_bundle", tool_registry)


if __name__ == "__main__":
    unittest.main()
