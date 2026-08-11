"""Mechanical scorer: harness outcome vs frozen golden (eight artifacts).

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Every named lineage assertion has an explicit handler; an unknown assertion
name FAILS the cell (no rubber-stamping — SCHEMA.md ruling #5 / MINOR-4:
result-layer assertions are dispatched to the result layer and re-verified).
Zero engine, zero model.
"""
from __future__ import annotations

import re
from typing import Any, Callable

# ---------------------------------------------------------------- subset compare

def subset_match(golden: Any, actual: Any, path: str, failures: list[str]) -> None:
    if isinstance(golden, dict):
        if not isinstance(actual, dict):
            failures.append(f"{path}: expected object, got {type(actual).__name__}")
            return
        for k, v in golden.items():
            subset_match(v, actual.get(k), f"{path}.{k}", failures)
    elif isinstance(golden, list):
        if not isinstance(actual, list) or len(golden) != len(actual):
            failures.append(f"{path}: list mismatch (golden {golden!r} vs {actual!r})")
            return
        for i, (g, a) in enumerate(zip(golden, actual)):
            subset_match(g, a, f"{path}[{i}]", failures)
    else:
        if golden != actual:
            failures.append(f"{path}: {golden!r} != {actual!r}")


# ------------------------------------------------- forbidden-interpretation rules

_FORBIDDEN_RULES: dict[str, list[str]] = {
    "empty_not_deny": ["denied", "deny", "violation", "error", "failed", "unsupported", "no access"],
    "incomplete_not_false": ["exists=false", "no such", "not found", "has no members", "false"],
    "underdetermined_not_notsatisfied": ["not satisfied", "not_satisfied", "false", "denied", "expectation failed"],
    "engine_fault_not_empty": ["no rows", "no members", "empty", "unsupported", "denied", "not found"],
}
_POSITIVE_CONTROLS: dict[str, str] = {
    "empty_not_deny": "the query completed and returned an empty result: no matching members",
    "incomplete_not_false": "the result is incomplete, so existence is underdetermined",
    "underdetermined_not_notsatisfied": "cannot be determined from an incomplete result",
    "engine_fault_not_empty": "evaluation aborted: the native engine reported an execution fault",
}


def interpretation_flags(oracle_name: str, candidate: str) -> bool:
    kws = _FORBIDDEN_RULES[oracle_name]
    text = candidate.lower()
    return any(kw in text for kw in kws)


def forbidden_oracle_selftest(oracle: dict) -> list[str]:
    failures = []
    name = oracle["name"]
    if name not in _FORBIDDEN_RULES:
        return [f"forbidden oracle '{name}' has no scorer rule"]
    for cand in oracle.get("rejects", ()):
        if not interpretation_flags(name, cand):
            failures.append(f"scorer failed to reject synthetic candidate {cand!r} under {name}")
    pos = _POSITIVE_CONTROLS[name]
    if interpretation_flags(name, pos):
        failures.append(f"scorer wrongly rejects positive control under {name}")
    return failures


# --------------------------------------------------------------- assertion handlers

def _edges(o: dict, rel: str) -> list[dict]:
    lin = o.get("lineage") or {}
    return [e for e in lin.get("lineage_edges", ()) if e["relation"] == rel]


def _coverage(o: dict) -> list[dict]:
    return (o.get("lineage") or {}).get("branch_coverage", [])


def _totality_ok(o: dict, key: str) -> bool:
    t = o.get("totality") or {}
    return t.get("ok", False) or not any(key in f for f in t.get("failures", ()))


def _handler_registry() -> list[tuple[re.Pattern, Callable[[dict, re.Match], bool]]]:
    H: list[tuple[str, Callable]] = []

    def add(pattern: str, fn: Callable) -> None:
        H.append((re.compile(pattern + r"$"), fn))

    add(r"every_authored_node_mapped", lambda o, m: _totality_ok(o, "invariant1"))
    add(r"every_lowered_node_attributed", lambda o, m: _totality_ok(o, "invariant2"))
    add(r"dnf_copies_recorded_as_one_to_many_edges", lambda o, m: len(_edges(o, "copies_to")) >= 1)
    add(r"synthetic_head_projection_only",
        lambda o, m: ((o.get("lineage") or {}).get("shipped_plan") or {}).get("head_binding_kind") == "projection")
    add(r"no_generated_alias_in_public_paths",
        lambda o, m: _totality_ok(o, "invariant5") and not any(
            re.search(r"__c\d", str(k)) for row in (o["result"].get("rows") or []) for k in row))
    add(r"bind_edge_present_for_(\w+?)_(\w+)",
        lambda o, m: any(e["from"].endswith(f":{m.group(1)}.{m.group(2)}") for e in _edges(o, "binds")))
    add(r"projects_to_edge_present_for_(\w+)_selection",
        lambda o, m: any(e["from"].startswith(f"authored:select:{m.group(1)}:") for e in _edges(o, "projects_to")))
    add(r"targets_expectation_edge_present", lambda o, m: len(_edges(o, "targets_expectation")) == 1)
    add(r"materializes_join_edge_present", lambda o, m: len(_edges(o, "materializes_join")) >= 1)
    add(r"injects_lookup_edge_present", lambda o, m: len(_edges(o, "injects_lookup")) >= 1)
    add(r"occurrence_aliases_independent",
        lambda o, m: len({s.split("__")[0] for s in (o.get("compile_meta") or {}).get("specialized_aliases", ())}) >= 2)
    add(r"distinct_run_local_row_anchor_per_row",
        lambda o, m: (len(o.get("row_anchors") or []) == len(o["result"].get("rows") or [])
                      and len(set(o.get("row_anchors") or [])) == len(o.get("row_anchors") or [])))
    add(r"self_row_included_correct_v0_semantics_no_inequality_operator",
        lambda o, m: any(set(r.values()) & {"alice"} for r in (o["result"].get("rows") or [])))
    add(r"join_materialized_in_branch_ab",
        lambda o, m: any(c["state"] == "materialized" and set(c["branch"]) == {"a", "b"}
                         for c in _coverage(o) if c["constraint"].startswith("authored:unify")))
    add(r"join_marked_not_applicable_by_candidate_semantics_in_branch_ac",
        lambda o, m: any(c["state"] == "not_applicable_by_candidate_semantics" and set(c["branch"]) == {"a", "c"}
                         for c in _coverage(o) if c["constraint"].startswith("authored:unify")))
    add(r"join_rejected_as_join_endpoint_not_total_in_branch_ac",
        lambda o, m: (o["result"].get("failure") or {}).get("code") == "JOIN_ENDPOINT_NOT_TOTAL")
    add(r"rejection_recorded_before_engine_invocation", lambda o, m: o["engine_invocations"] == 0)
    add(r"resolution_ambiguity_typed_pre_engine",
        lambda o, m: o["engine_invocations"] == 0 and o["resolution"]["status"] == "AMBIGUOUS_IDENTITY")
    add(r"ambiguous_candidates_enumerated_exactly_two",
        lambda o, m: len(((o["resolution"].get("diagnostics") or [{}])[0].get("candidates")) or []) == 2)
    add(r"attempted_authority_fields_enumerated_individually",
        lambda o, m: len(o["ingress"].get("attempted_authority_fields") or []) >= 2)
    add(r"aggregate_rejection_proves_composite_fail_closed_only",
        lambda o, m: o["ingress"]["status"] == "rejected_unknown_field" and o["engine_invocations"] == 0)
    add(r"ingress_rejected_before_resolution",
        lambda o, m: o["resolution"]["status"] == "not_reached")
    add(r"engine_invocations_zero", lambda o, m: o["engine_invocations"] == 0)
    add(r"model_invocations_zero", lambda o, m: o.get("model_invocations", 0) == 0)
    add(r"engine_fault_surfaced_as_typed_failure",
        lambda o, m: (o["result"].get("failure") or {}).get("code") == "EXECUTION_ENGINE_FAULT")
    add(r"no_fallback_result_synthesized",
        lambda o, m: o["result"].get("rows") is None and o["result"].get("query_summary") is None)
    add(r"expectation_set_mode_rejected_as_typed_diagnostic",
        lambda o, m: (o.get("expectation") or {}).get("status") == "unsupported"
        and "EXPECTATION_SET_MODE_UNSUPPORTED" in ((o.get("expectation") or {}).get("diagnostics") or []))
    add(r"field_navigation_resolution_recorded",
        lambda o, m: bool((o.get("compile_meta") or {}).get("navigations")))
    add(r"grant_checked_before_lowering",
        lambda o, m: (o.get("compile_meta") or {}).get("navigation_pre_lowering_validated") is True)
    add(r"selection_reuses_policy_materialized_field_variable",
        lambda o, m: (o.get("compile_meta") or {}).get("navigation_selection_reused") is True)
    add(r"grant_check_ordered_after_schema_resolution",
        lambda o, m: _probe_code(o, "restricted") == "FIELD_NAVIGATION_RESTRICTED"
        and _probe_code(o, "missing") == "FIELD_NAVIGATION_UNKNOWN_FIELD")
    add(r"probe_restricted_yields_FIELD_NAVIGATION_RESTRICTED",
        lambda o, m: _probe_code(o, "restricted") == "FIELD_NAVIGATION_RESTRICTED")
    add(r"probe_missing_yields_FIELD_NAVIGATION_UNKNOWN_FIELD",
        lambda o, m: _probe_code(o, "missing") == "FIELD_NAVIGATION_UNKNOWN_FIELD")
    add(r"probe_ambiguous_yields_PATH_UNRESOLVED_ALIAS",
        lambda o, m: _probe_code(o, "ambiguous") == "PATH_UNRESOLVED_ALIAS")
    add(r"probe_any_branch_unbound_yields_NAVIGATION_BRANCH_UNBOUND",
        lambda o, m: _probe_code(o, "any_branch_unbound") == "NAVIGATION_BRANCH_UNBOUND")
    add(r"probe_pin_mismatch_yields_PIN_MISMATCH",
        lambda o, m: _probe_code(o, "pin_mismatch") == "PIN_MISMATCH")
    add(r"single_explicit_catalog_invocation",
        lambda o, m: o.get("catalog_invocations") == 1)
    add(r"all_diagnostics_emitted_before_ledger_access_and_lowering",
        lambda o, m: o["engine_invocations"] == 0 and o.get("world_built") is not True)
    add(r"branch_count_exactly_32",
        lambda o, m: (o.get("publish_check") or {}).get("branch_count") == 32)
    add(r"publish_capability_accepted",
        lambda o, m: (o.get("publish_check") or {}).get("state") == "within_limit")
    add(r"publish_capability_rejected",
        lambda o, m: (o["result"].get("failure") or {}).get("code") == "DNF_BRANCH_LIMIT_EXCEEDED")
    add(r"diagnostic_DNF_BRANCH_LIMIT_EXCEEDED",
        lambda o, m: (o["result"].get("failure") or {}).get("code") == "DNF_BRANCH_LIMIT_EXCEEDED")
    add(r"diagnostic_SYNTHETIC_QUERY_NAMESPACE_COLLISION",
        lambda o, m: (o["result"].get("failure") or {}).get("code") == "SYNTHETIC_QUERY_NAMESPACE_COLLISION")
    add(r"authored_namespace_preserved_no_capture",
        lambda o, m: (o["result"].get("failure") or {}).get("code") == "SYNTHETIC_QUERY_NAMESPACE_COLLISION"
        and o.get("compile_meta") is None)
    return [(p, f) for p, f in H]


_REGISTRY = _handler_registry()


def _probe_code(o: dict, probe: str) -> str | None:
    for d in (o["result"].get("diagnostics") or []):
        if isinstance(d, dict) and d.get("probe") == probe:
            return d.get("code")
    return None


def check_assertions(outcome: dict, assertions: list[str]) -> list[str]:
    failures = []
    for name in assertions:
        matched = False
        for pat, fn in _REGISTRY:
            m = pat.match(name)
            if m:
                matched = True
                try:
                    ok = fn(outcome, m)
                except Exception as exc:  # noqa: BLE001 — assertion handlers must not crash the scorer
                    ok = False
                    failures.append(f"assertion '{name}' handler error: {exc!r}")
                    break
                if not ok:
                    failures.append(f"assertion '{name}' FAILED")
                break
        if not matched:
            failures.append(f"assertion '{name}' has NO HANDLER (refusing to rubber-stamp)")
    return failures


def score_cell(outcome: dict, golden: dict, fixture: dict) -> dict:
    failures: list[str] = []
    subset_match(golden["ingress"], outcome["ingress"], "ingress", failures)
    subset_match(golden["resolution"], outcome["resolution"], "resolution", failures)
    subset_match(golden["binding_path"], outcome.get("binding_path", {"bindings": [], "selections": []}),
                 "binding_path", failures)
    subset_match(golden["result"], outcome["result"], "result", failures)
    if golden.get("expectation") is None:
        if outcome.get("expectation") is not None:
            failures.append("expectation: golden null but harness produced one")
    else:
        subset_match(golden["expectation"], outcome.get("expectation"), "expectation", failures)
    subset_match({"anchor": golden["explain_target"]["anchor"],
                  "content_class": golden["explain_target"]["content_class"]},
                 {"anchor": outcome["explain"]["anchor"],
                  "content_class": outcome["explain"]["content_class"]},
                 "explain_target", failures)
    failures.extend(check_assertions(outcome, golden.get("lineage", {}).get("assertions", [])))
    if outcome["engine_invocations"] > fixture["engine_invocations_pinned"]:
        failures.append(
            f"ENGINE BUDGET: {outcome['engine_invocations']} > pinned {fixture['engine_invocations_pinned']}")
    oracle = golden.get("forbidden_interpretation_oracle")
    if oracle:
        failures.extend(forbidden_oracle_selftest(oracle))
    return {"cell_id": golden["cell_id"], "pass": not failures, "failures": failures}
