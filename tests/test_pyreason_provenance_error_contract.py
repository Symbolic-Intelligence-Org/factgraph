"""PyReason provenance decoding keeps its ValueError rejection contract at the event_log boundary.

Every case below reaches one ``raise ValueError`` site in
``factgraph.adapters.pyreason.provenance`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
The SDK row-explain consumer decodes the stored ``payload_type="event_log"``
provenance envelope through ``pyreason_trace_from_dict`` and treats any decode
failure as the minimal-fallback signal (adapter docs section 7).
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from factgraph.adapters.pyreason.provenance import (
    PyReasonTraceEventV0,
    PyReasonTraceV0,
    pyreason_trace_from_dict,
    pyreason_trace_to_dict,
    pyreason_trace_to_evidence_graph,
)


def _event_dict(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "time": 0,
        "fixpoint_op": 1,
        "component": "Alice",
        "component_type": "node",
        "label": "popular",
        "old_bound": [0.0, 1.0],
        "new_bound": [1.0, 1.0],
        "occurred_due_to": "seed_fact",
        "clause_groundings": [],
    }
    row.update(overrides)
    return row


def _payload(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "engine": "pyreason",
        "trace_type": "event_log",
        "timesteps": 2,
        "node_events": [_event_dict()],
        "edge_events": [],
    }
    row.update(overrides)
    return row


def _trace() -> PyReasonTraceV0:
    return PyReasonTraceV0(
        timesteps=2,
        node_events=(
            PyReasonTraceEventV0(
                time=0,
                fixpoint_op=1,
                component="Alice",
                component_type="node",
                label="popular",
                old_bound=(0.0, 1.0),
                new_bound=(1.0, 1.0),
                occurred_due_to="seed_fact",
                clause_groundings=(),
            ),
        ),
        edge_events=(),
    )


# --- pyreason_trace_from_dict / _event_from_dict: event_log payload shape rejections ---


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (None, "row must be Mapping[str, Any]"),
        ([("engine", "pyreason")], "row must be Mapping[str, Any]"),
        (_payload(timesteps="2"), "row.timesteps must be int"),
        (_payload(timesteps=True), "row.timesteps must be int"),
        (_payload(node_events=()), "row.node_events must be list"),
        (_payload(edge_events=()), "row.edge_events must be list"),
        (_payload(node_events=[None]), "trace event row must be Mapping[str, Any]"),
        (_payload(edge_events=[["time", 0]]), "trace event row must be Mapping[str, Any]"),
        (
            _payload(node_events=[_event_dict(clause_groundings=())]),
            "trace event clause_groundings must be list",
        ),
    ],
)
def test_trace_shape_rejections_preserve_exact_value_error(payload, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        pyreason_trace_from_dict(payload)
    assert type(caught.value) is ValueError


def test_trace_dict_roundtrip_positive_control():
    trace = _trace()
    payload = pyreason_trace_to_dict(trace)
    restored = pyreason_trace_from_dict(payload)
    assert restored == trace
    assert pyreason_trace_to_dict(restored) == payload


# --- _resolve_candidate_anchor: "candidate_payload.terms must be list" ---


@pytest.mark.parametrize("terms", [("Alice",), "Alice", {"value": "Alice"}])
def test_candidate_terms_rejection_preserves_exact_value_error(terms):
    with pytest.raises(ValueError, match=re.escape("candidate_payload.terms must be list")) as caught:
        pyreason_trace_to_evidence_graph(
            _trace(),
            candidate_id="cand_v2:alice",
            candidate_payload={"pred_id": "user:popular", "terms": terms},
        )
    assert type(caught.value) is ValueError


def test_candidate_terms_list_positive_control():
    graph = pyreason_trace_to_evidence_graph(
        _trace(),
        candidate_id="cand_v2:alice",
        candidate_payload={
            "pred_id": "user:popular",
            "terms": [{"kind": "entity_ref", "value": "Alice"}],
        },
    )
    assert graph.engine == "pyreason"
    assert graph.metadata["root_component"] == "Alice"
    assert graph.metadata["root_label"] == "popular"
