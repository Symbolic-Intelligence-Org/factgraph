from __future__ import annotations

import heapq
import re
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from factgraph.core.annotation.types import ConfidenceValue, NodeId, PathEdge, SupportStep

_EDGE_RE = re.compile(r"^(?P<src>.+?) -\[(?P<conf>[0-9.]+)\]-> (?P<dst>.+)$")
_EPSILON = 1e-9


@dataclass(frozen=True)
class MinMaxPathConclusion:
    source: NodeId
    target: NodeId
    confidence: ConfidenceValue
    min_support_depth: int
    support_path: tuple[SupportStep, ...]


def derive_min_max_path_confidence(
    edge_facts: Sequence[Mapping[str, Any]],
) -> list[MinMaxPathConclusion]:
    adjacency = _build_adjacency(edge_facts)
    conclusions: list[MinMaxPathConclusion] = []
    for source in sorted(adjacency):
        shortest_depths = _shortest_positive_depths(source, adjacency)
        widest = _widest_paths_from_source(source, adjacency)
        for target, info in widest.items():
            conclusions.append(
                MinMaxPathConclusion(
                    source=source,
                    target=target,
                    confidence=round(float(info["confidence"]), 6),
                    min_support_depth=shortest_depths[target],
                    support_path=tuple(_format_support_path(info["edges"], adjacency)),
                )
            )
    conclusions.sort(key=lambda row: (row.source, row.target))
    return conclusions


def serialize_min_max_conclusions(
    conclusions: Sequence[MinMaxPathConclusion],
) -> list[dict[str, Any]]:
    return [
        {
            "source": row.source,
            "target": row.target,
            "confidence": row.confidence,
            "min_support_depth": row.min_support_depth,
        }
        for row in conclusions
    ]


def build_min_max_provenance_entries(
    conclusions: Sequence[MinMaxPathConclusion],
) -> list[dict[str, Any]]:
    return [
        {
            "candidate": {
                "source": row.source,
                "target": row.target,
            },
            "support_path": list(row.support_path),
        }
        for row in conclusions
    ]


def validate_support_path(
    candidate: tuple[str, str],
    support_path: Sequence[Any],
    edge_set: set[tuple[str, str, float]],
) -> tuple[bool, str]:
    parsed: list[tuple[str, str, float]] = []
    for item in support_path:
        if not isinstance(item, str):
            return False, "internal_engine_node"
        match = _EDGE_RE.match(item)
        if match is None:
            return False, "internal_engine_node"
        edge = (
            match.group("src"),
            match.group("dst"),
            round(float(match.group("conf")), 6),
        )
        if edge not in edge_set:
            return False, "broken_support_path"
        parsed.append(edge)

    if not parsed:
        return False, "broken_support_path"
    if parsed[0][0] != candidate[0]:
        return False, "broken_support_path"
    if parsed[-1][1] != candidate[1]:
        return False, "broken_support_path"
    for left, right in pairwise(parsed):
        if left[1] != right[0]:
            return False, "broken_support_path"
    return True, ""


def _build_adjacency(
    edge_facts: Sequence[Mapping[str, Any]],
) -> dict[NodeId, list[tuple[NodeId, ConfidenceValue]]]:
    adjacency: dict[NodeId, list[tuple[NodeId, ConfidenceValue]]] = {}
    for row in _sort_edge_facts(edge_facts):
        source = _require_str(row.get("source_id", row.get("source")))
        target = _require_str(row.get("target_id", row.get("target")))
        confidence = round(float(row.get("confidence")), 6)
        adjacency.setdefault(source, []).append((target, confidence))
        adjacency.setdefault(target, [])
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1]))
    return adjacency


def _sort_edge_facts(
    edge_facts: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return sorted(
        edge_facts,
        key=lambda row: (
            _require_str(row.get("source_id", row.get("source"))),
            _require_str(row.get("target_id", row.get("target"))),
            float(row.get("confidence")),
        ),
    )


def _shortest_positive_depths(
    source: NodeId,
    adjacency: dict[NodeId, list[tuple[NodeId, ConfidenceValue]]],
) -> dict[NodeId, int]:
    distances: dict[NodeId, int] = {}
    queue: deque[tuple[NodeId, int]] = deque()
    for target, _ in adjacency.get(source, []):
        if target not in distances:
            distances[target] = 1
            queue.append((target, 1))

    while queue:
        node, depth = queue.popleft()
        for nxt, _ in adjacency.get(node, []):
            if nxt in distances:
                continue
            distances[nxt] = depth + 1
            queue.append((nxt, depth + 1))
    return distances


def _widest_paths_from_source(
    source: NodeId,
    adjacency: dict[NodeId, list[tuple[NodeId, ConfidenceValue]]],
) -> dict[NodeId, dict[str, Any]]:
    best: dict[NodeId, dict[str, Any]] = {}
    heap: list[tuple[float, int, tuple[PathEdge, ...], NodeId]] = []

    for target, conf in adjacency.get(source, []):
        edges = ((source, target),)
        _update_best(best, target, conf, 1, edges)
        heapq.heappush(heap, (-conf, 1, edges, target))

    while heap:
        neg_conf, depth, edges, node = heapq.heappop(heap)
        confidence = -neg_conf
        current = best.get(node)
        if current is None:
            continue
        if not _same_state(current, confidence, depth, edges):
            continue
        for nxt, edge_conf in adjacency.get(node, []):
            new_confidence = min(confidence, edge_conf)
            new_depth = depth + 1
            new_edges = edges + ((node, nxt),)
            if _update_best(best, nxt, new_confidence, new_depth, new_edges):
                heapq.heappush(heap, (-new_confidence, new_depth, new_edges, nxt))
    return best


def _update_best(
    best: dict[NodeId, dict[str, Any]],
    target: NodeId,
    confidence: ConfidenceValue,
    depth: int,
    edges: tuple[PathEdge, ...],
) -> bool:
    prev = best.get(target)
    candidate = {"confidence": confidence, "depth": depth, "edges": edges}
    if prev is None:
        best[target] = candidate
        return True
    if _is_better_candidate(candidate, prev):
        best[target] = candidate
        return True
    return False


def _is_better_candidate(candidate: dict[str, Any], prev: dict[str, Any]) -> bool:
    candidate_conf = float(candidate["confidence"])
    prev_conf = float(prev["confidence"])
    if candidate_conf > prev_conf + _EPSILON:
        return True
    if abs(candidate_conf - prev_conf) <= _EPSILON:
        if int(candidate["depth"]) < int(prev["depth"]):
            return True
        if int(candidate["depth"]) == int(prev["depth"]):
            return tuple(candidate["edges"]) < tuple(prev["edges"])
    return False


def _same_state(
    current: dict[str, Any],
    confidence: ConfidenceValue,
    depth: int,
    edges: tuple[PathEdge, ...],
) -> bool:
    return (
        abs(float(current["confidence"]) - confidence) <= _EPSILON
        and int(current["depth"]) == depth
        and tuple(current["edges"]) == tuple(edges)
    )


def _format_support_path(
    edges: tuple[PathEdge, ...],
    adjacency: dict[NodeId, list[tuple[NodeId, ConfidenceValue]]],
) -> list[SupportStep]:
    weights: dict[PathEdge, ConfidenceValue] = {}
    for source, neighbors in adjacency.items():
        for target, confidence in neighbors:
            weights[(source, target)] = confidence
    return [
        f"{source} -[{weights[(source, target)]:.6f}]-> {target}"
        for source, target in edges
    ]


def _require_str(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("edge facts require non-empty string endpoints")
    return value
