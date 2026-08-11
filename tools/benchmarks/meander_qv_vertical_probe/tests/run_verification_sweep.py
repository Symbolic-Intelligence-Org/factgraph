"""One-time implementation_verification sweep (user A′ ruling, 2026-08-11).

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Runs the full 20-cell corpus exactly once after the three located harness
root-cause fixes. Separately accounted: NOT primary/model/replay budget.
Caps for this sweep: exactly 20 harness invocations, at most 13 local engine
calls. Saves each cell's COMPLETE actual artifact (including lineage) to
reports/implementation_verification_manifest.json — coexisting with the
original reports/step3_run_manifest.json, which is never overwritten.
If ANY cell fails in this sweep: no further fix/rerun — straight to REVISE.
"""
from __future__ import annotations

import json
import os
import sys
import time

_PROBE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROBE_ROOT)
sys.path.insert(0, os.path.join(_PROBE_ROOT, "tests"))

from profiles import load_fixture, load_golden  # noqa: E402
from scorer import score_cell  # noqa: E402
import run_step3 as r3  # noqa: E402


def main() -> int:
    results = []
    invocations = 0
    engine_calls = 0
    t0 = time.time()
    for cell_id in r3.ZERO_FIRST_ORDER:
        fixture = load_fixture(cell_id)
        golden = load_golden(cell_id)
        outcome = r3._blank_outcome(cell_id)
        invocations += 1
        assert invocations <= 20, "sweep invocation cap"
        try:
            if "batch_probes" in fixture:
                r3.run_batch(fixture, outcome)
            elif r3._is_static_capability(fixture):
                r3.run_static_capability(fixture, outcome)
            else:
                r3.run_normal(fixture, outcome)
        except Exception as exc:  # noqa: BLE001
            outcome["result"] = {"kind": "harness_error", "error": repr(exc)}
        engine_calls += outcome["engine_invocations"]
        assert engine_calls <= 13, "sweep engine-call cap"
        score = score_cell(outcome, golden, fixture)
        results.append({"cell_id": cell_id, "score": score,
                        "actual_artifact": outcome})  # complete, including lineage
        print(f"[{'PASS' if score['pass'] else 'FAIL'}] {cell_id}  engine={outcome['engine_invocations']}")
        for f in score["failures"]:
            print(f"    - {f}")
    elapsed = time.time() - t0
    passed = sum(1 for r in results if r["score"]["pass"])
    manifest = {
        "record_type": "ImplementationVerificationManifestV0",
        "authorization": "user A-prime ruling 2026-08-11: one full 20-cell sweep after three "
                         "located harness root-cause fixes; separately accounted, not primary",
        "root_cause_fixes": [
            "resolver.py: attempted_authority_fields preserves submission order (experiment-v0 "
            "convention only, NOT a public canonical-ordering contract)",
            "tests/run_step3.py: static publish/catalog rejection carries "
            "content_class=structured_diagnostic",
            "evaluator.py: zero-row query_summary synthesized for task_kind=query only",
        ],
        "frozen_unchanged": "fixtures/goldens/SCHEMA/manifests/rubric/scorer/shipped source byte-identical",
        "sweep_invocations": invocations,
        "sweep_engine_calls": engine_calls,
        "cells_passed": passed,
        "cells_failed": 20 - passed,
        "elapsed_seconds": round(elapsed, 3),
        "on_failure_policy": "no further fix/rerun; straight to REVISE",
        "results": results,
    }
    out = os.path.join(_PROBE_ROOT, "reports", "implementation_verification_manifest.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nsweep: {passed}/20 PASS; invocations={invocations}; engine={engine_calls}; {elapsed:.2f}s")
    return 0 if passed == 20 else 1


if __name__ == "__main__":
    sys.exit(main())
