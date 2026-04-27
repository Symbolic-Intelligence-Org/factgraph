"""Layer 4C2 bundle manager tests."""

from __future__ import annotations

import unittest

from agent import BundleManager, BundleReviewAction, DraftManager, ExtractionProvenance
from agent.documents.bundle import FactDraftSpec


class AgentLayer4C2BundleManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.draft_manager = DraftManager()
        self.bundle_manager = BundleManager(draft_manager=self.draft_manager)

    def _spec(self, user_id: str, segment_id: str, start: int, end: int) -> FactDraftSpec:
        return FactDraftSpec(
            entity_type="User",
            entity_identity={"user_id": user_id, "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            extraction_provenance=ExtractionProvenance(
                source_document_id="doc_1",
                segment_id=segment_id,
                char_offset_start=start,
                char_offset_end=end,
                raw_text=f"segment {segment_id}",
            ),
        )

    def test_create_bundle_registers_managed_drafts_with_normalized_source(self) -> None:
        bundle = self.bundle_manager.create_bundle(
            session_id="agent_1",
            source_document_id="doc_1",
            source_document_name="sample.txt",
            facts=[self._spec("u1", "seg_1", 0, 12), self._spec("u2", "seg_2", 13, 24)],
            created_by="agent-test",
        )
        self.assertEqual(bundle.status, "created")
        self.assertEqual(len(bundle.draft_ids), 2)

        first = self.draft_manager.get_draft(bundle.draft_ids[0])
        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(first.source, "doc:sample.txt:seg:seg_1")
        self.assertEqual(first.source_loc, "chars:0-12")
        self.assertIsNotNone(first.extraction_provenance)
        assert first.extraction_provenance is not None
        self.assertEqual(first.extraction_provenance.segment_id, "seg_1")

    def test_apply_review_tracks_approved_ids_without_confirming_draft(self) -> None:
        bundle = self.bundle_manager.create_bundle(
            session_id="agent_1",
            source_document_id="doc_1",
            source_document_name="sample.txt",
            facts=[self._spec("u1", "seg_1", 0, 12)],
            created_by="agent-test",
        )
        self.bundle_manager.open_review(bundle.bundle_id)
        reviewed = self.bundle_manager.apply_review(
            bundle.bundle_id,
            [BundleReviewAction(draft_id=bundle.draft_ids[0], action="approve")],
        )
        self.assertEqual(reviewed.status, "approved")
        self.assertEqual(reviewed.approved_draft_ids, [bundle.draft_ids[0]])
        draft = self.draft_manager.get_draft(bundle.draft_ids[0])
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.status, "pending")

    def test_apply_review_rejects_draft_and_updates_bundle_status(self) -> None:
        bundle = self.bundle_manager.create_bundle(
            session_id="agent_1",
            source_document_id="doc_1",
            source_document_name="sample.txt",
            facts=[self._spec("u1", "seg_1", 0, 12)],
            created_by="agent-test",
        )
        self.bundle_manager.open_review(bundle.bundle_id)
        reviewed = self.bundle_manager.apply_review(
            bundle.bundle_id,
            [BundleReviewAction(draft_id=bundle.draft_ids[0], action="reject")],
        )
        self.assertEqual(reviewed.status, "rejected")
        draft = self.draft_manager.get_draft(bundle.draft_ids[0])
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.status, "rejected")

    def test_abandon_bundle_rejects_pending_drafts(self) -> None:
        bundle = self.bundle_manager.create_bundle(
            session_id="agent_1",
            source_document_id="doc_1",
            source_document_name="sample.txt",
            facts=[self._spec("u1", "seg_1", 0, 12), self._spec("u2", "seg_2", 13, 24)],
            created_by="agent-test",
        )
        abandoned = self.bundle_manager.abandon_bundle(bundle.bundle_id, reason="operator cancel")
        self.assertEqual(abandoned.status, "abandoned")
        self.assertEqual(abandoned.approved_draft_ids, [])
        for draft_id in bundle.draft_ids:
            draft = self.draft_manager.get_draft(draft_id)
            self.assertIsNotNone(draft)
            assert draft is not None
            self.assertEqual(draft.status, "rejected")

    def test_bundle_manager_checkpoint_roundtrip(self) -> None:
        bundle = self.bundle_manager.create_bundle(
            session_id="agent_1",
            source_document_id="doc_1",
            source_document_name="sample.txt",
            facts=[self._spec("u1", "seg_1", 0, 12)],
            created_by="agent-test",
        )
        self.bundle_manager.open_review(bundle.bundle_id)
        self.bundle_manager.apply_review(
            bundle.bundle_id,
            [BundleReviewAction(draft_id=bundle.draft_ids[0], action="approve")],
        )
        restored = BundleManager.from_checkpoint(
            self.bundle_manager.to_checkpoint(),
            draft_manager=self.draft_manager,
        )
        restored_bundle = restored.get_bundle(bundle.bundle_id)
        self.assertIsNotNone(restored_bundle)
        assert restored_bundle is not None
        self.assertEqual(restored_bundle.status, "approved")
        self.assertEqual(restored_bundle.approved_draft_ids, [bundle.draft_ids[0]])


if __name__ == "__main__":
    unittest.main()
