from __future__ import annotations

import unicodedata
from typing import Any

from factgraph.core.protocol.tup_v1 import display_float64_value, encode_value_bytes
from factgraph.core.view.projector import project_view_facts

from .protocol.semantic_candidates import (
    SemanticCandidateScalar,
    SemanticCandidateShapeError,
    SemanticValueCandidateBatchRequestV1,
    SemanticValueCandidateBatchResultV1,
    SemanticValueCandidateRequestV1,
    SemanticValueCandidateResultV1,
)
from .protocol.semantic_port import EntityIdentityEndpoint, FieldEndpoint
from .schema_runtime import SchemaIndex, entity_info, field_predicate, field_value_type


class SemanticCandidateRuntimeError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_semantic_value_candidates_v1(
    graph: Any, request: SemanticValueCandidateBatchRequestV1
) -> SemanticValueCandidateBatchResultV1:
    """Resolve a bounded batch from one projected view; perform no writes."""
    if not isinstance(request, SemanticValueCandidateBatchRequestV1):
        raise SemanticCandidateShapeError("request must be SemanticValueCandidateBatchRequestV1")
    try:
        before = graph._view_snapshot_digest(query_typed_values=True)
        view_facts = project_view_facts(graph.ledger, graph.schema_ir)
        after = graph._view_snapshot_digest(query_typed_values=True)
        index = graph._application_schema_index
    except AttributeError as exc:
        raise SemanticCandidateShapeError("graph lacks the FactGraph SDK view interface") from exc
    if before != after:
        raise SemanticCandidateRuntimeError(
            "FactGraph view changed during candidate capture",
            code="VIEW_CHANGED_DURING_CANDIDATE_CAPTURE",
        )
    items = tuple(_resolve_item(item, view_facts=view_facts, index=index) for item in request.items)
    return SemanticValueCandidateBatchResultV1(request.request_digest, before, items)


def _resolve_item(
    item: SemanticValueCandidateRequestV1,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
) -> SemanticValueCandidateResultV1:
    domain, values = _endpoint_values(item.endpoint, view_facts=view_facts, index=index)
    _assert_domain(item.supplied_value, domain)
    ordered = _distinct_sorted(values, domain)
    exact = tuple(
        value for value in ordered if _key(value, domain) == _key(item.supplied_value, domain)
    )
    normalized: tuple[SemanticCandidateScalar, ...] = ()
    suggestions: tuple[SemanticCandidateScalar, ...] = ()
    truncated = False
    if not exact and item.match_mode == "unicode_casefold_v1":
        assert isinstance(item.supplied_value, str)
        needle = _normalize(item.supplied_value)
        found_matches = tuple(
            value for value in ordered if isinstance(value, str) and _normalize(value) == needle
        )
        normalized = found_matches[:5]
        matches_truncated = len(found_matches) > 5
        if not normalized and needle and item.suggestion_limit:
            found = tuple(
                value
                for value in ordered
                if isinstance(value, str) and _normalize(value).startswith(needle)
            )
            truncated = len(found) > item.suggestion_limit
            suggestions = found[: item.suggestion_limit]
    else:
        matches_truncated = False
    return SemanticValueCandidateResultV1(
        item.correlation_key,
        exact,
        normalized,
        matches_truncated,
        suggestions,
        truncated,
    )


def _endpoint_values(
    endpoint: EntityIdentityEndpoint | FieldEndpoint,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
) -> tuple[str, list[SemanticCandidateScalar]]:
    if isinstance(endpoint, EntityIdentityEndpoint):
        info = entity_info(index, endpoint.entity_type)
        if len(info.identity_fields) != 1:
            raise SemanticCandidateRuntimeError(
                "single-field identity required", code="COMPOSITE_IDENTITY_UNSUPPORTED"
            )
        identity = info.identity_fields[0]
        pred = info.identity_predicates[identity.name]
        return identity.type_domain, [
            _public_value(row[-1], identity.type_domain)
            for row in view_facts.get(pred.pred_id, ())
            if row
        ]
    shape = field_value_type(index, endpoint.entity_type, endpoint.field_name)
    if shape.value_kind != "scalar" or shape.cardinality != "single" or shape.scalar_domain is None:
        raise SemanticCandidateRuntimeError(
            "single scalar field required", code="SEMANTIC_CANDIDATE_ENDPOINT_UNSUPPORTED"
        )
    pred = field_predicate(index, endpoint.entity_type, endpoint.field_name)
    return shape.scalar_domain, [
        _public_value(row[-1], shape.scalar_domain)
        for row in view_facts.get(pred.pred_id, ())
        if row
    ]


def _public_value(value: Any, domain: str) -> SemanticCandidateScalar:
    if domain == "float64":
        return float(display_float64_value(value))
    return value


def _assert_domain(value: SemanticCandidateScalar, domain: str) -> None:
    expected = {"string": str, "int": int, "float64": float, "bool": bool}.get(domain)
    if expected is None or type(value) is not expected:
        raise SemanticCandidateRuntimeError(
            f"value does not match {domain}", code="SEMANTIC_CANDIDATE_TYPE_MISMATCH"
        )


def _key(value: SemanticCandidateScalar, domain: str) -> bytes:
    return encode_value_bytes(domain, value)


def _distinct_sorted(
    values: list[SemanticCandidateScalar], domain: str
) -> tuple[SemanticCandidateScalar, ...]:
    by_key = {_key(value, domain): value for value in values}
    return tuple(by_key[key] for key in sorted(by_key))


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip()).casefold()


__all__ = ["SemanticCandidateRuntimeError", "resolve_semantic_value_candidates_v1"]
