from __future__ import annotations

from time import time_ns
from typing import Any

from ..documents import DocumentSegment
from ..errors import AgentContractError
from ..observability import AgentTracer, NoOpTracer
from ..session import AgentScope
from .extractor import ExtractionAgent
from .metrics import BatchExtractionMetrics, SegmentMetric
from .models import (
    BatchExtractionConfig,
    BatchExtractionError,
    BatchExtractionResult,
    ExtractionError,
    ExtractionRejection,
    ExtractionResult,
)
from .prompts import format_entity_context_header, format_gleaning_context


class BatchExtractor:
    """Sequential batch extraction orchestrator for one document."""

    def __init__(
        self,
        *,
        extraction_agent: ExtractionAgent,
        batch_config: BatchExtractionConfig | None = None,
        tracer: AgentTracer | None = None,
    ) -> None:
        if not isinstance(extraction_agent, ExtractionAgent):
            raise AgentContractError("extraction_agent must be ExtractionAgent")
        if batch_config is not None and not isinstance(batch_config, BatchExtractionConfig):
            raise AgentContractError("batch_config must be BatchExtractionConfig when provided")
        self._extraction_agent = extraction_agent
        self._batch_config = batch_config or BatchExtractionConfig()
        self._tracer: AgentTracer = tracer or NoOpTracer()

    def extract_batch(
        self,
        *,
        segments: list[DocumentSegment],
        schema_ir: dict[str, Any],
        scope: AgentScope,
        batch_config: BatchExtractionConfig | None = None,
        source_doc_name: str | None = None,
        entity_descriptions: dict[str, str] | None = None,
    ) -> BatchExtractionResult | BatchExtractionError:
        effective_config = batch_config or self._batch_config
        preflight_error = _validate_preflight(
            segments=segments,
            schema_ir=schema_ir,
            scope=scope,
            batch_config=effective_config,
        )
        if preflight_error is not None:
            return preflight_error

        assert isinstance(segments, list)
        assert isinstance(scope, AgentScope)
        assert isinstance(effective_config, BatchExtractionConfig)
        doc_id = segments[0].doc_id
        started_at_ns = time_ns()
        segment_results: list[ExtractionResult | ExtractionError] = []
        per_segment_metrics: list[SegmentMetric] = []
        aggregated_specs: list[Any] = []
        batch_cap_reached = False
        accumulated_valid_count = 0
        entity_accumulator: dict[tuple, dict[str, object]] = {}

        for segment in segments:
            if batch_cap_reached and effective_config.early_stop_on_batch_cap_reached:
                result = ExtractionError(
                    segment_id=segment.segment_id,
                    error_kind="batch_cap_reached",
                    error_message=f"batch cap reached at scope.max_batch_size={scope.max_batch_size}",
                )
                metric = _metric_from_error(result)
                segment_results.append(result)
                per_segment_metrics.append(metric)
                continue

            try:
                if effective_config.enable_entity_context and entity_accumulator:
                    prior_entity_context = format_entity_context_header(
                        list(entity_accumulator.values())
                    )
                else:
                    prior_entity_context = ""

                result = self._extraction_agent.extract_from_segment(
                    segment=segment,
                    schema_ir=schema_ir,
                    scope=scope,
                    config=effective_config.extraction_config,
                    prior_entity_context=prior_entity_context,
                    source_doc_name=source_doc_name,
                    entity_descriptions=entity_descriptions,
                )
                if isinstance(result, ExtractionResult):
                    remaining = max(0, scope.max_batch_size - accumulated_valid_count)
                    if len(result.valid_specs) <= remaining:
                        aggregated_specs.extend(result.valid_specs)
                        _accumulate_entities(entity_accumulator, result.valid_specs)
                        accumulated_valid_count += len(result.valid_specs)
                        metric = _metric_from_result(result)
                        if (
                            effective_config.early_stop_on_batch_cap_reached
                            and accumulated_valid_count >= scope.max_batch_size
                        ):
                            batch_cap_reached = True
                    else:
                        accepted = list(result.valid_specs[:remaining])
                        truncated_count = len(result.valid_specs) - len(accepted)
                        aggregated_specs.extend(accepted)
                        _accumulate_entities(entity_accumulator, accepted)
                        accumulated_valid_count += len(accepted)
                        result = _rebuild_with_batch_truncation(
                            result,
                            accepted=accepted,
                            batch_rejection=ExtractionRejection(
                                reason="scope_max_batch_size",
                                detail=(
                                    f"batch cap reached at accumulated valid count "
                                    f"{scope.max_batch_size}; truncated {truncated_count} "
                                    f"specs from segment {segment.segment_id}"
                                ),
                                proposal_index=-1,
                            ),
                        )
                        metric = _metric_from_result(result)
                        batch_cap_reached = True
                else:
                    metric = _metric_from_error(result)
            except Exception as exc:
                result = ExtractionError(
                    segment_id=segment.segment_id,
                    error_kind="unexpected",
                    error_message=str(exc) or "unexpected",
                )
                metric = _metric_from_error(result)

            segment_results.append(result)
            per_segment_metrics.append(metric)

        gleaning_count = 0
        if (
            effective_config.enable_gleaning
            and entity_accumulator
            and not batch_cap_reached
        ):
            for _gl_idx, (gl_segment, gl_pass1_result) in enumerate(
                zip(segments, segment_results)
            ):
                if not isinstance(gl_pass1_result, ExtractionResult):
                    continue
                if (
                    len(gl_pass1_result.valid_specs)
                    > effective_config.gleaning_yield_threshold
                ):
                    continue
                if accumulated_valid_count >= scope.max_batch_size:
                    break

                gleaning_context = format_gleaning_context(
                    entity_entries=list(entity_accumulator.values()),
                    pass1_yield=len(gl_pass1_result.valid_specs),
                )
                try:
                    gl_result = self._extraction_agent.extract_from_segment(
                        segment=gl_segment,
                        schema_ir=schema_ir,
                        scope=scope,
                        config=effective_config.extraction_config,
                        prior_entity_context=gleaning_context,
                        source_doc_name=source_doc_name,
                        entity_descriptions=entity_descriptions,
                    )
                except Exception:
                    gleaning_count += 1
                    continue

                if isinstance(gl_result, ExtractionResult) and gl_result.valid_specs:
                    remaining = max(0, scope.max_batch_size - accumulated_valid_count)
                    new_specs = gl_result.valid_specs[:remaining]
                    aggregated_specs.extend(new_specs)
                    _accumulate_entities(entity_accumulator, new_specs)
                    accumulated_valid_count += len(new_specs)

                gleaning_count += 1

        finished_at_ns = time_ns()
        metrics = BatchExtractionMetrics(
            doc_id=doc_id,
            total_segments=len(segments),
            success_segment_count=sum(
                1 for item in segment_results if isinstance(item, ExtractionResult)
            ),
            error_segment_count=sum(
                1 for item in segment_results if isinstance(item, ExtractionError)
            ),
            total_proposal_count=sum(metric.proposal_count for metric in per_segment_metrics),
            total_valid_count=sum(metric.valid_count for metric in per_segment_metrics),
            total_rejection_count=sum(metric.rejection_count for metric in per_segment_metrics),
            batch_started_at_ns=started_at_ns,
            batch_finished_at_ns=finished_at_ns,
            batch_duration_ms=max(0, int((finished_at_ns - started_at_ns) / 1_000_000)),
            per_segment_metrics=tuple(per_segment_metrics),
        )
        result = BatchExtractionResult(
            doc_id=doc_id,
            total_segments=len(segments),
            segment_results=tuple(segment_results),
            aggregated_specs=tuple(aggregated_specs),
            metrics=metrics,
            gleaning_segments_reexamined=gleaning_count,
        )
        self._emit_batch_trace(result)
        return result

    def _emit_batch_trace(self, result: BatchExtractionResult) -> None:
        try:
            metrics = result.metrics
            attributes = {
                "doc_id": metrics.doc_id,
                "total_segments": metrics.total_segments,
                "success_segment_count": metrics.success_segment_count,
                "error_segment_count": metrics.error_segment_count,
                "total_proposal_count": metrics.total_proposal_count,
                "total_valid_count": metrics.total_valid_count,
                "total_rejection_count": metrics.total_rejection_count,
                "batch_duration_ms": metrics.batch_duration_ms,
                "batch_cap_reached": self._detect_batch_cap_reached(result),
            }
            self._tracer.record_batch_extraction(attributes=attributes)
        except Exception:
            return

    @staticmethod
    def _detect_batch_cap_reached(result: BatchExtractionResult) -> bool:
        for segment_result in result.segment_results:
            if (
                isinstance(segment_result, ExtractionError)
                and segment_result.error_kind == "batch_cap_reached"
            ):
                return True
            if isinstance(segment_result, ExtractionResult):
                for rejection in segment_result.rejections:
                    if (
                        rejection.reason == "scope_max_batch_size"
                        and rejection.proposal_index == -1
                    ):
                        return True
        return False


def _validate_preflight(
    *,
    segments: list[DocumentSegment],
    schema_ir: dict[str, Any],
    scope: AgentScope,
    batch_config: BatchExtractionConfig,
) -> BatchExtractionError | None:
    doc_id: str | None = None
    if not isinstance(segments, list):
        return BatchExtractionError(
            doc_id=None,
            error_kind="config_invalid",
            error_message="segments must be list",
        )
    if not segments:
        return BatchExtractionError(
            doc_id=None,
            error_kind="empty_segments",
            error_message="segments must be non-empty list",
        )
    for segment in segments:
        if not isinstance(segment, DocumentSegment):
            return BatchExtractionError(
                doc_id=None,
                error_kind="config_invalid",
                error_message="segments entries must be DocumentSegment",
            )
    doc_id = segments[0].doc_id
    if any(segment.doc_id != doc_id for segment in segments):
        return BatchExtractionError(
            doc_id=None,
            error_kind="doc_id_mismatch",
            error_message="all segments must share the same doc_id",
        )
    if not isinstance(schema_ir, dict) or not schema_ir:
        return BatchExtractionError(
            doc_id=doc_id,
            error_kind="config_invalid",
            error_message="schema_ir must be non-empty object",
        )
    if not isinstance(scope, AgentScope):
        return BatchExtractionError(
            doc_id=doc_id,
            error_kind="config_invalid",
            error_message="scope must be AgentScope",
        )
    if not isinstance(batch_config, BatchExtractionConfig):
        return BatchExtractionError(
            doc_id=doc_id,
            error_kind="config_invalid",
            error_message="batch_config must be BatchExtractionConfig",
        )
    if len(segments) > batch_config.max_segments_per_batch:
        return BatchExtractionError(
            doc_id=doc_id,
            error_kind="segments_exceed_limit",
            error_message=(
                f"segments exceed max_segments_per_batch={batch_config.max_segments_per_batch}"
            ),
        )
    return None


def _metric_from_result(result: ExtractionResult) -> SegmentMetric:
    return SegmentMetric(
        segment_id=result.segment_id,
        model=result.model,
        llm_latency_ms=result.llm_latency_ms,
        proposal_count=result.total_proposals,
        valid_count=len(result.valid_specs),
        rejection_count=len(result.rejections),
        error_kind=None,
    )


def _metric_from_error(result: ExtractionError) -> SegmentMetric:
    return SegmentMetric(
        segment_id=result.segment_id,
        model=None,
        llm_latency_ms=None,
        proposal_count=0,
        valid_count=0,
        rejection_count=0,
        error_kind=result.error_kind,
    )


def _rebuild_with_batch_truncation(
    result: ExtractionResult,
    *,
    accepted: list[Any],
    batch_rejection: ExtractionRejection,
) -> ExtractionResult:
    return ExtractionResult(
        segment_id=result.segment_id,
        valid_specs=accepted,
        total_proposals=result.total_proposals,
        rejections=[*result.rejections, batch_rejection],
        model=result.model,
        llm_latency_ms=result.llm_latency_ms,
    )


def _accumulate_entities(
    accumulator: dict[tuple, dict[str, object]],
    specs: list[Any] | tuple[Any, ...],
) -> None:
    """Update the entity accumulator with newly extracted specs."""
    for spec in specs:
        entity_key = (
            spec.entity_type,
            tuple(sorted(spec.entity_identity.items())),
        )
        if entity_key not in accumulator:
            accumulator[entity_key] = {
                "entity_type": spec.entity_type,
                "identity": dict(spec.entity_identity),
                "facts": [],
            }
        if spec.field_values:
            _tag, first_val = spec.field_values[0]
            fact_repr = f'{spec.pred_id}="{first_val}"'
        else:
            fact_repr = spec.pred_id
        entry_facts = accumulator[entity_key]["facts"]
        if fact_repr not in entry_facts:
            entry_facts.append(fact_repr)
