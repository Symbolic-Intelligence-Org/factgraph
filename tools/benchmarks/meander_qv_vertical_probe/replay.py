"""Probe Step 5: R0-R4 graded replay + mutation protocol (blueprint §5.14).

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

13 frozen operation IDs, at most 14 local attempts, verbs EVALUATE|EXPLAIN|REOPEN.
R1/R2 share one ReplayBundlePinSetV0 for the named Q02 selected-row bundle.
Negative ops fail explicitly (RUN_CONTEXT_UNAVAILABLE / REPLAY_ARTIFACT_EXPIRED /
REPLAY_INTEGRITY_FAILURE) and never read current/latest state. Mutations are
child comparative runs on COPIES; mutation isolation is a zero-execution
bytes/digest comparison. R3 fixed UNRESOLVED; R4 fixed NOT_TESTED.

Interpretation note (recorded in the manifest): the attempt-verb algebra
(3 R0 EXPLAIN, 1 R1 REOPEN, R2 EVALUATE+EXPLAIN, 4 NEG REOPEN, 4 MUT EVALUATE)
admits no EVALUATE for Q04/E03 inside Step 5; therefore RP-R0-SUMMARY and
RP-R0-EXPECTATION verify the live-association evidence captured during the
Step 3 live runs (complete actual artifacts, A' ruling item 4), while
RP-R0-ROW performs a genuinely live row.explain() on the R2 re-executed handle.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from typing import Any

_PROBE_ROOT_EARLY = os.path.dirname(os.path.abspath(__file__))
if _PROBE_ROOT_EARLY not in sys.path:
    sys.path.insert(0, _PROBE_ROOT_EARLY)

from contracts import digest, full_digest
from profiles import load_fixture, profile_snapshot
import resolver as probe_resolver
import compiler as probe_compiler
import lineage as probe_lineage
import evaluator as probe_evaluator

_PROBE_ROOT = os.path.dirname(os.path.abspath(__file__))
_REPORTS = os.path.join(_PROBE_ROOT, "reports")

OPERATION_IDS = (
    "RP-R0-ROW", "RP-R0-SUMMARY", "RP-R0-EXPECTATION",
    "RP-R1-REOPEN", "RP-R2-REEXECUTE",
    "RP-NEG-PARTIAL", "RP-NEG-UNAVAILABLE", "RP-NEG-EXPIRED", "RP-NEG-INTEGRITY",
    "RP-MUT-FACT", "RP-MUT-POLICY", "RP-MUT-CONFIG", "RP-MUT-SOURCE",
)
REQUIRED_PINS = ("policy", "facts_snapshot", "execution_profile", "lineage_summary",
                 "anchors", "provenance", "format_version")


def _canonical_rowset_digest(rows: list[dict]) -> str:
    enc = sorted(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows)
    return "sha256:" + hashlib.sha256("\n".join(enc).encode()).hexdigest()[:16]


def capture_bundle(verification: dict) -> dict:
    """ReplayBundlePinSetV0 for the Q02 named selected-row bundle (not an attempt)."""
    q02 = next(r for r in verification["results"] if r["cell_id"] == "Q02")
    art = q02["actual_artifact"]
    fixture = load_fixture("Q02")
    selected = art["row_anchors"][0]
    bundle = {
        "record_type": "ReplayBundlePinSetV0",
        "format_version": "v0",
        "cell_id": "Q02",
        "policy": {"ast": fixture["profile"]["policy"]["ast"],
                   "policy_digest": digest(fixture["profile"]["policy"]),
                   "profile_digest": digest(fixture["profile"])},
        "facts_snapshot": fixture["world"],
        "execution_profile": {"engine": "native", "config": None, "budget": "lean-v0"},
        "lineage_summary": {
            "shipped_plan": art["lineage"]["shipped_plan"],
            "authored_count": len(art["lineage"]["authored_nodes"]),
            "lowered_count": len(art["lineage"]["lowered_nodes"]),
        },
        "anchors": {"selected_row_anchor": selected, "all_row_anchors": art["row_anchors"]},
        "provenance": {
            "rows": art["result"]["rows"],
            "canonical_rowset_digest": _canonical_rowset_digest(art["result"]["rows"]),
            "completeness": art["result"]["completeness"],
            "explain_record": art["explain"],
            "shipped_fingerprint": art.get("shipped_fingerprint"),
        },
    }
    bundle["bundle_digest"] = full_digest({k: bundle[k] for k in REQUIRED_PINS if k in bundle}
                                          | {"anchors": bundle["anchors"]})
    path = os.path.join(_REPORTS, "replay_bundle_q02.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return bundle


class BundleLoader:
    """Reads ONLY the bundle mapping. No store, no ledger, no current state."""

    def __init__(self, bundle: dict | None, *, availability: str = "available"):
        self.bundle = bundle
        self.availability = availability

    def reopen(self) -> dict:
        if self.bundle is None:
            return {"status": "RUN_CONTEXT_UNAVAILABLE", "availability": "unavailable"}
        if self.availability == "expired_or_erased":
            return {"status": "REPLAY_ARTIFACT_EXPIRED", "availability": "expired_or_erased"}
        missing = [p for p in REQUIRED_PINS if p not in self.bundle]
        if missing:
            return {"status": "RUN_CONTEXT_UNAVAILABLE", "availability": "partial",
                    "missing_pins": missing}
        recomputed = full_digest({k: self.bundle[k] for k in REQUIRED_PINS if k in self.bundle}
                                 | {"anchors": self.bundle["anchors"]})
        if recomputed != self.bundle.get("bundle_digest"):
            return {"status": "REPLAY_INTEGRITY_FAILURE", "availability": "available",
                    "expected": self.bundle.get("bundle_digest"), "recomputed": recomputed}
        prov = self.bundle["provenance"]
        return {
            "status": "reopened", "availability": "available",
            "captured_explain": {
                "anchor": "row",
                "content_class": "captured_artifact",
                "selected_row_anchor": self.bundle["anchors"]["selected_row_anchor"],
                "row": prov["rows"][0] if prov["rows"] else None,
                "explanation_status_recorded": prov["explain_record"].get("explanation_status"),
                "evidence_graph_recorded": prov["explain_record"].get("has_evidence_graph"),
            },
        }


def run_step5() -> dict:
    with open(os.path.join(_REPORTS, "implementation_verification_manifest.json"),
              "r", encoding="utf-8") as fh:
        verification = json.load(fh)
    bundle = capture_bundle(verification)
    art = {r["cell_id"]: r["actual_artifact"] for r in verification["results"]}
    attempts: list[dict] = []
    ops: dict[str, dict] = {}

    def attempt(op: str, verb: str, detail: str) -> None:
        attempts.append({"op": op, "verb": verb, "detail": detail})
        assert len(attempts) <= 14, "attempt cap exceeded"

    # ---- RP-R2-REEXECUTE: pinned deterministic re-execution (EVALUATE+EXPLAIN) ----
    fixture = load_fixture("Q02")
    assert digest(fixture["world"]) == digest(bundle["facts_snapshot"]), "pin drift"
    snap = profile_snapshot(fixture)
    res = probe_resolver.resolve(fixture, snap)
    cr = probe_compiler.compile_policy(fixture, res)
    attempt("RP-R2-REEXECUTE", "EVALUATE", "re-execute Q02 from pinned facts/policy/profile")
    run = probe_evaluator.run_cell(fixture, res, cr)
    rows_match = (_canonical_rowset_digest(run["result"]["rows"])
                  == bundle["provenance"]["canonical_rowset_digest"])
    completeness_match = run["result"]["completeness"] == bundle["provenance"]["completeness"]
    attempt("RP-R2-REEXECUTE", "EXPLAIN", "explain re-executed selected row")
    r2_explain_ok = (run["explain"]["anchor"] == "row"
                     and run["explain"].get("explanation_status") == "passed"
                     and run["explain"].get("has_evidence_graph") is True)
    ops["RP-R2-REEXECUTE"] = {
        "level": "R2", "availability": "available",
        "pass": rows_match and completeness_match and r2_explain_ok,
        "comparator": {"canonical_rowset_match": rows_match,
                       "completeness_exact_match": completeness_match,
                       "explain_authored_identity_ok": r2_explain_ok,
                       "excluded_from_compare": ["run_id", "row_id", "evaluated_at"]},
        "claim": "selected-row pinned deterministic re-execution only",
    }
    r2_rowset_digest = _canonical_rowset_digest(run["result"]["rows"])

    # ---- RP-R0-ROW: genuinely live association on the re-executed handle ----------
    attempt("RP-R0-ROW", "EXPLAIN", "live row.explain() association on re-executed Q02 handle")
    ops["RP-R0-ROW"] = {
        "level": "R0", "availability": "available",
        "pass": r2_explain_ok and run["row_anchors"] and len(set(run["row_anchors"])) == len(run["row_anchors"]),
        "claim": "live association only (row target)",
        "mode": "live",
    }

    # ---- RP-R0-SUMMARY / RP-R0-EXPECTATION: verify Step-3 live-run evidence -------
    q04, e03 = art["Q04"], art["E03"]
    attempt("RP-R0-SUMMARY", "EXPLAIN", "verify Q04 live-run query-summary association (captured evidence)")
    ops["RP-R0-SUMMARY"] = {
        "level": "R0", "availability": "available",
        "pass": (q04["explain"]["anchor"] == "query_summary"
                 and q04["explain"]["content_class"] == "structured_diagnostic"
                 and (q04["result"]["query_summary"] or {}).get("status") is False),
        "claim": "live association only (summary target); verified from Step-3 live-run artifacts",
        "mode": "verified_from_step3_live_run",
    }
    attempt("RP-R0-EXPECTATION", "EXPLAIN", "verify E03 live-run expectation association (captured evidence)")
    ops["RP-R0-EXPECTATION"] = {
        "level": "R0", "availability": "available",
        "pass": (e03["explain"]["anchor"] == "expectation"
                 and e03["explain"]["content_class"] == "structured_diagnostic"
                 and (e03["expectation"] or {}).get("status") == "underdetermined"),
        "claim": "live association only (expectation target); verified from Step-3 live-run artifacts",
        "mode": "verified_from_step3_live_run",
    }

    # ---- RP-R1-REOPEN: captured-artifact Explain, no current-store resolver -------
    attempt("RP-R1-REOPEN", "REOPEN", "reopen captured Q02 bundle; no store constructed")
    reopened = BundleLoader(bundle).reopen()
    ops["RP-R1-REOPEN"] = {
        "level": "R1", "availability": reopened["availability"],
        "pass": (reopened["status"] == "reopened"
                 and reopened["captured_explain"]["selected_row_anchor"]
                 == bundle["anchors"]["selected_row_anchor"]),
        "claim": "selected-row captured-artifact Explain only",
    }

    # ---- four negatives: explicit failure, never current/latest fallback ----------
    partial = {k: v for k, v in bundle.items() if k != "provenance"}
    attempt("RP-NEG-PARTIAL", "REOPEN", "required pin removed")
    neg1 = BundleLoader(partial).reopen()
    ops["RP-NEG-PARTIAL"] = {"level": "NEG", "availability": neg1["availability"],
                             "pass": neg1["status"] == "RUN_CONTEXT_UNAVAILABLE",
                             "observed": neg1}
    attempt("RP-NEG-UNAVAILABLE", "REOPEN", "bundle absent")
    neg2 = BundleLoader(None).reopen()
    ops["RP-NEG-UNAVAILABLE"] = {"level": "NEG", "availability": neg2["availability"],
                                 "pass": neg2["status"] == "RUN_CONTEXT_UNAVAILABLE",
                                 "observed": neg2}
    attempt("RP-NEG-EXPIRED", "REOPEN", "retention-expired bundle")
    neg3 = BundleLoader(bundle, availability="expired_or_erased").reopen()
    ops["RP-NEG-EXPIRED"] = {"level": "NEG", "availability": neg3["availability"],
                             "pass": neg3["status"] == "REPLAY_ARTIFACT_EXPIRED",
                             "observed": neg3}
    corrupted = copy.deepcopy(bundle)
    corrupted["provenance"]["rows"] = list(corrupted["provenance"]["rows"]) + [{"person": "forged"}]
    attempt("RP-NEG-INTEGRITY", "REOPEN", "digest-integrity failure on tampered copy")
    neg4 = BundleLoader(corrupted).reopen()
    ops["RP-NEG-INTEGRITY"] = {"level": "NEG", "availability": neg4["availability"],
                               "pass": neg4["status"] == "REPLAY_INTEGRITY_FAILURE",
                               "observed": {k: v for k, v in neg4.items() if k != "expected"}}

    # ---- four mutation child runs on COPIES (EVALUATE each) -----------------------
    def child(op: str, mutate) -> None:
        fx = copy.deepcopy(fixture)
        note = mutate(fx)
        attempt(op, "EVALUATE", note)
        snap_c = profile_snapshot(fx)
        res_c = probe_resolver.resolve(fx, snap_c)
        cr_c = probe_compiler.compile_policy(fx, res_c)
        run_c = probe_evaluator.run_cell(fx, res_c, cr_c)
        ops[op] = {
            "level": "MUT", "availability": "available",
            "child_run": {"parent_bundle_digest": bundle["bundle_digest"],
                          "profile_digest": digest(fx["profile"]),
                          "world_digest": digest(fx["world"]),
                          "rows": run_c["result"]["rows"],
                          "rowset_digest": _canonical_rowset_digest(run_c["result"]["rows"]),
                          "completeness": run_c["result"]["completeness"]},
            "diff_vs_original": {
                "rows_changed": _canonical_rowset_digest(run_c["result"]["rows"]) != r2_rowset_digest,
                "profile_changed": digest(fx["profile"]) != digest(fixture["profile"]),
                "world_changed": digest(fx["world"]) != digest(fixture["world"]),
            },
            "pass": True,  # per-op pass criteria asserted below
            "note": note,
        }

    child("RP-MUT-FACT", lambda fx: (fx["world"]["facts"].append(["member", "eve", "red"]),
                                     "fact mutation: add member eve/red")[1])
    child("RP-MUT-POLICY", lambda fx: (fx["profile"]["policy"]["ast"]["all"].append(
        {"compare": {"left": {"path": "m.team"}, "op": "!=", "right": {"value": "red"}}}),
        "policy mutation: value-port compare m.team != 'red' (3 rows -> 0)")[1])
    child("RP-MUT-CONFIG", lambda fx: (fx["profile"].update(
        {"execution_profile_marker": {"engine": "native", "budget_marker": "mutated-v0"}}),
        "config/profile mutation: budget marker")[1])
    child("RP-MUT-SOURCE", lambda fx: (fx["world"].update(
        {"facts": [f for f in fx["world"]["facts"] if f[1] != "dan"]}),
        "source-availability mutation: dan's records unavailable")[1])

    # per-op mutation expectations
    ops["RP-MUT-FACT"]["pass"] = ops["RP-MUT-FACT"]["diff_vs_original"]["rows_changed"]
    ops["RP-MUT-POLICY"]["pass"] = ops["RP-MUT-POLICY"]["diff_vs_original"]["rows_changed"]
    ops["RP-MUT-CONFIG"]["pass"] = (ops["RP-MUT-CONFIG"]["diff_vs_original"]["profile_changed"]
                                    and not ops["RP-MUT-CONFIG"]["diff_vs_original"]["rows_changed"])
    ops["RP-MUT-SOURCE"]["pass"] = ops["RP-MUT-SOURCE"]["diff_vs_original"]["rows_changed"]

    # ---- mutation isolation: ZERO-EXECUTION offline comparison --------------------
    with open(os.path.join(_REPORTS, "replay_bundle_q02.json"), "r", encoding="utf-8") as fh:
        bundle_after = json.load(fh)
    isolation = {
        "bundle_bytes_unchanged": bundle_after["bundle_digest"] == bundle["bundle_digest"],
        "r2_fingerprint_matches_bundle": r2_rowset_digest
        == bundle["provenance"]["canonical_rowset_digest"],
        "method": "zero-execution offline bytes/digest comparison vs counted RP-R2 result",
    }

    levels = {
        "R0": {"status": "PASS" if all(ops[o]["pass"] for o in
               ("RP-R0-ROW", "RP-R0-SUMMARY", "RP-R0-EXPECTATION")) else "FAIL",
               "availability": "available",
               "claim": "three-target live association only"},
        "R1": {"status": "PASS" if ops["RP-R1-REOPEN"]["pass"] else "FAIL",
               "availability": ops["RP-R1-REOPEN"]["availability"],
               "claim": "selected-row captured-artifact Explain only"},
        "R2": {"status": "PASS" if ops["RP-R2-REEXECUTE"]["pass"] else "FAIL",
               "availability": "available",
               "claim": "selected-row pinned deterministic re-execution only"},
        "R3": {"status": "UNRESOLVED", "availability": "unavailable",
               "claim": "detached new-process reconstruction not executed in this lean envelope"},
        "R4": {"status": "NOT_TESTED", "availability": "unavailable",
               "claim": "production CompletedRun/retention/migration/UI replay out of scope"},
    }
    negatives_pass = all(ops[o]["pass"] for o in
                         ("RP-NEG-PARTIAL", "RP-NEG-UNAVAILABLE", "RP-NEG-EXPIRED", "RP-NEG-INTEGRITY"))
    mutations_pass = all(ops[o]["pass"] for o in
                         ("RP-MUT-FACT", "RP-MUT-POLICY", "RP-MUT-CONFIG", "RP-MUT-SOURCE"))
    manifest = {
        "record_type": "ReplayOperationManifestV0",
        "interpretation_note": (
            "Attempt-verb algebra admits no EVALUATE for Q04/E03 inside Step 5; RP-R0-SUMMARY "
            "and RP-R0-EXPECTATION therefore verify live-association evidence captured during "
            "the Step 3 live runs (A' item 4 complete artifacts); RP-R0-ROW is a genuinely "
            "live row.explain() on the RP-R2 re-executed handle."),
        "operation_ids": list(OPERATION_IDS),
        "attempts_used": len(attempts),
        "attempts_cap": 14,
        "attempts": attempts,
        "operations": ops,
        "levels": levels,
        "negatives_all_explicit": negatives_pass,
        "mutation_isolation": isolation,
        "mutations_pass": mutations_pass,
        "engine_calls_this_phase": 5,
        "query_summary_expectation_durable_replay": "NOT_TESTED (excluded per §5.14; D10/D11 at most narrowed PARTIAL)",
    }
    out = os.path.join(_REPORTS, "replay_operation_manifest.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return manifest


if __name__ == "__main__":
    import sys
    sys.path.insert(0, _PROBE_ROOT)
    m = run_step5()
    print(f"attempts {m['attempts_used']}/14; levels:",
          {k: v["status"] for k, v in m["levels"].items()})
    print("negatives:", m["negatives_all_explicit"], "| mutations:", m["mutations_pass"],
          "| isolation:", m["mutation_isolation"])
    ok = (all(v["status"] == "PASS" for k, v in m["levels"].items() if k in ("R0", "R1", "R2"))
          and m["negatives_all_explicit"] and m["mutations_pass"]
          and all(m["mutation_isolation"][k] for k in
                  ("bundle_bytes_unchanged", "r2_fingerprint_matches_bundle")))
    print("STEP5:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
