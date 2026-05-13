"""Layer 4C3-c merged provenance -> meta source tests."""

from __future__ import annotations

import unittest

from factpy.agent import ExtractionProvenance
from factpy.agent.documents.bundle import _provenance_to_draft_source


class AgentLayer4C3cMergeMetaTests(unittest.TestCase):
    def test_single_source_provenance_uses_original_l4c2_format(self) -> None:
        provenance = ExtractionProvenance(
            source_document_id="doc_1",
            segment_id="seg_1",
            char_offset_start=0,
            char_offset_end=10,
            raw_text="Alice VIP",
        )

        source, source_loc = _provenance_to_draft_source(provenance, "sample.txt")

        self.assertEqual(source, "doc:sample.txt:seg:seg_1")
        self.assertEqual(source_loc, "chars:0-10")

    def test_merged_provenance_includes_merge_count_and_segment_list(self) -> None:
        provenance = ExtractionProvenance(
            source_document_id="doc_1",
            segment_id="seg_1",
            char_offset_start=0,
            char_offset_end=10,
            raw_text="Alice VIP",
            merged_from=(
                ExtractionProvenance(
                    source_document_id="doc_1",
                    segment_id="seg_2",
                    char_offset_start=20,
                    char_offset_end=30,
                    raw_text="Alice VIP again",
                ),
            ),
        )

        source, source_loc = _provenance_to_draft_source(provenance, "sample.txt")

        self.assertEqual(source, "doc:sample.txt:seg:seg_1:merged_from:1")
        self.assertEqual(source_loc, "chars:0-10:segments:seg_1,seg_2")


if __name__ == "__main__":
    unittest.main()
