"""Layer 4C3-a extraction workflow tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from factpy.agent import (
    AgentCheckpointStore,
    AgentScope,
    AgentSession,
    BundleManager,
    BundleReviewAction,
    CandidatePayloadCache,
    DocumentStaging,
    DraftManager,
    ExtractionAgent,
    ExtractionConfig,
    ReadReviewOrchestrator,
    RuntimeBootstrapSpec,
    WriteResult,
    WriteTools,
    build_layer3a_tool_registry,
)
from factpy.agent.tools._runtime_api import LocalRuntimeAPI
from factpy.agent.tools.evaluate import EvaluateTools
from factpy.agent.tools.explain import ExplainTools
from factpy.agent.tools.kg_read import KGReadTools
from factpy.service.runtime_v1 import (
    close_runtime_session,
    get_runtime_session,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
)
from factpy.tests._test_helpers import _schema_ir


class _FakeCompletions:
    def __init__(self, behavior):
        self._behavior = behavior

    def create(self, **kwargs):
        return self._behavior(kwargs)


class _FakeChat:
    def __init__(self, behavior):
        self.completions = _FakeCompletions(behavior)


class _FakeClient:
    def __init__(self, behavior):
        self.chat = _FakeChat(behavior)


def _open_session(open_dto: dict[str, object]) -> str:
    resp = open_runtime_session(open_dto)
    assert resp["ok"], resp
    return resp["session"]["session_id"]


class AgentLayer4C3aWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_l4c3a.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.open_dto = {"schema_ir": _schema_ir(), "ledger_path": self.ledger_path}
        self.runtime_session_id = _open_session(self.open_dto)

        self.agent_session = AgentSession(
            scope=AgentScope(
                agent_id="agent-l4c3a",
                allowed_entity_types=frozenset({"User"}),
                allowed_pred_ids=frozenset({"user:tag"}),
                require_source=True,
                max_batch_size=5,
            )
        )
        self.agent_session.bind_runtime_session(
            self.runtime_session_id,
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto(self.open_dto),
            burr_db_path=str(self.db_path),
        )
        self.draft_manager = DraftManager()
        self.bundle_manager = BundleManager(draft_manager=self.draft_manager)
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
        self.document_staging = DocumentStaging()

        def _behavior(kwargs):
            response_model = kwargs["response_model"]
            return response_model(
                proposals=[
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-doc-1"},
                            {"name": "locale", "value": "zh"},
                        ],
                        "pred_id": "user:tag",
                        "field_values": [{"tag": "string", "value": "vip"}],
                        "confidence": 0.93,
                        "llm_note": "directly stated",
                    }
                ]
            )

        self.extraction_agent = ExtractionAgent(
            config=ExtractionConfig(max_text_chars=200),
            llm_client=_FakeClient(_behavior),
        )
        self.orchestrator = ReadReviewOrchestrator(
            session=self.agent_session,
            draft_manager=self.draft_manager,
            kg_read_tools=self.kg,
            explain_tools=self.explain,
            evaluate_tools=self.evaluate_tools,
            candidate_cache=self.cache,
            checkpoint_store=self.checkpoint,
            write_tools=self.write_tools,
            document_staging=self.document_staging,
            bundle_manager=self.bundle_manager,
            extraction_agent=self.extraction_agent,
        )

    def tearDown(self) -> None:
        self.cache.close()
        self.checkpoint.close()
        if get_runtime_session(self.runtime_session_id).get("ok") is True:
            close_runtime_session(self.runtime_session_id)
        reset_runtime_sessions_for_tests()

    def test_extract_from_segment_is_pure_and_does_not_touch_session(self) -> None:
        staging = self.orchestrator.stage_document(
            doc_name="sample.txt",
            content=b"Section 1\nAlice is a VIP customer.",
        )
        before = self.agent_session.last_active_at
        result = self.orchestrator.extract_from_segment(segment=staging.segments[0])
        self.assertEqual(len(result.valid_specs), 1)
        self.assertEqual(self.agent_session.last_active_at, before)

    def test_extract_and_create_bundle_then_commit_claim(self) -> None:
        staging = self.orchestrator.stage_document(
            doc_name="sample.txt",
            content=b"Section 1\nAlice is a VIP customer.",
        )
        result, bundle = self.orchestrator.extract_and_create_bundle(
            segment=staging.segments[0],
            source_document_name=staging.source.doc_name,
        )
        self.assertEqual(len(result.valid_specs), 1)
        self.assertIsNotNone(bundle)
        assert bundle is not None

        self.orchestrator.open_bundle_review(bundle.bundle_id)
        reviewed = self.orchestrator.apply_bundle_review(
            bundle.bundle_id,
            [BundleReviewAction(draft_id=bundle.draft_ids[0], action="approve")],
        )
        self.assertEqual(reviewed.status, "approved")

        commit = self.orchestrator.commit_bundle(bundle.bundle_id, kind="add", confirmed_by="analyst-2")
        self.assertEqual(commit.committed_count, 1)
        self.assertIsInstance(commit.per_item_results[0], WriteResult)

        claims = self.kg.query_claims(self.runtime_session_id, pred_id="user:tag")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].meta["approved_by"], "analyst-2")
        self.assertEqual(
            claims[0].meta["source"],
            f"doc:{staging.source.doc_name}:seg:{staging.segments[0].segment_id}",
        )

    def test_build_layer3a_tool_registry_exposes_forty_five_tools(self) -> None:
        tool_registry = build_layer3a_tool_registry(orchestrator=self.orchestrator)
        self.assertEqual(len(tool_registry), 45)
        self.assertIn("extract_from_segment", tool_registry)
        self.assertIn("extract_and_create_bundle", tool_registry)


if __name__ == "__main__":
    unittest.main()
