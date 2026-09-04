"""CandidateProvenanceTimeline — runtime explain contract for PyReason event logs.

This is the PyReason counterpart to CandidateEvidenceTree:
- CandidateEvidenceTree -> tree-shaped, for native/souffle witnesses
- CandidateProvenanceTimeline -> event-chain, for pyreason temporal propagation

Blueprint: 2026-03-30_pyreason-runtime-explain-timeline.md
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimelineEvent:
    """A single bound change in a PyReason reasoning trace."""

    time: int
    fixpoint_op: int
    old_bound: tuple[float, float]
    new_bound: tuple[float, float]
    trigger: str  # rule label or "seed_fact"
    groundings: tuple[str, ...]  # opaque clause grounding strings


@dataclass(frozen=True)
class TimelineChain:
    """A sequence of bound changes for one (component_type, component, label)."""

    component: str  # node/edge identifier
    component_type: str  # "node" or "edge"
    label: str  # predicate short name
    events: tuple[TimelineEvent, ...]  # ordered by (time, fixpoint_op)


@dataclass(frozen=True)
class CandidateProvenanceTimeline:
    """Runtime explain contract for PyReason candidates.

    Chains are sorted by (component_type, component, label) lexicographic.
    root_chain_key identifies which chain matches the candidate payload.
    """

    candidate_id: str
    engine: str  # "pyreason"
    timesteps: int
    chains: tuple[TimelineChain, ...]
    root_chain_key: tuple[str, str, str]  # (component_type, component, label)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

_SEED_MARKERS = frozenset({"fact", "seed", "seed_fact"})


def _is_seed_trigger(trigger: str) -> bool:
    marker = trigger.strip().lower()
    return any(s in marker for s in _SEED_MARKERS)


def build_candidate_provenance_timeline(
    *,
    candidate_id: str,
    trace: Any,
    candidate_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build CandidateProvenanceTimeline dict from a PyReasonTraceV0.

    Args:
        candidate_id: The candidate this timeline explains.
        trace: A PyReasonTraceV0 instance (event log).
        candidate_payload: The candidate's payload dict with pred_id + terms,
            used to resolve which chain is the root.

    Returns:
        Dict with ``kind="candidate_provenance_timeline"``.

    Raises:
        ValueError: If inputs are invalid or root chain cannot be resolved.
    """
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be non-empty string")

    # --- resolve root anchor from candidate payload ---
    root_component_type, root_component, root_label = _resolve_candidate_anchor(
        candidate_payload
    )
    root_key = (root_component_type, root_component, root_label)

    # --- gather all events ---
    all_events = [*trace.node_events, *trace.edge_events]
    if not all_events:
        raise ValueError("PyReason trace has no events")

    # --- group by (component_type, component, label) ---
    chain_map: dict[tuple[str, str, str], list[Any]] = {}
    for event in all_events:
        comp_key = _normalize_component_key(event)
        key = (event.component_type, comp_key, event.label)
        chain_map.setdefault(key, []).append(event)

    # --- validate root chain exists ---
    if root_key not in chain_map:
        raise ValueError(
            f"candidate anchor not found in trace: "
            f"{root_component_type} {root_component} {root_label}"
        )

    # --- build sorted chains ---
    sorted_keys = sorted(chain_map.keys())
    chains = []
    for key in sorted_keys:
        raw_events = chain_map[key]
        raw_events.sort(key=lambda e: (int(e.time), int(e.fixpoint_op)))
        timeline_events = tuple(
            TimelineEvent(
                time=int(ev.time),
                fixpoint_op=int(ev.fixpoint_op),
                old_bound=(float(ev.old_bound[0]), float(ev.old_bound[1])),
                new_bound=(float(ev.new_bound[0]), float(ev.new_bound[1])),
                trigger=str(ev.occurred_due_to),
                groundings=tuple(str(g) for g in ev.clause_groundings),
            )
            for ev in raw_events
        )
        chains.append(
            TimelineChain(
                component=key[1],
                component_type=key[0],
                label=key[2],
                events=timeline_events,
            )
        )

    timeline = CandidateProvenanceTimeline(
        candidate_id=candidate_id,
        engine="pyreason",
        timesteps=int(trace.timesteps),
        chains=tuple(chains),
        root_chain_key=root_key,
    )

    return _timeline_to_dict(timeline)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _timeline_to_dict(tl: CandidateProvenanceTimeline) -> dict[str, Any]:
    return {
        "kind": "candidate_provenance_timeline",
        "candidate_id": tl.candidate_id,
        "engine": tl.engine,
        "timesteps": tl.timesteps,
        "chains": [
            {
                "component": chain.component,
                "component_type": chain.component_type,
                "label": chain.label,
                "events": [
                    {
                        "time": ev.time,
                        "fixpoint_op": ev.fixpoint_op,
                        "old_bound": list(ev.old_bound),
                        "new_bound": list(ev.new_bound),
                        "trigger": ev.trigger,
                        "groundings": list(ev.groundings),
                    }
                    for ev in chain.events
                ],
            }
            for chain in tl.chains
        ],
        "root_chain_key": list(tl.root_chain_key),
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summarize_candidate_provenance_timeline(timeline: dict[str, Any]) -> dict[str, Any]:
    """Produce a compact summary from a CandidateProvenanceTimeline dict."""
    chains = timeline.get("chains", [])
    root_key = tuple(timeline.get("root_chain_key", []))

    seed_count = 0
    derived_count = 0
    trigger_rules: set[str] = set()
    final_bound: list[float] | None = None

    for chain in chains:
        events = chain.get("events", [])
        if not events:
            continue
        first_trigger = events[0].get("trigger", "")
        if _is_seed_trigger(first_trigger):
            seed_count += 1
        else:
            derived_count += 1
        for ev in events:
            trigger = ev.get("trigger", "")
            if not _is_seed_trigger(trigger):
                trigger_rules.add(trigger)

        chain_key = (
            chain.get("component_type", ""),
            chain.get("component", ""),
            chain.get("label", ""),
        )
        if chain_key == root_key and events:
            final_bound = events[-1].get("new_bound")

    return {
        "explain_kind": "timeline",
        "timesteps": timeline.get("timesteps", 0),
        "chain_count": len(chains),
        "seed_count": seed_count,
        "derived_count": derived_count,
        "trigger_rules": sorted(trigger_rules),
        "final_bound": final_bound,
    }


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------


def render_candidate_provenance_timeline_narrative(
    timeline: dict[str, Any],
) -> dict[str, Any]:
    """Produce a chain-local narrative from a CandidateProvenanceTimeline dict.

    V1 narrative is strictly chain-local: each line describes one chain's events.
    Does NOT infer cross-chain causality from groundings.
    """
    chains = timeline.get("chains", [])
    root_key = tuple(timeline.get("root_chain_key", []))
    timesteps = timeline.get("timesteps", 0)

    propagation_lines: list[str] = []
    seed_labels: list[str] = []

    for chain in chains:
        events = chain.get("events", [])
        component = chain.get("component", "?")
        label = chain.get("label", "?")

        for ev in events:
            trigger = ev.get("trigger", "")
            new_bound = ev.get("new_bound", [0, 1])
            time = ev.get("time", 0)
            bound_str = f"[{new_bound[0]}, {new_bound[1]}]"

            if _is_seed_trigger(trigger):
                propagation_lines.append(
                    f"t={time}: {component}.{label} seeded {bound_str}"
                )
                seed_labels.append(f"{component} {label}")
            else:
                propagation_lines.append(
                    f"t={time}: {component}.{label} updated to {bound_str} by {trigger}"
                )

    propagation_lines.sort(key=lambda line: int(line.split(":")[0].split("=")[1]))

    root_label = root_key[2] if len(root_key) >= 3 else "?"
    headline = f"{root_label}: {len(chains)} chains, {timesteps} timesteps"

    seed_summary = (
        f"{len(seed_labels)} seed chain{'s' if len(seed_labels) != 1 else ''}"
    )

    return {
        "headline": headline,
        "propagation_lines": propagation_lines,
        "seed_summary": seed_summary,
        "convergence": f"Fixed point at t={timesteps}",
    }


def render_candidate_provenance_timeline_nl_explain(
    summary: dict[str, Any],
    narrative: dict[str, Any],
    *,
    locale: str = "en",
) -> dict[str, Any]:
    """Timeline NL explain — symmetric with CandidateEvidenceTree NL."""
    if not isinstance(summary, Mapping):
        raise ValueError("summary must be object")
    if not isinstance(narrative, Mapping):
        raise ValueError("narrative must be object")
    if not isinstance(locale, str) or not locale:
        raise ValueError("locale must be non-empty string")

    timesteps = int(summary.get("timesteps", 0))
    chain_count = int(summary.get("chain_count", 0))
    seed_count = int(summary.get("seed_count", 0))
    derived_count = int(summary.get("derived_count", 0))
    trigger_rules = summary.get("trigger_rules", [])
    final_bound = summary.get("final_bound")

    headline_text = str(narrative.get("headline", "Timeline propagation"))
    seed_summary = str(narrative.get("seed_summary", ""))
    convergence = str(narrative.get("convergence", ""))
    propagation_lines = narrative.get("propagation_lines", [])

    headline = (
        f"{headline_text} across {timesteps} timestep{'s' if timesteps != 1 else ''}."
    )

    paragraphs: list[str] = []

    overview_parts = [f"{chain_count} propagation chain{'s' if chain_count != 1 else ''}"]
    if seed_count:
        overview_parts.append(f"{seed_count} seeded")
    if derived_count:
        overview_parts.append(f"{derived_count} derived by rule")
    if isinstance(trigger_rules, list) and trigger_rules:
        overview_parts.append(
            f"rules: {', '.join(str(rule) for rule in trigger_rules if isinstance(rule, str) and rule)}"
        )
    paragraphs.append(f"Overview: {', '.join(overview_parts)}. {seed_summary}".strip())

    if isinstance(propagation_lines, list) and propagation_lines:
        events = " ".join(
            line.strip()
            for line in propagation_lines
            if isinstance(line, str) and line.strip()
        )
        if events:
            paragraphs.append(f"Propagation events: {events}")

    conv_parts: list[str] = []
    if convergence:
        conv_parts.append(convergence)
    if final_bound is not None:
        conv_parts.append(f"Final bound: {final_bound}.")
    if conv_parts:
        paragraphs.append(" ".join(conv_parts))

    return {"headline": headline, "paragraphs": paragraphs}


def build_candidate_provenance_steps(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Build a flat, time-ordered list of steps from a candidate_provenance_timeline dict.
    Seed events -> bound_seed; rule-update events -> bound_update.
    A synthetic convergence step is appended at the end.
    """
    chains = timeline.get("chains", [])
    if not isinstance(chains, list):
        raise ValueError("timeline.chains must be list")

    def _fmt_bound(b: Any) -> str:
        if isinstance(b, (list, tuple)) and len(b) == 2:
            return f"[{b[0]:.3f}, {b[1]:.3f}]"
        return str(b)

    all_events: list[tuple[int, int, dict[str, Any], dict[str, Any]]] = []
    for chain_idx, chain in enumerate(chains):
        if not isinstance(chain, Mapping):
            continue
        for event in chain.get("events", []):
            if not isinstance(event, Mapping):
                continue
            all_events.append((int(event.get("time", 0)), chain_idx, dict(event), dict(chain)))

    all_events.sort(key=lambda x: (x[0], x[1]))

    steps: list[dict[str, Any]] = []
    for step_num, (time, _chain_idx, event, chain) in enumerate(all_events, start=1):
        component = str(chain.get("component", ""))
        component_type = str(chain.get("component_type", ""))
        label = str(chain.get("label", ""))
        trigger = str(event.get("trigger", ""))
        old_bound = event.get("old_bound", [0.0, 0.0])
        new_bound = event.get("new_bound", [0.0, 0.0])
        groundings = event.get("groundings", [])

        is_seed = trigger == "seed_fact"
        step_kind = "bound_seed" if is_seed else "bound_update"
        old_str = _fmt_bound(old_bound)
        new_str = _fmt_bound(new_bound)

        if is_seed:
            description = f"t={time}: {component}.{label} initialized to {new_str}"
        else:
            description = f"t={time}: {component}.{label} updated {old_str} -> {new_str} by {trigger}"

        node_ref = f"{component_type}/{component}/{label}"
        steps.append(
            {
                "step_num": step_num,
                "step_kind": step_kind,
                "description": description,
                "node_ref": node_ref,
                "detail": {
                    "depth": 0,
                    "parent_node_ref": None,
                    "time": time,
                    "component": component,
                    "component_type": component_type,
                    "label": label,
                    "trigger": trigger,
                    "old_bound": old_bound,
                    "new_bound": new_bound,
                    "groundings": groundings,
                },
            }
        )

    if steps:
        n_chains = len([c for c in chains if isinstance(c, Mapping)])
        timesteps = timeline.get("timesteps", 0)
        conv_num = len(steps) + 1
        final_bounds = []
        for chain in chains:
            if not isinstance(chain, Mapping):
                continue
            evts = chain.get("events", [])
            if evts and isinstance(evts[-1], Mapping):
                nb = evts[-1].get("new_bound", [])
                comp = chain.get("component", "")
                lbl = chain.get("label", "")
                final_bounds.append(f"{comp}.{lbl}={_fmt_bound(nb)}")
        bound_summary = "; ".join(final_bounds) if final_bounds else "-"
        steps.append(
            {
                "step_num": conv_num,
                "step_kind": "convergence",
                "description": (
                    f"Converged after {timesteps} timestep(s) across {n_chains} chain(s). "
                    f"Final bounds: {bound_summary}"
                ),
                "node_ref": None,
                "detail": {
                    "depth": 0,
                    "parent_node_ref": None,
                    "timesteps": timesteps,
                    "chain_count": n_chains,
                },
            }
        )

    return steps


# ---------------------------------------------------------------------------
# Helpers (reused logic from pyreason adapter)
# ---------------------------------------------------------------------------


def _resolve_candidate_anchor(
    candidate_payload: Mapping[str, Any],
) -> tuple[str, str, str]:
    """Extract (component_type, component, label) from candidate payload."""
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
    label = _pred_short_name(pred_id)
    if len(entity_refs) == 1:
        return ("node", entity_refs[0], label)
    if len(entity_refs) >= 2:
        return ("edge", f"{entity_refs[0]}->{entity_refs[1]}", label)
    raise ValueError("candidate_payload must include at least one entity_ref term")


def _pred_short_name(pred_id: str) -> str:
    parts = pred_id.rsplit(":", 1)
    return parts[-1] if parts else pred_id


def _normalize_component_key(event: Any) -> str:
    if event.component_type != "edge":
        return event.component
    raw = event.component
    if isinstance(raw, str) and raw.startswith("(") and raw.endswith(")"):
        inner = raw[1:-1]
        parts = [p.strip().strip("'\"") for p in inner.split(",")]
        if len(parts) >= 2:
            return f"{parts[0]}->{parts[1]}"
    return raw


__all__ = [
    "CandidateProvenanceTimeline",
    "TimelineChain",
    "TimelineEvent",
    "build_candidate_provenance_steps",
    "build_candidate_provenance_timeline",
    "render_candidate_provenance_timeline_narrative",
    "render_candidate_provenance_timeline_nl_explain",
    "summarize_candidate_provenance_timeline",
]
