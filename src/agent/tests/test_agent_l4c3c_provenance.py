"""Layer 4C3-c merged provenance tests."""

from __future__ import annotations

import unittest

from agent import ExtractionProvenance


def _prov(
    segment_id: str,
    *,
    start: int = 0,
    end: int = 10,
    raw_text: str | None = None,
    merged_from: tuple[ExtractionProvenance, ...] = (),
) -> ExtractionProvenance:
    return ExtractionProvenance(
        source_document_id="doc_1",
        segment_id=segment_id,
        char_offset_start=start,
        char_offset_end=end,
        raw_text=raw_text or f"text-{segment_id}",
        extraction_method="llm_refined",
        merged_from=merged_from,
    )


class AgentLayer4C3cProvenanceTests(unittest.TestCase):
    def test_all_sources_recursively_flattens_and_dedupes_by_segment_id(self) -> None:
        seg_3 = _prov("seg_3", start=20, end=30)
        seg_2 = _prov("seg_2", start=10, end=20, merged_from=(seg_3,))
        root = _prov("seg_1", merged_from=(seg_2, seg_3))

        all_sources = root.all_sources()

        self.assertEqual(tuple(item.segment_id for item in all_sources), ("seg_1", "seg_2", "seg_3"))
        self.assertEqual(root.source_segment_ids(), ("seg_1", "seg_2", "seg_3"))
        self.assertTrue(root.is_merged())

    def test_to_checkpoint_roundtrip_preserves_nested_merged_from(self) -> None:
        seg_3 = _prov("seg_3", start=20, end=30)
        seg_2 = _prov("seg_2", start=10, end=20, merged_from=(seg_3,))
        root = _prov("seg_1", merged_from=(seg_2,))

        restored = ExtractionProvenance.from_checkpoint(root.to_checkpoint())

        self.assertEqual(restored.segment_id, "seg_1")
        self.assertEqual(restored.source_segment_ids(), ("seg_1", "seg_2", "seg_3"))
        self.assertEqual(restored.merged_from[0].segment_id, "seg_2")


if __name__ == "__main__":
    unittest.main()
