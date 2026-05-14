"""Layer 4C3-c resolution workflow tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agent import (
    AgentCheckpointStore,
    AgentScope,
    AgentSession,
    BatchExtractor,
    BundleManager,
    BundleReviewAction,
    CandidatePayloadCache,
    DocumentStaging,
    DraftManager,
    EntityResolver,
    ExtractionAgent,
    ExtractionConfig,
    ReadReviewOrchestrator,
    RuntimeBootstrapSpec,
    WriteResult,
    build_layer3a_tool_registry,
)
from agent.tools._runtime_api import LocalRuntimeAPI
from agent.tools.evaluate import EvaluateTools
from agent.tools.explain import ExplainTools
from agent.tools.kg_read import KGReadTools
from agent.tools.write import WriteTools
from service.runtime_v1 import (
    close_runtime_session,
    get_runtime_session,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
)
from factgraph.tests._test_helpers import _schema_ir


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


class AgentLayer4C3cWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_l4c3c.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.open_dto = {"schema_ir": _schema_ir(), "ledger_path": self.ledger_path}
        self.runtime_session_id = _open_session(self.open_dto)

        self.agent_session = AgentSession(
            scope=AgentScope(
                agent_id="agent-l4c3c",
                allowed_entity_types=frozenset({"User"}),
                allowed_pred_ids=frozenset({"user:tag"}),
                require_source=True,
                max_batch_size=10,
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
        self.entity_resolver = EntityResolver()

        def _behavior(kwargs):
            response_model = kwargs["response_model"]
            user_prompt = kwargs["messages"][1]["content"]
            if "Alice is a VIP customer" in user_prompt:
                proposals = [
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-doc-1"},
                            {"name": "locale", "value": "zh"},
                        ],
                        "pred_id": "user:tag",
                        "field_values": [{"tag": "string", "value": "vip"}],
                        "confidence": 0.91,
                    }
                ]
            elif "Bob is a staff user" in user_prompt:
                proposals = [
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-doc-2"},
                            {"name": "locale", "value": "en"},
                        ],
                        "pred_id": "user:tag",
                        "field_values": [{"tag": "string", "value": "staff"}],
                        "confidence": 0.87,
                    }
                ]
            else:
                proposals = []
            return response_model(proposals=proposals)

        self.extraction_agent = ExtractionAgent(
            config=ExtractionConfig(max_text_chars=500),
            llm_client=_FakeClient(_behavior),
        )
        self.batch_extractor = BatchExtractor(extraction_agent=self.extraction_agent)
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
            batch_extractor=self.batch_extractor,
            entity_resolver=self.entity_resolver,
        )

    def tearDown(self) -> None:
        self.cache.close()
        self.checkpoint.close()
        if get_runtime_session(self.runtime_session_id).get("ok") is True:
            close_runtime_session(self.runtime_session_id)
        reset_runtime_sessions_for_tests()

    def _stage(self):
        result = self.orchestrator.stage_document(
            doc_name="sample.txt",
            content=(
                b"Section 1\n"
                b"Alice is a VIP customer.\n\n"
                b"Section 2\n"
                b"Alice is a VIP customer.\n\n"
                b"Section 3\n"
                b"Bob is a staff user."
            ),
        )
        self.assertFalse(hasattr(result, "error_kind"))
        return result

    def test_resolve_batch_extraction_is_pure_and_does_not_checkpoint(self) -> None:
        staging = self._stage()
        batch = self.orchestrator.extract_from_segments(segments=list(staging.segments))

        before = self.agent_session.last_active_at
        resolution = self.orchestrator.resolve_batch_extraction(batch)

        self.assertEqual(len(batch.aggregated_specs), 3)
        self.assertEqual(len(resolution.resolved_specs), 2)
        self.assertEqual(resolution.stats.merge_count, 1)
        self.assertEqual(self.agent_session.last_active_at, before)
        with self.assertRaises(Exception):
            self.checkpoint.load(self.agent_session.agent_session_id)

    def test_extract_resolve_and_create_document_bundle_then_commit(self) -> None:
        staging = self._stage()

        batch, resolution, bundle = self.orchestrator.extract_resolve_and_create_document_bundle(
            segments=list(staging.segments),
            source_document_name=staging.source.doc_name,
        )

        self.assertEqual(len(batch.aggregated_specs), 3)
        self.assertIsNotNone(resolution)
        self.assertIsNotNone(bundle)
        assert resolution is not None
        assert bundle is not None
        self.assertEqual(len(resolution.resolved_specs), 2)
        self.assertEqual(resolution.stats.merge_count, 1)

        merged_spec = next(
            spec for spec in resolution.resolved_specs if spec.extraction_provenance.is_merged()
        )
        self.assertEqual(
            set(merged_spec.extraction_provenance.source_segment_ids()),
            {staging.segments[0].segment_id, staging.segments[1].segment_id},
        )

        self.orchestrator.open_bundle_review(bundle.bundle_id)
        reviewed = self.orchestrator.apply_bundle_review(
            bundle.bundle_id,
            [BundleReviewAction(draft_id=draft_id, action="approve") for draft_id in bundle.draft_ids],
        )
        self.assertEqual(reviewed.status, "approved")

        commit = self.orchestrator.commit_bundle(bundle.bundle_id, kind="add", confirmed_by="analyst-4")
        self.assertEqual(commit.committed_count, 2)
        self.assertTrue(all(isinstance(item, WriteResult) for item in commit.per_item_results))

        claims = self.kg.query_claims(self.runtime_session_id, pred_id="user:tag")
        self.assertEqual(len(claims), 2)
        merged_claim = next(
            claim for claim in claims if ":merged_from:" in str(claim.meta.get("source", ""))
        )
        self.assertIn(":merged_from:1", merged_claim.meta["source"])
        self.assertIn(staging.segments[0].segment_id, merged_claim.meta["source_loc"])
        self.assertIn(staging.segments[1].segment_id, merged_claim.meta["source_loc"])

    def test_build_layer3a_tool_registry_exposes_forty_five_tools(self) -> None:
        tool_registry = build_layer3a_tool_registry(orchestrator=self.orchestrator)
        self.assertEqual(len(tool_registry), 45)
        self.assertIn("resolve_batch_extraction", tool_registry)
        self.assertIn("extract_resolve_and_create_document_bundle", tool_registry)


if __name__ == "__main__":
    unittest.main()
