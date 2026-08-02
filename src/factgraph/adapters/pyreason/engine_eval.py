"""PyReason engine evaluator for ``Store.evaluate(mode="pyreason")``."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from factgraph.core.semantics import SemanticsProfile
from factgraph.adapters.pyreason.runner import (
    PyReasonRunConfig,
    _bounded_pred_ids,
    _parse_bounded_float,
    run_pyreason,
)
from factgraph.adapters.pyreason.session import PyReasonSession
from factgraph.adapters.pyreason.where_compile import compile_where_ir_to_pyreason
from factgraph.core.derivation.candidates import CandidateSet, make_candidate
from factgraph.core.evidence.write_protocol import now_epoch_nanos
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.store import builders as store_builders
from factgraph.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
    PYREASON_PROVENANCE_KIND,
    ProjectedFact,
    ProvenanceEnvelope,
    compute_provenance_digest,
)
from factgraph.core.store.types import EngineExtBase
from factgraph.core.view.projector import project_view_facts, project_view_facts_with_witness

_ZERO_SUPPORT_DIGEST = f"sha256:{'0' * 64}"


@dataclass(frozen=True)
class _TemporalProjectionState:
    timesteps: int | None = None
    active_by_asrt_id: dict[str, tuple[int, int | None]] = field(default_factory=dict)


def pyreason_engine_eval(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: list[Any],
    where: list[Any],
    mode: str = "pyreason",
    head: dict[str, Any] | None = None,
    engine_ext: EngineExtBase | None = None,
    engine_options: dict[str, Any] | None = None,
    semantics_profile: SemanticsProfile | None = None,
) -> list[CandidateSet]:
    """Evaluate a derivation through the PyReason adapter."""
    del mode
    del head
    from factgraph.adapters.pyreason.rule_ext import PyReasonRuleExt, resolve_pyreason_engine_ext

    if engine_ext is not None and not isinstance(engine_ext, PyReasonRuleExt):
        raise ValueError(
            f"PyReason engine_ext must be PyReasonRuleExt, got {type(engine_ext).__name__}"
        )

    resolved_engine_ext = resolve_pyreason_engine_ext(
        where=where,
        schema_ir=store.schema_ir,
        engine_ext=engine_ext,
        semantics_profile=semantics_profile,
    )
    iteration_count = _resolve_iteration_count(semantics_profile)
    temporal_state = _resolve_temporal_projection_state(
        store,
        store.schema_ir,
        semantics_profile=semantics_profile,
        engine_options=engine_options,
        iteration_count=iteration_count,
    )
    effective_engine_options = _engine_options_with_temporal_projection(
        engine_options,
        temporal_state=temporal_state,
        iteration_count=iteration_count,
    )
    config = replace(resolve_pyreason_run_config(effective_engine_options), atom_trace=True)
    session = _materialize_edb_session(store, store.schema_ir, temporal_state=temporal_state)
    rules = compile_where_ir_to_pyreason(
        target_pred_id=target_pred_id,
        head_vars=head_vars,
        where=where,
        schema_ir=store.schema_ir,
        engine_ext=resolved_engine_ext,
    )
    result = run_pyreason(
        session,
        rules=rules,
        config=config,
    )

    run_id = uuid4().hex
    generated_at = now_epoch_nanos()
    candidates: list[CandidateSet] = []
    for fact in result.derived_session.node_facts:
        candidate = _node_fact_to_candidate(
            store,
            fact,
            derivation_id=derivation_id,
            version=version,
            run_id=run_id,
            generated_at=generated_at,
        )
        if candidate is not None:
            candidates.append(candidate)
    for fact in result.derived_session.edge_facts:
        candidate = _edge_fact_to_candidate(
            store,
            fact,
            derivation_id=derivation_id,
            version=version,
            run_id=run_id,
            generated_at=generated_at,
        )
        if candidate is not None:
            candidates.append(candidate)
    candidates = _attach_pyreason_provenance(store, candidates, result.trace_dict)

    if not hasattr(store, "_engine_pending_annotations"):
        store._engine_pending_annotations = {}
    store._engine_pending_annotations[run_id] = list(result.derived_session.annotation_templates)
    return candidates


def resolve_pyreason_run_config(engine_options: dict[str, Any] | None) -> PyReasonRunConfig:
    """Normalize shared ``engine_options`` into adapter-local ``PyReasonRunConfig``."""
    default = PyReasonRunConfig(timesteps=2, atom_trace=False)
    if engine_options is None:
        return default
    if not isinstance(engine_options, dict):
        raise ValueError(
            f"PyReason engine_options must be dict[str, Any] or None, got {type(engine_options).__name__}"
        )

    supported_keys = {"timesteps"}
    unknown_keys = sorted(str(key) for key in engine_options if key not in supported_keys)
    if unknown_keys:
        supported = ", ".join(sorted(supported_keys))
        unknown = ", ".join(unknown_keys)
        raise ValueError(f"Unsupported PyReason engine_options: {unknown}. Supported keys: {supported}")

    timesteps = engine_options.get("timesteps", default.timesteps)
    if not isinstance(timesteps, int) or isinstance(timesteps, bool) or timesteps <= 0:
        raise ValueError("PyReason engine_options.timesteps must be a positive int")

    return PyReasonRunConfig(
        timesteps=timesteps,
        atom_trace=default.atom_trace,
        convergence_threshold=default.convergence_threshold,
        convergence_bound_threshold=default.convergence_bound_threshold,
    )


def _attach_pyreason_provenance(
    store: Any,
    candidates: list[CandidateSet],
    trace_dict: dict[str, Any] | None,
) -> list[CandidateSet]:
    if not candidates or not isinstance(trace_dict, dict):
        return candidates

    attached: list[CandidateSet] = []
    for candidate in candidates:
        envelope = ProvenanceEnvelope(
            candidate_id=candidate.candidate_id,
            engine="pyreason",
            payload_type="event_log",
            payload=trace_dict,
        )
        support_digest = compute_provenance_digest(envelope)
        store._remember_provenance_envelope(support_digest, envelope)
        attached.append(
            replace(
                candidate,
                support_digest=support_digest,
                support_kind=PYREASON_PROVENANCE_KIND,
            )
        )
    return attached


def _materialize_edb_session(
    store: Any,
    schema_ir: dict[str, Any],
    temporal_state: _TemporalProjectionState | None = None,
) -> PyReasonSession:
    """Project active Ledger facts into a ``PyReasonSession``.

    Non-bounded EDB facts enter PyReason with bound ``[1.0, 1.0]``.
    Predicates marked ``pyreason_bounded`` use point intervals from their value.
    """
    session = PyReasonSession(schema_ir)
    relationship_preds = _relationship_pred_ids(schema_ir)
    bounded = _bounded_pred_ids(schema_ir)

    if temporal_state is None:
        facts_by_pred = project_view_facts(store.ledger, schema_ir)
        for pred_id, fact_tuples in facts_by_pred.items():
            is_relationship = pred_id in relationship_preds
            for fact_tuple in fact_tuples:
                _write_projected_pyreason_fact(
                    session,
                    pred_id,
                    fact_tuple,
                    is_relationship=is_relationship,
                    bounded=bounded,
                    active_from=0,
                    active_to=None,
                )
        return session

    projected_by_pred = project_view_facts_with_witness(store.ledger, schema_ir)
    for pred_id, projected_facts in projected_by_pred.items():
        is_relationship = pred_id in relationship_preds
        for projected_fact in projected_facts:
            fact_tuple = projected_fact.fact_tuple
            active_from, active_to = _active_range_for_projected_fact(
                projected_fact,
                temporal_state=temporal_state,
            )
            _write_projected_pyreason_fact(
                session,
                pred_id,
                fact_tuple,
                is_relationship=is_relationship,
                bounded=bounded,
                active_from=active_from,
                active_to=active_to,
            )
    return session


def _write_projected_pyreason_fact(
    session: PyReasonSession,
    pred_id: str,
    fact_tuple: tuple[Any, ...],
    *,
    is_relationship: bool,
    bounded: set[str],
    active_from: int,
    active_to: int | None,
) -> None:
    if is_relationship:
        if len(fact_tuple) < 2:
            return
        from_ref = str(fact_tuple[0])
        to_ref = str(fact_tuple[1])
        value = str(fact_tuple[2]) if len(fact_tuple) > 2 else ""
        edge_bound = _edb_bound_for_value(value) if pred_id in bounded else (1.0, 1.0)
        session._write_edge_fact_internal(
            pred_id,
            from_ref,
            to_ref,
            value,
            bound=edge_bound,
            active_from=active_from,
            active_to=active_to,
        )
        return
    if not fact_tuple:
        return
    node_ref = str(fact_tuple[0])
    value = str(fact_tuple[1]) if len(fact_tuple) > 1 else "true"
    node_bound = _edb_bound_for_value(value) if pred_id in bounded else (1.0, 1.0)
    session._write_node_fact_internal(
        pred_id,
        node_ref,
        value,
        bound=node_bound,
        active_from=active_from,
        active_to=active_to,
    )


def _resolve_temporal_projection_state(
    store: Any,
    schema_ir: dict[str, Any],
    *,
    semantics_profile: SemanticsProfile | None,
    engine_options: dict[str, Any] | None,
    iteration_count: int | None = None,
) -> _TemporalProjectionState | None:
    if semantics_profile is None:
        return None
    if not isinstance(semantics_profile, SemanticsProfile):
        raise ValueError(
            f"semantics_profile must be SemanticsProfile or None, got {type(semantics_profile).__name__}"
        )
    if semantics_profile.engine != "pyreason":
        raise ValueError(
            f"PyReason consumption expected SemanticsProfile.engine='pyreason', got {semantics_profile.engine!r}"
        )

    projection = semantics_profile.temporal_projection
    mode = projection.get("mode", "none")
    if mode == "none":
        return None
    if mode == "fixed_timesteps":
        timesteps = projection["timesteps"]
        _reject_iteration_temporal_conflict(
            iteration_count,
            carrier="SemanticsProfile.temporal_projection.fixed_timesteps",
        )
        _reject_temporal_timesteps_conflict(
            timesteps,
            engine_options=engine_options,
            carrier="SemanticsProfile.temporal_projection.fixed_timesteps",
        )
        return _TemporalProjectionState(timesteps=timesteps)
    if mode in {"valid_time_boundaries", "fact_boundaries"}:
        carrier = f"SemanticsProfile.temporal_projection.{mode}"
        _reject_iteration_temporal_conflict(
            iteration_count,
            carrier=carrier,
        )
        universe = projection["universe"]
        state = _materialize_valid_time_boundaries(
            store,
            schema_ir,
            universe_start=universe[0],
            universe_end=universe[1],
        )
        if state.timesteps is not None:
            _reject_temporal_timesteps_conflict(
                state.timesteps,
                engine_options=engine_options,
                carrier=carrier,
            )
        return state
    if mode == "time_binned":
        carrier = f"SemanticsProfile.temporal_projection.{mode}"
        _reject_iteration_temporal_conflict(
            iteration_count,
            carrier=carrier,
        )
        universe = projection["universe"]
        state = _materialize_time_binned(
            store,
            schema_ir,
            universe_start=universe[0],
            universe_end=universe[1],
            bin_size=projection["bin_size"],
        )
        if state.timesteps is not None:
            _reject_temporal_timesteps_conflict(
                state.timesteps,
                engine_options=engine_options,
                carrier=carrier,
            )
        return state
    raise ValueError(f"Unsupported PyReason temporal_projection.mode: {mode!r}")


def _engine_options_with_temporal_projection(
    engine_options: dict[str, Any] | None,
    *,
    temporal_state: _TemporalProjectionState | None,
    iteration_count: int | None = None,
) -> dict[str, Any] | None:
    if iteration_count is not None:
        _reject_temporal_timesteps_conflict(
            iteration_count,
            engine_options=engine_options,
            carrier="SemanticsProfile.iteration_count",
        )
        effective = dict(engine_options or {})
        effective["timesteps"] = iteration_count
        return effective
    if temporal_state is None or temporal_state.timesteps is None:
        return engine_options
    effective = dict(engine_options or {})
    effective["timesteps"] = temporal_state.timesteps
    return effective


def _resolve_iteration_count(semantics_profile: SemanticsProfile | None) -> int | None:
    if semantics_profile is None:
        return None
    if not isinstance(semantics_profile, SemanticsProfile):
        raise ValueError(
            f"semantics_profile must be SemanticsProfile or None, got {type(semantics_profile).__name__}"
        )
    if semantics_profile.engine != "pyreason":
        raise ValueError(
            f"PyReason consumption expected SemanticsProfile.engine='pyreason', got {semantics_profile.engine!r}"
        )
    return semantics_profile.iteration_count


def _reject_iteration_temporal_conflict(iteration_count: int | None, *, carrier: str) -> None:
    if iteration_count is None:
        return
    raise ValueError(
        f"Conflicting PyReason timesteps between SemanticsProfile.iteration_count and {carrier}"
    )


def _reject_temporal_timesteps_conflict(
    timesteps: int,
    *,
    engine_options: dict[str, Any] | None,
    carrier: str,
) -> None:
    if not isinstance(engine_options, dict) or "timesteps" not in engine_options:
        return
    existing = engine_options["timesteps"]
    if existing != timesteps:
        raise ValueError(
            f"Conflicting PyReason timesteps between {carrier} and engine_options.timesteps"
        )


def _materialize_valid_time_boundaries(
    store: Any,
    schema_ir: dict[str, Any],
    *,
    universe_start: str,
    universe_end: str,
) -> _TemporalProjectionState:
    projected_by_pred = project_view_facts_with_witness(store.ledger, schema_ir)
    projected_facts = [
        fact
        for projected in projected_by_pred.values()
        for fact in projected
    ]

    valid_ranges: dict[str, tuple[str | None, str | None]] = {}
    boundaries = {universe_start, universe_end}
    for projected_fact in projected_facts:
        valid_from, valid_to = _valid_range_for_asrt_id(store, projected_fact.asrt_id)
        valid_ranges[projected_fact.asrt_id] = (valid_from, valid_to)
        boundaries.add(valid_from if valid_from is not None else universe_start)
        if valid_to is not None:
            boundaries.add(valid_to)

    ordered = sorted(boundaries)
    index_by_boundary = {boundary: idx for idx, boundary in enumerate(ordered)}
    active_by_asrt_id: dict[str, tuple[int, int | None]] = {}
    for projected_fact in projected_facts:
        valid_from, valid_to = valid_ranges[projected_fact.asrt_id]
        active_from = index_by_boundary[valid_from if valid_from is not None else universe_start]
        active_to = None if valid_to is None else index_by_boundary[valid_to]
        active_by_asrt_id[projected_fact.asrt_id] = (active_from, active_to)

    return _TemporalProjectionState(
        timesteps=max(0, len(ordered) - 1),
        active_by_asrt_id=active_by_asrt_id,
    )


def _materialize_time_binned(
    store: Any,
    schema_ir: dict[str, Any],
    *,
    universe_start: str,
    universe_end: str,
    bin_size: str,
) -> _TemporalProjectionState:
    start = _parse_time_binned_instant(
        universe_start,
        path="SemanticsProfile.temporal_projection.time_binned.universe[0]",
    )
    end = _parse_time_binned_instant(
        universe_end,
        path="SemanticsProfile.temporal_projection.time_binned.universe[1]",
    )
    if end <= start:
        raise ValueError("SemanticsProfile.temporal_projection.time_binned.universe start must be before end")

    step = _parse_time_binned_bin_size(bin_size)
    universe_duration = end - start
    universe_units = _timedelta_microseconds(universe_duration)
    step_units = _timedelta_microseconds(step)
    quotient, remainder = divmod(universe_units, step_units)
    if remainder != 0:
        raise ValueError(
            "SemanticsProfile.temporal_projection.time_binned universe duration "
            "must be an exact multiple of bin_size"
        )

    projected_by_pred = project_view_facts_with_witness(store.ledger, schema_ir)
    projected_facts = [
        fact
        for projected in projected_by_pred.values()
        for fact in projected
    ]

    active_by_asrt_id: dict[str, tuple[int, int | None]] = {}
    for projected_fact in projected_facts:
        valid_from, valid_to = _valid_range_for_asrt_id(store, projected_fact.asrt_id)
        active_from_dt = (
            start
            if valid_from is None
            else _parse_time_binned_instant(valid_from, path=f"{projected_fact.asrt_id}.valid_from")
        )
        active_to_dt = (
            None
            if valid_to is None
            else _parse_time_binned_instant(valid_to, path=f"{projected_fact.asrt_id}.valid_to")
        )
        if active_to_dt is not None and active_to_dt <= active_from_dt:
            raise ValueError(f"{projected_fact.asrt_id} valid_to must be after valid_from")
        if active_from_dt < start or active_from_dt >= end:
            raise ValueError(f"{projected_fact.asrt_id} valid_from must be within time_binned universe")
        if active_to_dt is not None and active_to_dt > end:
            raise ValueError(f"{projected_fact.asrt_id} valid_to must be within time_binned universe")

        active_from = _floor_bin_index(active_from_dt - start, step)
        active_to = None if active_to_dt is None else _ceil_bin_index(active_to_dt - start, step)
        active_by_asrt_id[projected_fact.asrt_id] = (active_from, active_to)

    return _TemporalProjectionState(
        timesteps=quotient,
        active_by_asrt_id=active_by_asrt_id,
    )


def _parse_time_binned_instant(value: str, *, path: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be non-empty string")
    if "T" not in value and " " not in value:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{path} must be ISO date or timezone-aware ISO datetime") from exc
        return datetime(
            parsed_date.year,
            parsed_date.month,
            parsed_date.day,
            tzinfo=timezone.utc,
        )
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{path} must be ISO date or timezone-aware ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{path} must include timezone when time is present")
    return parsed.astimezone(timezone.utc)


def _parse_time_binned_bin_size(value: str) -> timedelta:
    path = "SemanticsProfile.temporal_projection.time_binned.bin_size"
    if value == "1d":
        return timedelta(days=1)
    if value == "1h":
        return timedelta(hours=1)
    if value == "15m":
        return timedelta(minutes=15)
    if value == "1m":
        return timedelta(minutes=1)
    amount: str | None = None
    unit: str | None = None
    if value.startswith("PT") and value.endswith(("H", "M")):
        amount = value[2:-1]
        unit = value[-1]
    elif value.startswith("P") and value.endswith("D"):
        amount = value[1:-1]
        unit = "D"
    if amount is None or not amount.isdigit() or int(amount) <= 0:
        raise ValueError(f"{path} must be one of: P<n>D, PT<n>H, PT<n>M, 1d, 1h, 15m, 1m")
    count = int(amount)
    if unit == "D":
        return timedelta(days=count)
    if unit == "H":
        return timedelta(hours=count)
    return timedelta(minutes=count)


def _floor_bin_index(offset: timedelta, step: timedelta) -> int:
    return _timedelta_microseconds(offset) // _timedelta_microseconds(step)


def _ceil_bin_index(offset: timedelta, step: timedelta) -> int:
    offset_units = _timedelta_microseconds(offset)
    step_units = _timedelta_microseconds(step)
    quotient, remainder = divmod(offset_units, step_units)
    return quotient if remainder == 0 else quotient + 1


def _timedelta_microseconds(value: timedelta) -> int:
    return ((value.days * 24 * 60 * 60) + value.seconds) * 1_000_000 + value.microseconds


def _valid_range_for_asrt_id(store: Any, asrt_id: str) -> tuple[str | None, str | None]:
    valid_from = _meta_value_for_key(store, asrt_id, "valid_from")
    valid_to = _meta_value_for_key(store, asrt_id, "valid_to")
    return (valid_from, valid_to)


def _meta_value_for_key(store: Any, asrt_id: str, key: str) -> str | None:
    rows = store.ledger._effective_meta_rows(asrt_id=asrt_id, key=key)
    if not rows:
        return None
    value = rows[-1].value
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} meta must be string for PyReason valid_time_boundaries")
    return value


def _active_range_for_projected_fact(
    projected_fact: ProjectedFact,
    *,
    temporal_state: _TemporalProjectionState | None,
) -> tuple[int, int | None]:
    if temporal_state is None:
        return (0, None)
    return temporal_state.active_by_asrt_id.get(projected_fact.asrt_id, (0, None))


def _node_fact_to_candidate(
    store: Any,
    fact: dict[str, Any],
    *,
    derivation_id: str,
    version: str,
    run_id: str,
    generated_at: int,
) -> CandidateSet | None:
    pred_id = fact.get("pred_id")
    node_ref = fact.get("node_ref")
    if not isinstance(pred_id, str) or not pred_id:
        return None
    if not isinstance(node_ref, str) or not node_ref:
        return None

    schema_pred = store_builders.find_schema_pred(store, pred_id)
    if schema_pred is None:
        return None
    arg_specs = schema_pred.get("arg_specs")
    if not isinstance(arg_specs, list) or not arg_specs:
        return None

    tagged_args: list[tuple[str, Any]] = [("entity_ref", node_ref)]
    payload_terms: list[dict[str, Any]] = [{"kind": "entity_ref", "value": node_ref}]
    if len(arg_specs) > 1:
        value_spec = arg_specs[1] if isinstance(arg_specs[1], dict) else None
        value_tag = value_spec.get("type_domain") if isinstance(value_spec, dict) else "string"
        if not isinstance(value_tag, str) or not value_tag:
            value_tag = "string"
        value = fact.get("value", "")
        tagged_args.append((value_tag, value))
        payload_terms.append({"kind": "literal", "tag": value_tag, "value": value})

    key_terms = _key_terms_for_schema_pred(schema_pred, pred_id, tagged_args)
    tup_digest = sha256_token(canonical_bytes_tup_v1(tagged_args[1:])) if len(tagged_args) > 1 else None
    confidence = _lower_bound_confidence(fact.get("bound"))

    return make_candidate(
        derivation_id=derivation_id,
        derivation_version=version,
        run_id=run_id,
        target=pred_id,
        key_terms=key_terms,
        payload={"pred_id": pred_id, "terms": payload_terms},
        support_digest=_ZERO_SUPPORT_DIGEST,
        support_kind=ENGINE_NO_WITNESS_KIND,
        generated_at=generated_at,
        tup_digest=tup_digest,
        confidence=confidence,
    )


def _edge_fact_to_candidate(
    store: Any,
    fact: dict[str, Any],
    *,
    derivation_id: str,
    version: str,
    run_id: str,
    generated_at: int,
) -> CandidateSet | None:
    pred_id = fact.get("pred_id")
    from_ref = fact.get("from_ref")
    to_ref = fact.get("to_ref")
    if not isinstance(pred_id, str) or not pred_id:
        return None
    if not isinstance(from_ref, str) or not from_ref:
        return None
    if not isinstance(to_ref, str) or not to_ref:
        return None

    schema_pred = store_builders.find_schema_pred(store, pred_id)
    if schema_pred is None:
        return None
    arg_specs = schema_pred.get("arg_specs")
    if not isinstance(arg_specs, list) or len(arg_specs) < 2:
        return None

    tagged_args: list[tuple[str, Any]] = [("entity_ref", from_ref), ("entity_ref", to_ref)]
    payload_terms: list[dict[str, Any]] = [
        {"kind": "entity_ref", "value": from_ref},
        {"kind": "entity_ref", "value": to_ref},
    ]
    if len(arg_specs) > 2:
        value_spec = arg_specs[2] if isinstance(arg_specs[2], dict) else None
        value_tag = value_spec.get("type_domain") if isinstance(value_spec, dict) else "string"
        if not isinstance(value_tag, str) or not value_tag:
            value_tag = "string"
        value = fact.get("value", "")
        tagged_args.append((value_tag, value))
        payload_terms.append({"kind": "literal", "tag": value_tag, "value": value})

    key_terms = _key_terms_for_schema_pred(schema_pred, pred_id, tagged_args)
    tup_digest = sha256_token(canonical_bytes_tup_v1(tagged_args[1:]))
    confidence = _lower_bound_confidence(fact.get("bound"))

    return make_candidate(
        derivation_id=derivation_id,
        derivation_version=version,
        run_id=run_id,
        target=pred_id,
        key_terms=key_terms,
        payload={"pred_id": pred_id, "terms": payload_terms},
        support_digest=_ZERO_SUPPORT_DIGEST,
        support_kind=ENGINE_NO_WITNESS_KIND,
        generated_at=generated_at,
        tup_digest=tup_digest,
        confidence=confidence,
    )


def _key_terms_for_schema_pred(
    schema_pred: dict[str, Any],
    pred_id: str,
    tagged_args: list[tuple[str, Any]],
) -> list[tuple[str, Any]]:
    group_key_indexes = store_builders.read_group_key_indexes(schema_pred, len(tagged_args))
    dims_terms = [tagged_args[idx] for idx in group_key_indexes if idx != 0]
    return [("string", pred_id), tagged_args[0], *dims_terms]


def _lower_bound_confidence(bound: Any) -> float | None:
    if isinstance(bound, (list, tuple)) and len(bound) >= 1:
        lo = bound[0]
        if isinstance(lo, (int, float)) and not isinstance(lo, bool):
            return float(lo)
    return None


def _edb_bound_for_value(value: str) -> tuple[float, float]:
    """Parse EDB value as ``[0,1]`` float -> point interval; fallback to ``(1.0, 1.0)``."""
    parsed = _parse_bounded_float(value)
    if parsed is None:
        return (1.0, 1.0)
    return (parsed, parsed)


def _relationship_pred_ids(schema_ir: dict[str, Any]) -> set[str]:
    predicates = schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        return set()
    return {
        pred["pred_id"]
        for pred in predicates
        if isinstance(pred, dict)
        and isinstance(pred.get("pred_id"), str)
        and pred.get("relationship_type")
    }


__all__ = [
    "pyreason_engine_eval",
    "resolve_pyreason_run_config",
    "_materialize_edb_session",
]
