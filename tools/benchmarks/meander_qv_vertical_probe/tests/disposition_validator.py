"""DispositionPrecedenceValidatorV0 (blueprint §5.15) + fail-closed self-tests.

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Mechanically derives the unique terminal disposition from a COMPLETE frozen
inventory of kills, thresholds, gates and invalidations. Fail-closed: any
missing mandatory input section, any type-malformed record, any unknown kill
id / allowlist state, or an absent mandatory threshold key => the experiment
cannot PROCEED. Precedence: STOP-class kill > invalidation or REVISE-class kill
> ordinary threshold/gate REVISE > PROCEED_TO_ADR_CANDIDATES.

experiment_validity axis (separate from disposition):
    VALID       — all prerequisites met (PROCEED), or a kill validly fired (STOP)
    INVALID     — the evidence inventory is itself malformed/unknown/contradictory
    UNRESOLVED  — the experiment ran validly but eligibility gates/thresholds are unmet

Zero engine/model/replay. Corrected at closure of `9b818490` per user ruling.
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
# thresholds that MUST be present (absence is a fail-closed eligibility miss, not PROCEED)
MANDATORY_THRESHOLD_KEYS = ("dual_model_arms_pass",)
MANDATORY_INPUT_SECTIONS = ("kills", "thresholds", "gates", "invalidations", "allowlisted_states")
NON_BLOCKING_ALLOWLIST = (
    "R3=UNRESOLVED", "R4=NOT_TESTED", "product/P-GATE=NOT_TESTED/UNCHANGED",
    "query_summary_expectation_durable_replay=NOT_TESTED",
    "agent_dimension=NOT_TESTED/UNRESOLVED",
    "evidencegraph_identity=UNRESOLVED",
)

_SECTION_TYPES = {"kills": list, "thresholds": dict, "gates": dict,
                  "invalidations": list, "allowlisted_states": list}


def _invalid(detail: str) -> dict:
    return {"disposition": "REVISE", "reason": "EXPERIMENT_INVALID",
            "experiment_validity": "INVALID", "detail": detail}


def derive(evidence: dict) -> dict:
    # ---- 1. complete mandatory inventory + container types (fail-closed) ----------
    for section in MANDATORY_INPUT_SECTIONS:
        if section not in evidence:
            return _invalid(f"missing mandatory input section {section!r}")
        if not isinstance(evidence[section], _SECTION_TYPES[section]):
            return _invalid(f"section {section!r} has wrong type "
                            f"{type(evidence[section]).__name__}")
    # ---- 2. record-level type validation ------------------------------------------
    for k in evidence["kills"]:
        if not isinstance(k, dict) or not isinstance(k.get("id"), str) \
                or not isinstance(k.get("fired"), bool):
            return _invalid(f"malformed kill record {k!r}")
    for tk, tv in evidence["thresholds"].items():
        if not isinstance(tv, bool):
            return _invalid(f"threshold {tk!r} value is not bool: {tv!r}")
    for g, gv in evidence["gates"].items():
        if gv is not None and not isinstance(gv, bool):
            return _invalid(f"gate {g!r} value is not bool/None: {gv!r}")
    for state in evidence["allowlisted_states"]:
        if state not in NON_BLOCKING_ALLOWLIST:
            return _invalid(f"state {state!r} not in pre-registered allowlist")
    # ---- 3. kill precedence bookkeeping -------------------------------------------
    fired_stop, fired_revise = [], []
    seen: dict[str, bool] = {}
    for k in evidence["kills"]:
        kid = k["id"]
        if kid not in KILL_TERMINAL_CLASS:
            return _invalid(f"unknown kill id {kid!r}")
        if kid in seen and seen[kid] != k["fired"]:
            return _invalid(f"duplicate conflicting record for {kid}")
        seen[kid] = k["fired"]
        if k["fired"]:
            (fired_stop if KILL_TERMINAL_CLASS[kid] == "STOP" else fired_revise).append(kid)
    # ---- 4. mandatory gate/threshold-key presence (structural) --------------------
    gates = evidence["gates"]
    for g in REQUIRED_GATES:
        if g not in gates:
            return _invalid(f"missing mandatory gate input {g!r}")
    thresholds = evidence["thresholds"]
    missing_threshold_keys = [t for t in MANDATORY_THRESHOLD_KEYS if t not in thresholds]
    # ---- 5. precedence resolution -------------------------------------------------
    if fired_stop:
        return {"disposition": "STOP", "reason": "STOP_CLASS_KILL",
                "experiment_validity": "VALID", "detail": sorted(fired_stop)}
    if evidence["invalidations"]:
        return {"disposition": "REVISE", "reason": "EXPERIMENT_INVALID",
                "experiment_validity": "INVALID", "detail": list(evidence["invalidations"])}
    if fired_revise:
        return {"disposition": "REVISE", "reason": "REVISE_CLASS_KILL",
                "experiment_validity": "UNRESOLVED", "detail": sorted(fired_revise)}
    unmet = [g for g in REQUIRED_GATES if gates.get(g) is not True]
    unmet += [t for t, ok in thresholds.items() if ok is not True]
    unmet += [f"missing:{t}" for t in missing_threshold_keys]  # fail-closed: absent == unmet
    if unmet:
        return {"disposition": "REVISE", "reason": "THRESHOLD_UNMET",
                "experiment_validity": "UNRESOLVED", "detail": sorted(unmet)}
    return {"disposition": "PROCEED_TO_ADR_CANDIDATES", "reason": "ALL_PREREQUISITES_MET",
            "experiment_validity": "VALID", "detail": []}


def validate_declared(evidence: dict, declared_disposition: str,
                      declared_validity: str | None = None) -> dict:
    derived = derive(evidence)
    ok = derived["disposition"] == declared_disposition and (
        declared_validity is None or derived["experiment_validity"] == declared_validity)
    verdict = "ACCEPT" if ok else derived["reason"]
    return {"derived": derived, "declared_disposition": declared_disposition,
            "declared_validity": declared_validity, "consistent": ok, "verdict": verdict}


def _full(**kw) -> dict:
    base = {"kills": [], "gates": {g: True for g in REQUIRED_GATES},
            "thresholds": {t: True for t in MANDATORY_THRESHOLD_KEYS},
            "invalidations": [], "allowlisted_states": []}
    base.update(kw)
    return base


def selftest() -> list[str]:
    fails: list[str] = []

    def expect(label, ev, disp, reason=None, validity=None):
        r = derive(ev)
        if r["disposition"] != disp or (reason and r["reason"] != reason) \
                or (validity and r["experiment_validity"] != validity):
            fails.append(f"{label}: {r}")

    # 1. STOP precedence: a STOP kill dominates a REVISE kill and unmet gates
    expect("stop-precedence",
           _full(kills=[{"id": "K-AUTHORITY", "fired": True}, {"id": "K-BUDGET", "fired": True}],
                 gates={g: False for g in REQUIRED_GATES}),
           "STOP", "STOP_CLASS_KILL", "VALID")
    # 2. invalidation -> REVISE/EXPERIMENT_INVALID even with clean gates
    expect("invalidation", _full(invalidations=["score invalidated"]),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    # 3. REVISE-class kill
    expect("revise-kill", _full(kills=[{"id": "K-SC02", "fired": True}]),
           "REVISE", "REVISE_CLASS_KILL", "UNRESOLVED")
    # 4. threshold unmet -> REVISE/THRESHOLD_UNMET/UNRESOLVED; allowlist never blocks
    expect("threshold-unmet",
           _full(gates={**{g: True for g in REQUIRED_GATES}, "replay_r2_q02": False},
                 allowlisted_states=["R3=UNRESOLVED", "R4=NOT_TESTED"]),
           "REVISE", "THRESHOLD_UNMET", "UNRESOLVED")
    # 5. FAIL-CLOSED: absent mandatory dual_model_arms_pass must NOT proceed
    expect("missing-dual-model-arms",
           _full(thresholds={}),
           "REVISE", "THRESHOLD_UNMET", "UNRESOLVED")
    # 6. FAIL-CLOSED: missing whole mandatory section
    expect("missing-kills-section",
           {"gates": {g: True for g in REQUIRED_GATES}, "thresholds": {"dual_model_arms_pass": True},
            "invalidations": [], "allowlisted_states": []},
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    # 7. type errors
    expect("type-error-kill-fired",
           _full(kills=[{"id": "K-ZERO", "fired": "yes"}]),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    expect("type-error-threshold",
           _full(thresholds={"dual_model_arms_pass": "true"}),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    expect("type-error-section",
           {"kills": {}, "gates": {}, "thresholds": {}, "invalidations": [], "allowlisted_states": []},
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    # 8. unknown kill id / unknown allowlist state
    expect("unknown-kill", _full(kills=[{"id": "K-MADE-UP", "fired": False}]),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    expect("unknown-state", _full(allowlisted_states=["made_up"]),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    # 9. empty-threshold-but-mandatory-present still needs gates: proceed only when all hold
    expect("empty-optional-thresholds-proceed",
           _full(allowlisted_states=["product/P-GATE=NOT_TESTED/UNCHANGED"]),
           "PROCEED_TO_ADR_CANDIDATES", "ALL_PREREQUISITES_MET", "VALID")
    # 10. full terminal-tuple assertion on the ACTUAL closure evidence
    closure = _full(
        gates={"step3_exit_all_items": False, "replay_r0_three_target": False,
               "replay_r1_q02": False, "replay_r2_q02": False, "mutation_isolation": True,
               "negatives_explicit": True, "compat_no_side_effect": True},
        thresholds={"dual_model_arms_pass": False},
        allowlisted_states=["agent_dimension=NOT_TESTED/UNRESOLVED", "R3=UNRESOLVED",
                            "R4=NOT_TESTED", "evidencegraph_identity=UNRESOLVED"])
    r = derive(closure)
    tup = (r["disposition"], r["reason"], r["experiment_validity"])
    if tup != ("REVISE", "THRESHOLD_UNMET", "UNRESOLVED"):
        fails.append(f"closure-terminal-tuple: {r}")
    vd = validate_declared(closure, "REVISE", "UNRESOLVED")
    if not vd["consistent"] or vd["verdict"] != "ACCEPT":
        fails.append(f"closure-validate_declared: {vd}")
    return fails


if __name__ == "__main__":
    import sys
    f = selftest()
    print("disposition validator fail-closed self-check:",
          "PASS (10 groups)" if not f else "\n".join(f))
    sys.exit(0 if not f else 1)
