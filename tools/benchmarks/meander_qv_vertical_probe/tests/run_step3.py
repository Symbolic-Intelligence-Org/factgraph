"""Step 3 primary runner: exactly one primary invocation per cell, 20 total.

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Order: 0-engine cells first, then engine cells. The runner refuses to touch the
engine when a cell's pin is 0 (a pipeline that *reaches* the engine step under a
0-pin is a cell failure, never a silent engine call). Emits a run manifest to
reports/step3_run_manifest.json.

Usage:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src:<probe_root> \
        .../envs/factpy/bin/python tests/run_step3.py
"""
from __future__ import annotations

import json
import os
import sys
import time

_PROBE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROBE_ROOT)
sys.path.insert(0, os.path.join(_PROBE_ROOT, "tests"))

from contracts import ProbeError, digest  # noqa: E402
from profiles import load_fixture, load_golden, profile_snapshot  # noqa: E402
import resolver  # noqa: E402
import compiler as probe_compiler  # noqa: E402
import lineage as probe_lineage  # noqa: E402
import evaluator as probe_evaluator  # noqa: E402
from scorer import score_cell  # noqa: E402

ZERO_FIRST_ORDER = [
    # 0-engine cells first
    "NAV02", "SC12-32", "SC12-P", "AC21", "A01-AMB", "A01-AUTH", "SC01-B",
    # engine cells, simple -> complex
    "Q01", "Q03", "Q04", "Q02", "Q05", "E01", "E02", "E04", "E03",
    "NAV01", "P01", "SC01-A", "X01",
]


def _blank_outcome(cell_id: str) -> dict:
    return {
        "cell_id": cell_id,
        "ingress": {"status": "not_reached", "attempted_authority_fields": []},
        "resolution": {"status": "not_reached", "diagnostics": []},
        "binding_path": {"bindings": [], "selections": []},
        "result": None,
        "expectation": None,
        "explain": {"anchor": "none", "content_class": "none"},
        "engine_invocations": 0,
        "model_invocations": 0,
        "lineage": None,
        "totality": None,
        "compile_meta": None,
        "row_anchors": [],
        "publish_check": None,
        "world_built": False,
        "catalog_invocations": 0,
    }


def _is_static_capability(fixture: dict) -> bool:
    prof = fixture["profile"]
    return (fixture["engine_invocations_pinned"] == 0
            and "batch_probes" not in fixture
            and fixture.get("candidate_semantics") is None
            and not prof.get("slot_descriptors"))


def run_batch(fixture: dict, outcome: dict) -> None:
    """NAV02: one explicit catalog invocation, five named probes, zero engine."""
    from contracts import PIN_MISMATCH, static_validation_result
    outcome["ingress"] = {"status": "accepted", "attempted_authority_fields": []}
    outcome["resolution"] = {"status": "static_validation_only", "diagnostics": []}
    outcome["catalog_invocations"] = 1
    diags = []
    world = fixture["world"]
    for probe in fixture["batch_probes"]:
        code = None
        try:
            if probe.get("schema_digest_pin") is not None:
                actual = digest(world.get("entity_types", []))
                if probe["schema_digest_pin"] != actual:
                    raise ProbeError(PIN_MISMATCH, stage="resolution")
            ast = probe["policy"]["ast"]
            occ_specs = {r["rule_id"]: r for r in world.get("rules", ())}
            occs = probe_compiler._walk_occurrences(ast)
            occ_index = {}
            for occ in occs:
                if occ["rule_ref"] in occ_specs:
                    occ_index[occ["alias"]] = {"occurrence": occ, "rule_spec": occ_specs[occ["rule_ref"]]}
            branches = probe_compiler.ast_branches(ast)
            p = probe_compiler._resolve_path(probe["path"], occ_index)
            probe_compiler._validate_navigation(p, world, probe.get("field_path_grants", []), branches)
        except ProbeError as pe:
            code = pe.code
        diags.append({"probe": probe["name"], "code": code})
    outcome["result"] = static_validation_result(diags, assertions_ok=True)
    outcome["explain"] = {"anchor": "none", "content_class": "structured_diagnostic"}


def run_static_capability(fixture: dict, outcome: dict) -> None:
    """SC12-32 / SC12-P / AC21: catalog + publish capability only; never engine."""
    from contracts import static_validation_result
    outcome["catalog_invocations"] = 1
    try:
        probe_compiler.validate_catalog(fixture["world"])
        ast = fixture["profile"]["policy"]["ast"]
        branches = probe_compiler.ast_branches(ast)
        limit = probe_compiler._DNF_LIMIT
        outcome["publish_check"] = {
            "owner": "ProbeProfileCapabilityValidatorV0", "stage": "profile_publish_freeze",
            "branch_count": len(branches), "limit": limit,
            "state": "within_limit" if len(branches) <= limit else "exceeded",
        }
        if len(branches) > limit:
            raise ProbeError("DNF_BRANCH_LIMIT_EXCEEDED", stage="profile_publish_freeze",
                             owner="ProbeProfileCapabilityValidatorV0")
        outcome["result"] = static_validation_result([], assertions_ok=True)
    except ProbeError as pe:
        failure = {"code": pe.code, "stage": pe.stage}
        if pe.extra.get("owner"):
            failure["owner"] = pe.extra["owner"]
        outcome["result"] = static_validation_result([], assertions_ok=False, failure=failure)
        # a publish/catalog rejection carries structured diagnostic content
        outcome["explain"] = {"anchor": "none", "content_class": "structured_diagnostic"}


def run_normal(fixture: dict, outcome: dict) -> None:
    from contracts import typed_failure_result
    snapshot = profile_snapshot(fixture)
    pin = fixture["engine_invocations_pinned"]
    try:
        resolution = resolver.resolve(fixture, snapshot)
    except ProbeError as pe:
        art = pe.extra.get("artifact") or {}
        if pe.stage == "ingress":
            outcome["ingress"] = {"status": art.get("status", "rejected_unknown_field"),
                                  "attempted_authority_fields": art.get("attempted_authority_fields", [])}
            outcome["resolution"] = {"status": "not_reached", "diagnostics": []}
        else:
            outcome["ingress"] = {"status": "accepted",
                                  "attempted_authority_fields": art.get("attempted_authority_fields", [])}
            outcome["resolution"] = {"status": art.get("status", pe.code),
                                     "diagnostics": art.get("diagnostics", pe.diagnostics)}
        outcome["result"] = typed_failure_result(
            {"code": "INGRESS_UNKNOWN_FIELDS" if pe.stage == "ingress" else pe.code})
        return
    outcome["ingress"] = {"status": "accepted", "attempted_authority_fields": []}
    outcome["resolution"] = {"status": "resolved", "diagnostics": []}
    prof = fixture["profile"]
    outcome["binding_path"] = {
        "bindings": [{"path": t["path"], "term": resolution["normalized_slot_values"][t["slot"]]}
                     for t in prof.get("bind_templates", ())],
        "selections": [{"alias": t["alias"], "path": t["path"]} for t in prof.get("select_templates", ())],
    }
    try:
        cr = probe_compiler.compile_policy(fixture, resolution,
                                           candidate_semantics=fixture.get("candidate_semantics"))
    except ProbeError as pe:
        outcome["result"] = typed_failure_result({"code": pe.code})
        return
    outcome["publish_check"] = cr["publish_check"]
    outcome["compile_meta"] = {
        "specialized_aliases": sorted({f"{a}__" for a in cr["specialized"]}),
        "navigations": cr["navigations"],
        "navigation_pre_lowering_validated": True,
        "navigation_selection_reused": bool(cr["navigations"]) and any(
            s["path"].count(".") == 2 for s in cr["selections"]),
        "select_map": cr["select_map"],
    }
    golden_expect_present = prof["task_kind"] == "validation"
    lin = probe_lineage.build_lineage(cr, expectation_present=golden_expect_present)
    lin["query_digest"] = resolution.get("resolved_request_digest")
    outcome["lineage"] = lin
    outcome["totality"] = probe_lineage.check_totality(lin)
    if pin == 0:
        outcome["result"] = typed_failure_result(
            {"code": "PIPELINE_REACHED_ENGINE_UNDER_ZERO_PIN"})
        return
    outcome["world_built"] = True
    run = probe_evaluator.run_cell(fixture, resolution, cr)
    outcome["engine_invocations"] = run["engine_invocations"]
    outcome["result"] = run["result"]
    outcome["expectation"] = run["expectation"]
    outcome["explain"] = run["explain"]
    outcome["row_anchors"] = run.get("row_anchors", [])
    outcome["shipped_fingerprint"] = run.get("shipped_fingerprint")


def main() -> int:
    results = []
    invocations = 0
    t0 = time.time()
    for cell_id in ZERO_FIRST_ORDER:
        fixture = load_fixture(cell_id)
        golden = load_golden(cell_id)
        outcome = _blank_outcome(cell_id)
        invocations += 1
        try:
            if "batch_probes" in fixture:
                run_batch(fixture, outcome)
            elif _is_static_capability(fixture):
                run_static_capability(fixture, outcome)
            else:
                run_normal(fixture, outcome)
        except Exception as exc:  # noqa: BLE001 — harness defect surfaces as cell failure
            outcome["result"] = {"kind": "harness_error", "error": repr(exc)}
        score = score_cell(outcome, golden, fixture)
        results.append({"cell_id": cell_id, "outcome_digest": digest(
            {k: v for k, v in outcome.items() if k != "lineage"}),
            "engine_invocations": outcome["engine_invocations"],
            "score": score})
        status = "PASS" if score["pass"] else "FAIL"
        print(f"[{status}] {cell_id}  engine={outcome['engine_invocations']}"
              + ("" if score["pass"] else f"  failures={len(score['failures'])}"))
        for f in score["failures"]:
            print(f"    - {f}")
    elapsed = time.time() - t0
    passed = sum(1 for r in results if r["score"]["pass"])
    manifest = {
        "record_type": "Step3RunManifestV0",
        "primary_invocations": invocations,
        "cells_passed": passed,
        "cells_failed": 20 - passed,
        "engine_invocations_total": sum(r["engine_invocations"] for r in results),
        "elapsed_seconds": round(elapsed, 3),
        "results": results,
    }
    out = os.path.join(_PROBE_ROOT, "reports", "step3_run_manifest.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\n{passed}/20 PASS; engine calls={manifest['engine_invocations_total']}; {elapsed:.2f}s")
    return 0 if passed == 20 else 1


if __name__ == "__main__":
    sys.exit(main())
