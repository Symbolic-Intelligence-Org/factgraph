"""PyReason reusable runner: session -> graph -> reason -> trace -> derived facts."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from factpy_kernel.adapters.pyreason.provenance import (
    PyReasonTraceV0,
    parse_pyreason_trace,
    pyreason_trace_to_dict,
)
from factpy_kernel.adapters.pyreason.session import PyReasonSession


@dataclass
class PyReasonRunConfig:
    """Engine-level run configuration for PyReason."""

    timesteps: int = 1
    atom_trace: bool = True
    convergence_threshold: float | None = None
    convergence_bound_threshold: float | None = None


@dataclass
class PyReasonRunResult:
    """Complete result from a ``run_pyreason()`` invocation."""

    interpretation: Any
    trace: PyReasonTraceV0 | None
    trace_dict: dict[str, Any] | None
    derived_session: PyReasonSession
    config: PyReasonRunConfig
    elapsed_seconds: float


def build_pyreason_graph(session: PyReasonSession) -> Any:
    """Build a NetworkX DiGraph from session facts."""
    import networkx as nx

    graph = nx.DiGraph()

    nodes: set[str] = set()
    for fact in session.node_facts:
        nodes.add(str(fact["node_ref"]))
    for fact in session.edge_facts:
        nodes.add(str(fact["from_ref"]))
        nodes.add(str(fact["to_ref"]))
    for node in sorted(nodes):
        graph.add_node(node)

    for fact in session.node_facts:
        attr_name = str(fact["pred_id"]).split(":", 1)[1]
        graph.nodes[str(fact["node_ref"])][attr_name] = 1

    for fact in session.edge_facts:
        attr_name = str(fact["pred_id"]).split(":", 1)[1]
        from_ref = str(fact["from_ref"])
        to_ref = str(fact["to_ref"])
        if graph.has_edge(from_ref, to_ref):
            graph.edges[from_ref, to_ref][attr_name] = 1
        else:
            graph.add_edge(from_ref, to_ref, **{attr_name: 1})

    return graph


def _extract_derived_facts(
    interpretation: Any,
    schema_ir: dict[str, Any],
    input_session: PyReasonSession,
) -> PyReasonSession:
    """Extract facts derived by reasoning into a new session."""
    input_node_keys: set[tuple[str, str]] = set()
    for fact in input_session.node_facts:
        field_name = str(fact["pred_id"]).split(":", 1)[1]
        input_node_keys.add((str(fact["node_ref"]), field_name))

    input_edge_keys: set[tuple[str, str, str]] = set()
    for fact in input_session.edge_facts:
        field_name = str(fact["pred_id"]).split(":", 1)[1]
        input_edge_keys.add((str(fact["from_ref"]), str(fact["to_ref"]), field_name))

    pred_lookup: dict[str, str] = {}
    rel_preds: set[str] = set()
    for pred in schema_ir.get("predicates", []):
        if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str):
            field_name = pred["pred_id"].split(":", 1)[1]
            pred_lookup[field_name] = pred["pred_id"]
            if pred.get("relationship_type"):
                rel_preds.add(pred["pred_id"])

    derived = PyReasonSession(schema_ir)
    interp_dict = interpretation.get_dict()

    for timestep in sorted(interp_dict.keys()):
        if timestep == 0:
            continue
        for component, preds in interp_dict[timestep].items():
            for pred_name, (lo, hi) in preds.items():
                if lo == 0.0 and hi == 0.0:
                    continue

                pred_id = pred_lookup.get(pred_name)
                if pred_id is None:
                    continue

                if pred_id in rel_preds:
                    parts = _parse_edge_component(str(component))
                    if parts is None:
                        continue
                    from_ref, to_ref = parts
                    key = (from_ref, to_ref, pred_name)
                    if key in input_edge_keys:
                        continue
                    input_edge_keys.add(key)
                    derived._write_edge_fact_internal(
                        pred_id,
                        from_ref,
                        to_ref,
                        "",
                        bound=[lo, hi],
                        active_from=timestep,
                        meta={"source": "pyreason_derived", "derived_at_timestep": timestep},
                    )
                    continue

                key = (str(component), pred_name)
                if key in input_node_keys:
                    continue
                input_node_keys.add(key)
                derived._write_node_fact_internal(
                    pred_id,
                    str(component),
                    str(lo == 1.0 and hi == 1.0).lower(),
                    bound=[lo, hi],
                    active_from=timestep,
                    meta={"source": "pyreason_derived", "derived_at_timestep": timestep},
                )

    return derived


def _parse_edge_component(component: str) -> tuple[str, str] | None:
    """Parse PyReason edge component names to ``(from_ref, to_ref)``."""
    if component.startswith("(") and component.endswith(")"):
        inner = component[1:-1]
        parts = [part.strip() for part in inner.split(",")]
        if len(parts) == 2:
            return (parts[0], parts[1])
    if "-" in component:
        parts = component.split("-", 1)
        if len(parts) == 2:
            return (parts[0], parts[1])
    return None


def run_pyreason(
    session: PyReasonSession,
    *,
    rules: list[tuple[str, str]] | None = None,
    facts: list[tuple[str, str, int, int]] | None = None,
    config: PyReasonRunConfig | None = None,
) -> PyReasonRunResult:
    """Run PyReason reasoning on a populated session."""
    import pyreason as pr

    if config is None:
        config = PyReasonRunConfig()
    if rules is None:
        rules = []
    if facts is None:
        facts = []

    start = time.monotonic()

    graph = build_pyreason_graph(session)
    pr.reset()
    pr.load_graph(graph)

    for body_str, name_str in rules:
        pr.add_rule(pr.Rule(body_str, name_str))

    for atom_str, name_str, start_time, end_time in facts:
        pr.add_fact(pr.Fact(atom_str, name_str, start_time, end_time))

    pr.settings.atom_trace = config.atom_trace
    interpretation = pr.reason(timesteps=config.timesteps)

    trace: PyReasonTraceV0 | None = None
    trace_dict: dict[str, Any] | None = None
    if config.atom_trace:
        nodes_trace, edges_trace = pr.get_rule_trace(interpretation)
        trace = parse_pyreason_trace(nodes_trace, edges_trace, timesteps=config.timesteps)
        trace_dict = pyreason_trace_to_dict(trace)

    derived_session = _extract_derived_facts(interpretation, session._schema_ir, session)
    pr.reset()

    return PyReasonRunResult(
        interpretation=interpretation,
        trace=trace,
        trace_dict=trace_dict,
        derived_session=derived_session,
        config=config,
        elapsed_seconds=time.monotonic() - start,
    )
