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
from typing import TYPE_CHECKING, Any

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
