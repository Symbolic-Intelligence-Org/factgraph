"""PyReason provenance trace carrier (adapter-local, V0 spike).

Converts PyReason's pandas DataFrame rule trace into adapter-local
frozen dataclasses. This is NOT a core contract — field shapes may
change based on spike findings.

Key difference from Souffle provenance:
    Souffle: proof TREE per conclusion (SouffleProofTreeV0)
    PyReason: event LOG of all changes (PyReasonTraceV0)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from kernel.adapters.pyreason._helpers import _parse_edge_component, _pred_short_name
from kernel.audit.evidence_graph import (
    EDGE_UPDATES,
    LAYOUT_TIMELINE,
    NODE_CONCLUSION,
    NODE_PREMISE,
    NODE_SEED,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
)
from kernel.core.store._support import PYREASON_PROVENANCE_KIND

if TYPE_CHECKING:
    import pandas as pd


@dataclass(frozen=True)
class PyReasonTraceEventV0:
    """Single row from a PyReason rule trace DataFrame.

    Adapter-local. NOT a core contract.
    """

    time: int
    fixpoint_op: int
    component: str
    component_type: str
    label: str
    old_bound: tuple[float, float]
    new_bound: tuple[float, float]
    occurred_due_to: str
    clause_groundings: tuple[str, ...]


@dataclass(frozen=True)
class PyReasonTraceV0:
    """Complete trace from a PyReason reasoning run.

    This is an EVENT LOG, not a proof tree.
    Each event records a single bound change caused by a rule or fact.
    """

    timesteps: int
    node_events: tuple[PyReasonTraceEventV0, ...]
    edge_events: tuple[PyReasonTraceEventV0, ...]


def parse_pyreason_trace(
    nodes_trace_df: Any,
    edges_trace_df: Any,
    *,
    timesteps: int,
) -> PyReasonTraceV0:
    """Convert PyReason DataFrames to an adapter-local trace carrier."""
    node_events = tuple(_parse_trace_df(nodes_trace_df, "node"))
    edge_events = tuple(_parse_trace_df(edges_trace_df, "edge"))
    return PyReasonTraceV0(
        timesteps=timesteps,
        node_events=node_events,
        edge_events=edge_events,
    )


def pyreason_trace_to_dict(trace: PyReasonTraceV0) -> dict[str, Any]:
    """Serialize PyReasonTraceV0 to a JSON-friendly dict."""
    return {
        "engine": "pyreason",
        "trace_type": "event_log",
        "timesteps": trace.timesteps,
        "node_events": [_event_to_dict(event) for event in trace.node_events],
        "edge_events": [_event_to_dict(event) for event in trace.edge_events],
    }


def pyreason_trace_from_dict(row: Mapping[str, Any]) -> PyReasonTraceV0:
    """Reconstruct ``PyReasonTraceV0`` from a JSON-friendly dict."""
    if not isinstance(row, Mapping):
        raise ValueError("row must be Mapping[str, Any]")
    if row.get("engine") != "pyreason":
        raise ValueError("row.engine must be 'pyreason'")
    if row.get("trace_type") != "event_log":
        raise ValueError("row.trace_type must be 'event_log'")

    timesteps = row.get("timesteps")
    if isinstance(timesteps, bool) or not isinstance(timesteps, int):
        raise ValueError("row.timesteps must be int")
    raw_node_events = row.get("node_events")
    raw_edge_events = row.get("edge_events")
    if not isinstance(raw_node_events, list):
        raise ValueError("row.node_events must be list")
    if not isinstance(raw_edge_events, list):
        raise ValueError("row.edge_events must be list")

    return PyReasonTraceV0(
        timesteps=timesteps,
        node_events=tuple(_event_from_dict(event) for event in raw_node_events),
        edge_events=tuple(_event_from_dict(event) for event in raw_edge_events),
    )


def pyreason_trace_to_evidence_graph(
    trace: PyReasonTraceV0,
    *,
    candidate_id: str,
    candidate_payload: Mapping[str, Any],
    support_kind: str = PYREASON_PROVENANCE_KIND,
) -> EvidenceGraph:
    """Convert a PyReason event log into an EvidenceGraph timeline.

    The current carrier is a run-scoped event log, not a lossless proof graph.
    v1 therefore keeps all timeline events, roots the graph at the candidate's
    matching event, and only materializes intra-fact update chains. Clause
    groundings stay in ``engine_meta`` until a richer causal mapping is available.
    """
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be non-empty string")

    component_type, root_component, root_label = _resolve_candidate_anchor(candidate_payload)
    ordered_events = sorted(
        (*trace.node_events, *trace.edge_events),
        key=lambda event: (
            int(event.time),
            int(event.fixpoint_op),
            str(event.component_type),
            _normalize_component_key(event),
            str(event.label),
        ),
    )
    if not ordered_events:
        raise ValueError("PyReason trace has no events")

    node_specs: list[tuple[PyReasonTraceEventV0, str]] = []
    root_node_id: str | None = None
    chains: dict[tuple[str, str, str], list[tuple[int, str, PyReasonTraceEventV0]]] = {}

    matching_positions = [
        idx
        for idx, event in enumerate(ordered_events)
        if event.component_type == component_type
        and _normalize_component_key(event) == root_component
        and event.label == root_label
    ]
    if not matching_positions:
        raise ValueError(
            "candidate anchor not found in PyReason trace: "
            f"{component_type} {root_component} {root_label}"
        )
    root_position = matching_positions[-1]

    for idx, event in enumerate(ordered_events):
        component_key = _normalize_component_key(event)
        node_id = f"pyreason:{candidate_id}:event:{idx}"
        node_specs.append((event, node_id))
        if idx == root_position:
            root_node_id = node_id
        chain_key = (event.component_type, component_key, event.label)
        chains.setdefault(chain_key, []).append((idx, node_id, event))

    if root_node_id is None:  # pragma: no cover - guarded by matching_positions
        raise ValueError("failed to resolve root node for PyReason evidence graph")

    nodes: list[EvidenceNode] = []
    edges: list[EvidenceEdge] = []
    first_positions_by_chain = {chain_key: chain[0][0] for chain_key, chain in chains.items()}

    for idx, (event, node_id) in enumerate(node_specs):
        component_key = _normalize_component_key(event)
        chain_key = (event.component_type, component_key, event.label)
        if idx == root_position:
            node_kind = NODE_CONCLUSION
        elif first_positions_by_chain[chain_key] == idx and _is_seed_event(event):
            node_kind = NODE_SEED
        else:
            node_kind = NODE_PREMISE
        nodes.append(
            EvidenceNode(
                node_id=node_id,
                node_kind=node_kind,
                component=component_key,
                label=event.label,
                value_summary=_format_bound_summary(event.new_bound),
                timestamp=event.time,
                engine_meta={
                    "component_type": event.component_type,
                    "fixpoint_op": event.fixpoint_op,
                    "occurred_due_to": event.occurred_due_to,
                    "old_bound": event.old_bound,
                    "new_bound": event.new_bound,
                    "clause_groundings": event.clause_groundings,
                    "raw_component": event.component,
                },
            )
        )

    edge_counter = 0
    for chain_key in sorted(chains):
        chain = sorted(chains[chain_key], key=lambda item: item[0])
        for previous, current in zip(chain, chain[1:]):
            edge_counter += 1
            _, previous_node_id, _previous_event = previous
            _, current_node_id, current_event = current
            edges.append(
                EvidenceEdge(
                    edge_id=f"pyreason:{candidate_id}:edge:{edge_counter}",
                    from_node_id=previous_node_id,
                    to_node_id=current_node_id,
                    edge_kind=EDGE_UPDATES,
                    rule_label=current_event.occurred_due_to,
                    engine_meta={
                        "component_type": current_event.component_type,
                        "fixpoint_op": current_event.fixpoint_op,
                        "clause_groundings": current_event.clause_groundings,
                    },
                )
            )

    return EvidenceGraph(
        graph_id=f"eg:{candidate_id}",
        engine="pyreason",
        root_node_id=root_node_id,
        nodes=tuple(nodes),
        edges=tuple(edges),
        support_kind=support_kind,
        layout_hint=LAYOUT_TIMELINE,
        metadata={
            "timesteps": trace.timesteps,
            "node_event_count": len(trace.node_events),
            "edge_event_count": len(trace.edge_events),
            "root_component_type": component_type,
            "root_component": root_component,
            "root_label": root_label,
        },
    )


def _parse_trace_df(df: Any, component_type: str) -> list[PyReasonTraceEventV0]:
    """Parse a single trace DataFrame (nodes or edges) into event rows."""
    events: list[PyReasonTraceEventV0] = []
    if df is None or len(df) == 0:
        return events

    clause_cols = [column for column in df.columns if str(column).startswith("Clause-")]
    fixpoint_col = "Fixed-Point-Operation"
    if fixpoint_col not in df.columns and "Fixed-Point-Op" in df.columns:
        fixpoint_col = "Fixed-Point-Op"
    component_col = "Node"
    if component_col not in df.columns and "Edge" in df.columns:
        component_col = "Edge"

    for _, row in df.iterrows():
        groundings: list[str] = []
        for column in clause_cols:
            value = row.get(column)
            if value is None:
                continue
            value_text = str(value)
            if value_text == "None":
                continue
            groundings.append(value_text)

        old_bound = _parse_bound(row.get("Old Bound", "[0.0,1.0]"))
        new_bound = _parse_bound(row.get("New Bound", "[0.0,1.0]"))

        events.append(
            PyReasonTraceEventV0(
                time=int(row.get("Time", 0)),
                fixpoint_op=int(row.get(fixpoint_col, 0)),
                component=str(row.get(component_col, "?")),
                component_type=component_type,
                label=str(row.get("Label", "?")),
                old_bound=old_bound,
                new_bound=new_bound,
                occurred_due_to=str(row.get("Occurred Due To", "?")),
                clause_groundings=tuple(groundings),
            )
        )

    return events


def _parse_bound(raw: Any) -> tuple[float, float]:
    """Parse a PyReason bound value into a `(lower, upper)` tuple."""
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return float(raw[0]), float(raw[1])
    if isinstance(raw, str):
        cleaned = raw.strip("[]() ")
        if "," in cleaned:
            left, right = cleaned.split(",", 1)
            return float(left.strip()), float(right.strip())
    return 0.0, 1.0


def _event_to_dict(event: PyReasonTraceEventV0) -> dict[str, Any]:
    """Serialize a single trace event to a JSON-friendly dict."""
    return {
        "time": event.time,
        "fixpoint_op": event.fixpoint_op,
        "component": event.component,
        "component_type": event.component_type,
        "label": event.label,
        "old_bound": list(event.old_bound),
        "new_bound": list(event.new_bound),
        "occurred_due_to": event.occurred_due_to,
        "clause_groundings": list(event.clause_groundings),
    }


def _event_from_dict(row: Any) -> PyReasonTraceEventV0:
    if not isinstance(row, Mapping):
        raise ValueError("trace event row must be Mapping[str, Any]")
    clause_groundings = row.get("clause_groundings")
    if not isinstance(clause_groundings, list):
        raise ValueError("trace event clause_groundings must be list")
    return PyReasonTraceEventV0(
        time=int(row.get("time", 0)),
        fixpoint_op=int(row.get("fixpoint_op", 0)),
        component=str(row.get("component", "?")),
        component_type=str(row.get("component_type", "?")),
        label=str(row.get("label", "?")),
        old_bound=_parse_bound(row.get("old_bound", [0.0, 1.0])),
        new_bound=_parse_bound(row.get("new_bound", [0.0, 1.0])),
        occurred_due_to=str(row.get("occurred_due_to", "?")),
        clause_groundings=tuple(str(item) for item in clause_groundings),
    )


def _resolve_candidate_anchor(candidate_payload: Mapping[str, Any]) -> tuple[str, str, str]:
    pred_id = candidate_payload.get("pred_id")
    if not isinstance(pred_id, str) or not pred_id:
        raise ValueError("candidate_payload.pred_id must be non-empty string")
    terms = candidate_payload.get("terms")
    if not isinstance(terms, list):
        raise ValueError("candidate_payload.terms must be list")

    entity_refs = [
        str(term.get("value"))
        for term in terms
        if isinstance(term, dict)
        and term.get("kind") == "entity_ref"
        and isinstance(term.get("value"), str)
        and term.get("value")
    ]
    if len(entity_refs) == 1:
        return ("node", entity_refs[0], _pred_short_name(pred_id))
    if len(entity_refs) >= 2:
        return ("edge", f"{entity_refs[0]}->{entity_refs[1]}", _pred_short_name(pred_id))
    raise ValueError("candidate_payload must include at least one entity_ref term")


def _normalize_component_key(event: PyReasonTraceEventV0) -> str:
    if event.component_type != "edge":
        return event.component
    parsed = _parse_edge_component(event.component)
    if parsed is None:
        return event.component
    return f"{parsed[0]}->{parsed[1]}"


def _format_bound_summary(bound: tuple[float, float]) -> str:
    return f"[{float(bound[0])}, {float(bound[1])}]"


def _is_seed_event(event: PyReasonTraceEventV0) -> bool:
    marker = event.occurred_due_to.strip().lower()
    return "fact" in marker or "seed" in marker


__all__ = [
    "PyReasonTraceEventV0",
    "PyReasonTraceV0",
    "parse_pyreason_trace",
    "pyreason_trace_from_dict",
    "pyreason_trace_to_dict",
    "pyreason_trace_to_evidence_graph",
]
