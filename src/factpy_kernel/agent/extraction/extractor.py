from __future__ import annotations

from time import perf_counter_ns
from typing import Any

from ..documents import DocumentSegment, FactDraftSpec
from ..errors import AgentContractError
from ..observability import AgentTracer, NoOpTracer
from ..session import AgentScope
from .llm import build_default_llm_client, build_response_model
from .models import ExtractionConfig, ExtractionError, ExtractionRejection, ExtractionResult
from .prompts import build_messages, build_schema_summary, truncate_prompt_text
from .validation import validate_proposal


class ExtractionAgent:
    """Pure single-segment LLM extraction agent."""

    def __init__(
        self,
        *,
        config: ExtractionConfig | None = None,
        llm_client: Any | None = None,
        tracer: AgentTracer | None = None,
    ) -> None:
        self._config = config or ExtractionConfig()
        self._llm_client = llm_client
        self._tracer: AgentTracer = tracer or NoOpTracer()

    @property
    def config(self) -> ExtractionConfig:
        return self._config

    def extract_from_segment(
        self,
        *,
        segment: DocumentSegment,
        schema_ir: dict[str, Any],
        scope: AgentScope,
        config: ExtractionConfig | None = None,
        prior_entity_context: str = "",
        source_doc_name: str | None = None,
    ) -> ExtractionResult | ExtractionError:
        if not isinstance(segment, DocumentSegment):
            raise AgentContractError("segment must be DocumentSegment")
        if not isinstance(scope, AgentScope):
            raise AgentContractError("scope must be AgentScope")
        effective_config = config or self._config
        config_error = _validate_config(effective_config)
        if config_error is not None:
            return self._return_result(
                segment,
                ExtractionError(
                    segment_id=segment.segment_id,
                    error_kind="config_invalid",
                    error_message=config_error,
                ),
            )
        if not isinstance(schema_ir, dict) or not schema_ir:
            return self._return_result(
                segment,
                ExtractionError(
                    segment_id=segment.segment_id,
                    error_kind="config_invalid",
                    error_message="schema_ir must be non-empty object",
                ),
            )
        if not isinstance(segment.raw_text, str) or not segment.raw_text.strip():
            return self._return_result(
                segment,
                ExtractionError(
                    segment_id=segment.segment_id,
                    error_kind="config_invalid",
                    error_message="segment.raw_text must be non-empty",
                ),
            )

        try:
            response_model = build_response_model(schema_ir)
        except Exception as exc:
            return self._return_result(
                segment,
                ExtractionError(
                    segment_id=segment.segment_id,
                    error_kind="config_invalid",
                    error_message=f"unable to build response model: {exc}",
                ),
            )

        schema_summary = build_schema_summary(schema_ir)
        raw_text_for_llm = truncate_prompt_text(
            segment.raw_text,
            max_text_chars=effective_config.max_text_chars,
        )
        messages = build_messages(
            segment=segment,
            schema_summary=schema_summary,
            raw_text_for_llm=raw_text_for_llm,
            prior_entity_context=prior_entity_context,
            source_doc_name=source_doc_name,
        )

        if self._llm_client is None:
            try:
                llm_client = build_default_llm_client()
            except ImportError as exc:
                return self._return_result(
                    segment,
                    ExtractionError(
                        segment_id=segment.segment_id,
                        error_kind="dependency_missing",
                        error_message=f"extraction requires instructor and litellm: {exc}",
                    ),
                )
        else:
            llm_client = self._llm_client

        started_ns = perf_counter_ns()
        try:
            response = llm_client.chat.completions.create(
                model=effective_config.model,
                response_model=response_model,
                messages=messages,
                max_retries=effective_config.max_retries,
                temperature=effective_config.temperature,
                max_tokens=effective_config.max_tokens,
                timeout=effective_config.timeout_seconds,
            )
        except TimeoutError as exc:
            return self._return_result(
                segment,
                ExtractionError(
                    segment_id=segment.segment_id,
                    error_kind="llm_timeout",
                    error_message=str(exc) or "llm timeout",
                ),
            )
        except Exception as exc:
            kind = _classify_llm_exception(exc)
            return self._return_result(
                segment,
                ExtractionError(
                    segment_id=segment.segment_id,
                    error_kind=kind,
                    error_message=str(exc) or kind,
                ),
            )
        llm_latency_ms = max(0, int((perf_counter_ns() - started_ns) / 1_000_000))

        proposals = _extract_proposals(response)
        total_proposals = len(proposals)
        accepted: list[tuple[int, FactDraftSpec]] = []
        rejections: list[ExtractionRejection] = []
        for proposal_index, proposal in enumerate(proposals):
            try:
                spec, rejection = validate_proposal(
                    proposal,
                    proposal_index,
                    schema_ir=schema_ir,
                    scope=scope,
                    segment=segment,
                )
            except AgentContractError as exc:
                rejection = ExtractionRejection(
                    reason="spec_construction_failure",
                    detail=str(exc),
                    proposal_index=proposal_index,
                )
                spec = None
            if rejection is not None:
                rejections.append(rejection)
                continue
            assert spec is not None
            accepted.append((proposal_index, spec))

        valid_specs: list[FactDraftSpec] = []
        for keep_index, (proposal_index, spec) in enumerate(accepted):
            if keep_index < scope.max_batch_size:
                valid_specs.append(spec)
            else:
                rejections.append(
                    ExtractionRejection(
                        reason="scope_max_batch_size",
                        detail=f"proposal exceeds scope.max_batch_size={scope.max_batch_size}",
                        proposal_index=proposal_index,
                    )
                )

        return self._return_result(
            segment,
            ExtractionResult(
                segment_id=segment.segment_id,
                valid_specs=valid_specs,
                total_proposals=total_proposals,
                rejections=sorted(rejections, key=lambda item: item.proposal_index),
                model=effective_config.model,
                llm_latency_ms=llm_latency_ms,
            ),
        )

    def _return_result(
        self,
        segment: DocumentSegment,
        result: ExtractionResult | ExtractionError,
    ) -> ExtractionResult | ExtractionError:
        self._emit_single_segment_trace(segment, result)
        return result

    def _emit_single_segment_trace(
        self,
        segment: DocumentSegment,
        result: ExtractionResult | ExtractionError,
    ) -> None:
        try:
            if isinstance(result, ExtractionResult):
                attributes = {
                    "segment_id": segment.segment_id,
                    "doc_id": segment.doc_id,
                    "model": result.model,
                    "llm_latency_ms": result.llm_latency_ms,
                    "proposal_count": result.total_proposals,
                    "valid_count": len(result.valid_specs),
                    "rejection_count": len(result.rejections),
                    "error_kind": None,
                    "structural_clarity": segment.structural_clarity,
                    "pattern_type": segment.pattern_type,
                }
            else:
                attributes = {
                    "segment_id": segment.segment_id,
                    "doc_id": segment.doc_id,
                    "model": None,
                    "llm_latency_ms": None,
                    "proposal_count": 0,
                    "valid_count": 0,
                    "rejection_count": 0,
                    "error_kind": result.error_kind,
                    "structural_clarity": segment.structural_clarity,
                    "pattern_type": segment.pattern_type,
                }
            self._tracer.record_single_segment_extraction(attributes=attributes)
        except Exception:
            return


def _extract_proposals(response: Any) -> list[Any]:
    if isinstance(response, dict):
        proposals = response.get("proposals", [])
    else:
        proposals = getattr(response, "proposals", [])
    if not isinstance(proposals, list):
        raise AgentContractError("LLM response proposals must be list")
    return list(proposals)


def _validate_config(config: ExtractionConfig) -> str | None:
    if not isinstance(config.model, str) or not config.model:
        return "config.model must be non-empty string"
    if not isinstance(config.max_retries, int) or config.max_retries < 0:
        return "config.max_retries must be non-negative int"
    if isinstance(config.temperature, bool) or not isinstance(config.temperature, (int, float)):
        return "config.temperature must be float"
    if not (0.0 <= float(config.temperature) <= 2.0):
        return "config.temperature must be in [0, 2]"
    if config.max_tokens is not None and (
        not isinstance(config.max_tokens, int) or config.max_tokens <= 0
    ):
        return "config.max_tokens must be positive int when provided"
    if isinstance(config.timeout_seconds, bool) or not isinstance(config.timeout_seconds, (int, float)):
        return "config.timeout_seconds must be float"
    if float(config.timeout_seconds) <= 0:
        return "config.timeout_seconds must be positive"
    if not isinstance(config.max_text_chars, int) or config.max_text_chars <= 0:
        return "config.max_text_chars must be positive int"
    return None


def _classify_llm_exception(exc: Exception) -> str:
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if "timeout" in name or "timeout" in message:
        return "llm_timeout"
    if "retry" in name or "retry" in message:
        return "instructor_retry_exhausted"
    return "llm_unavailable"
