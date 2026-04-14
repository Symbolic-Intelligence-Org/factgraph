"""High-level extraction API for product use.

Usage (Python classes):
    from factpy_kernel.agent.extraction import extract_document
    result = extract_document(content=..., doc_name="readme.pdf", schema_classes=[Document, Module])

Usage (pre-compiled schema_ir, for HTTP endpoint):
    from factpy_kernel.agent.extraction import extract_document_from_ir
    result = extract_document_from_ir(content=..., doc_name="readme.pdf", schema_ir={...})
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from factpy_kernel.sdk.compile import compile_schema_from_classes

from ..documents import DocumentStaging, StagingError
from ..session import AgentScope
from .batch import BatchExtractor
from .extractor import ExtractionAgent
from .metrics import BatchExtractionMetrics
from .models import (
    BatchExtractionConfig,
    BatchExtractionError,
    ExtractionConfig,
)
from .resolution import EntityResolver, MergeEvent, ResolutionConfig, ResolutionError


class ExtractionDocumentError(Exception):
    """Raised when extract_document fails at any pipeline stage."""

    def __init__(self, stage: str, detail: object, message: str) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(message)


@dataclass(frozen=True)
class ExtractionDocumentResult:
    """Result of a complete document extraction pipeline."""

    doc_name: str
    doc_id: str
    entities: tuple[dict[str, object], ...]
    facts: tuple[Any, ...]
    metrics: BatchExtractionMetrics
    merge_events: tuple[MergeEvent, ...]
    gleaning_segments_reexamined: int
    staging_segments: int
    model: str


def _resolve_config_value(
    explicit: object,
    config_val: object,
    env_key: str,
    default: object,
    *,
    coerce: type | None = None,
) -> object:
    if explicit is not None:
        return explicit
    if config_val is not None:
        return config_val
    env_raw = os.environ.get(env_key)
    if env_raw is not None and env_raw != "":
        return coerce(env_raw) if coerce else env_raw
    return default


def _run_extraction_pipeline(
    *,
    schema_ir: dict[str, Any],
    content: bytes,
    doc_name: str,
    model: str | None = None,
    temperature: float | None = None,
    timeout_seconds: float | None = None,
    entity_descriptions: dict[str, str] | None = None,
    allowed_entity_types: frozenset[str] | None = None,
    allowed_pred_ids: frozenset[str] | None = None,
    enable_gleaning: bool = True,
    enable_alias_merge: bool = True,
    max_batch_size: int = 1000,
    require_source: bool = True,
    extraction_config: ExtractionConfig | None = None,
) -> ExtractionDocumentResult:
    """Shared pipeline: staging -> extraction -> resolution.

    Both extract_document() and extract_document_from_ir() delegate here.
    """
    if allowed_entity_types is None:
        allowed_entity_types = frozenset(
            entity["entity_type"]
            for entity in schema_ir.get("entities", [])
            if isinstance(entity, dict) and isinstance(entity.get("entity_type"), str)
        )
    if allowed_pred_ids is None:
        allowed_pred_ids = frozenset(
            predicate["pred_id"]
            for predicate in schema_ir.get("predicates", [])
            if isinstance(predicate, dict) and isinstance(predicate.get("pred_id"), str)
        )

    defaults = ExtractionConfig()
    effective_model = _resolve_config_value(
        model,
        extraction_config.model if extraction_config else None,
        "FACTPY_EXTRACTION_MODEL",
        defaults.model,
    )
    effective_temperature = _resolve_config_value(
        temperature,
        extraction_config.temperature if extraction_config else None,
        "FACTPY_EXTRACTION_TEMPERATURE",
        defaults.temperature,
        coerce=float,
    )
    effective_timeout = _resolve_config_value(
        timeout_seconds,
        extraction_config.timeout_seconds if extraction_config else None,
        "FACTPY_EXTRACTION_TIMEOUT",
        defaults.timeout_seconds,
        coerce=float,
    )

    config = ExtractionConfig(
        model=str(effective_model),
        temperature=float(effective_temperature),
        timeout_seconds=float(effective_timeout),
        max_retries=extraction_config.max_retries if extraction_config else defaults.max_retries,
        max_tokens=extraction_config.max_tokens if extraction_config else defaults.max_tokens,
        max_text_chars=(
            extraction_config.max_text_chars if extraction_config else defaults.max_text_chars
        ),
    )

    scope = AgentScope(
        agent_id="extract_document",
        allowed_entity_types=allowed_entity_types,
        allowed_pred_ids=allowed_pred_ids,
        max_batch_size=max_batch_size,
        require_source=require_source,
    )

    staging = DocumentStaging().stage_document(doc_name=doc_name, content=content)
    if isinstance(staging, StagingError):
        raise ExtractionDocumentError(
            "staging",
            staging,
            f"Staging failed: {staging.error_message}",
        )

    extractor = BatchExtractor(
        extraction_agent=ExtractionAgent(config=config),
        batch_config=BatchExtractionConfig(
            enable_entity_context=True,
            enable_gleaning=enable_gleaning,
            gleaning_yield_threshold=0,
        ),
    )
    batch = extractor.extract_batch(
        segments=list(staging.segments),
        schema_ir=schema_ir,
        scope=scope,
        source_doc_name=doc_name,
        entity_descriptions=entity_descriptions,
    )
    if isinstance(batch, BatchExtractionError):
        raise ExtractionDocumentError(
            "extraction",
            batch,
            f"Extraction failed: {batch.error_message}",
        )

    resolver = EntityResolver(
        config=ResolutionConfig(
            enable_dedupe=True,
            enable_alias_merge=enable_alias_merge,
        ),
    )
    resolved = resolver.resolve_batch(list(batch.aggregated_specs))
    if isinstance(resolved, ResolutionError):
        raise ExtractionDocumentError(
            "resolution",
            resolved,
            f"Resolution failed: {resolved.error_message}",
        )

    entity_keys: dict[tuple[object, ...], dict[str, object]] = {}
    for spec in resolved.resolved_specs:
        key = (spec.entity_type, tuple(sorted(spec.entity_identity.items())))
        if key not in entity_keys:
            entity_keys[key] = {
                "entity_type": spec.entity_type,
                "identity": dict(spec.entity_identity),
                "fact_count": 0,
            }
        entity_keys[key]["fact_count"] += 1

    return ExtractionDocumentResult(
        doc_name=doc_name,
        doc_id=staging.source.doc_id,
        entities=tuple(entity_keys.values()),
        facts=tuple(resolved.resolved_specs),
        metrics=batch.metrics,
        merge_events=tuple(resolved.merge_events),
        gleaning_segments_reexamined=batch.gleaning_segments_reexamined,
        staging_segments=len(staging.segments),
        model=str(effective_model),
    )


def extract_document(
    *,
    content: bytes,
    doc_name: str,
    schema_classes: list[type],
    **kwargs: Any,
) -> ExtractionDocumentResult:
    """Extract structured facts from a document. Accepts Python Entity classes."""
    schema_ir = compile_schema_from_classes(schema_classes)
    return _run_extraction_pipeline(
        schema_ir=schema_ir,
        content=content,
        doc_name=doc_name,
        **kwargs,
    )


def extract_document_from_ir(
    *,
    content: bytes,
    doc_name: str,
    schema_ir: dict[str, Any],
    **kwargs: Any,
) -> ExtractionDocumentResult:
    """Extract structured facts from a document. Accepts pre-compiled schema_ir."""
    return _run_extraction_pipeline(
        schema_ir=schema_ir,
        content=content,
        doc_name=doc_name,
        **kwargs,
    )
