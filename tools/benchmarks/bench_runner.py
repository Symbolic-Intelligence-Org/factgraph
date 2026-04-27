from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kernel.adapters.problog.problog_engine import ProbLogEngineError, run_problog
from kernel.adapters.souffle.runner import find_souffle_binary
from kernel.core.annotation import (
    build_direct_evidence_candidates_proto,
    build_max_evidence_provenance,
    build_min_max_provenance_entries,
    derive_certainty_summary,
    derive_min_max_path_confidence,
    rank_certainty_conditions,
    serialize_min_max_conclusions,
    sort_raw_candidates_proto,
)
from workload_a_reference import (
    build_provenance_entries as build_workload_a_provenance_entries,
    derive_workload_a_minmax,
    sort_edge_facts,
)
from workload_b_reference import (
    build_workload_b_golden,
    compare_result_to_golden as compare_workload_b_to_golden,  # imported for local availability / future parity
    sort_init_state_facts,
    sort_property_facts,
    sort_rules,
)
from workload_c_reference import (
    build_direct_evidence_candidates,
    build_provenance_entries,
    sort_evidence_facts,
    sort_raw_candidates,
    sort_struct_facts,
)

WORKLOAD_A = "A"
WORKLOAD_B = "B"
WORKLOAD_C = "C"
WORKLOAD_D = "D"
BASELINES = {"problog", "pyreason", "souffle_proto", "souffle_full_a", "annotation_kernel"}
_EPSILON = 1e-9


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark runner for annotation-kernel spike workloads.")
    parser.add_argument("--workload", required=True, choices=["A", "B", "C", "D"])
    parser.add_argument("--baseline", required=True, choices=sorted(BASELINES))
    parser.add_argument("--input", required=True, help="Input workload JSON file")
    parser.add_argument("--output", required=True, help="Output normalized result JSON file")
    parser.add_argument("--measure-memory", action="store_true", help="Capture Python peak memory via tracemalloc")
    args = parser.parse_args()

    input_path = Path(args.input)
    if args.workload == WORKLOAD_A:
        if args.baseline not in {"problog", "pyreason", "souffle_proto", "souffle_full_a"}:
            raise SystemExit(f"baseline {args.baseline} is not supported for workload {WORKLOAD_A}")
        payload = _load_workload_a(input_path)
        runner = {
            "problog": _run_workload_a_problog,
            "pyreason": _run_workload_a_pyreason,
            "souffle_proto": _run_workload_a_souffle_proto,
            "souffle_full_a": _run_workload_a_souffle_full_a,
        }[args.baseline]
    elif args.workload == WORKLOAD_B:
        if args.baseline not in {"problog", "pyreason", "souffle_proto"}:
            raise SystemExit(f"baseline {args.baseline} is not supported for workload {WORKLOAD_B}")
        payload = _load_workload_b(input_path)
        runner = {
            "problog": _run_workload_b_problog,
            "pyreason": _run_workload_b_pyreason,
            "souffle_proto": _run_workload_b_souffle_proto,
        }[args.baseline]
    elif args.workload == WORKLOAD_C:
        if args.baseline == "souffle_full_a":
            raise SystemExit("baseline souffle_full_a is only supported for workload A")
        payload = _load_workload_c(input_path)
        runner = {
            "problog": _run_workload_c_problog,
            "pyreason": _run_workload_c_pyreason,
            "souffle_proto": _run_workload_c_souffle_proto,
        }[args.baseline]
    elif args.workload == WORKLOAD_D:
        if args.baseline not in {"annotation_kernel"}:
            raise SystemExit(f"baseline {args.baseline} is not supported for workload {WORKLOAD_D}")
        payload = _load_workload_d(input_path)
        runner = {
            "annotation_kernel": _run_workload_d_annotation_kernel,
        }[args.baseline]
    else:
        raise SystemExit(
            f"bench_runner smoke v0 currently implements only workloads {WORKLOAD_A}, {WORKLOAD_B}, {WORKLOAD_C}, and {WORKLOAD_D}"
        )

    result = _run_with_measurement(
        runner=runner,
        payload=payload,
        measure_memory=args.measure_memory,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _run_with_measurement(
    *,
    runner: Any,
    payload: dict[str, Any],
    measure_memory: bool,
) -> dict[str, Any]:
    if measure_memory:
        tracemalloc.start()
    started = time.perf_counter()
    result = runner(payload)
    wall_clock = time.perf_counter() - started
    peak_mb = 0.0
    if measure_memory:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = peak / (1024.0 * 1024.0)

    result["wall_clock_seconds"] = _round_float(wall_clock, 6)
    result["peak_memory_mb"] = _round_float(peak_mb, 3)
    return result


def _load_workload_c(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("workload input must be a JSON object")

    workload = raw.get("workload")
    if workload not in {None, WORKLOAD_C}:
        raise ValueError(f"workload input must target {WORKLOAD_C}, got: {workload!r}")

    struct_facts_raw = raw.get("struct_facts")
    evidence_facts_raw = raw.get("evidence_facts")
    if not isinstance(struct_facts_raw, list) or not isinstance(evidence_facts_raw, list):
        raise ValueError("workload C input must provide 'struct_facts' and 'evidence_facts' lists")

    struct_facts = [_coerce_struct_fact(item) for item in struct_facts_raw]
    evidence_facts = [_coerce_evidence_fact(item) for item in evidence_facts_raw]

    return {
        "workload": WORKLOAD_C,
        "seed": raw.get("seed"),
        "struct_facts": struct_facts,
        "evidence_facts": evidence_facts,
    }


def _load_workload_d(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("workload input must be a JSON object")

    workload = raw.get("workload")
    if workload not in {None, WORKLOAD_D}:
        raise ValueError(f"workload input must target {WORKLOAD_D}, got: {workload!r}")

    evidence_tree = raw.get("evidence_tree")
    condition_weights = raw.get("condition_weights")
    if not isinstance(evidence_tree, dict):
        raise ValueError("workload D input must provide 'evidence_tree' dict")
    if not isinstance(condition_weights, dict):
        raise ValueError("workload D input must provide 'condition_weights' dict")

    return {
        "workload": WORKLOAD_D,
        "seed": raw.get("seed"),
        "scale": raw.get("scale", "1x"),
        "confidence_kind": raw.get("confidence_kind", "certainty"),
        "evidence_tree": evidence_tree,
        "condition_weights": condition_weights,
    }


def _run_workload_d_annotation_kernel(payload: dict[str, Any]) -> dict[str, Any]:
    tree_dict = payload["evidence_tree"]
    cw = payload["condition_weights"]
    ck = payload.get("confidence_kind", "certainty")

    summary = derive_certainty_summary(tree_dict, cw, ck)
    if summary is None:
        return {
            "workload": WORKLOAD_D,
            "baseline": "annotation_kernel",
            "algebra": "bottleneck_min",
            "aggregate_certainty": None,
            "condition_count": 0,
            "weighted_condition_count": 0,
            "results": [],
            "unsupported_features": [],
            "notes": "derive_certainty_summary returned None",
        }

    ranked = rank_certainty_conditions(summary.conditions, summary.aggregate_certainty)
    return {
        "workload": WORKLOAD_D,
        "baseline": "annotation_kernel",
        "algebra": "bottleneck_min",
        "aggregate_certainty": summary.aggregate_certainty,
        "condition_count": summary.condition_count,
        "weighted_condition_count": summary.weighted_condition_count,
        "results": [
            {
                "atom_key": rc.atom_key,
                "node_kind": rc.node_kind,
                "weight": rc.weight,
                "impact": rc.impact,
                "is_bottleneck": rc.is_bottleneck,
            }
            for rc in ranked
        ],
        "unsupported_features": [],
        "notes": "",
    }


def _load_workload_a(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("workload input must be a JSON object")

    workload = raw.get("workload")
    if workload not in {None, WORKLOAD_A}:
        raise ValueError(f"workload input must target {WORKLOAD_A}, got: {workload!r}")

    edge_facts_raw = raw.get("edge_facts")
    if not isinstance(edge_facts_raw, list):
        raise ValueError("workload A input must provide 'edge_facts' list")

    edge_facts = [_coerce_edge_fact(item) for item in edge_facts_raw]
    return {
        "workload": WORKLOAD_A,
        "seed": raw.get("seed"),
        "scale": raw.get("scale", "1x"),
        "edge_facts": edge_facts,
    }


def _load_workload_b(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("workload input must be a JSON object")

    workload = raw.get("workload")
    if workload not in {None, WORKLOAD_B}:
        raise ValueError(f"workload input must target {WORKLOAD_B}, got: {workload!r}")

    init_state_raw = raw.get("init_state_facts")
    property_raw = raw.get("property_facts")
    rules_raw = raw.get("rules")
    if not isinstance(init_state_raw, list) or not isinstance(property_raw, list) or not isinstance(rules_raw, list):
        raise ValueError("workload B input must provide init_state_facts, property_facts, and rules lists")

    return {
        "workload": WORKLOAD_B,
        "seed": raw.get("seed"),
        "scale": raw.get("scale", "1x"),
        "t_max": int(raw.get("t_max", 20)),
        "init_state_facts": [_coerce_init_state_fact(item) for item in init_state_raw],
        "property_facts": [_coerce_property_fact(item) for item in property_raw],
        "rules": [_coerce_rule(item) for item in rules_raw],
    }


def _coerce_struct_fact(item: Any) -> dict[str, str]:
    if isinstance(item, dict):
        subject = _require_str(item.get("subject_id", item.get("subject")), "struct_fact.subject_id")
        relation = _require_str(item.get("relation"), "struct_fact.relation")
        obj = _require_str(item.get("object_id", item.get("object")), "struct_fact.object_id")
        return {"subject_id": subject, "relation": relation, "object_id": obj}
    if isinstance(item, (list, tuple)) and len(item) == 3:
        return {
            "subject_id": _require_str(item[0], "struct_fact[0]"),
            "relation": _require_str(item[1], "struct_fact[1]"),
            "object_id": _require_str(item[2], "struct_fact[2]"),
        }
    raise ValueError(f"unsupported struct_fact item: {item!r}")


def _coerce_edge_fact(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        source = _require_str(item.get("source_id", item.get("source")), "edge.source_id")
        target = _require_str(item.get("target_id", item.get("target")), "edge.target_id")
        confidence = _require_probability(item.get("confidence"), "edge.confidence")
        return {
            "source_id": source,
            "target_id": target,
            "confidence": confidence,
        }
    if isinstance(item, (list, tuple)) and len(item) == 3:
        return {
            "source_id": _require_str(item[0], "edge[0]"),
            "target_id": _require_str(item[1], "edge[1]"),
            "confidence": _require_probability(item[2], "edge[2]"),
        }
    raise ValueError(f"unsupported edge item: {item!r}")


def _coerce_init_state_fact(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        entity = _require_str(item.get("entity_id", item.get("entity")), "state.entity_id")
        timestep = _require_int(item.get("timestep"), "state.timestep")
        status = _require_str(item.get("status"), "state.status")
        return {"entity_id": entity, "timestep": timestep, "status": status}
    if isinstance(item, (list, tuple)) and len(item) == 3:
        return {
            "entity_id": _require_str(item[0], "state[0]"),
            "timestep": _require_int(item[1], "state[1]"),
            "status": _require_str(item[2], "state[2]"),
        }
    raise ValueError(f"unsupported init_state item: {item!r}")


def _coerce_property_fact(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        entity = _require_str(item.get("entity_id", item.get("entity")), "property.entity_id")
        prop_name = _require_str(item.get("prop_name"), "property.prop_name")
        prop_value = _require_str(item.get("prop_value"), "property.prop_value")
        return {"entity_id": entity, "prop_name": prop_name, "prop_value": prop_value}
    if isinstance(item, (list, tuple)) and len(item) == 3:
        return {
            "entity_id": _require_str(item[0], "property[0]"),
            "prop_name": _require_str(item[1], "property[1]"),
            "prop_value": _require_str(item[2], "property[2]"),
        }
    raise ValueError(f"unsupported property item: {item!r}")


def _coerce_rule(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"unsupported rule item: {item!r}")
    template = _require_str(item.get("template"), "rule.template")
    rule_id = _require_int(item.get("rule_id"), "rule.rule_id")
    rule_label = _require_str(item.get("rule_label"), "rule.rule_label")
    source_status = _require_str(item.get("source_status"), "rule.source_status")
    target_status = _require_str(item.get("target_status"), "rule.target_status")
    out = {
        "rule_id": rule_id,
        "rule_label": rule_label,
        "template": template,
        "source_status": source_status,
        "target_status": target_status,
    }
    if template == "T2":
        out["class_value"] = _require_str(item.get("class_value"), "rule.class_value")
    elif template == "T3":
        out["helper_class"] = _require_str(item.get("helper_class"), "rule.helper_class")
    else:
        raise ValueError(f"unsupported rule template: {template}")
    return out


def _coerce_evidence_fact(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        claim_id = _require_str(item.get("claim_id"), "evidence.claim_id")
        subject = _require_str(item.get("subject_id", item.get("subject")), "evidence.subject_id")
        relation = _require_str(item.get("relation"), "evidence.relation")
        obj = _require_str(item.get("object_id", item.get("object")), "evidence.object_id")
        confidence = _require_probability(item.get("confidence"), "evidence.confidence")
        source = _require_str(item.get("source"), "evidence.source")
        return {
            "claim_id": claim_id,
            "subject_id": subject,
            "relation": relation,
            "object_id": obj,
            "confidence": confidence,
            "source": source,
        }
    if isinstance(item, (list, tuple)) and len(item) == 6:
        return {
            "claim_id": _require_str(item[0], "evidence[0]"),
            "subject_id": _require_str(item[1], "evidence[1]"),
            "relation": _require_str(item[2], "evidence[2]"),
            "object_id": _require_str(item[3], "evidence[3]"),
            "confidence": _require_probability(item[4], "evidence[4]"),
            "source": _require_str(item[5], "evidence[5]"),
        }
    raise ValueError(f"unsupported evidence item: {item!r}")


def _run_workload_c_pyreason(payload: dict[str, Any]) -> dict[str, Any]:
    unsupported: list[str] = []
    if importlib.util.find_spec("pyreason") is None:
        unsupported.append("engine_unavailable:pyreason_module")
    unsupported.append("pyreason_bridge_v0_not_implemented")
    return _base_result(
        baseline="pyreason",
        raw_candidates=[],
        provenance_entries=[],
        unsupported_features=unsupported,
        notes="PyReason baseline is intentionally routed through bridge v0; smoke runner currently reports availability only.",
    )


def _run_workload_a_pyreason(payload: dict[str, Any]) -> dict[str, Any]:
    unsupported: list[str] = []
    if importlib.util.find_spec("pyreason") is None:
        unsupported.append("engine_unavailable:pyreason_module")
    unsupported.append("pyreason_bridge_v0_not_implemented")
    return {
        "workload": WORKLOAD_A,
        "baseline": "pyreason",
        "algebra": "min_max",
        "wall_clock_seconds": 0.0,
        "peak_memory_mb": 0.0,
        "results": [],
        "provenance_entries": [],
        "unsupported_features": unsupported,
        "notes": "PyReason baseline is intentionally routed through bridge v0; workload A runner currently reports availability only.",
    }


def _run_workload_a_problog(payload: dict[str, Any]) -> dict[str, Any]:
    program = _build_workload_a_problog_program(payload)
    with tempfile.TemporaryDirectory(prefix="bench_workload_a_problog_") as tmpdir:
        pl_path = Path(tmpdir) / "workload_a.pl"
        pl_path.write_text(program, encoding="utf-8", newline="\n")
        try:
            raw_output = run_problog(pl_path, timeout=30)
        except ProbLogEngineError as exc:
            message = str(exc)
            if "not available" in message:
                return {
                    "workload": WORKLOAD_A,
                    "baseline": "problog",
                    "algebra": "min_max",
                    "wall_clock_seconds": 0.0,
                    "peak_memory_mb": 0.0,
                    "results": [],
                    "provenance_entries": [],
                    "unsupported_features": ["engine_unavailable:problog_cli"],
                    "notes": message,
                }
            if "timed out" in message:
                return {
                    "workload": WORKLOAD_A,
                    "baseline": "problog",
                    "algebra": "min_max",
                    "wall_clock_seconds": 0.0,
                    "peak_memory_mb": 0.0,
                    "results": [],
                    "provenance_entries": [],
                    "unsupported_features": ["engine_timeout:problog_cli"],
                    "notes": message,
                }
            return {
                "workload": WORKLOAD_A,
                "baseline": "problog",
                "algebra": "min_max",
                "wall_clock_seconds": 0.0,
                "peak_memory_mb": 0.0,
                "results": [],
                "provenance_entries": [],
                "unsupported_features": ["engine_error:problog_cli"],
                "notes": message,
            }

    reference_rows = derive_workload_a_minmax(payload)
    reference_index = {
        (row["source"], row["target"]): row
        for row in reference_rows
    }
    results = _parse_workload_a_problog_output(raw_output, reference_index)
    provenance_entries = build_workload_a_provenance_entries(
        [reference_index[(row["source"], row["target"])] for row in results if (row["source"], row["target"]) in reference_index]
    )
    return {
        "workload": WORKLOAD_A,
        "baseline": "problog",
        "algebra": "min_max",
        "wall_clock_seconds": 0.0,
        "peak_memory_mb": 0.0,
        "results": results,
        "provenance_entries": provenance_entries,
        "unsupported_features": ["semantic_mismatch:min_max_vs_possible_world"],
        "notes": "ProbLog baseline reports possible-world reachability probability per pair; confidence deltas against min-max golden are expected semantic differences.",
    }


def _run_workload_a_souffle_proto(payload: dict[str, Any]) -> dict[str, Any]:
    souffle_bin = find_souffle_binary()
    if souffle_bin is None:
        return {
            "workload": WORKLOAD_A,
            "baseline": "souffle_proto",
            "algebra": "min_max",
            "wall_clock_seconds": 0.0,
            "peak_memory_mb": 0.0,
            "results": [],
            "provenance_entries": [],
            "unsupported_features": ["engine_unavailable:souffle_cli"],
            "notes": "Souffle CLI not found on PATH and SOUFFLE_BIN is unset.",
        }

    with tempfile.TemporaryDirectory(prefix="bench_workload_a_souffle_") as tmpdir:
        tmp_root = Path(tmpdir)
        facts_dir = tmp_root / "facts"
        out_dir = tmp_root / "out"
        facts_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_souffle_edges(payload["edge_facts"], facts_dir / "edge.facts")
        program_path = tmp_root / "workload_a.dl"
        program_path.write_text(_build_workload_a_souffle_program(), encoding="utf-8", newline="\n")

        proc = subprocess.run(
            [str(souffle_bin), "-F", str(facts_dir), "-D", str(out_dir), str(program_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(f"Souffle workload A execution failed: {stderr or proc.returncode}")

        reachable_pairs = _read_souffle_reachable_pairs(out_dir)

    prototype_rows = derive_min_max_path_confidence(payload["edge_facts"])
    filtered_rows = [
        row for row in prototype_rows if (row.source, row.target) in reachable_pairs
    ]
    if len(filtered_rows) != len(reachable_pairs):
        reference_pairs = {(row.source, row.target) for row in filtered_rows}
        missing = sorted(reachable_pairs - reference_pairs)
        raise RuntimeError(f"Souffle reachable pairs missing from reference DP: {missing[:5]}")

    return {
        "workload": WORKLOAD_A,
        "baseline": "souffle_proto",
        "algebra": "min_max",
        "wall_clock_seconds": 0.0,
        "peak_memory_mb": 0.0,
        "results": serialize_min_max_conclusions(filtered_rows),
        "provenance_entries": build_min_max_provenance_entries(filtered_rows),
        "unsupported_features": [],
        "notes": "Souffle baseline executes structural closure only; internal annotation prototype computes exact min-max confidence via DP, not by path enumeration.",
    }


def _run_workload_a_souffle_full_a(payload: dict[str, Any]) -> dict[str, Any]:
    souffle_bin = find_souffle_binary()
    if souffle_bin is None:
        return {
            "workload": WORKLOAD_A,
            "baseline": "souffle_full_a",
            "algebra": "min_max",
            "wall_clock_seconds": 0.0,
            "peak_memory_mb": 0.0,
            "results": [],
            "provenance_entries": [],
            "unsupported_features": ["engine_unavailable:souffle_cli"],
            "notes": "Souffle CLI not found on PATH and SOUFFLE_BIN is unset.",
        }

    with tempfile.TemporaryDirectory(prefix="bench_workload_a_souffle_full_") as tmpdir:
        tmp_root = Path(tmpdir)
        facts_dir = tmp_root / "facts"
        out_dir = tmp_root / "out"
        facts_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_souffle_weighted_edges(payload["edge_facts"], facts_dir / "edge.facts")
        program_path = tmp_root / "workload_a_full.dl"
        program_path.write_text(_build_workload_a_souffle_full_program(), encoding="utf-8", newline="\n")

        proc = subprocess.run(
            [str(souffle_bin), "-F", str(facts_dir), "-D", str(out_dir), str(program_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(f"Souffle workload A full execution failed: {stderr or proc.returncode}")

        result_rows = _read_souffle_best_confidence(out_dir)

    reference_rows = derive_workload_a_minmax(payload)
    reference_index = {
        (row["source"], row["target"]): row
        for row in reference_rows
    }
    normalized: list[dict[str, Any]] = []
    provenance_source_rows: list[dict[str, Any]] = []
    for row in result_rows:
        key = (row["source"], row["target"])
        reference = reference_index.get(key)
        normalized.append(
            {
                "source": row["source"],
                "target": row["target"],
                "confidence": row["confidence"],
                "min_support_depth": reference["min_support_depth"] if reference is not None else None,
            }
        )
        if reference is not None:
            provenance_source_rows.append(reference)

    return {
        "workload": WORKLOAD_A,
        "baseline": "souffle_full_a",
        "algebra": "min_max",
        "wall_clock_seconds": 0.0,
        "peak_memory_mb": 0.0,
        "results": normalized,
        "provenance_entries": build_workload_a_provenance_entries(provenance_source_rows),
        "unsupported_features": ["provenance_reconstructed_from_reference"],
        "notes": "Exploratory variant: Souffle executes R1-R4 natively; support paths are reconstructed from frozen min-max reference rows, not extracted from Souffle itself.",
    }


def _run_workload_b_pyreason(payload: dict[str, Any]) -> dict[str, Any]:
    unsupported: list[str] = []
    if importlib.util.find_spec("pyreason") is None:
        unsupported.append("engine_unavailable:pyreason_module")
    unsupported.append("pyreason_bridge_v0_not_implemented")
    return _base_result_workload_b(
        baseline="pyreason",
        t_max=int(payload["t_max"]),
        results=[],
        provenance_entries=[],
        state_history_summary={},
        unsupported_features=unsupported,
        notes="PyReason baseline is intentionally blocked behind bridge v0 for Workload B.",
        native_temporal_advantage=False,
        annotation_kernel_noop=False,
    )


def _run_workload_b_problog(payload: dict[str, Any]) -> dict[str, Any]:
    return _base_result_workload_b(
        baseline="problog",
        t_max=int(payload["t_max"]),
        results=[],
        provenance_entries=[],
        state_history_summary={},
        unsupported_features=["workload_b_problog_not_implemented"],
        notes="Workload B currently prioritizes the Souffle proto path; ProbLog time-unrolling path is not implemented in smoke v0.",
        native_temporal_advantage=False,
        annotation_kernel_noop=False,
    )


def _run_workload_b_souffle_proto(payload: dict[str, Any]) -> dict[str, Any]:
    souffle_bin = find_souffle_binary()
    if souffle_bin is None:
        return _base_result_workload_b(
            baseline="souffle_proto",
            t_max=int(payload["t_max"]),
            results=[],
            provenance_entries=[],
            state_history_summary={},
            unsupported_features=["engine_unavailable:souffle_cli"],
            notes="Souffle CLI not found on PATH and SOUFFLE_BIN is unset.",
            native_temporal_advantage=False,
            annotation_kernel_noop=True,
        )

    with tempfile.TemporaryDirectory(prefix="bench_workload_b_souffle_") as tmpdir:
        tmp_root = Path(tmpdir)
        facts_dir = tmp_root / "facts"
        out_dir = tmp_root / "out"
        facts_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_souffle_init_states(payload["init_state_facts"], facts_dir / "init_state.facts")
        _write_souffle_properties(payload["property_facts"], facts_dir / "property.facts")
        program_path = tmp_root / "workload_b.dl"
        program_path.write_text(_build_workload_b_souffle_program(payload), encoding="utf-8", newline="\n")

        proc = subprocess.run(
            [str(souffle_bin), "-F", str(facts_dir), "-D", str(out_dir), str(program_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(f"Souffle workload B execution failed: {stderr or proc.returncode}")

        all_states = _read_souffle_state_rows(out_dir)
        raw_provenance = _read_souffle_workload_b_provenance(out_dir)

    state_index = {(row["entity"], row["timestep"]): row["status"] for row in all_states}
    t_max = int(payload["t_max"])
    results: list[dict[str, Any]] = []
    state_history_summary: dict[str, list[str]] = {}
    entities = [row["entity_id"] for row in sort_init_state_facts(payload["init_state_facts"])]
    for entity in entities:
        initial_status = state_index[(entity, 0)]
        history = [initial_status]
        first_transition_at: int | None = None
        transition_count = 0
        prev_status = initial_status
        for timestep in range(1, t_max + 1):
            status = state_index[(entity, timestep)]
            if status != prev_status:
                transition_count += 1
                if first_transition_at is None:
                    first_transition_at = timestep
                history.append(status)
            prev_status = status
        state_history_summary[entity] = history
        results.append(
            {
                "entity": entity,
                "final_status": state_index[(entity, t_max)],
                "first_transition_at": first_transition_at,
                "transition_count": transition_count,
            }
        )

    provenance_entries = []
    for entry in raw_provenance:
        entity = entry["entity"]
        timestep = entry["timestep"]
        new_status = entry["status"]
        prev_status = state_index.get((entity, timestep - 1))
        if prev_status == new_status:
            continue
        trigger_entities = [entity] if not entry["helper"] else [entity, entry["helper"]]
        provenance_entries.append(
            {
                "entity": entity,
                "timestep": timestep,
                "new_status": new_status,
                "trigger_rule": entry["rule_label"],
                "trigger_entities": trigger_entities,
            }
        )

    return _base_result_workload_b(
        baseline="souffle_proto",
        t_max=int(payload["t_max"]),
        results=results,
        provenance_entries=provenance_entries,
        state_history_summary=state_history_summary,
        unsupported_features=[],
        notes='annotation_kernel_noop: true',
        native_temporal_advantage=False,
        annotation_kernel_noop=True,
    )


def _run_workload_c_problog(payload: dict[str, Any]) -> dict[str, Any]:
    program = _build_workload_c_problog_program(payload)
    with tempfile.TemporaryDirectory(prefix="bench_workload_c_problog_") as tmpdir:
        pl_path = Path(tmpdir) / "workload_c.pl"
        pl_path.write_text(program, encoding="utf-8", newline="\n")
        try:
            raw_output = run_problog(pl_path, timeout=30)
        except ProbLogEngineError as exc:
            message = str(exc)
            if "not available" in message:
                return _base_result(
                    baseline="problog",
                    raw_candidates=[],
                    provenance_entries=[],
                    unsupported_features=["engine_unavailable:problog_cli"],
                    notes=message,
                )
            if "timed out" in message:
                return _base_result(
                    baseline="problog",
                    raw_candidates=[],
                    provenance_entries=[],
                    unsupported_features=["engine_timeout:problog_cli"],
                    notes=message,
                )
            return _base_result(
                baseline="problog",
                raw_candidates=[],
                provenance_entries=[],
                unsupported_features=["engine_error:problog_cli"],
                notes=message,
            )

    raw_candidates = _parse_workload_c_problog_output(raw_output, payload)
    provenance_entries = build_provenance_entries(
        payload["struct_facts"],
        payload["evidence_facts"],
        raw_candidates,
    )
    return _base_result(
        baseline="problog",
        raw_candidates=raw_candidates,
        provenance_entries=provenance_entries,
        unsupported_features=[],
        notes="Top-K ranking intentionally deferred to harness; direct evidence provenance reconstructed from input facts.",
    )


def _run_workload_c_souffle_proto(payload: dict[str, Any]) -> dict[str, Any]:
    souffle_bin = find_souffle_binary()
    if souffle_bin is None:
        return _base_result(
            baseline="souffle_proto",
            raw_candidates=[],
            provenance_entries=[],
            unsupported_features=["engine_unavailable:souffle_cli"],
            notes="Souffle CLI not found on PATH and SOUFFLE_BIN is unset.",
        )

    with tempfile.TemporaryDirectory(prefix="bench_workload_c_souffle_") as tmpdir:
        tmp_root = Path(tmpdir)
        facts_dir = tmp_root / "facts"
        out_dir = tmp_root / "out"
        facts_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_souffle_struct_facts(payload["struct_facts"], facts_dir / "struct_fact.facts")
        program_path = tmp_root / "workload_c.dl"
        program_path.write_text(_build_workload_c_souffle_program(), encoding="utf-8", newline="\n")

        proc = subprocess.run(
            [str(souffle_bin), "-F", str(facts_dir), "-D", str(out_dir), str(program_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(f"Souffle workload C execution failed: {stderr or proc.returncode}")

        derived_candidates = _read_souffle_derived_candidates(out_dir)

    raw_candidates = build_direct_evidence_candidates_proto(payload["evidence_facts"])
    raw_candidates.extend(derived_candidates)
    raw_candidates = sort_raw_candidates_proto(raw_candidates)
    provenance_entries = build_max_evidence_provenance(
        payload["struct_facts"],
        payload["evidence_facts"],
        raw_candidates,
    )
    return _base_result(
        baseline="souffle_proto",
        raw_candidates=raw_candidates,
        provenance_entries=provenance_entries,
        unsupported_features=[],
        notes="Top-K ranking intentionally deferred to harness; annotation kernel v0 only merges evidence with Souffle-derived structural candidates.",
    )


def _build_workload_a_problog_program(payload: dict[str, Any]) -> str:
    lines = [
        "% workload A smoke runner v0",
        "% confidence is possible-world reachability probability, not min-max path bottleneck",
        "",
    ]
    for row in sort_edge_facts(payload["edge_facts"]):
        conf = _format_float(row["confidence"])
        lines.append(
            f"{conf}::edge("
            f"{_to_problog_atom(row['source_id'])}, "
            f"{_to_problog_atom(row['target_id'])}"
            ")."
        )
    lines.extend(
        [
            "",
            "reachable(X, Y) :- edge(X, Y).",
            "reachable(X, Z) :- reachable(X, Y), edge(Y, Z).",
            "query(reachable(X, Y)).",
            "",
        ]
    )
    return "\n".join(lines)


def _build_workload_a_souffle_program() -> str:
    return "\n".join(
        [
            ".decl edge(source:symbol, target:symbol)",
            ".input edge",
            ".decl reachable(source:symbol, target:symbol)",
            ".output reachable",
            "",
            "reachable(X, Y) :- edge(X, Y).",
            "reachable(X, Z) :- reachable(X, Y), edge(Y, Z).",
            "",
        ]
    )


def _build_workload_a_souffle_full_program() -> str:
    return "\n".join(
        [
            ".decl edge(source:symbol, target:symbol, conf:float)",
            ".input edge",
            ".decl path_confidence(source:symbol, target:symbol, conf:float)",
            ".decl best_confidence(source:symbol, target:symbol, conf:float)",
            ".output best_confidence",
            "",
            "path_confidence(X, Y, C) :- edge(X, Y, C).",
            "path_confidence(X, Z, C) :- path_confidence(X, Y, C1), edge(Y, Z, C2), C = min(C1, C2).",
            "best_confidence(X, Y, C) :- path_confidence(X, Y, _), C = max v : { path_confidence(X, Y, v) }.",
            "",
        ]
    )


def _build_workload_b_souffle_program(payload: dict[str, Any]) -> str:
    t_max = int(payload["t_max"])
    lines = [
        ".decl init_state(entity:symbol, status:symbol)",
        ".input init_state",
        ".decl property(entity:symbol, prop_name:symbol, prop_value:symbol)",
        ".input property",
        ".decl state(entity:symbol, timestep:number, status:symbol)",
        ".output state",
        ".decl provenance(entity:symbol, timestep:number, status:symbol, rule_id:number, helper:symbol)",
        ".output provenance",
        "",
    ]
    lines.extend(
        [
            ".decl state_t0(entity:symbol, status:symbol)",
            "state_t0(E, S) :- init_state(E, S).",
            "state(E, 0, S) :- state_t0(E, S).",
            "",
        ]
    )

    for timestep in range(1, t_max + 1):
        prev_step = timestep - 1
        lines.extend(
            [
                f".decl state_candidate_t{timestep}(entity:symbol, status:symbol, priority:number, rule_id:number, helper:symbol)",
                f".decl best_priority_t{timestep}(entity:symbol, priority:number)",
                f".decl state_t{timestep}(entity:symbol, status:symbol)",
                "",
                f'state_candidate_t{timestep}(E, S, 0, 0, "") :- state_t{prev_step}(E, S).',
            ]
        )
        for rule in sort_rules(payload["rules"]):
            if rule["template"] == "T2":
                lines.append(
                    'state_candidate_t{timestep}(E, "{target}", {priority}, {rule_id}, "") :- '
                    'state_t{prev_step}(E, "{source}"), property(E, "class", "{cls}").'.format(
                        timestep=timestep,
                        target=rule["target_status"],
                        priority=rule["rule_id"],
                        rule_id=rule["rule_id"],
                        prev_step=prev_step,
                        source=rule["source_status"],
                        cls=rule["class_value"],
                    )
                )
            elif rule["template"] == "T3":
                lines.append(
                    'state_candidate_t{timestep}(E1, "{target}", {priority}, {rule_id}, E2) :- '
                    'state_t{prev_step}(E1, "{source}"), state_t{prev_step}(E2, "active"), property(E2, "class", "{helper_class}"), '
                    "E1 != E2.".format(
                        timestep=timestep,
                        target=rule["target_status"],
                        priority=rule["rule_id"],
                        rule_id=rule["rule_id"],
                        prev_step=prev_step,
                        source=rule["source_status"],
                        helper_class=rule["helper_class"],
                    )
                )
        lines.extend(
            [
                f"best_priority_t{timestep}(E, P) :- state_candidate_t{timestep}(E, _, _, _, _), P = max p : {{ state_candidate_t{timestep}(E, _, p, _, _) }}.",
                f"state_t{timestep}(E, S) :- state_candidate_t{timestep}(E, S, P, _, _), best_priority_t{timestep}(E, P).",
                f"state(E, {timestep}, S) :- state_t{timestep}(E, S).",
                f"provenance(E, {timestep}, S, R, H) :- state_candidate_t{timestep}(E, S, P, R, H), best_priority_t{timestep}(E, P).",
                "",
            ]
        )
    return "\n".join(lines)


def _write_souffle_edges(edge_facts: list[dict[str, Any]], path: Path) -> None:
    rows = [[row["source_id"], row["target_id"]] for row in sort_edge_facts(edge_facts)]
    path.write_text(
        "".join("\t".join(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _write_souffle_weighted_edges(edge_facts: list[dict[str, Any]], path: Path) -> None:
    rows = [
        [row["source_id"], row["target_id"], _format_float(row["confidence"])]
        for row in sort_edge_facts(edge_facts)
    ]
    path.write_text(
        "".join("\t".join(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _write_souffle_init_states(init_state_facts: list[dict[str, Any]], path: Path) -> None:
    rows = [[row["entity_id"], row["status"]] for row in sort_init_state_facts(init_state_facts)]
    path.write_text(
        "".join("\t".join(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _write_souffle_properties(property_facts: list[dict[str, Any]], path: Path) -> None:
    rows = [[row["entity_id"], row["prop_name"], row["prop_value"]] for row in sort_property_facts(property_facts)]
    path.write_text(
        "".join("\t".join(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _read_souffle_reachable_pairs(out_dir: Path) -> set[tuple[str, str]]:
    csv_path = out_dir / "reachable.csv"
    facts_path = out_dir / "reachable.facts"
    path = csv_path if csv_path.exists() else facts_path
    if not path.exists():
        return set()
    out: set[tuple[str, str]] = set()
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) != 2:
                continue
            out.add((row[0], row[1]))
    return out


def _read_souffle_best_confidence(out_dir: Path) -> list[dict[str, Any]]:
    csv_path = out_dir / "best_confidence.csv"
    facts_path = out_dir / "best_confidence.facts"
    path = csv_path if csv_path.exists() else facts_path
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) != 3:
                continue
            rows.append(
                {
                    "source": row[0],
                    "target": row[1],
                    "confidence": _round_float(float(row[2]), 6),
                }
            )
    rows.sort(key=lambda item: (item["source"], item["target"]))
    return rows


def _read_souffle_state_rows(out_dir: Path) -> list[dict[str, Any]]:
    csv_path = out_dir / "state.csv"
    facts_path = out_dir / "state.facts"
    path = csv_path if csv_path.exists() else facts_path
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) != 3:
                continue
            rows.append(
                {
                    "entity": row[0],
                    "timestep": int(row[1]),
                    "status": row[2],
                }
            )
    rows.sort(key=lambda item: (item["entity"], item["timestep"], item["status"]))
    return rows


def _read_souffle_workload_b_provenance(out_dir: Path) -> list[dict[str, Any]]:
    csv_path = out_dir / "provenance.csv"
    facts_path = out_dir / "provenance.facts"
    path = csv_path if csv_path.exists() else facts_path
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) != 5:
                continue
            rule_id = int(row[3])
            rule_label = "T1" if rule_id == 0 else ("T2_" + str(rule_id) if 100 <= rule_id < 200 else "T3_" + str(rule_id))
            rows.append(
                {
                    "entity": row[0],
                    "timestep": int(row[1]),
                    "status": row[2],
                    "rule_id": rule_id,
                    "rule_label": rule_label,
                    "helper": row[4],
                }
            )
    rows.sort(key=lambda item: (item["entity"], item["timestep"], item["status"], item["rule_id"], item["helper"]))
    return rows


def _parse_workload_a_problog_output(
    raw_output: str,
    reference_index: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw_line in raw_output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%") or line.startswith("#"):
            continue
        split = _split_probability_line(line)
        if split is None:
            continue
        expr, prob_text = split
        if expr.startswith("query(") and expr.endswith(")"):
            expr = expr[6:-1].strip()
        if not expr.startswith("reachable(") or not expr.endswith(")"):
            continue
        args = _split_top_level_args(expr[len("reachable(") : -1])
        if len(args) != 2:
            continue
        source = _decode_problog_atom(args[0])
        target = _decode_problog_atom(args[1])
        reference = reference_index.get((source, target))
        out.append(
            {
                "source": source,
                "target": target,
                "confidence": _round_float(float(prob_text), 6),
                "min_support_depth": reference["min_support_depth"] if reference is not None else None,
            }
        )
    out.sort(key=lambda row: (row["source"], row["target"]))
    return out


def _build_workload_c_problog_program(payload: dict[str, Any]) -> str:
    lines = [
        "% workload C smoke runner v0",
        "% Top-K ranking is deferred to harness",
        "",
    ]
    for row in sort_struct_facts(payload["struct_facts"]):
        lines.append(
            "1.0::struct_fact("
            f"{_to_problog_atom(row['subject_id'])}, "
            f"{_to_problog_atom(row['relation'])}, "
            f"{_to_problog_atom(row['object_id'])}"
            ")."
        )
    for row in sort_evidence_facts(payload["evidence_facts"]):
        conf = _format_float(row["confidence"])
        lines.append(
            f"{conf}::evidence("
            f"{_to_problog_atom(row['claim_id'])}, "
            f"{_to_problog_atom(row['subject_id'])}, "
            f"{_to_problog_atom(row['relation'])}, "
            f"{_to_problog_atom(row['object_id'])}, "
            f"{conf}, "
            f"{_to_problog_atom(row['source'])}"
            ")."
        )

    lines.extend(
        [
            "",
            "candidate(S, R, O, C) :- evidence(_, S, R, O, C, _).",
            'derived_relation(S, indirect_dependency, O) :- struct_fact(S, depends_on, M), struct_fact(M, depends_on, O).',
            'derived_relation(S, reachable_monitor, O) :- struct_fact(S, monitors, M), struct_fact(M, is_component_of, O).',
            "candidate(S, R, O, 1.0) :- derived_relation(S, R, O).",
            "query(candidate(S, R, O, C)).",
            "",
        ]
    )
    return "\n".join(lines)


def _build_workload_c_souffle_program() -> str:
    return "\n".join(
        [
            ".decl struct_fact(subject:symbol, relation:symbol, object:symbol)",
            ".input struct_fact",
            ".decl derived_relation(subject:symbol, relation:symbol, object:symbol)",
            ".output derived_relation",
            "",
            'derived_relation(S, "indirect_dependency", O) :-',
            '  struct_fact(S, "depends_on", M),',
            '  struct_fact(M, "depends_on", O).',
            "",
            'derived_relation(S, "reachable_monitor", O) :-',
            '  struct_fact(S, "monitors", M),',
            '  struct_fact(M, "is_component_of", O).',
            "",
        ]
    )


def _write_souffle_struct_facts(struct_facts: list[dict[str, str]], path: Path) -> None:
    rows = [
        [row["subject_id"], row["relation"], row["object_id"]]
        for row in sort_struct_facts(struct_facts)
    ]
    path.write_text(
        "".join("\t".join(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _read_souffle_derived_candidates(out_dir: Path) -> list[dict[str, Any]]:
    csv_path = out_dir / "derived_relation.csv"
    facts_path = out_dir / "derived_relation.facts"
    path = csv_path if csv_path.exists() else facts_path
    if not path.exists():
        return []

    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) != 3:
                continue
            out.append(
                {
                    "subject": row[0],
                    "relation": row[1],
                    "object": row[2],
                    "confidence": 1.0,
                    "source_type": "derived",
                    "claim_id": None,
                }
            )
    return sort_raw_candidates(out)


def _parse_workload_c_problog_output(raw_output: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_candidates: list[dict[str, Any]] = []
    evidence_index = _index_evidence_by_triple_and_confidence(payload["evidence_facts"])

    for raw_line in raw_output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%") or line.startswith("#"):
            continue
        split = _split_probability_line(line)
        if split is None:
            continue
        expr, prob_text = split
        if expr.startswith("query(") and expr.endswith(")"):
            expr = expr[6:-1].strip()
        if not expr.startswith("candidate(") or not expr.endswith(")"):
            continue
        args = _split_top_level_args(expr[len("candidate(") : -1])
        if len(args) != 4:
            continue
        subject = _decode_problog_atom(args[0])
        relation = _decode_problog_atom(args[1])
        obj = _decode_problog_atom(args[2])
        conf_term = float(args[3])
        confidence = _round_float(float(prob_text), 6)
        matched_claims = evidence_index.get((subject, relation, obj, _round_float(conf_term, 6)), [])
        raw_candidates.append(
            {
                "subject": subject,
                "relation": relation,
                "object": obj,
                "confidence": confidence,
                "source_type": "direct_evidence" if matched_claims else "derived",
                "claim_id": matched_claims[0] if len(matched_claims) == 1 else None,
            }
        )

    return sort_raw_candidates(raw_candidates)


def _split_probability_line(line: str) -> tuple[str, str] | None:
    if "\t" in line:
        lhs, rhs = line.rsplit("\t", 1)
        lhs = lhs.strip()
        if lhs.endswith(":"):
            lhs = lhs[:-1].rstrip()
        return lhs, rhs.strip()
    if ":" in line:
        lhs, rhs = line.rsplit(":", 1)
        rhs = rhs.strip()
        if _looks_like_float(rhs):
            return lhs.strip(), rhs
    return None


def _split_top_level_args(text: str) -> list[str]:
    args: list[str] = []
    start = 0
    depth = 0
    in_single = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_single:
            if ch == "'" and i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            args.append(text[start:i].strip())
            start = i + 1
        i += 1
    args.append(text[start:].strip())
    return args


def _decode_problog_atom(token: str) -> str:
    value = token.strip()
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        inner = value[1:-1]
        return inner.replace("''", "'")
    return value


def _base_result(
    *,
    baseline: str,
    raw_candidates: list[dict[str, Any]],
    provenance_entries: list[dict[str, Any]],
    unsupported_features: list[str],
    notes: str,
) -> dict[str, Any]:
    return {
        "workload": WORKLOAD_C,
        "baseline": baseline,
        "aggregation": "max",
        "wall_clock_seconds": 0.0,
        "peak_memory_mb": 0.0,
        "raw_candidates": raw_candidates,
        "provenance_entries": provenance_entries,
        "unsupported_features": unsupported_features,
        "notes": notes,
    }


def _base_result_workload_b(
    *,
    baseline: str,
    t_max: int,
    results: list[dict[str, Any]],
    provenance_entries: list[dict[str, Any]],
    state_history_summary: dict[str, list[str]],
    unsupported_features: list[str],
    notes: str,
    native_temporal_advantage: bool,
    annotation_kernel_noop: bool,
) -> dict[str, Any]:
    return {
        "workload": WORKLOAD_B,
        "baseline": baseline,
        "T_max": t_max,
        "wall_clock_seconds": 0.0,
        "rule_unrolling_seconds": 0.0,
        "peak_memory_mb": 0.0,
        "results": results,
        "state_history_summary": state_history_summary,
        "provenance_entries": provenance_entries,
        "unsupported_features": unsupported_features,
        "native_temporal_advantage": native_temporal_advantage,
        "annotation_kernel_noop": annotation_kernel_noop,
        "notes": notes,
    }

def _index_evidence_by_triple_and_confidence(
    evidence_facts: list[dict[str, Any]],
) -> dict[tuple[str, str, str, float], list[str]]:
    out: dict[tuple[str, str, str, float], list[str]] = {}
    for row in evidence_facts:
        key = (
            row["subject_id"],
            row["relation"],
            row["object_id"],
            _round_float(row["confidence"], 6),
        )
        out.setdefault(key, []).append(row["claim_id"])
    for claim_ids in out.values():
        claim_ids.sort()
    return out


def _to_problog_atom(value: str) -> str:
    if value and value.replace("_", "").isalnum() and value[0].isalpha():
        return value
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be non-empty string")
    return value


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be int")
    return int(value)


def _require_probability(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be float within [0,1]")
    prob = float(value)
    if prob < 0.0 or prob > 1.0:
        raise ValueError(f"{field_name} must be within [0,1]")
    return _round_float(prob, 6)


def _looks_like_float(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _format_float(value: float) -> str:
    if math.isclose(value, round(value), abs_tol=_EPSILON):
        return f"{value:.1f}"
    return f"{value:.12g}"


def _round_float(value: float, digits: int) -> float:
    return round(float(value), digits)


if __name__ == "__main__":
    main()
