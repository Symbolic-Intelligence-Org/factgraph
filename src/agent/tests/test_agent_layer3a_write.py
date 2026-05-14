"""Layer 3A structured write tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agent import (
    AgentCheckpointStore,
    AgentScope,
    AgentScopeViolation,
    AgentSession,
    CandidatePayloadCache,
    DraftManager,
    EvaluateTools,
    FactDraft,
    ReadReviewOrchestrator,
    RuntimeBootstrapSpec,
    WriteError,
    WriteResult,
    WriteTools,
    build_layer3a_tool_registry,
)
from agent.tools._runtime_api import LocalRuntimeAPI
from agent.tools.explain import ExplainTools
from agent.tools.kg_read import KGReadTools
from agent.tools.write import draft_to_write_request
from service.runtime_v1 import (
    close_runtime_session,
    get_runtime_session,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
)
from factgraph.tests._test_helpers import User, _schema_ir, _seed_users_for_syntax_matrix
from factgraph.sdk import SDKStore


def _open_session(open_dto: dict[str, object]) -> str:
    resp = open_runtime_session(open_dto)
    assert resp["ok"], resp
    return resp["session"]["session_id"]


class AgentLayer3AWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_layer3a.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.schema_ir = _schema_ir()
        self.open_dto = {"schema_ir": self.schema_ir, "ledger_path": self.ledger_path}
        self.runtime_session_id = _open_session(self.open_dto)

        self.agent_session = AgentSession(
            scope=AgentScope(
                agent_id="agent-layer3a",
                allowed_entity_types=frozenset({"User"}),
                allowed_pred_ids=frozenset({"user:name", "user:tag"}),
            )
        )
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
        self.write_tools = WriteTools(runtime_api=self.runtime_api, session=self.agent_session)
        self.orchestrator = ReadReviewOrchestrator(
            session=self.agent_session,
            draft_manager=self.draft_manager,
            kg_read_tools=self.kg,
            explain_tools=self.explain,
            evaluate_tools=self.evaluate_tools,
            candidate_cache=self.cache,
            checkpoint_store=self.checkpoint,
            write_tools=self.write_tools,
        )

        self.sdk = SDKStore([User])
        self.refs = _seed_users_for_syntax_matrix(self.sdk)

    def tearDown(self) -> None:
        self.cache.close()
        self.checkpoint.close()
        if get_runtime_session(self.runtime_session_id).get("ok") is True:
            close_runtime_session(self.runtime_session_id)
        reset_runtime_sessions_for_tests()

    def _make_confirmed_draft(
        self,
        *,
        entity_identity: dict[str, object],
        pred_id: str,
        field_values: list[tuple[str, object]],
        confidence: float | None = None,
        source: str | None = None,
        source_loc: str | None = None,
        note: str | None = None,
    ) -> FactDraft:
        draft = self.draft_manager.create_draft(
            self.agent_session.agent_session_id,
            entity_type="User",
            entity_identity=entity_identity,
            pred_id=pred_id,
            field_values=field_values,
            confidence=confidence,
            source=source,
            source_loc=source_loc,
            note=note,
            conversation_turn=1,
        )
        return self.draft_manager.confirm_draft(draft.draft_id)

    def test_draft_to_write_request_uses_schema_aware_e_ref_and_meta(self) -> None:
        draft = self._make_confirmed_draft(
            entity_identity={"user_id": "u-syntax-1", "locale": "zh"},
            pred_id="user:name",
            field_values=[("string", "Alice")],
            confidence=0.7,
            source="manual",
            source_loc="turn:1",
            note="seed",
        )
        request = draft_to_write_request(
            draft,
            schema_ir=self.schema_ir,
            agent_id="agent-layer3a",
            confirmed_by="analyst-1",
            bundle_id="bundle-1",
        )
        self.assertEqual(request.e_ref, self.refs["u1"])
        self.assertEqual(request.meta["approved_by"], "analyst-1")
        self.assertEqual(request.meta["agent_executor"], "agent-layer3a")
        self.assertEqual(request.meta["confidence"], 0.7)
        self.assertEqual(request.meta["source"], "manual")
        self.assertEqual(request.meta["source_loc"], "turn:1")
        self.assertEqual(request.meta["trace_id"], "bundle-1")

    def test_write_tools_commit_draft_returns_result_and_visible_claim(self) -> None:
        draft = self._make_confirmed_draft(
            entity_identity={"user_id": "u-syntax-1", "locale": "zh"},
            pred_id="user:name",
            field_values=[("string", "Alice")],
            source="manual",
        )
        result = self.write_tools.commit_draft(draft, kind="set", confirmed_by="analyst-1")
        self.assertIsInstance(result, WriteResult)
        claims = self.kg.query_claims(self.runtime_session_id, pred_id="user:name", e_ref=self.refs["u1"])
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].rest_terms, [("string", "Alice")])
        self.assertEqual(claims[0].meta["approved_by"], "analyst-1")
        self.assertEqual(claims[0].meta["agent_executor"], "agent-layer3a")

    def test_write_tools_commit_draft_returns_write_error_for_runtime_failure(self) -> None:
        draft = self._make_confirmed_draft(
            entity_identity={"user_id": "u-syntax-2", "locale": "en"},
            pred_id="user:name",
            field_values=[("badtag", "Bob")],
        )
        result = self.write_tools.commit_draft(draft, kind="set")
        self.assertIsInstance(result, WriteError)
        self.assertTrue(result.error_message)
        self.assertIn(result.error_kind, {"runtime", "shape"})

    def test_prepare_draft_creates_pending_draft(self) -> None:
        draft = self.orchestrator.prepare_draft(
            entity_type="User",
            entity_identity={"user_id": "u-syntax-1", "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            source="manual",
            conversation_turn=2,
        )
        self.assertEqual(draft.status, "pending")
        self.assertEqual(
            self.draft_manager.list_drafts(self.agent_session.agent_session_id, status="pending")[0].draft_id,
            draft.draft_id,
        )

    def test_prepare_draft_scope_violation_does_not_store_draft(self) -> None:
        with self.assertRaises(AgentScopeViolation):
            self.orchestrator.prepare_draft(
                entity_type="Account",
                entity_identity={"account_id": "acct-1"},
                pred_id="user:tag",
                field_values=[("string", "vip")],
            )
        self.assertEqual(
            self.draft_manager.list_drafts(self.agent_session.agent_session_id),
            [],
        )

    def test_confirm_and_commit_marks_committed_and_checkpoints(self) -> None:
        draft = self.orchestrator.prepare_draft(
            entity_type="User",
            entity_identity={"user_id": "u-syntax-1", "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            source="manual",
        )
        result = self.orchestrator.confirm_and_commit(
            draft.draft_id,
            kind="add",
            bundle_id="bundle-write-1",
            confirmed_by="analyst-1",
        )
        self.assertIsInstance(result, WriteResult)
        committed = self.draft_manager.get_draft(draft.draft_id)
        self.assertIsNotNone(committed)
        assert committed is not None
        self.assertEqual(committed.status, "committed")
        self.assertEqual(committed.assertion_id, result.assertion_id)
        restored_session, restored_drafts, _ = self.checkpoint.load(self.agent_session.agent_session_id)
        self.assertEqual(restored_session.runtime_session_id, self.runtime_session_id)
        restored = restored_drafts.get_draft(draft.draft_id)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.status, "committed")
        claims = self.kg.query_claims(self.runtime_session_id, pred_id="user:tag", e_ref=self.refs["u1"])
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].meta["approved_by"], "analyst-1")
        self.assertEqual(claims[0].meta["trace_id"], "bundle-write-1")

    def test_confirm_and_commit_runtime_failure_rejects_draft(self) -> None:
        draft = self.orchestrator.prepare_draft(
            entity_type="User",
            entity_identity={"user_id": "u-syntax-2", "locale": "en"},
            pred_id="user:name",
            field_values=[("badtag", "Bob")],
        )
        result = self.orchestrator.confirm_and_commit(draft.draft_id, kind="set")
        self.assertIsInstance(result, WriteError)
        rejected = self.draft_manager.get_draft(draft.draft_id)
        self.assertIsNotNone(rejected)
        assert rejected is not None
        self.assertEqual(rejected.status, "rejected")
        _, restored_drafts, _ = self.checkpoint.load(self.agent_session.agent_session_id)
        restored = restored_drafts.get_draft(draft.draft_id)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.status, "rejected")

    def test_confirm_and_commit_rechecks_scope_and_rejects_on_scope_change(self) -> None:
        draft = self.orchestrator.prepare_draft(
            entity_type="User",
            entity_identity={"user_id": "u-syntax-3", "locale": "zh"},
            pred_id="user:name",
            field_values=[("string", "Carol")],
        )
        self.agent_session.scope = AgentScope(
            agent_id="agent-layer3a",
            allowed_entity_types=frozenset({"User"}),
            allowed_pred_ids=frozenset({"user:tag"}),
        )
        with self.assertRaises(AgentScopeViolation):
            self.orchestrator.confirm_and_commit(draft.draft_id)
        rejected = self.draft_manager.get_draft(draft.draft_id)
        self.assertIsNotNone(rejected)
        assert rejected is not None
        self.assertEqual(rejected.status, "rejected")

    def test_confirm_and_commit_many_checkpoints_once_and_returns_mixed_results(self) -> None:
        good = self.orchestrator.prepare_draft(
            entity_type="User",
            entity_identity={"user_id": "u-syntax-1", "locale": "zh"},
            pred_id="user:name",
            field_values=[("string", "Alice")],
        )
        bad = self.orchestrator.prepare_draft(
            entity_type="User",
            entity_identity={"user_id": "u-syntax-2", "locale": "en"},
            pred_id="user:name",
            field_values=[("badtag", "Bob")],
        )
        with patch.object(self.orchestrator, "_checkpoint", wraps=self.orchestrator._checkpoint) as mocked:
            results = self.orchestrator.confirm_and_commit_many(
                [good.draft_id, bad.draft_id],
                kind="set",
            )
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(len(results), 2)
        self.assertTrue(any(isinstance(item, WriteResult) for item in results))
        self.assertTrue(any(isinstance(item, WriteError) for item in results))

    def test_build_layer3a_tool_registry_exposes_forty_five_tools(self) -> None:
        tool_registry = build_layer3a_tool_registry(orchestrator=self.orchestrator)
        self.assertEqual(len(tool_registry), 45)
        self.assertIn("create_document_bundle", tool_registry)
        self.assertIn("commit_bundle", tool_registry)
        self.assertIn("prepare_draft", tool_registry)
        self.assertIn("confirm_and_commit", tool_registry)
        self.assertIn("confirm_and_commit_many", tool_registry)
        self.assertIn("list_committed_drafts", tool_registry)
        self.assertIn("preview_retract", tool_registry)
        self.assertIn("confirm_and_retract", tool_registry)
        self.assertIn("validate_rule", tool_registry)
        self.assertIn("preview_rule", tool_registry)
        self.assertIn("register_and_evaluate_rule", tool_registry)
        self.assertIn("list_ephemeral_rules", tool_registry)
        self.assertIn("clear_ephemeral_rules", tool_registry)
        self.assertIn("stage_document", tool_registry)
        self.assertIn("list_supported_document_formats", tool_registry)
        self.assertIn("extract_from_segment", tool_registry)
        self.assertIn("extract_and_create_bundle", tool_registry)


if __name__ == "__main__":
    unittest.main()
