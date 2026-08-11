"""DispositionPrecedenceValidatorV0 (blueprint §5.15) + four offline self-test groups.

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Mechanically derives the unique terminal disposition from frozen evidence/kill/
gate manifests. Precedence: STOP-class kill > invalidation or REVISE-class kill
> ordinary threshold REVISE > PROCEED_TO_ADR_CANDIDATES. Unknown IDs, duplicate
conflicting records or missing mandatory inputs => EXPERIMENT_INVALID -> REVISE.
Pre-registered non-blocking allowlist (R3=UNRESOLVED, R4=NOT_TESTED, product/
P-GATE untouched axes) never blocks by string-scan. Zero engine/model/replay.
"""
from __future__ import annotations

KILL_TERMINAL_CLASS = {
    "K-AUTHORITY": "STOP", "K-SEMANTIC": "STOP", "K-ZERO": "STOP", "K-SELECT": "STOP",
    "K-SC01": "STOP", "K-REPLAY": "STOP", "K-COMPAT": "STOP", "K-SCHEMA": "STOP",
    "K-CB0": "STOP", "K-SCOPE": "STOP", "K-DATA": "STOP",
    "K-SC02": "REVISE", "K-THRESHOLD": "REVISE", "K-BUDGET": "REVISE",
}
REQUIRED_GATES = (
    "step3_exit_all_items", "replay_r0_three_target", "replay_r1_q02", "replay_r2_q02",
    "mutation_isolation", "negatives_explicit", "compat_no_side_effect",
)
NON_BLOCKING_ALLOWLIST = (
    "R3=UNRESOLVED", "R4=NOT_TESTED", "product/P-GATE=NOT_TESTED/UNCHANGED",
    "query_summary_expectation_durable_replay=NOT_TESTED",
    "agent_dimension=UNRESOLVED_WITHOUT_BYOK_EGRESS",
)


def derive(evidence: dict) -> dict:
    """evidence = {kills: [{id, fired}], invalidations: [..], gates: {name: bool|None},
                    thresholds: {name: bool}, allowlisted_states: [..]}"""
    problems: list[str] = []
    fired_stop, fired_revise = [], []
    seen: dict[str, bool] = {}
    for k in evidence.get("kills", ()):
        kid = k.get("id")
        if kid not in KILL_TERMINAL_CLASS:
            return {"disposition": "REVISE", "reason": "EXPERIMENT_INVALID",
                    "detail": f"unknown kill id {kid!r}"}
        if kid in seen and seen[kid] != bool(k.get("fired")):
            return {"disposition": "REVISE", "reason": "EXPERIMENT_INVALID",
                    "detail": f"duplicate conflicting record for {kid}"}
        seen[kid] = bool(k.get("fired"))
        if k.get("fired"):
            (fired_stop if KILL_TERMINAL_CLASS[kid] == "STOP" else fired_revise).append(kid)
    for state in evidence.get("allowlisted_states", ()):
        if state not in NON_BLOCKING_ALLOWLIST:
            problems.append(f"state {state!r} not in pre-registered allowlist")
    gates = evidence.get("gates", {})
    for g in REQUIRED_GATES:
        if g not in gates:
            return {"disposition": "REVISE", "reason": "EXPERIMENT_INVALID",
                    "detail": f"missing mandatory gate input {g!r}"}
    if fired_stop:
        return {"disposition": "STOP", "reason": "STOP_CLASS_KILL", "detail": sorted(fired_stop)}
    if evidence.get("invalidations"):
        return {"disposition": "REVISE", "reason": "EXPERIMENT_INVALID",
                "detail": list(evidence["invalidations"])}
    if fired_revise:
        return {"disposition": "REVISE", "reason": "REVISE_CLASS_KILL", "detail": sorted(fired_revise)}
    unmet = [g for g in REQUIRED_GATES if gates.get(g) is not True]
    unmet += [t for t, ok in evidence.get("thresholds", {}).items() if ok is not True]
    if unmet or problems:
        return {"disposition": "REVISE", "reason": "THRESHOLD_UNMET",
                "detail": sorted(unmet) + problems}
    return {"disposition": "PROCEED_TO_ADR_CANDIDATES", "reason": "ALL_PREREQUISITES_MET",
            "detail": []}


def validate_declared(evidence: dict, declared: str) -> dict:
    derived = derive(evidence)
    ok = derived["disposition"] == declared
    return {"derived": derived, "declared": declared, "consistent": ok,
            "verdict": "ACCEPT" if ok else
            {"STOP": "CONTRADICTED", "REVISE": "CONTRADICTED"}.get(derived["disposition"], "CONTRADICTED")}


def selftest() -> list[str]:
    fails: list[str] = []
    base_gates = {g: True for g in REQUIRED_GATES}
    # group 1: STOP-class kill dominates everything
    r = derive({"kills": [{"id": "K-AUTHORITY", "fired": True}, {"id": "K-BUDGET", "fired": True}],
                "gates": base_gates, "thresholds": {"t": True}})
    if r["disposition"] != "STOP":
        fails.append(f"stop-group: {r}")
    # group 2: invalidation -> REVISE even with clean gates
    r = derive({"kills": [], "invalidations": ["score invalidated"], "gates": base_gates})
    if (r["disposition"], r["reason"]) != ("REVISE", "EXPERIMENT_INVALID"):
        fails.append(f"invalidation-group: {r}")
    # group 3: threshold unmet -> REVISE; allowlisted states never block
    r = derive({"kills": [{"id": "K-SC02", "fired": False}], "gates": {**base_gates, "replay_r2_q02": False},
                "allowlisted_states": ["R3=UNRESOLVED", "R4=NOT_TESTED"]})
    if (r["disposition"], r["reason"]) != ("REVISE", "THRESHOLD_UNMET"):
        fails.append(f"threshold-group: {r}")
    # group 4: proceed only when everything holds; unknown kill id invalidates
    r = derive({"kills": [{"id": "K-ZERO", "fired": False}], "gates": base_gates,
                "thresholds": {"canonical_equivalence": True},
                "allowlisted_states": ["product/P-GATE=NOT_TESTED/UNCHANGED"]})
    if r["disposition"] != "PROCEED_TO_ADR_CANDIDATES":
        fails.append(f"proceed-group: {r}")
    r = derive({"kills": [{"id": "K-MADE-UP", "fired": False}], "gates": base_gates})
    if r["reason"] != "EXPERIMENT_INVALID":
        fails.append(f"unknown-id-group: {r}")
    return fails


if __name__ == "__main__":
    import sys
    f = selftest()
    print("disposition validator selftest:", "PASS (4 groups + unknown-id)" if not f else f)
    sys.exit(0 if not f else 1)
