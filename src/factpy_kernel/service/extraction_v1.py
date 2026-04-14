"""Extraction HTTP endpoint handler."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from factpy_kernel.agent.extraction import (
    ExtractionDocumentError,
    ExtractionDocumentResult,
    extract_document_from_ir,
)
from factpy_kernel.service._common import error_response, ok_response


def extract_document_endpoint(
    file_bytes: bytes,
    doc_name: str,
    options: dict[str, Any],
) -> JSONResponse:
    """Handle POST /v1/extraction/documents.

    Receives already-parsed options dict and raw file bytes from the route layer.
    """
    if not isinstance(options, dict):
        return JSONResponse(
            status_code=422,
            content=error_response(
                [
                    {
                        "kind": "validation",
                        "path": "options",
                        "details": {"message": "options must decode to a JSON object"},
                    }
                ]
            ),
        )

    schema_ir = options.get("schema_ir")
    if not isinstance(schema_ir, dict) or not schema_ir:
        return JSONResponse(
            status_code=422,
            content=error_response(
                [
                    {
                        "kind": "validation",
                        "path": "options.schema_ir",
                        "details": {
                            "message": "options.schema_ir is required and must be a non-empty object"
                        },
                    }
                ]
            ),
        )

    try:
        result = extract_document_from_ir(
            content=file_bytes,
            doc_name=doc_name,
            schema_ir=schema_ir,
            model=options.get("model"),
            entity_descriptions=options.get("entity_descriptions"),
            enable_gleaning=options.get("enable_gleaning", True),
            enable_alias_merge=options.get("enable_alias_merge", True),
            max_batch_size=options.get("max_batch_size", 1000),
            require_source=options.get("require_source", True),
        )
    except ExtractionDocumentError as exc:
        return JSONResponse(
            status_code=500,
            content=error_response(
                [
                    {
                        "kind": "extraction",
                        "path": "$",
                        "details": {"stage": exc.stage, "message": str(exc)},
                    }
                ]
            ),
        )

    return JSONResponse(
        status_code=200,
        content=ok_response(result=_serialize_result(result)),
    )


def _serialize_result(result: ExtractionDocumentResult) -> dict[str, Any]:
    """Serialize ExtractionDocumentResult to JSON-safe dict."""
    facts = []
    for spec in result.facts:
        facts.append(
            {
                "entity_type": spec.entity_type,
                "entity_identity": dict(spec.entity_identity),
                "pred_id": spec.pred_id,
                "field_values": [[tag, value] for tag, value in spec.field_values],
                "confidence": spec.confidence,
            }
        )

    merge_events = []
    for event in result.merge_events:
        merge_events.append(
            {
                "fact_key_repr": event.fact_key_repr,
                "primary_segment_id": event.primary_segment_id,
                "merged_segment_id": event.merged_segment_id,
                "entity_type": event.entity_type,
                "pred_id": event.pred_id,
                "alias_merge": event.alias_merge,
            }
        )

    return {
        "doc_name": result.doc_name,
        "doc_id": result.doc_id,
        "model": result.model,
        "staging_segments": result.staging_segments,
        "gleaning_segments_reexamined": result.gleaning_segments_reexamined,
        "entities": list(result.entities),
        "facts": facts,
        "metrics": {
            "total_segments": result.metrics.total_segments,
            "success_segment_count": result.metrics.success_segment_count,
            "error_segment_count": result.metrics.error_segment_count,
            "total_proposal_count": result.metrics.total_proposal_count,
            "total_valid_count": result.metrics.total_valid_count,
            "total_rejection_count": result.metrics.total_rejection_count,
            "batch_duration_ms": result.metrics.batch_duration_ms,
        },
        "merge_events": merge_events,
    }
