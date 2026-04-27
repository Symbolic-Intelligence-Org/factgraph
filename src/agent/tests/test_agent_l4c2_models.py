"""Layer 4C2 document bundle model tests."""

from __future__ import annotations

import unittest

from agent import DraftBundle, ExtractionProvenance, FactDraft
from agent.documents.bundle import BundleCommitResult, BundleReviewAction, FactDraftSpec


class AgentLayer4C2ModelTests(unittest.TestCase):
    def test_extraction_provenance_roundtrip(self) -> None:
        provenance = ExtractionProvenance(
            source_document_id="doc_123",
            segment_id="seg_001",
            char_offset_start=12,
            char_offset_end=48,
            raw_text="If account is dormant then flag review.",
            page_number=2,
            extraction_method="manual",
        )
        restored = ExtractionProvenance.from_checkpoint(provenance.to_checkpoint())
        self.assertEqual(restored, provenance)

    def test_fact_draft_roundtrip_preserves_extraction_provenance(self) -> None:
        provenance = ExtractionProvenance(
            source_document_id="doc_123",
            segment_id="seg_001",
            char_offset_start=12,
            char_offset_end=48,
            raw_text="If account is dormant then flag review.",
        )
        draft = FactDraft(
            draft_id="draft_1",
            entity_type="User",
            entity_identity={"user_id": "u1", "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            confidence=0.8,
            source="doc:sample.txt:seg:seg_001",
            source_loc="chars:12-48",
            note="from document",
            created_at=1,
            status="pending",
            session_id="agent_1",
            conversation_turn=1,
            extraction_provenance=provenance,
        )
        restored = FactDraft.from_checkpoint(draft.to_checkpoint())
        self.assertEqual(restored.extraction_provenance, provenance)
        self.assertEqual(restored.source_loc, "chars:12-48")

    def test_fact_draft_spec_roundtrip(self) -> None:
        spec = FactDraftSpec(
            entity_type="User",
            entity_identity={"user_id": "u1", "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            extraction_provenance=ExtractionProvenance(
                source_document_id="doc_123",
                segment_id="seg_001",
                char_offset_start=0,
                char_offset_end=18,
                raw_text="VIP user paragraph",
            ),
            confidence=0.6,
            note="candidate",
            conversation_turn=3,
        )
        restored = FactDraftSpec.from_checkpoint(spec.to_checkpoint())
        self.assertEqual(restored.entity_type, "User")
        self.assertEqual(restored.extraction_provenance.segment_id, "seg_001")
        self.assertEqual(restored.note, "candidate")

    def test_draft_bundle_roundtrip_preserves_approved_ids(self) -> None:
        bundle = DraftBundle(
            bundle_id="bundle_1",
            source_document_id="doc_123",
            source_document_name="sample.txt",
            draft_ids=["draft_1", "draft_2"],
            approved_draft_ids=["draft_1"],
            created_at=10,
            created_by="agent",
            status="approved",
            confirmed_by="analyst-1",
            confirmed_at=11,
        )
        restored = DraftBundle.from_checkpoint(bundle.to_checkpoint())
        self.assertEqual(restored.approved_draft_ids, ["draft_1"])
        self.assertEqual(restored.status, "approved")

    def test_bundle_review_action_validates(self) -> None:
        action = BundleReviewAction(draft_id="draft_1", action="approve", note="looks good")
        self.assertEqual(action.action, "approve")

    def test_bundle_commit_result_tracks_rejected_count(self) -> None:
        result = BundleCommitResult(
            bundle_id="bundle_1",
            total=2,
            committed_count=1,
            rejected_count=1,
            failed_count=0,
            per_item_results=[],
            committed_at=20,
        )
        self.assertEqual(result.rejected_count, 1)


if __name__ == "__main__":
    unittest.main()
