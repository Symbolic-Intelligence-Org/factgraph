"""Layer 4C1 document staging model tests."""

from __future__ import annotations

import unittest

from factpy.agent import DocumentSegment, DocumentSource, StagingError, StagingResult


class AgentLayer4C1ModelTests(unittest.TestCase):
    def test_model_fields_roundtrip(self) -> None:
        source = DocumentSource(
            doc_id="abc123def4567890",
            doc_name="sample.txt",
            doc_type="txt",
            byte_size=42,
            ingested_at=123,
        )
        segment = DocumentSegment(
            segment_id="abc123de_0000",
            doc_id=source.doc_id,
            segment_index=0,
            section_label="Intro",
            page_number=None,
            char_offset_start=0,
            char_offset_end=12,
            raw_text="Hello world.",
            structural_clarity=0.2,
            pattern_type="narrative",
            parser_version="0.1.0",
        )
        result = StagingResult(
            source=source,
            segments=(segment,),
            total_chars=12,
            high_clarity_count=0,
            parser_name="txt",
            parser_version="0.1.0",
            staged_at=456,
        )
        error = StagingError(
            doc_name="broken.pdf",
            error_kind="unsupported_format",
            error_message="unsupported format: pdf",
        )

        self.assertEqual(result.source.doc_id, source.doc_id)
        self.assertEqual(result.segments[0].segment_id, "abc123de_0000")
        self.assertEqual(error.error_kind, "unsupported_format")


if __name__ == "__main__":
    unittest.main()
