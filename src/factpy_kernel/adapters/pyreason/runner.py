"""PyReason reusable runner: session -> graph -> reason -> trace -> derived facts."""
from __future__ import annotations

import re
import struct
import threading
import time
import warnings
from dataclasses import dataclass
from typing import Any

from factpy_kernel.adapters.pyreason.provenance import (
    PyReasonTraceV0,
    parse_pyreason_trace,
    pyreason_trace_to_dict,
)
from factpy_kernel.adapters.pyreason.rule_ext import (
    PyReasonFactDef,
    compile_pyreason_rule,
)
from factpy_kernel.adapters.pyreason.session import PyReasonSession
from factpy_kernel.sdk.dsl.rule import Rule

_PYREASON_LOCK = threading.Lock()


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


def _bounded_pred_ids(schema_ir: dict[str, Any]) -> set[str]:
    """Return numeric pred_ids marked ``pyreason_bounded`` in schema_ir."""
    result: set[str] = set()
    for pred in schema_ir.get("predicates", []):
        if not isinstance(pred, dict) or not pred.get("pyreason_bounded"):
            continue
        pred_id = pred.get("pred_id")
        arg_specs = pred.get("arg_specs")
        if not isinstance(pred_id, str) or not isinstance(arg_specs, list):
            continue
        value_idx = 2 if pred.get("relationship_type") else 1
        if len(arg_specs) <= value_idx or not isinstance(arg_specs[value_idx], dict):
            continue
        type_domain = arg_specs[value_idx].get("type_domain")
        if type_domain in {"int", "float64", "float32"}:
            result.add(pred_id)
    return result


def _parse_bounded_float(value: Any) -> float | None:
    """Parse a bounded numeric value from decimal or canonical float64 hex."""
    try:
        if isinstance(value, str) and value.startswith("0x") and len(value) == 18:
            fval = struct.unpack(">d", int(value, 16).to_bytes(8, "big", signed=False))[0]
        else:
            fval = float(value)
        if 0.0 <= fval <= 1.0:
            return fval
    except (OverflowError, ValueError, TypeError, struct.error):
        pass
    return None


def build_pyreason_graph(session: PyReasonSession, schema_ir: dict[str, Any] | None = None) -> Any:
    """Build a NetworkX DiGraph with structure plus edge-label attributes.

    PyReason uses separate channels for node labels and edge labels in the
    integration path we support:

    - node labels are registered later via ``pr.add_fact(...)``
    - edge labels remain on graph edges as attributes

    When an edge fact carries a non-default interval, the current adapter
    lowers it to a lower-bound summary on the graph attribute.
    """
    import networkx as nx
    del schema_ir

    graph = nx.DiGraph()

    nodes: set[str] = set()
    for fact in session.node_facts:
        nodes.add(str(fact["node_ref"]))
    for fact in session.edge_facts:
        nodes.add(str(fact["from_ref"]))
        nodes.add(str(fact["to_ref"]))
    for node in sorted(nodes):
        graph.add_node(node)

    for fact in session.edge_facts:
        from_ref = str(fact["from_ref"])
        to_ref = str(fact["to_ref"])
        attr_name = _pred_short_name(str(fact["pred_id"]))
        lo, hi = fact.get("bound", (1.0, 1.0))
        val = lo if lo != 1.0 or hi != 1.0 else 1
        if graph.has_edge(from_ref, to_ref):
            graph.edges[from_ref, to_ref][attr_name] = val
        else:
            graph.add_edge(from_ref, to_ref, **{attr_name: val})

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

    bounded = _bounded_pred_ids(schema_ir)
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
                    edge_derived_value = str(lo) if pred_id in bounded else ""
                    derived._write_edge_fact_internal(
                        pred_id,
                        from_ref,
                        to_ref,
                        edge_derived_value,
                        bound=[lo, hi],
                        active_from=timestep,
                        meta={"source": "pyreason_derived", "derived_at_timestep": timestep},
                    )
                    continue

                key = (str(component), pred_name)
                if key in input_node_keys:
                    continue
                input_node_keys.add(key)
                derived_value = str(lo) if pred_id in bounded else str(lo == 1.0 and hi == 1.0).lower()
                derived._write_node_fact_internal(
                    pred_id,
                    str(component),
                    derived_value,
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


def _format_fact_text_with_bound(atom: str, bound: tuple[float, float] | list[float]) -> str:
    """Render a typed fact as PyReason fact text with an explicit interval."""
    lo = float(bound[0])
    hi = float(bound[1])
    return f"{atom} : [{lo}, {hi}]"


def _pred_short_name(pred_id: str) -> str:
    parts = pred_id.split(":", 1)
    return parts[1] if len(parts) > 1 else pred_id


def _normalize_bound(bound: tuple[float, float] | list[float]) -> tuple[float, float]:
    return (float(bound[0]), float(bound[1]))


def _is_default_bound(bound: tuple[float, float] | list[float]) -> bool:
    return _normalize_bound(bound) == (1.0, 1.0)


def _is_node_fact_text(fact_text: str) -> bool:
    compact = fact_text.replace(" ", "")
    pred_comp = compact.split(":", 1)[0]
    idx = pred_comp.find("(")
    if idx < 0 or not pred_comp.endswith(")"):
        return False
    component = pred_comp[idx + 1:-1]
    return "," not in component


def _bound_from_fact_text(fact_text: str) -> tuple[float, float] | None:
    compact = fact_text.replace(" ", "")
    if ":" not in compact:
        return (1.0, 1.0)

    _, bound_text = compact.split(":", 1)
    lowered = bound_text.lower()
    if lowered == "true":
        return (1.0, 1.0)
    if lowered == "false":
        return (0.0, 0.0)
    if not (bound_text.startswith("[") and bound_text.endswith("]")):
        return None

    try:
        lo_str, hi_str = bound_text[1:-1].split(",", 1)
        return (float(lo_str), float(hi_str))
    except (TypeError, ValueError):
        return None


def _bounded_node_seed_descriptors(
    session: PyReasonSession,
    *,
    facts: list[tuple[str, str, int, int]] | None,
    fact_defs: list[PyReasonFactDef] | None,
) -> list[str]:
    descriptors: list[str] = []

    for fact in session.node_facts:
        bound = fact.get("bound", (1.0, 1.0))
        if _is_default_bound(bound):
            continue
        descriptors.append(f"session:{fact['pred_id']}@{fact['node_ref']}={_normalize_bound(bound)}")

    for fact_def in fact_defs or []:
        if _is_node_fact_text(fact_def.atom) and not _is_default_bound(fact_def.bound):
            descriptors.append(f"fact_def:{fact_def.name}={_normalize_bound(fact_def.bound)}")

    for fact_text, name_str, _, _ in facts or []:
        if not _is_node_fact_text(fact_text):
            continue
        bound = _bound_from_fact_text(fact_text)
        if bound is None or _is_default_bound(bound):
            continue
        label = name_str or fact_text
        descriptors.append(f"fact:{label}={bound}")

    return descriptors


def _warn_on_bounded_node_seeds(
    session: PyReasonSession,
    *,
    all_rules: list[tuple[str, str]],
    facts: list[tuple[str, str, int, int]] | None,
    fact_defs: list[PyReasonFactDef] | None,
) -> None:
    if not all_rules:
        return
    if _rules_have_explicit_body_intervals(all_rules):
        return

    descriptors = _bounded_node_seed_descriptors(session, facts=facts, fact_defs=fact_defs)
    if not descriptors:
        return

    preview = ", ".join(descriptors[:3])
    if len(descriptors) > 3:
        preview = f"{preview}, ..."

    warnings.warn(
        "PyReason body clauses default to an implicit [1.0, 1.0] interval threshold. "
        "This run combines rules with bounded node seeds and no explicit body-clause "
        "intervals, so those seeds may fail to match rule bodies. Add explicit clause "
        "bounds (for example `popular(y) : [0.5, 1.0]`) when bounded seeds should "
        f"participate in matching. Affected seeds: {preview}",
        UserWarning,
        stacklevel=2,
    )


def _rules_have_explicit_body_intervals(all_rules: list[tuple[str, str]]) -> bool:
    for rule_text, _ in all_rules:
        body = rule_text.split("<-", 1)[1] if "<-" in rule_text else rule_text
        if re.search(r"\)\s*:\s*\[", body):
            return True
    return False


def _session_fact_records(
    session: PyReasonSession,
    *,
    default_end_time: int,
) -> list[tuple[str, str, int, int]]:
    """Lower session node facts into PyReason ``add_fact()`` records only."""
    records: list[tuple[str, str, int, int]] = []
    for idx, fact in enumerate(session.node_facts):
        atom = f"{_pred_short_name(str(fact['pred_id']))}({str(fact['node_ref'])})"
        end_time = int(fact["active_to"]) if fact.get("active_to") is not None else default_end_time
        records.append(
            (
                _format_fact_text_with_bound(atom, fact.get("bound", (1.0, 1.0))),
                f"session_node_{idx}",
                int(fact.get("active_from", 0)),
                end_time,
            )
        )
    return records


def run_pyreason(
    session: PyReasonSession,
    *,
    rules: list[tuple[str, str]] | None = None,
    rule_defs: list[Rule] | None = None,
    facts: list[tuple[str, str, int, int]] | None = None,
    fact_defs: list[PyReasonFactDef] | None = None,
    config: PyReasonRunConfig | None = None,
) -> PyReasonRunResult:
    """Run PyReason reasoning on a populated session."""
    import pyreason as pr

    if config is None:
        config = PyReasonRunConfig()

    all_rules: list[tuple[str, str]] = list(rules or [])
    for rule_def in rule_defs or []:
        all_rules.append(compile_pyreason_rule(rule_def))

    _warn_on_bounded_node_seeds(
        session,
        all_rules=all_rules,
        facts=facts,
        fact_defs=fact_defs,
    )

    all_facts: list[tuple[str, str, int, int]] = _session_fact_records(
        session,
        default_end_time=config.timesteps,
    )
    all_facts.extend(list(facts or []))
    for fact_def in fact_defs or []:
        all_facts.append(
            (
                _format_fact_text_with_bound(fact_def.atom, fact_def.bound),
                fact_def.name,
                fact_def.start,
                fact_def.end,
            )
        )

    start = time.monotonic()

    graph = build_pyreason_graph(session, schema_ir=session._schema_ir)
    with _PYREASON_LOCK:
        pr.reset()
        try:
            pr.load_graph(graph)

            for body_str, name_str in all_rules:
                pr.add_rule(pr.Rule(body_str, name_str))

            for fact_text, name_str, start_time, end_time in all_facts:
                pr.add_fact(pr.Fact(fact_text, name_str, start_time, end_time))

            pr.settings.atom_trace = config.atom_trace
            interpretation = pr.reason(timesteps=config.timesteps)

            trace: PyReasonTraceV0 | None = None
            trace_dict: dict[str, Any] | None = None
            if config.atom_trace:
                nodes_trace, edges_trace = pr.get_rule_trace(interpretation)
                trace = parse_pyreason_trace(nodes_trace, edges_trace, timesteps=config.timesteps)
                trace_dict = pyreason_trace_to_dict(trace)

            derived_session = _extract_derived_facts(interpretation, session._schema_ir, session)
        finally:
            pr.reset()

    return PyReasonRunResult(
        interpretation=interpretation,
        trace=trace,
        trace_dict=trace_dict,
        derived_session=derived_session,
        config=config,
        elapsed_seconds=time.monotonic() - start,
    )
