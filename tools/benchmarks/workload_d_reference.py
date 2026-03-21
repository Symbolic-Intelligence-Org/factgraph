"""Workload D — Certainty Annotation Benchmark.

Generates synthetic evidence trees with condition nodes, derives certainty
summaries via the annotation kernel, and validates ranked impact breakdowns
against golden output.

Algebra: bottleneck (min weighted impact).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from factpy_kernel.core.annotation import (  # noqa: E402
    derive_certainty_summary,
    rank_certainty_conditions,
)

_CONDITION_SUFFIXES = (
    ":entity_name",
    ":entity_status",
    ":entity_tag",
    ":check_active",
    ":check_threshold",
    ":eq",
    ":gt",
    ":lt",
    ":match",
    ":flag",
)


def generate_workload_d(
    *,
    n_conditions: int = 20,
    max_depth: int = 4,
    weighted_ratio: float = 0.8,
    confidence_ratio: float = 0.7,
    seed: int = 42,
    scale: str = "1x",
) -> dict[str, Any]:
    """Generate a synthetic certainty workload payload."""
    rng = random.Random(seed)

    # Build condition nodes
    condition_nodes: list[dict[str, Any]] = []
    for i in range(n_conditions):
        suffix = rng.choice(_CONDITION_SUFFIXES)
        atom_key = f"b0.a{i}{suffix}"

        if rng.random() < 0.6:
            node: dict[str, Any] = {
                "node_id": f"pwg:{i}",
                "node_kind": "predicate_witness_group",
                "pred_atom_key": atom_key,
                "children": [],
            }
        else:
            node = {
                "node_id": f"nfc:{i}",
                "node_kind": "non_fact_check",
                "step_key": atom_key,
                "children": [],
            }

        if rng.random() < confidence_ratio:
            node["condition_confidence"] = round(rng.uniform(0.1, 1.0), 6)

        condition_nodes.append(node)

    # Build nested tree structure
    root_children = _build_nested_tree(rng, condition_nodes, max_depth)

    tree_dict: dict[str, Any] = {
        "kind": "candidate_evidence_tree",
        "candidate_id": "cand_v2:bench_d",
        "support_digest": "sha256:bench_d",
        "root": {
            "node_id": "result:bench_d",
            "node_kind": "candidate_result",
            "children": [
                {
                    "node_id": "support:bench_d",
                    "node_kind": "support_section",
                    "children": root_children,
                }
            ],
        },
    }

    # Build condition_weights (partial coverage)
    all_prefixes = [f"b0.a{i}" for i in range(n_conditions)]
    n_weighted = max(0, int(n_conditions * weighted_ratio))
    weighted_prefixes = rng.sample(all_prefixes, min(n_weighted, len(all_prefixes)))
    condition_weights: dict[str, float] = {}
    for prefix in sorted(weighted_prefixes):
        condition_weights[prefix] = round(rng.uniform(0.1, 1.0), 6)

    return {
        "workload": "D",
        "seed": seed,
        "scale": scale,
        "confidence_kind": "certainty",
        "n_conditions": n_conditions,
        "max_depth": max_depth,
        "weighted_ratio": weighted_ratio,
        "confidence_ratio": confidence_ratio,
        "evidence_tree": tree_dict,
        "condition_weights": condition_weights,
    }


def _build_nested_tree(
    rng: random.Random,
    nodes: list[dict[str, Any]],
    max_depth: int,
    current_depth: int = 0,
) -> list[dict[str, Any]]:
    """Distribute condition nodes across a nested tree structure."""
    if not nodes or current_depth >= max_depth:
        return list(nodes)

    result: list[dict[str, Any]] = []
    i = 0
    while i < len(nodes):
        # 30% chance to wrap next batch in an intermediate container
        if current_depth < max_depth - 1 and rng.random() < 0.3:
            batch_size = rng.randint(1, min(3, len(nodes) - i))
            batch = nodes[i : i + batch_size]
            container: dict[str, Any] = {
                "node_id": f"container:d{current_depth}_{i}",
                "node_kind": "support_section",
                "children": _build_nested_tree(rng, batch, max_depth, current_depth + 1),
            }
            result.append(container)
            i += batch_size
        else:
            result.append(nodes[i])
            i += 1
    return result


def build_workload_d_golden(payload: dict[str, Any]) -> dict[str, Any]:
    """Build golden output by running the annotation kernel."""
    tree_dict = payload["evidence_tree"]
    condition_weights = payload["condition_weights"]
    confidence_kind = payload.get("confidence_kind", "certainty")

    summary = derive_certainty_summary(tree_dict, condition_weights, confidence_kind)
    if summary is None:
        return {
            "workload": "D",
            "query": "certainty_annotation",
            "algebra": "bottleneck_min",
            "seed": payload.get("seed"),
            "scale": payload.get("scale", "1x"),
            "aggregate_certainty": None,
            "condition_count": 0,
            "weighted_condition_count": 0,
            "results": [],
            "provenance_complete": True,
        }

    ranked = rank_certainty_conditions(summary.conditions, summary.aggregate_certainty)
    results = [
        {
            "atom_key": rc.atom_key,
            "node_kind": rc.node_kind,
            "weight": rc.weight,
            "impact": rc.impact,
            "is_bottleneck": rc.is_bottleneck,
        }
        for rc in ranked
    ]

    return {
        "workload": "D",
        "query": "certainty_annotation",
        "algebra": "bottleneck_min",
        "seed": payload.get("seed"),
        "scale": payload.get("scale", "1x"),
        "aggregate_certainty": summary.aggregate_certainty,
        "condition_count": summary.condition_count,
        "weighted_condition_count": summary.weighted_condition_count,
        "results": results,
        "provenance_complete": True,
    }


_EPSILON = 1e-6


def compare_result_to_golden(
    result: dict[str, Any],
    golden: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Compare a benchmark result against golden output."""
    result_conditions = result.get("results", [])
    golden_conditions = golden.get("results", [])

    # 1. Aggregate certainty delta
    result_agg = result.get("aggregate_certainty")
    golden_agg = golden.get("aggregate_certainty")
    aggregate_match = True
    aggregate_delta: dict[str, Any] = {
        "result": result_agg,
        "golden": golden_agg,
    }
    if result_agg is not None and golden_agg is not None:
        delta = abs(result_agg - golden_agg)
        aggregate_delta["abs_delta"] = delta
        if delta >= _EPSILON:
            aggregate_match = False
    elif result_agg != golden_agg:
        aggregate_match = False

    # 2. Per-condition impact deltas
    golden_by_key = {c["atom_key"]: c for c in golden_conditions}
    result_by_key = {c["atom_key"]: c for c in result_conditions}

    golden_keys = set(golden_by_key.keys())
    result_keys = set(result_by_key.keys())
    missing = sorted(golden_keys - result_keys)
    extra = sorted(result_keys - golden_keys)

    impact_deltas: list[dict[str, Any]] = []
    impact_match = True
    for key in sorted(golden_keys & result_keys):
        g_impact = golden_by_key[key].get("impact")
        r_impact = result_by_key[key].get("impact")
        if g_impact is not None and r_impact is not None:
            delta = abs(g_impact - r_impact)
            if delta >= _EPSILON:
                impact_match = False
                impact_deltas.append({
                    "atom_key": key,
                    "result_impact": r_impact,
                    "golden_impact": g_impact,
                    "abs_delta": delta,
                })
        elif g_impact != r_impact:
            impact_match = False
            impact_deltas.append({
                "atom_key": key,
                "result_impact": r_impact,
                "golden_impact": g_impact,
                "abs_delta": None,
            })

    # 3. Ranking order
    result_order = [c["atom_key"] for c in result_conditions]
    golden_order = [c["atom_key"] for c in golden_conditions]
    ranking_matches = result_order == golden_order

    # 4. Bottleneck accuracy
    result_bottlenecks = {c["atom_key"] for c in result_conditions if c.get("is_bottleneck")}
    golden_bottlenecks = {c["atom_key"] for c in golden_conditions if c.get("is_bottleneck")}
    bottleneck_matches = result_bottlenecks == golden_bottlenecks

    # 5. Overall
    matches_golden = (
        aggregate_match
        and impact_match
        and ranking_matches
        and bottleneck_matches
        and not missing
        and not extra
    )

    return {
        "baseline": result.get("baseline", "unknown"),
        "unsupported_features": result.get("unsupported_features", []),
        "notes": result.get("notes", ""),
        "result_count": len(result_conditions),
        "golden_diff": {
            "missing": missing,
            "extra": extra,
            "aggregate_delta": aggregate_delta,
            "aggregate_matches": aggregate_match,
            "impact_deltas": impact_deltas,
            "ranking_matches_golden": ranking_matches,
            "bottleneck_matches_golden": bottleneck_matches,
            "matches_golden": matches_golden,
        },
    }
