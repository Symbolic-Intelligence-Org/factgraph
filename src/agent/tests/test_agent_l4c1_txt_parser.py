"""Layer 4C1 plain text parser tests."""

from __future__ import annotations

import unittest

from agent.documents.models import DocumentSource
from agent.documents.parsers.txt import PlainTextParser


class AgentLayer4C1TxtParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = PlainTextParser()
        self.source = DocumentSource(
            doc_id="abcdef0123456789",
            doc_name="sample.md",
            doc_type="md",
            byte_size=0,
            ingested_at=1,
        )

    def test_parse_splits_on_blank_lines_and_preserves_offsets(self) -> None:
        text = "# Intro\nIf user is vip then notify.\n\nAlice owns account.\n\nNarrative details."
        segments = self.parser.parse(self.source, text.encode("utf-8"))
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].section_label, "Intro")
        self.assertEqual(segments[0].pattern_type, "if_then")
        self.assertEqual(text[segments[1].char_offset_start : segments[1].char_offset_end], "Alice owns account.")
        self.assertEqual(segments[1].pattern_type, "entity_relation")

    def test_parse_is_deterministic(self) -> None:
        payload = b"Line one.\n\nLine two."
        first = self.parser.parse(self.source, payload)
        second = self.parser.parse(self.source, payload)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
