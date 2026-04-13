from __future__ import annotations

import re

from ..clarity import compute_structural_clarity, detect_section_label
from ..models import DocumentSegment, DocumentSource
from .base import ParseError


class PlainTextParser:
    parser_name = "txt"
    parser_version = "0.1.0"
    supported_doc_types = ("txt", "md")

    def can_parse(self, doc_type: str) -> bool:
        return doc_type in self.supported_doc_types

    def parse(
        self,
        source: DocumentSource,
        content: bytes,
    ) -> list[DocumentSegment]:
        text = _decode_text(content)
        if not text.strip():
            raise ParseError("empty_document", "document has no extractable text")

        segments: list[DocumentSegment] = []
        for segment_index, (start, end, raw_text) in enumerate(_paragraph_ranges(text)):
            clarity, pattern_type = compute_structural_clarity(raw_text)
            segments.append(
                DocumentSegment(
                    segment_id=f"{source.doc_id[:8]}_{segment_index:04d}",
                    doc_id=source.doc_id,
                    segment_index=segment_index,
                    section_label=detect_section_label(raw_text),
                    page_number=None,
                    char_offset_start=start,
                    char_offset_end=end,
                    raw_text=raw_text,
                    structural_clarity=clarity,
                    pattern_type=pattern_type,
                    parser_version=self.parser_version,
                )
            )

        if not segments:
            raise ParseError("empty_document", "document has no extractable text")
        return segments


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("parse_failure", "unable to decode text content")


def _paragraph_ranges(text: str) -> list[tuple[int, int, str]]:
    segments: list[tuple[int, int, str]] = []
    start = 0
    for match in re.finditer(r"\n\s*\n+", text):
        _append_range(text, start, match.start(), segments)
        start = match.end()
    _append_range(text, start, len(text), segments)
    return segments


def _append_range(
    text: str,
    start: int,
    end: int,
    segments: list[tuple[int, int, str]],
) -> None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start >= end:
        return
    segments.append((start, end, text[start:end]))
