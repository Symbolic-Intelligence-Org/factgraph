from __future__ import annotations

from io import BytesIO
from importlib.util import find_spec
from typing import Any

from ..clarity import compute_structural_clarity, detect_section_label
from ..models import DocumentSegment, DocumentSource
from .base import ParseError


def docx_parser_available() -> bool:
    return find_spec("docx") is not None


class PythonDocxParser:
    parser_name = "python_docx"
    parser_version = "0.1.0"
    supported_doc_types = ("docx",)

    def can_parse(self, doc_type: str) -> bool:
        return doc_type in self.supported_doc_types

    def parse(
        self,
        source: DocumentSource,
        content: bytes,
    ) -> list[DocumentSegment]:
        if not docx_parser_available():
            raise ParseError("unsupported_format", "python-docx dependency is unavailable")

        from factpy.agent.documents.parsers.docx import Document  # type: ignore[import-not-found]

        try:
            document = Document(BytesIO(content))
        except Exception as exc:  # pragma: no cover - library-specific parse failure
            raise ParseError("parse_failure", f"failed to parse docx: {exc}") from exc

        entries: list[tuple[str, str | None]] = []
        current_section: str | None = None
        for block in _iter_block_items(document):
            if _is_paragraph(block):
                text = block.text.strip()
                if not text:
                    continue
                style_name = getattr(getattr(block, "style", None), "name", "") or ""
                if style_name.lower().startswith("heading"):
                    current_section = text
                section_label = current_section or detect_section_label(text)
                entries.append((text, section_label))
                continue
            row_texts = _table_row_texts(block)
            for row_text in row_texts:
                entries.append((row_text, current_section))

        if not entries:
            raise ParseError("empty_document", "document has no extractable text")

        segments: list[DocumentSegment] = []
        cursor = 0
        for segment_index, (raw_text, section_label) in enumerate(entries):
            clarity, pattern_type = compute_structural_clarity(raw_text)
            start = cursor
            end = start + len(raw_text)
            segments.append(
                DocumentSegment(
                    segment_id=f"{source.doc_id[:8]}_{segment_index:04d}",
                    doc_id=source.doc_id,
                    segment_index=segment_index,
                    section_label=section_label,
                    page_number=None,
                    char_offset_start=start,
                    char_offset_end=end,
                    raw_text=raw_text,
                    structural_clarity=clarity,
                    pattern_type=pattern_type,
                    parser_version=self.parser_version,
                )
            )
            cursor = end + 2
        return segments


def _is_paragraph(block: Any) -> bool:
    return block.__class__.__name__ == "Paragraph"


def _iter_block_items(document: Any):
    from docx.document import Document as DocumentType  # type: ignore[import-not-found]
    from docx.table import Table  # type: ignore[import-not-found]
    from docx.text.paragraph import Paragraph  # type: ignore[import-not-found]

    if not isinstance(document, DocumentType):
        raise ParseError("parse_failure", "unexpected docx document type")

    parent_elm = document.element.body
    for child in parent_elm.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def _table_row_texts(table: Any) -> list[str]:
    rows: list[str] = []
    for row in getattr(table, "rows", []):
        cells = []
        for cell in getattr(row, "cells", []):
            text = " ".join(paragraph.text.strip() for paragraph in cell.paragraphs if paragraph.text.strip())
            cells.append(text)
        row_text = " | ".join(cell for cell in cells if cell)
        if row_text:
            rows.append(row_text)
    return rows
