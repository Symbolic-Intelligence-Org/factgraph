"""Layer 4C2 document bundle workflow tests."""

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
    ExtractionProvenance,
    FactDraftSpec,
    ReadReviewOrchestrator,
    RuntimeBootstrapSpec,
    WriteResult,
    WriteTools,
    recover_agent_session,
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


def _open_session(open_dto: dict[str, object]) -> str:
    resp = open_runtime_session(open_dto)
    assert resp["ok"], resp
    return resp["session"]["session_id"]


class AgentLayer4C2WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_l4c2.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.open_dto = {"schema_ir": _schema_ir(), "ledger_path": self.ledger_path}
        self.runtime_session_id = _open_session(self.open_dto)

        self.agent_session = AgentSession(
            scope=AgentScope(
                agent_id="agent-l4c2",
                allowed_entity_types=frozenset({"User"}),
                allowed_pred_ids=frozenset({"user:tag"}),
                require_source=True,
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
                b"Bob is a staff user."
            ),
        )
        self.assertFalse(hasattr(result, "error_kind"))
        return result

    def _spec_from_segment(self, *, user_id: str, locale: str, tag: str, segment) -> FactDraftSpec:
        return FactDraftSpec(
            entity_type="User",
            entity_identity={"user_id": user_id, "locale": locale},
            pred_id="user:tag",
            field_values=[("string", tag)],
            extraction_provenance=ExtractionProvenance(
                source_document_id=segment.doc_id,
                segment_id=segment.segment_id,
                char_offset_start=segment.char_offset_start,
                char_offset_end=segment.char_offset_end,
                raw_text=segment.raw_text,
                page_number=segment.page_number,
                extraction_method="manual",
            ),
            note="from staged segment",
            conversation_turn=1,
        )

    def test_create_document_bundle_checkpoints_bundle_state(self) -> None:
        staging = self._stage()
        bundle = self.orchestrator.create_document_bundle(
            source_document_id=staging.source.doc_id,
            source_document_name=staging.source.doc_name,
            facts=[
                self._spec_from_segment(
                    user_id="u-doc-1",
                    locale="zh",
                    tag="vip",
                    segment=staging.segments[0],
                )
            ],
        )
        restored_session, restored_drafts, restored_bundles = self.checkpoint.load(
            self.agent_session.agent_session_id
        )
        self.assertEqual(restored_session.runtime_session_id, self.runtime_session_id)
        self.assertEqual(len(restored_drafts.list_drafts(self.agent_session.agent_session_id)), 1)
        restored_bundle = restored_bundles.get_bundle(bundle.bundle_id)
        self.assertIsNotNone(restored_bundle)
        assert restored_bundle is not None
        self.assertEqual(restored_bundle.status, "created")

    def test_stage_bundle_review_commit_writes_claims_with_document_provenance(self) -> None:
        staging = self._stage()
        bundle = self.orchestrator.create_document_bundle(
            source_document_id=staging.source.doc_id,
            source_document_name=staging.source.doc_name,
            facts=[
                self._spec_from_segment(
                    user_id="u-doc-1",
                    locale="zh",
                    tag="vip",
                    segment=staging.segments[0],
                ),
                self._spec_from_segment(
                    user_id="u-doc-2",
                    locale="en",
                    tag="staff",
                    segment=staging.segments[1],
                ),
            ],
        )
        self.orchestrator.open_bundle_review(bundle.bundle_id)
        reviewed = self.orchestrator.apply_bundle_review(
            bundle.bundle_id,
            [
                BundleReviewAction(draft_id=bundle.draft_ids[0], action="approve"),
                BundleReviewAction(draft_id=bundle.draft_ids[1], action="reject"),
            ],
        )
        self.assertEqual(reviewed.status, "approved")
        result = self.orchestrator.commit_bundle(bundle.bundle_id, kind="add", confirmed_by="analyst-1")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.committed_count, 1)
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(result.failed_count, 0)
        self.assertIsInstance(result.per_item_results[0], WriteResult)

        claims = self.kg.query_claims(self.runtime_session_id, pred_id="user:tag")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].rest_terms, [("string", "vip")])
        self.assertEqual(
            claims[0].meta["source"],
            f"doc:{staging.source.doc_name}:seg:{staging.segments[0].segment_id}",
        )
        self.assertEqual(
            claims[0].meta["source_loc"],
            f"chars:{staging.segments[0].char_offset_start}-{staging.segments[0].char_offset_end}",
        )
        self.assertEqual(claims[0].meta["trace_id"], bundle.bundle_id)
        self.assertEqual(claims[0].meta["approved_by"], "analyst-1")
        self.assertEqual(claims[0].meta["agent_executor"], "agent-l4c2")

        committed = self.draft_manager.get_draft(bundle.draft_ids[0])
        rejected = self.draft_manager.get_draft(bundle.draft_ids[1])
        self.assertIsNotNone(committed)
        self.assertIsNotNone(rejected)
        assert committed is not None and rejected is not None
        self.assertEqual(committed.status, "committed")
        self.assertEqual(rejected.status, "rejected")

    def test_recover_agent_session_restores_bundle_manager(self) -> None:
        staging = self._stage()
        bundle = self.orchestrator.create_document_bundle(
            source_document_id=staging.source.doc_id,
            source_document_name=staging.source.doc_name,
            facts=[
                self._spec_from_segment(
                    user_id="u-doc-1",
                    locale="zh",
                    tag="vip",
                    segment=staging.segments[0],
                )
            ],
        )
        self.orchestrator.open_bundle_review(bundle.bundle_id)
        self.orchestrator.apply_bundle_review(
            bundle.bundle_id,
            [BundleReviewAction(draft_id=bundle.draft_ids[0], action="approve")],
        )

        close_runtime_session(self.runtime_session_id)
        result = recover_agent_session(self.agent_session.agent_session_id, db_path=self.db_path)
        self.addCleanup(result.candidate_cache.close)
        self.runtime_session_id = result.session.runtime_session_id

        recovered_bundle = result.bundle_manager.get_bundle(bundle.bundle_id)
        self.assertIsNotNone(recovered_bundle)
        assert recovered_bundle is not None
        self.assertEqual(recovered_bundle.status, "approved")
        self.assertEqual(recovered_bundle.approved_draft_ids, [bundle.draft_ids[0]])


if __name__ == "__main__":
    unittest.main()
