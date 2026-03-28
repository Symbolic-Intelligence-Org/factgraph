"""ProbLog provenance trace carrier (adapter-local, V0 spike)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

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


def _normalize_depth(indent: str) -> int:
    if not indent:
        return 0
    return max(0, len(indent) - 1)


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


__all__ = [
    "ProbLogAnswerV0",
    "ProbLogProvenanceError",
    "ProbLogTraceEventV0",
    "ProbLogTraceV0",
    "parse_problog_trace",
    "problog_trace_to_dict",
]
