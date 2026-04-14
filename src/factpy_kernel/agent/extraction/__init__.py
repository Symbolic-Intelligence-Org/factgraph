from __future__ import annotations

from .api import (
    ExtractionDocumentError,
    ExtractionDocumentResult,
    extract_document,
    extract_document_from_ir,
)
from .batch import BatchExtractor
from .extractor import ExtractionAgent
from .llm import build_response_model
from .metrics import BatchExtractionMetrics, SegmentMetric
from .models import (
    BatchExtractionConfig,
    BatchExtractionError,
    BatchExtractionResult,
    ExtractionConfig,
    ExtractionError,
    ExtractionRejection,
    ExtractionResult,
)
from .prompts import build_messages, build_schema_summary, truncate_prompt_text
from .resolution import (
    EntityResolver,
    MergeEvent,
    ResolutionConfig,
    ResolutionError,
    ResolutionResult,
    ResolutionStats,
)
from .validation import validate_proposal

__all__ = [
    "BatchExtractionConfig",
    "BatchExtractionError",
    "BatchExtractionMetrics",
    "BatchExtractionResult",
    "BatchExtractor",
    "ExtractionDocumentError",
    "ExtractionDocumentResult",
    "ExtractionAgent",
    "ExtractionConfig",
    "ExtractionError",
    "ExtractionRejection",
    "ExtractionResult",
    "EntityResolver",
    "MergeEvent",
    "ResolutionConfig",
    "ResolutionError",
    "ResolutionResult",
    "ResolutionStats",
    "SegmentMetric",
    "build_messages",
    "build_response_model",
    "build_schema_summary",
    "extract_document",
    "extract_document_from_ir",
    "truncate_prompt_text",
    "validate_proposal",
]
