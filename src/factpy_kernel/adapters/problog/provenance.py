"""ProbLog provenance trace carrier (adapter-local, V0 spike)."""
from __future__ import annotations

from collections import Counter
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from factpy_kernel.adapters.problog._parsing import _split_top_level_args
from factpy_kernel.audit.evidence_graph import (
    EDGE_DERIVES,
    LAYOUT_TREE,
    NODE_CONCLUSION,
    NODE_PREMISE,
    NODE_SEED,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
)
from factpy_kernel.core.store._support import PROBLOG_PROVENANCE_KIND

_TRACE_CALL_RE = re.compile(
    r"^(?P<indent>\s*)(?P<event>call)\s+(?P<goal>.+?)\s+\{(?P<started>[0-9.]+)\}\s+\[(?P<location>[^\]]*)\]$"
)
_TRACE_RESULT_RE = re.compile(
    r"^(?P<indent>\s*)(?P<event>result)\s+(?P<goal>.+?)\s+\((?P<result_terms>.*)\)\s+\{\{(?P<bindings>.*)\}\}\s+\{(?P<started>[0-9.]+)\}\s+\[(?P<location>[^\]]*)\]$"
)
_TRACE_COMPLETE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<event>complete|fail)\s+(?P<goal>.+?)\s+\{(?P<started>[0-9.]+)\}\s+\{(?P<elapsed>[0-9.]+)\}\s+\[(?P<location>[^\]]*)\]$"
)
_ANSWER_RE = re.compile(r"^(?P<query>.+?):\s*(?P<probability>[0-9.eE+-]+)\s*$")


class ProbLogProvenanceError(Exception):
    pass


@dataclass(frozen=True)
class ProbLogTraceEventV0:
    depth: int
    event_type: str
    goal: str
    started_seconds: float
    elapsed_seconds: float | None = None
    location: str | None = None
    result_terms: tuple[str, ...] = ()
    bindings_text: str | None = None


@dataclass(frozen=True)
class ProbLogAnswerV0:
    query: str
    probability: float


@dataclass(frozen=True)
class ProbLogTraceV0:
    events: tuple[ProbLogTraceEventV0, ...]
    answers: tuple[ProbLogAnswerV0, ...]


@dataclass
class _ProbLogCallFrame:
    frame_id: str
    call_event: ProbLogTraceEventV0
    parent_frame_id: str | None = None
    child_frame_ids: list[str] = field(default_factory=list)
    result_event: ProbLogTraceEventV0 | None = None
    complete_event: ProbLogTraceEventV0 | None = None
    fail_event: ProbLogTraceEventV0 | None = None


def parse_problog_trace(raw_output: str) -> ProbLogTraceV0:
    if not isinstance(raw_output, str):
        raise ProbLogProvenanceError("raw_output must be string")

    events: list[ProbLogTraceEventV0] = []
    answers: list[ProbLogAnswerV0] = []
    for raw_line in raw_output.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue

        trace_match = _TRACE_CALL_RE.match(line)
        if trace_match is not None:
            events.append(
                ProbLogTraceEventV0(
                    depth=_normalize_depth(trace_match.group("indent")),
                    event_type="call",
                    goal=trace_match.group("goal"),
                    started_seconds=float(trace_match.group("started")),
                    location=_normalize_location(trace_match.group("location")),
                )
            )
            continue

        trace_match = _TRACE_RESULT_RE.match(line)
        if trace_match is not None:
            events.append(
                ProbLogTraceEventV0(
                    depth=_normalize_depth(trace_match.group("indent")),
                    event_type="result",
                    goal=trace_match.group("goal"),
                    started_seconds=float(trace_match.group("started")),
                    location=_normalize_location(trace_match.group("location")),
                    result_terms=_split_terms(trace_match.group("result_terms")),
                    bindings_text=_normalize_optional_text(trace_match.group("bindings")),
                )
            )
            continue

        trace_match = _TRACE_COMPLETE_RE.match(line)
        if trace_match is not None:
            events.append(
                ProbLogTraceEventV0(
                    depth=_normalize_depth(trace_match.group("indent")),
                    event_type=trace_match.group("event"),
                    goal=trace_match.group("goal"),
                    started_seconds=float(trace_match.group("started")),
                    elapsed_seconds=float(trace_match.group("elapsed")),
                    location=_normalize_location(trace_match.group("location")),
                )
            )
            continue

        answer_match = _ANSWER_RE.match(line.strip())
        if answer_match is not None:
            answers.append(
                ProbLogAnswerV0(
                    query=answer_match.group("query").strip(),
                    probability=float(answer_match.group("probability")),
                )
            )

    return ProbLogTraceV0(
        events=tuple(events),
        answers=tuple(answers),
    )


def problog_trace_to_dict(trace: ProbLogTraceV0) -> dict[str, Any]:
    return {
        "engine": "problog",
        "trace_type": "proof_trace",
        "events": [
            {
                "depth": event.depth,
                "event_type": event.event_type,
                "goal": event.goal,
                "started_seconds": event.started_seconds,
                "elapsed_seconds": event.elapsed_seconds,
                "location": event.location,
                "result_terms": list(event.result_terms),
                "bindings_text": event.bindings_text,
            }
            for event in trace.events
        ],
        "answers": [
            {
                "query": answer.query,
                "probability": answer.probability,
            }
            for answer in trace.answers
        ],
    }


def problog_trace_from_dict(row: Mapping[str, Any]) -> ProbLogTraceV0:
    if not isinstance(row, Mapping):
        raise ValueError("row must be Mapping[str, Any]")
    if row.get("engine") != "problog":
        raise ValueError("row.engine must be 'problog'")
    if row.get("trace_type") != "proof_trace":
        raise ValueError("row.trace_type must be 'proof_trace'")
    raw_events = row.get("events")
    raw_answers = row.get("answers")
    if not isinstance(raw_events, list):
        raise ValueError("row.events must be list")
    if not isinstance(raw_answers, list):
        raise ValueError("row.answers must be list")
    return ProbLogTraceV0(
        events=tuple(_trace_event_from_dict(event) for event in raw_events),
        answers=tuple(_answer_from_dict(answer) for answer in raw_answers),
    )


def problog_trace_to_evidence_graph(
    trace: ProbLogTraceV0,
    *,
    candidate_id: str,
    candidate_payload: Mapping[str, Any],
    support_kind: str = PROBLOG_PROVENANCE_KIND,
) -> EvidenceGraph:
    """Convert a ProbLog proof trace into a candidate-anchored EvidenceGraph tree."""
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be non-empty string")
    if not trace.events:
        raise ValueError("ProbLog trace has no events")

    candidate_info = _resolve_candidate_info(candidate_payload)
    frames = _build_call_frames(trace)
    if not frames:
        raise ValueError("ProbLog trace has no call frames")

    root_frame_id, matched_answer = _select_root_frame(
        trace=trace,
        frames=frames,
        candidate_label=candidate_info["label"],
        candidate_term_counter=candidate_info["term_counter"],
    )
    if root_frame_id is None:
        raise ValueError("candidate anchor not found in ProbLog trace")

    frame_order = _collect_frame_subtree(frames, root_frame_id)
    nodes: list[EvidenceNode] = []
    edges: list[EvidenceEdge] = []
    node_id_by_frame_id: dict[str, str] = {}

    for idx, frame_id in enumerate(frame_order):
        frame = frames[frame_id]
        goal_name, goal_args = _parse_goal_expr(frame.call_event.goal)
        node_id = f"problog:{candidate_id}:frame:{idx}"
        node_id_by_frame_id[frame_id] = node_id

        if frame_id == root_frame_id:
            node_kind = NODE_CONCLUSION
            label = candidate_info["label"]
            component = candidate_info["component"]
            value_summary = _format_probability(matched_answer.probability) if matched_answer else _frame_value_summary(frame)
        else:
            label = goal_name
            component = _goal_component(goal_args)
            value_summary = _frame_value_summary(frame)
            node_kind = NODE_SEED if not frame.child_frame_ids else NODE_PREMISE

        nodes.append(
            EvidenceNode(
                node_id=node_id,
                node_kind=node_kind,
                component=component,
                label=label,
                value_summary=value_summary,
                timestamp=None,
                engine_meta={
                    "goal": frame.call_event.goal,
                    "goal_name": goal_name,
                    "goal_args": goal_args,
                    "call_started_seconds": frame.call_event.started_seconds,
                    "location": frame.call_event.location,
                    "result_terms": frame.result_event.result_terms if frame.result_event else (),
                    "bindings_text": frame.result_event.bindings_text if frame.result_event else None,
                    "elapsed_seconds": frame.complete_event.elapsed_seconds if frame.complete_event else None,
                    "event_status": _frame_status(frame),
                    "synthetic_goal": _is_synthetic_goal_name(goal_name),
                    "answer_probability": matched_answer.probability if frame_id == root_frame_id and matched_answer else None,
                },
            )
        )

    edge_counter = 0
    for frame_id in frame_order:
        parent_frame = frames[frame_id]
        for child_frame_id in parent_frame.child_frame_ids:
            if child_frame_id not in node_id_by_frame_id:
                continue
            edge_counter += 1
            child_frame = frames[child_frame_id]
            edges.append(
                EvidenceEdge(
                    edge_id=f"problog:{candidate_id}:edge:{edge_counter}",
                    from_node_id=node_id_by_frame_id[child_frame_id],
                    to_node_id=node_id_by_frame_id[frame_id],
                    edge_kind=EDGE_DERIVES,
                    rule_label=None,
                    engine_meta={
                        "parent_goal": parent_frame.call_event.goal,
                        "child_goal": child_frame.call_event.goal,
                        "parent_location": parent_frame.call_event.location,
                    },
                )
            )

    return EvidenceGraph(
        graph_id=f"eg:{candidate_id}",
        engine="problog",
        root_node_id=node_id_by_frame_id[root_frame_id],
        nodes=tuple(nodes),
        edges=tuple(edges),
        support_kind=support_kind,
        layout_hint=LAYOUT_TREE,
        metadata={
            "event_count": len(trace.events),
            "answer_count": len(trace.answers),
            "root_goal": frames[root_frame_id].call_event.goal,
            "answer_probability": matched_answer.probability if matched_answer else None,
        },
    )


def problog_trace_to_candidate_evidence_tree(
    trace: ProbLogTraceV0,
    *,
    candidate_id: str,
    candidate_payload: Mapping[str, Any],
    support_digest: str,
    support_kind: str = PROBLOG_PROVENANCE_KIND,
) -> dict[str, Any]:
    """Convert a ProbLog proof trace into CandidateEvidenceTree."""
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be non-empty string")
    if not isinstance(support_digest, str) or not support_digest:
        raise ValueError("support_digest must be non-empty string")
    if not trace.events:
        raise ValueError("ProbLog trace has no events")

    candidate_info = _resolve_candidate_info(candidate_payload)
    frames = _build_call_frames(trace)
    if not frames:
        raise ValueError("ProbLog trace has no call frames")

    root_frame_id, matched_answer = _select_root_frame(
        trace=trace,
        frames=frames,
        candidate_label=candidate_info["label"],
        candidate_term_counter=candidate_info["term_counter"],
    )
    if root_frame_id is None:
        raise ValueError("candidate anchor not found in ProbLog trace")

    visible_frame_ids = _collect_visible_frames(frames, root_frame_id)
    node_id_by_frame_id = {
        frame_id: f"problog:{candidate_id}:frame:{idx}"
        for idx, frame_id in enumerate(visible_frame_ids, start=1)
    }
    support_children = _build_visible_tree_nodes(
        frames=frames,
        frame_id=root_frame_id,
        node_id_by_frame_id=node_id_by_frame_id,
    )
    root_node: dict[str, Any] = {
        "node_id": f"cand:{candidate_id}",
        "node_kind": "candidate_result",
        "title": f"Candidate {candidate_id}",
        "root_result_kind": "fact",
        "binding": _candidate_binding_from_payload(candidate_payload),
        "rule_refs": [],
        "rule_ref_edges": [],
        "children": [
            {
                "node_id": f"support:{candidate_id}",
                "node_kind": "support_section",
                "title": "Support",
                "children": support_children,
            }
        ],
    }
    if matched_answer is not None:
        root_node["engine_meta"] = {
            "engine": "problog",
            "probability": matched_answer.probability,
        }

    return {
        "kind": "candidate_evidence_tree",
        "candidate_id": candidate_id,
        "support_digest": support_digest,
        "support_kind": support_kind,
        "root": root_node,
    }


def _normalize_depth(indent: str) -> int:
    if not indent:
        return 0
    return max(0, len(indent) - 1)


def _trace_event_from_dict(row: Any) -> ProbLogTraceEventV0:
    if not isinstance(row, Mapping):
        raise ValueError("trace event row must be Mapping[str, Any]")
    result_terms = row.get("result_terms", [])
    if not isinstance(result_terms, list):
        raise ValueError("trace event result_terms must be list")
    elapsed_seconds = row.get("elapsed_seconds")
    if elapsed_seconds is not None:
        elapsed_seconds = float(elapsed_seconds)
    location = row.get("location")
    if location is not None:
        location = str(location)
    bindings_text = row.get("bindings_text")
    if bindings_text is not None:
        bindings_text = str(bindings_text)
    return ProbLogTraceEventV0(
        depth=int(row.get("depth", 0)),
        event_type=str(row.get("event_type", "")),
        goal=str(row.get("goal", "")),
        started_seconds=float(row.get("started_seconds", 0.0)),
        elapsed_seconds=elapsed_seconds,
        location=location,
        result_terms=tuple(str(item) for item in result_terms),
        bindings_text=bindings_text,
    )


def _answer_from_dict(row: Any) -> ProbLogAnswerV0:
    if not isinstance(row, Mapping):
        raise ValueError("answer row must be Mapping[str, Any]")
    return ProbLogAnswerV0(
        query=str(row.get("query", "")),
        probability=float(row.get("probability", 0.0)),
    )


def _normalize_location(raw: str) -> str | None:
    value = raw.strip()
    return value or None


def _normalize_optional_text(raw: str) -> str | None:
    value = raw.strip()
    return value or None


def _split_terms(raw_terms: str) -> tuple[str, ...]:
    value = raw_terms.strip()
    if not value:
        return ()
    parts = [part.strip() for part in value.split(",") if part.strip()]
    return tuple(parts)


def _build_call_frames(trace: ProbLogTraceV0) -> dict[str, _ProbLogCallFrame]:
    frames: dict[str, _ProbLogCallFrame] = {}
    open_stack: list[str] = []
    counter = 0

    for event in trace.events:
        if event.event_type == "call":
            while len(open_stack) > event.depth:
                open_stack.pop()
            parent_frame_id = open_stack[-1] if open_stack else None
            frame_id = f"frame:{counter}"
            counter += 1
            frames[frame_id] = _ProbLogCallFrame(
                frame_id=frame_id,
                call_event=event,
                parent_frame_id=parent_frame_id,
            )
            if parent_frame_id is not None:
                frames[parent_frame_id].child_frame_ids.append(frame_id)
            open_stack.append(frame_id)
            continue

        if event.event_type == "result":
            frame_id = _find_matching_open_frame(
                open_stack,
                frames,
                goal=event.goal,
                expected_depth=event.depth - 1,
            )
            if frame_id is not None:
                frames[frame_id].result_event = event
            continue

        if event.event_type in {"complete", "fail"}:
            frame_id = _find_matching_open_frame(
                open_stack,
                frames,
                goal=event.goal,
                expected_depth=event.depth,
            )
            if frame_id is None:
                continue
            if event.event_type == "complete":
                frames[frame_id].complete_event = event
            else:
                frames[frame_id].fail_event = event
            while open_stack:
                popped = open_stack.pop()
                if popped == frame_id:
                    break

    return frames


def _find_matching_open_frame(
    open_stack: list[str],
    frames: Mapping[str, _ProbLogCallFrame],
    *,
    goal: str,
    expected_depth: int,
) -> str | None:
    for frame_id in reversed(open_stack):
        frame = frames[frame_id]
        if frame.call_event.goal != goal:
            continue
        if frame.call_event.depth != expected_depth:
            continue
        return frame_id
    return None


def _resolve_candidate_info(candidate_payload: Mapping[str, Any]) -> dict[str, Any]:
    pred_id = candidate_payload.get("pred_id")
    if not isinstance(pred_id, str) or not pred_id:
        raise ValueError("candidate_payload.pred_id must be non-empty string")
    terms = candidate_payload.get("terms")
    if not isinstance(terms, list):
        raise ValueError("candidate_payload.terms must be list")

    normalized_terms: list[str] = []
    entity_refs: list[str] = []
    for term in terms:
        if not isinstance(term, dict):
            continue
        kind = term.get("kind")
        if kind == "entity_ref":
            value = term.get("value")
            if isinstance(value, str) and value:
                entity_refs.append(value)
                normalized_terms.append(value)
            continue
        if kind == "literal":
            normalized_terms.append(_normalize_goal_token(term.get("value")))
            continue
        if kind == "candidate_ref":
            candidate_key = term.get("candidate_key")
            if isinstance(candidate_key, str) and candidate_key:
                normalized_terms.append(candidate_key)

    if entity_refs:
        component = entity_refs[0] if len(entity_refs) == 1 else f"{entity_refs[0]}->{entity_refs[1]}"
    elif normalized_terms:
        component = " | ".join(normalized_terms)
    else:
        raise ValueError("candidate_payload.terms must carry at least one usable value")

    return {
        "label": _pred_short_name(pred_id),
        "component": component,
        "term_counter": Counter(normalized_terms),
    }


def _select_root_frame(
    *,
    trace: ProbLogTraceV0,
    frames: Mapping[str, _ProbLogCallFrame],
    candidate_label: str,
    candidate_term_counter: Counter[str],
) -> tuple[str | None, ProbLogAnswerV0 | None]:
    best_answer: ProbLogAnswerV0 | None = None
    best_answer_score: tuple[int, int, int] | None = None
    for answer in trace.answers:
        goal_name, goal_args = _parse_goal_expr(answer.query)
        goal_counter = Counter(_normalize_goal_token(arg) for arg in goal_args)
        if not _counter_is_subset(candidate_term_counter, goal_counter):
            continue
        synthetic_penalty = 1 if _is_synthetic_goal_name(goal_name) else 0
        score = (sum(goal_counter.values()) - sum(candidate_term_counter.values()), synthetic_penalty, -len(goal_args))
        if best_answer_score is None or score < best_answer_score:
            best_answer = answer
            best_answer_score = score

    if best_answer is not None:
        for frame_id, frame in frames.items():
            if frame.call_event.goal == best_answer.query:
                return frame_id, best_answer

    best_frame_id: str | None = None
    best_frame_score: tuple[int, int, int] | None = None
    for frame_id, frame in frames.items():
        goal_name, goal_args = _parse_goal_expr(frame.call_event.goal)
        goal_counter = Counter(_normalize_goal_token(arg) for arg in goal_args)
        if not _counter_is_subset(candidate_term_counter, goal_counter):
            continue
        label_penalty = 0 if goal_name == candidate_label else 1
        synthetic_penalty = 1 if _is_synthetic_goal_name(goal_name) else 0
        score = (label_penalty, sum(goal_counter.values()) - sum(candidate_term_counter.values()), synthetic_penalty)
        if best_frame_score is None or score < best_frame_score:
            best_frame_id = frame_id
            best_frame_score = score
    return best_frame_id, best_answer


def _collect_frame_subtree(
    frames: Mapping[str, _ProbLogCallFrame],
    root_frame_id: str,
) -> list[str]:
    order: list[str] = []

    def _walk(frame_id: str) -> None:
        order.append(frame_id)
        for child_frame_id in frames[frame_id].child_frame_ids:
            _walk(child_frame_id)

    _walk(root_frame_id)
    return order


def _collect_visible_frames(
    frames: Mapping[str, _ProbLogCallFrame],
    root_frame_id: str,
) -> list[str]:
    order: list[str] = []

    def _walk(frame_id: str) -> None:
        frame = frames[frame_id]
        goal_name, _goal_args = _parse_goal_expr(frame.call_event.goal)
        synthetic = _is_synthetic_goal_name(goal_name)
        if not synthetic:
            order.append(frame_id)
        for child_frame_id in frame.child_frame_ids:
            _walk(child_frame_id)

    _walk(root_frame_id)
    return order


def _build_visible_tree_nodes(
    *,
    frames: Mapping[str, _ProbLogCallFrame],
    frame_id: str,
    node_id_by_frame_id: Mapping[str, str],
) -> list[dict[str, Any]]:
    frame = frames[frame_id]
    goal_name, goal_args = _parse_goal_expr(frame.call_event.goal)
    if _is_synthetic_goal_name(goal_name):
        nodes: list[dict[str, Any]] = []
        for child_frame_id in frame.child_frame_ids:
            nodes.extend(
                _build_visible_tree_nodes(
                    frames=frames,
                    frame_id=child_frame_id,
                    node_id_by_frame_id=node_id_by_frame_id,
                )
            )
        return nodes

    child_nodes: list[dict[str, Any]] = []
    for child_frame_id in frame.child_frame_ids:
        child_nodes.extend(
            _build_visible_tree_nodes(
                frames=frames,
                frame_id=child_frame_id,
                node_id_by_frame_id=node_id_by_frame_id,
            )
        )

    node_id = node_id_by_frame_id[frame_id]
    normalized_goal_args = [_normalize_goal_token(arg) for arg in goal_args]
    if frame.fail_event is not None and not child_nodes:
        return [
            {
                "node_id": node_id,
                "node_kind": "non_fact_check",
                "title": f"ProbLog goal {goal_name}",
                "step_key": frame.frame_id,
                "check_kind": goal_name,
                "status": "fail",
                "details": {
                    "goal": frame.call_event.goal,
                    "goal_args": normalized_goal_args,
                },
                "children": [],
            }
        ]

    base_node = {
        "node_id": node_id,
        "title": f"Proof {goal_name}",
        "pred_id": goal_name,
        "goal": frame.call_event.goal,
        "goal_args": normalized_goal_args,
    }
    if child_nodes:
        return [
            {
                **base_node,
                "node_kind": "proof_goal",
                "children": child_nodes,
            }
        ]
    return [
        {
            **base_node,
            "node_kind": "proof_leaf",
            "children": [],
        }
    ]


def _parse_goal_expr(expr: str) -> tuple[str, tuple[str, ...]]:
    text = expr.strip()
    if not text:
        raise ProbLogProvenanceError("empty goal expression in ProbLog trace")
    if "(" not in text:
        return text, ()
    idx = text.find("(")
    if idx <= 0 or not text.endswith(")"):
        raise ProbLogProvenanceError(f"invalid goal expression: {expr}")
    name = text[:idx].strip()
    args_text = text[idx + 1 : -1].strip()
    if not name:
        raise ProbLogProvenanceError(f"invalid goal expression: {expr}")
    if not args_text:
        return name, ()
    return name, tuple(_split_top_level_args(args_text))


def _goal_component(goal_args: tuple[str, ...]) -> str:
    normalized = [_normalize_goal_token(arg) for arg in goal_args]
    if not normalized:
        return "true"
    if len(normalized) == 1:
        return normalized[0]
    if len(normalized) == 2:
        return f"{normalized[0]}->{normalized[1]}"
    return " | ".join(normalized)


def _frame_value_summary(frame: _ProbLogCallFrame) -> str:
    status = _frame_status(frame)
    if status == "fail":
        return "false"
    if status == "result":
        return "true"
    return status


def _frame_status(frame: _ProbLogCallFrame) -> str:
    if frame.fail_event is not None:
        return "fail"
    if frame.result_event is not None:
        return "result"
    if frame.complete_event is not None:
        return "complete"
    return "call"


def _counter_is_subset(need: Counter[str], have: Counter[str]) -> bool:
    for key, count in need.items():
        if have.get(key, 0) < count:
            return False
    return True


def _normalize_goal_token(raw: Any) -> str:
    text = str(raw).strip()
    if len(text) >= 2 and ((text[0] == '"' and text[-1] == '"') or (text[0] == "'" and text[-1] == "'")):
        text = text[1:-1]
    return text


def _format_probability(probability: float) -> str:
    return f"{float(probability):.12g}"


def _is_synthetic_goal_name(name: str) -> bool:
    return name == "query" or name == "answer" or name.startswith("rule_body_")


def _pred_short_name(pred_id: str) -> str:
    parts = pred_id.split(":", 1)
    return parts[1] if len(parts) > 1 else pred_id


def _candidate_binding_from_payload(candidate_payload: Mapping[str, Any]) -> dict[str, Any]:
    terms = candidate_payload.get("terms")
    if not isinstance(terms, list):
        raise ValueError("candidate_payload.terms must be list")
    binding: dict[str, Any] = {}
    for idx, term in enumerate(terms):
        if not isinstance(term, Mapping):
            continue
        kind = term.get("kind")
        if kind in {"entity_ref", "literal"}:
            binding[f"arg_{idx}"] = term.get("value")
        elif kind == "candidate_ref":
            binding[f"arg_{idx}"] = term.get("candidate_key")
    return binding


__all__ = [
    "ProbLogAnswerV0",
    "ProbLogProvenanceError",
    "ProbLogTraceEventV0",
    "ProbLogTraceV0",
    "parse_problog_trace",
    "problog_trace_from_dict",
    "problog_trace_to_candidate_evidence_tree",
    "problog_trace_to_evidence_graph",
    "problog_trace_to_dict",
]
