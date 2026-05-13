from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..errors import AgentContractError


@dataclass(frozen=True)
class SegmentMetric:
    """Per-segment lightweight extraction metrics."""

    segment_id: str
    model: str | None
    llm_latency_ms: int | None
    proposal_count: int
    valid_count: int
    rejection_count: int
    error_kind: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not self.segment_id:
            raise AgentContractError("segment_id must be non-empty string")
        if self.model is not None and (not isinstance(self.model, str) or not self.model):
            raise AgentContractError("model must be non-empty string when provided")
        if self.llm_latency_ms is not None and (
            not isinstance(self.llm_latency_ms, int) or self.llm_latency_ms < 0
        ):
            raise AgentContractError("llm_latency_ms must be non-negative int when provided")
        if not isinstance(self.proposal_count, int) or self.proposal_count < 0:
            raise AgentContractError("proposal_count must be non-negative int")
        if not isinstance(self.valid_count, int) or self.valid_count < 0:
            raise AgentContractError("valid_count must be non-negative int")
        if not isinstance(self.rejection_count, int) or self.rejection_count < 0:
            raise AgentContractError("rejection_count must be non-negative int")
        if self.error_kind is not None and (not isinstance(self.error_kind, str) or not self.error_kind):
            raise AgentContractError("error_kind must be non-empty string when provided")


@dataclass(frozen=True)
class BatchExtractionMetrics:
    """Batch-level extraction metrics for one document."""

    doc_id: str
    total_segments: int
    success_segment_count: int
    error_segment_count: int
    total_proposal_count: int
    total_valid_count: int
    total_rejection_count: int
    batch_started_at_ns: int
    batch_finished_at_ns: int
    batch_duration_ms: int
    per_segment_metrics: tuple[SegmentMetric, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.doc_id, str) or not self.doc_id:
            raise AgentContractError("doc_id must be non-empty string")
        for name in (
            "total_segments",
            "success_segment_count",
            "error_segment_count",
            "total_proposal_count",
            "total_valid_count",
            "total_rejection_count",
            "batch_started_at_ns",
            "batch_finished_at_ns",
            "batch_duration_ms",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise AgentContractError(f"{name} must be non-negative int")
        if not isinstance(self.per_segment_metrics, tuple):
            raise AgentContractError("per_segment_metrics must be tuple")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "per_segment_metrics": [asdict(metric) for metric in self.per_segment_metrics],
        }
