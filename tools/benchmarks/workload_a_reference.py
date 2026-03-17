from __future__ import annotations

import heapq
import random
import re
from collections import deque
from typing import Any

_EDGE_RE = re.compile(r"^(?P<src>.+?) -\[(?P<conf>[0-9.]+)\]-> (?P<dst>.+)$")
_EPSILON = 1e-9


def generate_workload_a(
    *,
    n_nodes: int = 200,
    n_edges: int = 800,
    seed: int = 42,
    scale: str = "1x",
) -> dict[str, Any]:
    random.seed(seed)
    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    attempts = 0
    while len(facts) < n_edges and attempts < n_edges * 10:
        attempts += 1
        source = f"e{random.randint(0, n_nodes - 1):03d}"
        target = f"e{random.randint(0, n_nodes - 1):03d}"
        if source == target:
            continue
        key = (source, target)
        if key in seen:
            continue
        seen.add(key)
        facts.append(
            {
                "source_id": source,
                "target_id": target,
                "confidence": round(random.uniform(0.3, 1.0), 4),
            }
        )

    return {
        "workload": "A",
        "seed": seed,
        "scale": scale,
        "edge_facts": sort_edge_facts(facts),
    }


def build_workload_a_golden(payload: dict[str, Any]) -> dict[str, Any]:
    results = derive_workload_a_minmax(payload)
    return {
        "workload": "A",
        "query": "best_confidence",
        "algebra": "min_max",
        "seed": payload.get("seed"),
        "scale": payload.get("scale", "1x"),
        "results": [
            {
                "source": row["source"],
                "target": row["target"],
                "confidence": row["confidence"],
                "min_support_depth": row["min_support_depth"],
            }
            for row in results
        ],
        "total_reachable_pairs": len(results),
        "provenance_complete": True,
    }


def derive_workload_a_minmax(payload: dict[str, Any]) -> list[dict[str, Any]]:
    edge_facts = sort_edge_facts(payload["edge_facts"])
    adjacency = _build_adjacency(edge_facts)

    results: list[dict[str, Any]] = []
    for source in sorted(adjacency):
        shortest_depths = _shortest_positive_depths(source, adjacency)
        widest = _widest_paths_from_source(source, adjacency)
        for target, info in widest.items():
            results.append(
                {
                    "source": source,
                    "target": target,
                    "confidence": round(float(info["confidence"]), 6),
                    "min_support_depth": shortest_depths[target],
                    "support_path": _format_support_path(info["edges"], adjacency),
                }
            )
    return sorted(results, key=lambda row: (row["source"], row["target"]))


def build_provenance_entries(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate": {
                "source": row["source"],
                "target": row["target"],
            },
            "support_path": list(row["support_path"]),
        }
        for row in results
    ]


def compare_result_to_golden(
    result: dict[str, Any],
    golden: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    result_rows = result.get("results", [])
    if not isinstance(result_rows, list):
        raise ValueError("result.results must be a list")
    provenance_entries = result.get("provenance_entries", [])
    if not isinstance(provenance_entries, list):
        raise ValueError("result.provenance_entries must be a list")

    provenance = check_provenance_completeness(result_rows, provenance_entries, payload)
    diff = diff_against_golden(result_rows, golden)
    return {
        "baseline": result.get("baseline"),
        "unsupported_features": result.get("unsupported_features", []),
        "notes": result.get("notes", ""),
        "result_count": len(result_rows),
        "provenance_check": provenance,
        "golden_diff": diff,
    }


def check_provenance_completeness(
    result_rows: list[dict[str, Any]],
    provenance_entries: list[dict[str, Any]],
    payload: dict[str, Any],
) -> dict[str, Any]:
    edge_set = {
        (row["source_id"], row["target_id"], round(float(row["confidence"]), 6))
        for row in payload["edge_facts"]
    }
    entry_map: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in provenance_entries:
        candidate = entry.get("candidate", {})
        if not isinstance(candidate, dict):
            continue
        source = candidate.get("source")
        target = candidate.get("target")
        if isinstance(source, str) and isinstance(target, str):
            entry_map[(source, target)] = entry

    complete = 0
    gaps: list[dict[str, Any]] = []
    for row in result_rows:
        key = (row["source"], row["target"])
        entry = entry_map.get(key)
        if entry is None:
            gaps.append({"candidate": {"source": key[0], "target": key[1]}, "gap_type": "missing_provenance_entry"})
            continue
        support_path = entry.get("support_path")
        if not isinstance(support_path, list) or not support_path:
            gaps.append({"candidate": {"source": key[0], "target": key[1]}, "gap_type": "missing_provenance_entry"})
            continue
        ok, gap_type = _validate_support_path(key, support_path, edge_set)
        if ok:
            complete += 1
        else:
            gaps.append({"candidate": {"source": key[0], "target": key[1]}, "gap_type": gap_type})

    total = len(result_rows)
    return {
        "complete_count": complete,
        "total_checked": total,
        "complete_rate": 1.0 if total == 0 else round(complete / total, 6),
        "gaps": gaps,
    }


def diff_against_golden(result_rows: list[dict[str, Any]], golden: dict[str, Any]) -> dict[str, Any]:
    golden_rows = golden.get("results", [])
    if not isinstance(golden_rows, list):
        raise ValueError("golden.results must be a list")

    result_map = {
        (row["source"], row["target"]): row
        for row in result_rows
    }
    golden_map = {
        (row["source"], row["target"]): row
        for row in golden_rows
    }

    result_keys = set(result_map)
    golden_keys = set(golden_map)
    missing = [{"source": s, "target": t} for s, t in sorted(golden_keys - result_keys)]
    extra = [{"source": s, "target": t} for s, t in sorted(result_keys - golden_keys)]

    confidence_deltas: list[dict[str, Any]] = []
    confidence_ok = True
    for key in sorted(result_keys & golden_keys):
        result_conf = round(float(result_map[key]["confidence"]), 6)
        golden_conf = round(float(golden_map[key]["confidence"]), 6)
        abs_delta = round(abs(result_conf - golden_conf), 6)
        rel_delta = 0.0 if golden_conf == 0.0 else round(abs_delta / golden_conf, 6)
        if abs_delta >= 0.001:
            confidence_ok = False
        confidence_deltas.append(
            {
                "candidate": {"source": key[0], "target": key[1]},
                "result_confidence": result_conf,
                "golden_confidence": golden_conf,
                "absolute_delta": abs_delta,
                "relative_delta": rel_delta,
            }
        )

    return {
        "missing": missing,
        "extra": extra,
        "confidence_deltas": confidence_deltas,
        "matches_golden": not missing and not extra and confidence_ok,
    }


def sort_edge_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["source_id"], row["target_id"], float(row["confidence"])))


def _build_adjacency(edge_facts: list[dict[str, Any]]) -> dict[str, list[tuple[str, float]]]:
    adjacency: dict[str, list[tuple[str, float]]] = {}
    for row in edge_facts:
        adjacency.setdefault(row["source_id"], []).append((row["target_id"], round(float(row["confidence"]), 6)))
        adjacency.setdefault(row["target_id"], [])
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1]))
    return adjacency


def _shortest_positive_depths(
    source: str,
    adjacency: dict[str, list[tuple[str, float]]],
) -> dict[str, int]:
    dist: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque()
    for target, _ in adjacency.get(source, []):
        if target not in dist:
            dist[target] = 1
            queue.append((target, 1))

    while queue:
        node, depth = queue.popleft()
        for nxt, _ in adjacency.get(node, []):
            if nxt in dist:
                continue
            dist[nxt] = depth + 1
            queue.append((nxt, depth + 1))
    return dist


def _widest_paths_from_source(
    source: str,
    adjacency: dict[str, list[tuple[str, float]]],
) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    heap: list[tuple[float, int, tuple[tuple[str, str], ...], str]] = []

    for target, conf in adjacency.get(source, []):
        edges = ((source, target),)
        _update_best(best, target, conf, 1, edges)
        heapq.heappush(heap, (-conf, 1, edges, target))

    while heap:
        neg_conf, depth, edges, node = heapq.heappop(heap)
        conf = -neg_conf
        current = best.get(node)
        if current is None:
            continue
        if not _same_state(current, conf, depth, edges):
            continue
        for nxt, edge_conf in adjacency.get(node, []):
            new_conf = min(conf, edge_conf)
            new_depth = depth + 1
            new_edges = edges + ((node, nxt),)
            if _update_best(best, nxt, new_conf, new_depth, new_edges):
                heapq.heappush(heap, (-new_conf, new_depth, new_edges, nxt))
    return best


def _update_best(
    best: dict[str, dict[str, Any]],
    target: str,
    confidence: float,
    depth: int,
    edges: tuple[tuple[str, str], ...],
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
    cand_conf = float(candidate["confidence"])
    prev_conf = float(prev["confidence"])
    if cand_conf > prev_conf + _EPSILON:
        return True
    if abs(cand_conf - prev_conf) <= _EPSILON:
        if int(candidate["depth"]) < int(prev["depth"]):
            return True
        if int(candidate["depth"]) == int(prev["depth"]):
            return tuple(candidate["edges"]) < tuple(prev["edges"])
    return False


def _same_state(
    current: dict[str, Any],
    confidence: float,
    depth: int,
    edges: tuple[tuple[str, str], ...],
) -> bool:
    return (
        abs(float(current["confidence"]) - confidence) <= _EPSILON
        and int(current["depth"]) == depth
        and tuple(current["edges"]) == tuple(edges)
    )


def _format_support_path(
    edges: tuple[tuple[str, str], ...],
    adjacency: dict[str, list[tuple[str, float]]],
) -> list[str]:
    weights: dict[tuple[str, str], float] = {}
    for source, neighbors in adjacency.items():
        for target, conf in neighbors:
            weights[(source, target)] = conf
    return [
        f"{source} -[{weights[(source, target)]:.6f}]-> {target}"
        for source, target in edges
    ]


def _validate_support_path(
    candidate: tuple[str, str],
    support_path: list[Any],
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
    for left, right in zip(parsed, parsed[1:]):
        if left[1] != right[0]:
            return False, "broken_support_path"
    return True, ""
