from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import TYPE_CHECKING, Any, Literal

from ..errors import AgentContractError

if TYPE_CHECKING:
    from factgraph.application.protocol.provenance_v1 import ProvenanceRefV1


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
        """Return all contributing nodes, deduped by document-plus-segment identity.

        ``segment_id`` is only locally meaningful inside one source document.
        Collapsing it globally would silently erase a contributing source when
        two documents happen to use the same segment identifier.
        """

        flattened: list[ExtractionProvenance] = []
        seen_source_segments: set[tuple[str, str]] = set()

        def _walk(provenance: ExtractionProvenance) -> None:
            source_key = (provenance.source_document_id, provenance.segment_id)
            if source_key in seen_source_segments:
                return
            seen_source_segments.add(source_key)
            flattened.append(provenance)
            for nested in provenance.merged_from:
                _walk(nested)

        _walk(self)
        return tuple(flattened)

    def source_segment_ids(self) -> tuple[str, ...]:
        """Return legacy display segment identifiers in first-seen source order.

        Callers that dedupe provenance must use the document-plus-segment
        identity carried by :meth:`all_sources`, not these display values.
        """

        return tuple(provenance.segment_id for provenance in self.all_sources())

    def is_merged(self) -> bool:
        return bool(self.merged_from)

    def to_factgraph_provenance_refs(self) -> tuple["ProvenanceRefV1", ...]:
        """Return bounded, FactGraph-neutral references for all source segments.

        This is deliberately a lazy bridge: document staging and Agent draft
        checkpointing continue to own ``raw_text`` and the legacy
        ``source/source_loc`` mirror.  The returned values contain only a
        stable opaque source token, a char/page locator, the SHA-256 of source
        text, and the neutral ``agent_extraction`` role.  They do not carry
        raw text, document names, ACLs, tenant data, admission decisions, or a
        SourceRecord-like object.

        Merged provenance is expanded through :meth:`all_sources` in its
        established first-seen order.  FactGraph's closed reference cap and
        full-wire deduplication are enforced before the tuple is returned.
        """

        # Import only on use: Agent documents remain independently usable in
        # environments that do not import the product Scenario/Explain layer.
        from factgraph.application.protocol.common import ProtocolShapeError
        from factgraph.application.protocol.provenance_v1 import (
            ProvenanceLocatorV1,
            ProvenanceRefV1,
            canonical_provenance_refs_v1,
        )

        references: list[ProvenanceRefV1] = []
        try:
            for source in self.all_sources():
                document_id = _require_non_empty_str(
                    source.source_document_id, "source_document_id"
                )
                segment_id = _require_non_empty_str(source.segment_id, "segment_id")
                start = _require_non_negative_int(source.char_offset_start, "char_offset_start")
                end = _require_non_negative_int(source.char_offset_end, "char_offset_end")
                if end < start:
                    raise AgentContractError("char_offset_end must not precede char_offset_start")
                raw_text = _require_non_empty_str(source.raw_text, "raw_text")
                page = _optional_non_negative_int(source.page_number, "page_number")
                locator_ref = f"chars:{start}-{end}"
                if page is not None:
                    locator_ref = f"page:{page}:{locator_ref}"
                references.append(
                    ProvenanceRefV1(
                        source_ref=_factgraph_source_ref(document_id, segment_id),
                        locator=ProvenanceLocatorV1.opaque(locator_ref),
                        origin_role="agent_extraction",
                        content_digest=f"sha256:{sha256(raw_text.encode('utf-8')).hexdigest()}",
                    )
                )
            return canonical_provenance_refs_v1(tuple(references))
        except AgentContractError:
            raise
        except (ProtocolShapeError, TypeError, ValueError, UnicodeError) as exc:
            raise AgentContractError(
                "extraction provenance cannot be converted to FactGraph-neutral references"
            ) from exc

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


def _factgraph_source_ref(document_id: str, segment_id: str) -> str:
    """Return a stable opaque bridge key without exposing document identifiers."""

    payload = json.dumps(
        {"document_id": document_id, "segment_id": segment_id},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"agent-document:{sha256(payload).hexdigest()}"
