from __future__ import annotations

from dataclasses import dataclass, replace
from time import time_ns
from typing import Any, Literal

from ..documents import ExtractionProvenance, FactDraftSpec
from ..errors import AgentContractError
from ..observability import AgentTracer, NoOpTracer


@dataclass(frozen=True)
class MergeEvent:
    fact_key_repr: str
    primary_segment_id: str
    merged_segment_id: str
    entity_type: str
    pred_id: str
    alias_merge: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.fact_key_repr, str) or not self.fact_key_repr:
            raise AgentContractError("fact_key_repr must be non-empty string")
        if not isinstance(self.primary_segment_id, str) or not self.primary_segment_id:
            raise AgentContractError("primary_segment_id must be non-empty string")
        if not isinstance(self.merged_segment_id, str) or not self.merged_segment_id:
            raise AgentContractError("merged_segment_id must be non-empty string")
        if not isinstance(self.entity_type, str) or not self.entity_type:
            raise AgentContractError("entity_type must be non-empty string")
        if not isinstance(self.pred_id, str) or not self.pred_id:
            raise AgentContractError("pred_id must be non-empty string")
        if not isinstance(self.alias_merge, bool):
            raise AgentContractError("alias_merge must be bool")


@dataclass(frozen=True)
class ResolutionStats:
    input_spec_count: int
    output_spec_count: int
    merge_count: int
    unique_entity_count: int
    unique_fact_count: int
    resolution_duration_ms: int

    def __post_init__(self) -> None:
        for field_name in (
            "input_spec_count",
            "output_spec_count",
            "merge_count",
            "unique_entity_count",
            "unique_fact_count",
            "resolution_duration_ms",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise AgentContractError(f"{field_name} must be non-negative int")


@dataclass(frozen=True)
class ResolutionResult:
    doc_id: str
    resolved_specs: tuple[FactDraftSpec, ...]
    merge_events: tuple[MergeEvent, ...]
    stats: ResolutionStats

    def __post_init__(self) -> None:
        if not isinstance(self.doc_id, str) or not self.doc_id:
            raise AgentContractError("doc_id must be non-empty string")
        if not isinstance(self.resolved_specs, tuple):
            raise AgentContractError("resolved_specs must be tuple")
        if not isinstance(self.merge_events, tuple):
            raise AgentContractError("merge_events must be tuple")
        if not isinstance(self.stats, ResolutionStats):
            raise AgentContractError("stats must be ResolutionStats")

    def has_merges(self) -> bool:
        return self.stats.merge_count > 0


@dataclass(frozen=True)
class ResolutionError:
    doc_id: str | None
    error_kind: Literal["empty_specs", "doc_id_mismatch", "config_invalid"]
    error_message: str

    def __post_init__(self) -> None:
        if self.doc_id is not None and (not isinstance(self.doc_id, str) or not self.doc_id):
            raise AgentContractError("doc_id must be non-empty string when provided")
        if not isinstance(self.error_message, str) or not self.error_message:
            raise AgentContractError("error_message must be non-empty string")


@dataclass(frozen=True)
class ResolutionConfig:
    enable_dedupe: bool = True
    max_input_specs: int = 10000
    enable_alias_merge: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.enable_dedupe, bool):
            raise AgentContractError("enable_dedupe must be bool")
        if (
            isinstance(self.max_input_specs, bool)
            or not isinstance(self.max_input_specs, int)
            or self.max_input_specs <= 0
        ):
            raise AgentContractError("max_input_specs must be positive int")
        if not isinstance(self.enable_alias_merge, bool):
            raise AgentContractError("enable_alias_merge must be bool")


class EntityResolver:
    """Single-document deterministic dedupe + merge for extracted fact specs."""

    def __init__(
        self,
        *,
        config: ResolutionConfig | None = None,
        tracer: AgentTracer | None = None,
    ) -> None:
        if config is not None and not isinstance(config, ResolutionConfig):
            raise AgentContractError("config must be ResolutionConfig when provided")
        self._config = config or ResolutionConfig()
        self._tracer: AgentTracer = tracer or NoOpTracer()

    def resolve_batch(
        self,
        specs: list[FactDraftSpec],
        *,
        config: ResolutionConfig | None = None,
    ) -> ResolutionResult | ResolutionError:
        effective_config = config or self._config
        started_at_ns = time_ns()
        preflight = _validate_resolution_preflight(specs=specs, config=effective_config)
        if preflight is not None:
            return preflight

        assert isinstance(specs, list)
        assert isinstance(effective_config, ResolutionConfig)
        doc_id = specs[0].extraction_provenance.source_document_id

        if not effective_config.enable_dedupe:
            result = _build_resolution_result(
                doc_id=doc_id,
                resolved_specs=tuple(specs),
                merge_events=(),
                input_spec_count=len(specs),
                started_at_ns=started_at_ns,
            )
            self._emit_resolution_trace(result, effective_config)
            return result

        key_to_spec: dict[tuple[Any, str, tuple[tuple[str, Any], ...]], FactDraftSpec] = {}
        merge_events: list[MergeEvent] = []
        alias_map: dict[tuple[str, tuple[tuple[str, Any], ...]], tuple[str, tuple[tuple[str, Any], ...]]] = {}
        canonical_keys: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
        canonical_primary_segment_ids: dict[
            tuple[str, tuple[tuple[str, Any], ...]],
            str,
        ] = {}
        for spec in specs:
            raw_entity_key = _compute_entity_key(spec)
            is_alias = False
            alias_primary_segment_id: str | None = None

            if effective_config.enable_alias_merge:
                if raw_entity_key in alias_map:
                    canonical = alias_map[raw_entity_key]
                    is_alias = canonical != raw_entity_key
                else:
                    matched = False
                    for canonical in canonical_keys:
                        if _is_entity_alias(raw_entity_key, canonical):
                            alias_map[raw_entity_key] = canonical
                            is_alias = True
                            matched = True
                            break
                    if not matched:
                        alias_map[raw_entity_key] = raw_entity_key
                        canonical_keys.append(raw_entity_key)
                        canonical_primary_segment_ids[raw_entity_key] = (
                            spec.extraction_provenance.segment_id
                        )
                entity_key = alias_map[raw_entity_key]
                if is_alias:
                    alias_primary_segment_id = canonical_primary_segment_ids.get(entity_key)
            else:
                entity_key = raw_entity_key

            if entity_key != raw_entity_key:
                spec = replace(spec, entity_identity=dict(entity_key[1]))

            field_items = tuple((tag, value) for tag, value in spec.field_values)
            fact_key = (entity_key, spec.pred_id, field_items)
            current = key_to_spec.get(fact_key)
            if current is None:
                key_to_spec[fact_key] = spec
                if is_alias and alias_primary_segment_id is not None:
                    merge_events.append(
                        MergeEvent(
                            fact_key_repr=repr(fact_key),
                            primary_segment_id=alias_primary_segment_id,
                            merged_segment_id=spec.extraction_provenance.segment_id,
                            entity_type=spec.entity_type,
                            pred_id=spec.pred_id,
                            alias_merge=True,
                        )
                    )
                continue
            merged = _merge_specs(current, spec)
            key_to_spec[fact_key] = merged
            merge_events.append(
                MergeEvent(
                    fact_key_repr=repr(fact_key),
                    primary_segment_id=current.extraction_provenance.segment_id,
                    merged_segment_id=spec.extraction_provenance.segment_id,
                    entity_type=spec.entity_type,
                    pred_id=spec.pred_id,
                    alias_merge=is_alias,
                )
            )

        result = _build_resolution_result(
            doc_id=doc_id,
            resolved_specs=tuple(key_to_spec.values()),
            merge_events=tuple(merge_events),
            input_spec_count=len(specs),
            started_at_ns=started_at_ns,
        )
        self._emit_resolution_trace(result, effective_config)
        return result

    def _emit_resolution_trace(
        self,
        result: ResolutionResult,
        effective_config: ResolutionConfig,
    ) -> None:
        try:
            stats = result.stats
            attributes = {
                "doc_id": result.doc_id,
                "input_spec_count": stats.input_spec_count,
                "output_spec_count": stats.output_spec_count,
                "merge_count": stats.merge_count,
                "unique_entity_count": stats.unique_entity_count,
                "unique_fact_count": stats.unique_fact_count,
                "resolution_duration_ms": stats.resolution_duration_ms,
                "dedupe_enabled": effective_config.enable_dedupe,
            }
            self._tracer.record_resolution(attributes=attributes)
        except Exception:
            return


def _compute_entity_key(spec: FactDraftSpec) -> tuple[str, tuple[tuple[str, Any], ...]]:
    identity_items = tuple(sorted(spec.entity_identity.items(), key=lambda item: item[0]))
    return (spec.entity_type, identity_items)


def _compute_fact_key(spec: FactDraftSpec) -> tuple[Any, str, tuple[tuple[str, Any], ...]]:
    entity_key = _compute_entity_key(spec)
    field_items = tuple((tag, value) for tag, value in spec.field_values)
    return (entity_key, spec.pred_id, field_items)


def _is_entity_alias(
    key_a: tuple[str, tuple[tuple[str, Any], ...]],
    key_b: tuple[str, tuple[tuple[str, Any], ...]],
) -> bool:
    """Check if two entity keys are aliases (same type, token-subset identity).

    V1 restriction: only matches single-field string identities.
    """
    entity_type_a, identity_a = key_a
    entity_type_b, identity_b = key_b
    if entity_type_a != entity_type_b:
        return False
    if len(identity_a) != 1 or len(identity_b) != 1:
        return False
    val_a = str(identity_a[0][1]).lower()
    val_b = str(identity_b[0][1]).lower()
    if val_a == val_b:
        return False
    tokens_a = set(val_a.split())
    tokens_b = set(val_b.split())
    shorter, longer = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    return bool(shorter) and shorter.issubset(longer)


def _merge_specs(primary: FactDraftSpec, other: FactDraftSpec) -> FactDraftSpec:
    primary_prov = primary.extraction_provenance
    other_prov = other.extraction_provenance

    existing_segment_ids = set(primary_prov.source_segment_ids())
    additions: list[ExtractionProvenance] = []
    for candidate in other_prov.all_sources():
        if candidate.segment_id in existing_segment_ids:
            continue
        existing_segment_ids.add(candidate.segment_id)
        additions.append(candidate)

    new_provenance = replace(
        primary_prov,
        merged_from=(*primary_prov.merged_from, *additions),
    )

    if primary.confidence is None:
        new_confidence = other.confidence
    elif other.confidence is None:
        new_confidence = primary.confidence
    else:
        new_confidence = max(primary.confidence, other.confidence)

    return replace(
        primary,
        extraction_provenance=new_provenance,
        confidence=new_confidence,
    )


def _validate_resolution_preflight(
    *,
    specs: list[FactDraftSpec],
    config: ResolutionConfig,
) -> ResolutionError | None:
    doc_id: str | None = None
    if not isinstance(specs, list):
        return ResolutionError(
            doc_id=None,
            error_kind="config_invalid",
            error_message="specs must be list",
        )
    if not specs:
        return ResolutionError(
            doc_id=None,
            error_kind="empty_specs",
            error_message="specs must be non-empty list",
        )
    for spec in specs:
        if not isinstance(spec, FactDraftSpec):
            return ResolutionError(
                doc_id=None,
                error_kind="config_invalid",
                error_message="specs entries must be FactDraftSpec",
            )
    doc_id = specs[0].extraction_provenance.source_document_id
    if any(spec.extraction_provenance.source_document_id != doc_id for spec in specs):
        return ResolutionError(
            doc_id=None,
            error_kind="doc_id_mismatch",
            error_message="all specs must share the same source_document_id",
        )
    if not isinstance(config, ResolutionConfig):
        return ResolutionError(
            doc_id=doc_id,
            error_kind="config_invalid",
            error_message="config must be ResolutionConfig",
        )
    if len(specs) > config.max_input_specs:
        return ResolutionError(
            doc_id=doc_id,
            error_kind="config_invalid",
            error_message=f"specs exceed max_input_specs={config.max_input_specs}",
        )
    return None


def _build_resolution_result(
    *,
    doc_id: str,
    resolved_specs: tuple[FactDraftSpec, ...],
    merge_events: tuple[MergeEvent, ...],
    input_spec_count: int,
    started_at_ns: int,
) -> ResolutionResult:
    finished_at_ns = time_ns()
    entity_keys = {_compute_entity_key(spec) for spec in resolved_specs}
    stats = ResolutionStats(
        input_spec_count=input_spec_count,
        output_spec_count=len(resolved_specs),
        merge_count=len(merge_events),
        unique_entity_count=len(entity_keys),
        unique_fact_count=len(resolved_specs),
        resolution_duration_ms=max(0, int((finished_at_ns - started_at_ns) / 1_000_000)),
    )
    return ResolutionResult(
        doc_id=doc_id,
        resolved_specs=resolved_specs,
        merge_events=merge_events,
        stats=stats,
    )
