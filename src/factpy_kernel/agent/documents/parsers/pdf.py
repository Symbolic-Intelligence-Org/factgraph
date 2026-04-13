from __future__ import annotations

from importlib.util import find_spec
from typing import Any

from ..clarity import compute_structural_clarity, detect_section_label
from ..models import DocumentSegment, DocumentSource
from .base import ParseError


def pdf_parser_available() -> bool:
    return (find_spec("fitz") is not None or find_spec("pymupdf") is not None) and find_spec("pymupdf4llm") is not None


class PyMuPDFParser:
    parser_name = "pymupdf"
    parser_version = "0.1.0"
    supported_doc_types = ("pdf",)

    def can_parse(self, doc_type: str) -> bool:
        return doc_type in self.supported_doc_types

    def parse(
        self,
        source: DocumentSource,
        content: bytes,
    ) -> list[DocumentSegment]:
        if not pdf_parser_available():
            raise ParseError("unsupported_format", "pymupdf/pymupdf4llm dependencies are unavailable")

        try:
            import fitz  # type: ignore[import-not-found]
            import pymupdf4llm  # type: ignore[import-not-found]  # noqa: F401
        except Exception as exc:  # pragma: no cover - guarded by availability check
            raise ParseError("unsupported_format", f"pdf dependencies unavailable: {exc}") from exc

        try:
            document = fitz.open(stream=content, filetype="pdf")
        except Exception as exc:  # pragma: no cover - library-specific parse failure
            raise ParseError("parse_failure", f"failed to parse pdf: {exc}") from exc

        segments: list[DocumentSegment] = []
        cursor = 0
        segment_index = 0
        for page_number, page in enumerate(document, start=1):
            for raw_text in _page_blocks(page):
                clarity, pattern_type = compute_structural_clarity(raw_text)
                start = cursor
                end = start + len(raw_text)
                segments.append(
                    DocumentSegment(
                        segment_id=f"{source.doc_id[:8]}_{segment_index:04d}",
                        doc_id=source.doc_id,
                        segment_index=segment_index,
                        section_label=detect_section_label(raw_text),
                        page_number=page_number,
                        char_offset_start=start,
                        char_offset_end=end,
                        raw_text=raw_text,
                        structural_clarity=clarity,
                        pattern_type=pattern_type,
                        parser_version=self.parser_version,
                    )
                )
                segment_index += 1
                cursor = end + 2

        if not segments:
            raise ParseError("empty_document", "document has no extractable text")
        return segments


def _page_blocks(page: Any) -> list[str]:
    blocks = page.get_text("blocks")
    out: list[str] = []
    for block in sorted(blocks, key=lambda item: (item[1], item[0])):
        if len(block) < 5:
            continue
        raw_text = str(block[4]).strip()
        if raw_text:
            out.append(raw_text)
    return out
