from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.audit.static_ui import render_audit_static_site
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.rules.rule_ir import RuleRegistry, RuleSpec, run_rule_with_trace
from factpy_kernel.core.store import Store
from factpy_kernel.ecss import (
    ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
    ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
    ECSS_OBLIGATION_TIMESTAMP_PRED_ID,
    ECSS_WINDOW_END_PRED_ID,
    ECSS_WINDOW_START_PRED_ID,
    extend_schema_ir_with_ecss_temporal_predicates,
    extend_schema_ir_with_ecss_uncertainty_predicates,
)
from factpy_kernel.sdk import Entity, Identity, compile_schema_from_classes


class Assessment(Entity):
    assessment_id: str = Identity(primary_key=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Scenario A audit delivery shape baseline.")
    parser.add_argument(
        "--scales",
        default="1,100,1000",
        help="Comma-separated assessment counts to benchmark.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output path. When omitted, writes to stdout.",
    )
    args = parser.parse_args()

    scales = [int(item.strip()) for item in args.scales.split(",") if item.strip()]
    if not scales or any(item <= 0 for item in scales):
        raise SystemExit("--scales must contain positive integers")

    payload = {
        "benchmark": "scenario_a_audit_delivery_shape",
        "generated_at_epoch_ns": time.time_ns(),
        "scales": [_bench_scale(scale) for scale in scales],
    }
    out_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_text, encoding="utf-8", newline="\n")
        print(out_path)
        return
    print(out_text, end="")


def _bench_scale(scale: int) -> dict[str, Any]:
    store = Store(_scenario_a_schema())
    _seed_assessments(store, scale)
    rule_spec = _composite_rule_spec()

    run_started = time.perf_counter()
    trace_result = run_rule_with_trace(store, rule_spec, RuleRegistry())
    run_seconds = time.perf_counter() - run_started

    readback_started = time.perf_counter()
    live_trace = store.explain_rule_trace(trace_result.rule_run_id)
    readback_seconds = time.perf_counter() - readback_started
    if not isinstance(live_trace, dict):
        raise RuntimeError("expected rule trace readback to return dict payload")

    with TemporaryDirectory() as package_dir, TemporaryDirectory() as site_dir:
        export_started = time.perf_counter()
        manifest_path = export_package(
            store,
            Path(package_dir),
            ExportOptions(package_kind="audit"),
        )
        export_seconds = time.perf_counter() - export_started

        render_started = time.perf_counter()
        site_manifest = render_audit_static_site(package_dir, site_dir)
        render_seconds = time.perf_counter() - render_started

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        audit_files = manifest["paths"]["audit_files"]
        rule_trace_path = Path(package_dir) / audit_files["rule_trace_artifacts"]
        trace_page_count = len(list((Path(site_dir) / "rule_traces").glob("*.html")))
        assertion_page_count = len(list((Path(site_dir) / "assertions").glob("*.html")))

        return {
            "assessment_count": scale,
            "rows_returned": len(trace_result.rows),
            "rule_run_id": trace_result.rule_run_id,
            "live": {
                "run_rule_with_trace_seconds": round(run_seconds, 6),
                "trace_readback_seconds": round(readback_seconds, 6),
                "invocation_count": len(live_trace.get("invocations", [])),
            },
            "audit_export": {
                "export_seconds": round(export_seconds, 6),
                "rule_trace_artifacts_bytes": rule_trace_path.stat().st_size,
            },
            "static_delivery": {
                "render_seconds": round(render_seconds, 6),
                "trace_page_count": trace_page_count,
                "assertion_page_count": assertion_page_count,
                "site_rule_trace_count": site_manifest.get("rule_trace_count", 0),
            },
        }


def _scenario_a_schema() -> dict[str, Any]:
    schema_ir = compile_schema_from_classes([Assessment])
    schema_ir = extend_schema_ir_with_ecss_temporal_predicates(schema_ir)
    schema_ir = extend_schema_ir_with_ecss_uncertainty_predicates(schema_ir)
    return schema_ir


def _seed_assessments(store: Store, scale: int) -> None:
    for idx in range(scale):
        assessment_ref = encode_idref_v1("Assessment", [("assessment_id", "string", f"ASSESS-{idx:04d}")])
        event_ts = 100 + idx
        window_start_ts = event_ts - 20
        window_end_ts = event_ts + 20
        pc_ppm = 80
        pc_threshold_ppm = 100
        success_ppm = 920000
        success_threshold_ppm = 900000
        set_field(store.ledger, ECSS_OBLIGATION_TIMESTAMP_PRED_ID, assessment_ref, [("time", event_ts)])
        set_field(store.ledger, ECSS_WINDOW_START_PRED_ID, assessment_ref, [("time", window_start_ts)])
        set_field(store.ledger, ECSS_WINDOW_END_PRED_ID, assessment_ref, [("time", window_end_ts)])
        set_field(store.ledger, ECSS_COLLISION_PROBABILITY_PPM_PRED_ID, assessment_ref, [("int", pc_ppm)])
        set_field(
            store.ledger,
            ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
            assessment_ref,
            [("int", pc_threshold_ppm)],
        )
        set_field(
            store.ledger,
            ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
            assessment_ref,
            [("int", success_ppm)],
        )
        set_field(
            store.ledger,
            ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
            assessment_ref,
            [("int", success_threshold_ppm)],
        )


def _composite_rule_spec() -> RuleSpec:
    return RuleSpec(
        rule_id="q.scenario_a_audit_delivery_shape_bench",
        version="1.0.0",
        select_vars=["$assessment"],
        where=[
            ("pred", ECSS_OBLIGATION_TIMESTAMP_PRED_ID, ["$assessment", "$event_ts"]),
            ("pred", ECSS_WINDOW_START_PRED_ID, ["$assessment", "$window_start_ts"]),
            ("pred", ECSS_WINDOW_END_PRED_ID, ["$assessment", "$window_end_ts"]),
            ("pred", ECSS_COLLISION_PROBABILITY_PPM_PRED_ID, ["$assessment", "$pc_ppm"]),
            ("pred", ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID, ["$assessment", "$pc_threshold_ppm"]),
            ("pred", ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID, ["$assessment", "$success_ppm"]),
            ("pred", ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID, ["$assessment", "$success_threshold_ppm"]),
            ("le", "$window_start_ts", "$event_ts"),
            ("le", "$event_ts", "$window_end_ts"),
            ("le", "$pc_ppm", "$pc_threshold_ppm"),
            ("ge", "$success_ppm", "$success_threshold_ppm"),
        ],
        expose=True,
    )


if __name__ == "__main__":
    main()
