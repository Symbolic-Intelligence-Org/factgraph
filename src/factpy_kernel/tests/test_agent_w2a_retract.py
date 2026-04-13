"""W2a exact retract tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from factpy_kernel.agent import (
    AgentCheckpointStore,
    AgentScope,
    AgentSession,
    CandidatePayloadCache,
    DraftManager,
    EvaluateTools,
    ReadReviewOrchestrator,
    RetractError,
    RetractRequest,
    RetractResult,
    RuntimeBootstrapSpec,
    WriteTools,
    build_layer3a_tool_registry,
)
from factpy_kernel.agent.tools._runtime_api import LocalRuntimeAPI
from factpy_kernel.agent.tools.explain import ExplainTools
from factpy_kernel.agent.tools.kg_read import KGReadTools
from factpy_kernel.service.runtime_v1 import (
    _require_session,
    close_runtime_session,
    get_runtime_session,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)
from factpy_kernel.tests._test_helpers import User, _schema_ir, _seed_users_for_syntax_matrix
from factpy_kernel.sdk import SDKStore


def _open_session(open_dto: dict[str, object]) -> str:
    resp = open_runtime_session(open_dto)
    assert resp["ok"], resp
    return resp["session"]["session_id"]


class AgentW2AExactRetractTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_w2a.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.schema_ir = _schema_ir()
        self.open_dto = {"schema_ir": self.schema_ir, "ledger_path": self.ledger_path}
        self.runtime_session_id = _open_session(self.open_dto)

        self.agent_session = AgentSession(scope=AgentScope(agent_id="agent-w2a"))
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
        self.seed_asrt_id = self._write_claim(
            pred_id="user:name",
            e_ref=self.refs["u1"],
            rest_terms=[["string", "Alice"]],
            meta={"source": "manual"},
        )

    def tearDown(self) -> None:
        self.cache.close()
        self.checkpoint.close()
        if get_runtime_session(self.runtime_session_id).get("ok") is True:
            close_runtime_session(self.runtime_session_id)
        reset_runtime_sessions_for_tests()

    def _write_claim(
        self,
        *,
        pred_id: str,
        e_ref: str,
        rest_terms: list[list[object]],
        meta: dict[str, object] | None = None,
    ) -> str:
        resp = write_runtime_fact(
            self.runtime_session_id,
            {
                "pred_id": pred_id,
                "e_ref": e_ref,
                "rest_terms": rest_terms,
                "meta": meta,
            },
            kind="add",
        )
        self.assertTrue(resp["ok"], resp)
        return resp["write"]["assertion_id"]

    def _claim_by_asrt_id(self, asrt_id: str):
        for claim in self.kg.query_claims(self.runtime_session_id):
            if claim.asrt_id == asrt_id:
                return claim
        return None

    def test_retract_request_to_dto_uses_confirmed_by_and_agent_executor(self) -> None:
        request = RetractRequest(
            asrt_id="A1",
            note="duplicate",
            confirmed_by="analyst-1",
            trace_id="batch-1",
        )
        dto = request.to_dto(agent_id="agent-w2a")
        self.assertEqual(dto["asrt_id"], "A1")
        self.assertEqual(dto["meta"]["approved_by"], "analyst-1")
        self.assertEqual(dto["meta"]["agent_executor"], "agent-w2a")
        self.assertEqual(dto["meta"]["note"], "duplicate")
        self.assertEqual(dto["meta"]["trace_id"], "batch-1")

    def test_write_tools_retract_returns_result_and_marks_original_claim_revoked(self) -> None:
        result = self.write_tools.retract(
            RetractRequest(
                asrt_id=self.seed_asrt_id,
                note="duplicate",
                confirmed_by="analyst-1",
                trace_id="retract-1",
            )
        )
        self.assertIsInstance(result, RetractResult)
        assert isinstance(result, RetractResult)
        self.assertEqual(result.revoked_asrt_id, self.seed_asrt_id)
        original = self._claim_by_asrt_id(self.seed_asrt_id)
        self.assertIsNotNone(original)
        assert original is not None
        self.assertTrue(original.is_revoked)

        ledger = _require_session(self.runtime_session_id).store.ledger
        meta_rows = ledger.find_meta(asrt_id=result.revoker_asrt_id)
        meta_map = {row.key: row.value for row in meta_rows}
        self.assertEqual(meta_map["approved_by"], "analyst-1")
        self.assertEqual(meta_map["agent_executor"], "agent-w2a")
        self.assertEqual(meta_map["note"], "duplicate")
        self.assertEqual(meta_map["trace_id"], "retract-1")
        self.assertEqual(meta_map["revoked_asrt_id"], self.seed_asrt_id)

    def test_write_tools_retract_returns_error_for_unknown_assertion(self) -> None:
        result = self.write_tools.retract(RetractRequest(asrt_id="missing-asrt"))
        self.assertIsInstance(result, RetractError)
        assert isinstance(result, RetractError)
        self.assertTrue(result.error_message)
        self.assertIn(result.error_kind, {"runtime", "shape"})

    def test_preview_retract_returns_claim_result_for_existing_assertion(self) -> None:
        preview = self.orchestrator.preview_retract(self.seed_asrt_id)
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(preview.asrt_id, self.seed_asrt_id)
        self.assertEqual(preview.pred_id, "user:name")
        self.assertEqual(preview.e_ref, self.refs["u1"])
        self.assertEqual(preview.rest_terms, [("string", "Alice")])
        self.assertFalse(preview.is_revoked)

    def test_preview_retract_returns_none_for_unknown_assertion(self) -> None:
        self.assertIsNone(self.orchestrator.preview_retract("missing-asrt"))

    def test_preview_retract_returns_revoked_claim_when_already_retracted(self) -> None:
        first = self.orchestrator.confirm_and_retract(self.seed_asrt_id, confirmed_by="analyst-1")
        self.assertIsInstance(first, RetractResult)
        preview = self.orchestrator.preview_retract(self.seed_asrt_id)
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertTrue(preview.is_revoked)

    def test_confirm_and_retract_returns_result_and_checkpoints(self) -> None:
        result = self.orchestrator.confirm_and_retract(
            self.seed_asrt_id,
            note="cleanup",
            confirmed_by="analyst-1",
            trace_id="retract-2",
        )
        self.assertIsInstance(result, RetractResult)
        assert isinstance(result, RetractResult)
        restored_session, _, _ = self.checkpoint.load(self.agent_session.agent_session_id)
        self.assertEqual(restored_session.runtime_session_id, self.runtime_session_id)
        original = self._claim_by_asrt_id(self.seed_asrt_id)
        self.assertIsNotNone(original)
        assert original is not None
        self.assertTrue(original.is_revoked)

    def test_confirm_and_retract_is_idempotent(self) -> None:
        first = self.orchestrator.confirm_and_retract(self.seed_asrt_id, confirmed_by="analyst-1")
        second = self.orchestrator.confirm_and_retract(self.seed_asrt_id, confirmed_by="analyst-1")
        self.assertIsInstance(first, RetractResult)
        self.assertIsInstance(second, RetractResult)
        assert isinstance(first, RetractResult)
        assert isinstance(second, RetractResult)
        self.assertEqual(first.revoker_asrt_id, second.revoker_asrt_id)

    def test_confirm_and_retract_returns_error_for_unknown_assertion(self) -> None:
        result = self.orchestrator.confirm_and_retract("missing-asrt", confirmed_by="analyst-1")
        self.assertIsInstance(result, RetractError)
        assert isinstance(result, RetractError)
        self.assertEqual(result.error_kind, "not_found")

    def test_build_layer3a_tool_registry_exposes_forty_five_tools(self) -> None:
        tool_registry = build_layer3a_tool_registry(orchestrator=self.orchestrator)
        self.assertEqual(len(tool_registry), 45)
        self.assertIn("create_document_bundle", tool_registry)
        self.assertIn("commit_bundle", tool_registry)
        self.assertIn("preview_retract", tool_registry)
        self.assertIn("confirm_and_retract", tool_registry)
        self.assertIn("validate_rule", tool_registry)
        self.assertIn("register_and_evaluate_rule", tool_registry)
        self.assertIn("extract_from_segment", tool_registry)
        self.assertIn("extract_and_create_bundle", tool_registry)


if __name__ == "__main__":
    unittest.main()
