from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..errors import AgentContractError


@dataclass(frozen=True)
class DocumentSource:
    doc_id: str
    doc_name: str
    doc_type: Literal["pdf", "docx", "txt", "md"]
    byte_size: int
    ingested_at: int


@dataclass(frozen=True)
class DocumentSegment:
    segment_id: str
    doc_id: str
    segment_index: int
    section_label: str | None
    page_number: int | None
    char_offset_start: int
    char_offset_end: int
    raw_text: str
    structural_clarity: float
    pattern_type: Literal["if_then", "entity_relation", "definition", "narrative"]
    parser_version: str


@dataclass(frozen=True)
class StagingResult:
    source: DocumentSource
    segments: tuple[DocumentSegment, ...]
    total_chars: int
    high_clarity_count: int
    parser_name: str
    parser_version: str
    staged_at: int


@dataclass(frozen=True)
class StagingError:
    doc_name: str
    error_kind: str
    error_message: str


@dataclass(frozen=True)
class ExtractionProvenance:
    source_document_id: str
    segment_id: str
    char_offset_start: int
    char_offset_end: int
    raw_text: str
    page_number: int | None = None
    extraction_method: Literal["manual", "llm_refined"] = "manual"
    merged_from: tuple["ExtractionProvenance", ...] = ()

    def all_sources(self) -> tuple["ExtractionProvenance", ...]:
        """Return all contributing provenance nodes recursively, deduped by segment_id."""

        flattened: list[ExtractionProvenance] = []
        seen_segment_ids: set[str] = set()

        def _walk(provenance: ExtractionProvenance) -> None:
            if provenance.segment_id in seen_segment_ids:
                return
            seen_segment_ids.add(provenance.segment_id)
            flattened.append(provenance)
            for nested in provenance.merged_from:
                _walk(nested)

        _walk(self)
        return tuple(flattened)

    def source_segment_ids(self) -> tuple[str, ...]:
        return tuple(provenance.segment_id for provenance in self.all_sources())

    def is_merged(self) -> bool:
        return bool(self.merged_from)

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "segment_id": self.segment_id,
            "char_offset_start": self.char_offset_start,
            "char_offset_end": self.char_offset_end,
            "raw_text": self.raw_text,
            "page_number": self.page_number,
            "extraction_method": self.extraction_method,
            "merged_from": [item.to_checkpoint() for item in self.merged_from],
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "ExtractionProvenance":
        if not isinstance(data, dict):
            raise AgentContractError("extraction_provenance checkpoint must be object")
        extraction_method = data.get("extraction_method", "manual")
        if extraction_method not in {"manual", "llm_refined"}:
            raise AgentContractError("extraction_method must be manual|llm_refined")
        merged_from_raw = data.get("merged_from", ())
        if not isinstance(merged_from_raw, (list, tuple)):
            raise AgentContractError("merged_from must be list|tuple when provided")
        return cls(
            source_document_id=_require_non_empty_str(
                data.get("source_document_id"), "source_document_id"
            ),
            segment_id=_require_non_empty_str(data.get("segment_id"), "segment_id"),
            char_offset_start=_require_non_negative_int(
                data.get("char_offset_start"), "char_offset_start"
            ),
            char_offset_end=_require_non_negative_int(
                data.get("char_offset_end"), "char_offset_end"
            ),
            raw_text=_require_non_empty_str(data.get("raw_text"), "raw_text"),
            page_number=_optional_non_negative_int(data.get("page_number"), "page_number"),
            extraction_method=extraction_method,
            merged_from=tuple(
                cls.from_checkpoint(_require_dict(item, "merged_from_item"))
                for item in merged_from_raw
            ),
        )


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value


def _require_non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AgentContractError(f"{name} must be non-negative int")
    return value


def _optional_non_negative_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    return _require_non_negative_int(value, name)


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentContractError(f"{name} must be object")
    return dict(value)
