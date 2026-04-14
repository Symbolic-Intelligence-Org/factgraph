from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..documents import FactDraftSpec
from ..errors import AgentContractError
from .metrics import BatchExtractionMetrics


@dataclass(frozen=True)
class ExtractionConfig:
    """LLM extraction call configuration."""

    model: str = "gpt-4.1"
    max_retries: int = 2
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout_seconds: float = 30.0
    max_text_chars: int = 4000


@dataclass(frozen=True)
class ExtractionRejection:
    """Structured description for one rejected proposal."""

    reason: Literal[
        "schema_entity_type_unknown",
        "schema_pred_id_unknown",
        "schema_field_type_mismatch",
        "scope_entity_type_denied",
        "scope_pred_id_denied",
        "scope_min_confidence",
        "scope_max_batch_size",
        "spec_construction_failure",
    ]
    detail: str
    proposal_index: int

    def __post_init__(self) -> None:
        if not isinstance(self.detail, str) or not self.detail:
            raise AgentContractError("detail must be non-empty string")
        if not isinstance(self.proposal_index, int) or self.proposal_index < -1:
            raise AgentContractError("proposal_index must be int >= -1")


@dataclass(frozen=True)
class ExtractionResult:
    """Validated single-segment extraction result."""

    segment_id: str
    valid_specs: list[FactDraftSpec]
    total_proposals: int
    rejections: list[ExtractionRejection]
    model: str
    llm_latency_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not self.segment_id:
            raise AgentContractError("segment_id must be non-empty string")
        if not isinstance(self.valid_specs, list):
            raise AgentContractError("valid_specs must be list")
        if not isinstance(self.rejections, list):
            raise AgentContractError("rejections must be list")
        if not isinstance(self.total_proposals, int) or self.total_proposals < 0:
            raise AgentContractError("total_proposals must be non-negative int")
        if not isinstance(self.model, str) or not self.model:
            raise AgentContractError("model must be non-empty string")
        if not isinstance(self.llm_latency_ms, int) or self.llm_latency_ms < 0:
            raise AgentContractError("llm_latency_ms must be non-negative int")


@dataclass(frozen=True)
class ExtractionError:
    """Whole-call extraction failure."""

    segment_id: str
    error_kind: Literal[
        "llm_unavailable",
        "llm_timeout",
        "instructor_retry_exhausted",
        "config_invalid",
        "dependency_missing",
        "unexpected",
        "batch_cap_reached",
    ]
    error_message: str

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not self.segment_id:
            raise AgentContractError("segment_id must be non-empty string")
        if not isinstance(self.error_message, str) or not self.error_message:
            raise AgentContractError("error_message must be non-empty string")


@dataclass(frozen=True)
class BatchExtractionConfig:
    """Batch-level orchestration config for multi-segment extraction."""

    extraction_config: ExtractionConfig | None = None
    max_segments_per_batch: int = 1000
    early_stop_on_batch_cap_reached: bool = True
    enable_entity_context: bool = True
    enable_gleaning: bool = False
    gleaning_yield_threshold: int = 0

    def __post_init__(self) -> None:
        if self.extraction_config is not None and not isinstance(
            self.extraction_config, ExtractionConfig
        ):
            raise AgentContractError("extraction_config must be ExtractionConfig when provided")
        if (
            not isinstance(self.max_segments_per_batch, int)
            or self.max_segments_per_batch <= 0
        ):
            raise AgentContractError("max_segments_per_batch must be positive int")
        if not isinstance(self.early_stop_on_batch_cap_reached, bool):
            raise AgentContractError("early_stop_on_batch_cap_reached must be bool")
        if not isinstance(self.enable_entity_context, bool):
            raise AgentContractError("enable_entity_context must be bool")
        if not isinstance(self.enable_gleaning, bool):
            raise AgentContractError("enable_gleaning must be bool")
        if (
            not isinstance(self.gleaning_yield_threshold, int)
            or self.gleaning_yield_threshold < 0
        ):
            raise AgentContractError("gleaning_yield_threshold must be non-negative int")


@dataclass(frozen=True)
class BatchExtractionResult:
    """Validated batch extraction result for one document."""

    doc_id: str
    total_segments: int
    segment_results: tuple[ExtractionResult | ExtractionError, ...]
    aggregated_specs: tuple[FactDraftSpec, ...]
    metrics: BatchExtractionMetrics
    gleaning_segments_reexamined: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.doc_id, str) or not self.doc_id:
            raise AgentContractError("doc_id must be non-empty string")
        if not isinstance(self.total_segments, int) or self.total_segments < 0:
            raise AgentContractError("total_segments must be non-negative int")
        if not isinstance(self.segment_results, tuple):
            raise AgentContractError("segment_results must be tuple")
        if not isinstance(self.aggregated_specs, tuple):
            raise AgentContractError("aggregated_specs must be tuple")
        if not isinstance(self.metrics, BatchExtractionMetrics):
            raise AgentContractError("metrics must be BatchExtractionMetrics")
        if (
            not isinstance(self.gleaning_segments_reexamined, int)
            or self.gleaning_segments_reexamined < 0
        ):
            raise AgentContractError("gleaning_segments_reexamined must be non-negative int")

    def success_count(self) -> int:
        return sum(1 for item in self.segment_results if isinstance(item, ExtractionResult))

    def error_count(self) -> int:
        return sum(1 for item in self.segment_results if isinstance(item, ExtractionError))

    def has_any_valid(self) -> bool:
        return bool(self.aggregated_specs)


@dataclass(frozen=True)
class BatchExtractionError:
    """Batch-level preflight failure that prevents extraction from starting."""

    doc_id: str | None
    error_kind: Literal[
        "empty_segments",
        "doc_id_mismatch",
        "segments_exceed_limit",
        "config_invalid",
    ]
    error_message: str

    def __post_init__(self) -> None:
        if self.doc_id is not None and (not isinstance(self.doc_id, str) or not self.doc_id):
            raise AgentContractError("doc_id must be non-empty string when provided")
        if not isinstance(self.error_message, str) or not self.error_message:
            raise AgentContractError("error_message must be non-empty string")
