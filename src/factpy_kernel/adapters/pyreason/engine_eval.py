"""PyReason engine evaluator for ``Store.evaluate(mode="pyreason")``."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from factpy_kernel.adapters.pyreason.runner import (
    PyReasonRunConfig,
    _bounded_pred_ids,
    _parse_bounded_float,
    run_pyreason,
)
from factpy_kernel.adapters.pyreason.session import PyReasonSession
from factpy_kernel.adapters.pyreason.where_compile import compile_where_ir_to_pyreason
from factpy_kernel.core.derivation.candidates import CandidateSet, make_candidate
from factpy_kernel.core.evidence.write_protocol import now_epoch_nanos
from factpy_kernel.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factpy_kernel.core.protocol.digests import sha256_token
from factpy_kernel.core.store import builders as store_builders
from factpy_kernel.core.store._support import ENGINE_NO_WITNESS_KIND
from factpy_kernel.core.store.types import EngineExtBase
from factpy_kernel.core.view.projector import project_view_facts

_ZERO_SUPPORT_DIGEST = f"sha256:{'0' * 64}"


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
) -> list[CandidateSet]:
    """Evaluate a derivation through the PyReason adapter."""
    del mode
    del head
    from factpy_kernel.adapters.pyreason.rule_ext import PyReasonRuleExt

    if engine_ext is not None and not isinstance(engine_ext, PyReasonRuleExt):
        raise ValueError(
            f"PyReason engine_ext must be PyReasonRuleExt, got {type(engine_ext).__name__}"
        )

    session = _materialize_edb_session(store, store.schema_ir)
    rules = compile_where_ir_to_pyreason(
        target_pred_id=target_pred_id,
        head_vars=head_vars,
        where=where,
        schema_ir=store.schema_ir,
        engine_ext=engine_ext,
    )
    result = run_pyreason(
        session,
        rules=rules,
        config=PyReasonRunConfig(timesteps=2, atom_trace=False),
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

    if not hasattr(store, "_engine_pending_annotations"):
        store._engine_pending_annotations = {}
    store._engine_pending_annotations[run_id] = list(result.derived_session.annotation_templates)
    return candidates


def _materialize_edb_session(
    store: Any,
    schema_ir: dict[str, Any],
) -> PyReasonSession:
    """Project active Ledger facts into a ``PyReasonSession``.

    Non-bounded EDB facts enter PyReason with bound ``[1.0, 1.0]``.
    Predicates marked ``pyreason_bounded`` use point intervals from their value.
    """
    session = PyReasonSession(schema_ir)
    facts_by_pred = project_view_facts(store.ledger, schema_ir)
    relationship_preds = _relationship_pred_ids(schema_ir)
    bounded = _bounded_pred_ids(schema_ir)

    for pred_id, fact_tuples in facts_by_pred.items():
        is_relationship = pred_id in relationship_preds
        for fact_tuple in fact_tuples:
            if is_relationship:
                if len(fact_tuple) < 2:
                    continue
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
                )
                continue
            if not fact_tuple:
                continue
            node_ref = str(fact_tuple[0])
            value = str(fact_tuple[1]) if len(fact_tuple) > 1 else "true"
            node_bound = _edb_bound_for_value(value) if pred_id in bounded else (1.0, 1.0)
            session._write_node_fact_internal(
                pred_id,
                node_ref,
                value,
                bound=node_bound,
            )

    return session


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
    "_materialize_edb_session",
]
