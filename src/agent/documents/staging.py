from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from ..errors import AgentContractError
from .models import DocumentSegment, DocumentSource, StagingError, StagingResult
from .parsers import (
    DocumentParser,
    ParseError,
    PlainTextParser,
    PyMuPDFParser,
    PythonDocxParser,
    docx_parser_available,
    pdf_parser_available,
)


class DocumentStaging:
    """Deterministic document segmentation and provenance staging."""

    def __init__(self, parsers: list[DocumentParser] | None = None) -> None:
        self._parsers = list(parsers) if parsers is not None else _default_parsers()

    def stage_document(
        self,
        *,
        doc_name: str,
        content: bytes,
        doc_type: str | None = None,
    ) -> StagingResult | StagingError:
        if not isinstance(doc_name, str) or not doc_name:
            raise AgentContractError("doc_name must be non-empty string")
        if isinstance(content, bytearray):
            content = bytes(content)
        if not isinstance(content, bytes):
            raise AgentContractError("content must be bytes")

        normalized_doc_type = _normalize_doc_type(doc_type, doc_name)
        if normalized_doc_type is None:
            return StagingError(
                doc_name=doc_name,
                error_kind="unsupported_format",
                error_message=f"unsupported document format for {doc_name}",
            )

        parser = next((item for item in self._parsers if item.can_parse(normalized_doc_type)), None)
        if parser is None:
            return StagingError(
                doc_name=doc_name,
                error_kind="unsupported_format",
                error_message=f"unsupported format: {normalized_doc_type}",
            )

        source = DocumentSource(
            doc_id=hashlib.sha256(content).hexdigest()[:16],
            doc_name=doc_name,
            doc_type=normalized_doc_type,
            byte_size=len(content),
            ingested_at=time.time_ns(),
        )
        try:
            segments = parser.parse(source, content)
        except ParseError as exc:
            return StagingError(
                doc_name=doc_name,
                error_kind=exc.kind,
                error_message=exc.message,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            return StagingError(
                doc_name=doc_name,
                error_kind="parse_failure",
                error_message=str(exc),
            )

        if not segments:
            return StagingError(
                doc_name=doc_name,
                error_kind="empty_document",
                error_message="document has no extractable text",
            )

        return StagingResult(
            source=source,
            segments=tuple(segments),
            total_chars=max(segment.char_offset_end for segment in segments),
            high_clarity_count=sum(1 for segment in segments if segment.structural_clarity >= 0.7),
            parser_name=parser.parser_name,
            parser_version=parser.parser_version,
            staged_at=time.time_ns(),
        )

    def list_supported_formats(self) -> list[str]:
        out: list[str] = []
        for parser in self._parsers:
            for doc_type in getattr(parser, "supported_doc_types", ()):
                if doc_type not in out:
                    out.append(doc_type)
        return out


def _default_parsers() -> list[DocumentParser]:
    parsers: list[DocumentParser] = [PlainTextParser()]
    if pdf_parser_available():
        parsers.append(PyMuPDFParser())
    if docx_parser_available():
        parsers.append(PythonDocxParser())
    return parsers


def _normalize_doc_type(doc_type: str | None, doc_name: str) -> str | None:
    if doc_type is not None:
        candidate = str(doc_type).strip().lower().lstrip(".")
    else:
        suffix = Path(doc_name).suffix.lower().lstrip(".")
        candidate = {"markdown": "md", "text": "txt"}.get(suffix, suffix)
    if candidate in {"txt", "md", "pdf", "docx"}:
        return candidate
    return None
