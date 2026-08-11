"""DispositionPrecedenceValidatorV0 (blueprint §5.15) + fail-closed self-tests.

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Single precedence semantics (no two-semantics split):
  * A confirmed STOP-class kill dominates EVERYTHING else — invalidation,
    unknown allowlist state, missing/unmet thresholds, malformed OTHER sections,
    and every REVISE condition.
  * The ONLY thing that can make STOP untrustworthy is a malformed `kills`
    inventory itself. `kills` must therefore be a COMPLETE, well-formed census:
    exactly one bool record for every id in KILL_TERMINAL_CLASS, no missing, no
    extra, no duplicate, correct types. A malformed kills census fails closed to
    EXPERIMENT_INVALID (STOP cannot be trusted). This is the natural precondition
    for the blueprint's existing "STOP-first, else malformed -> REVISE" rule, not
    a second semantics — so the blueprint precedence text is unchanged.

experiment_validity axis (separate from disposition):
    VALID       — all prerequisites met (PROCEED) or a kill validly fired (STOP)
    INVALID     — the evidence census is itself malformed/unknown/contradictory
    UNRESOLVED  — the experiment ran validly but eligibility gates/thresholds unmet

Full terminal tuple emitted and compared: disposition, reason,
experiment_validity, architecture_hypothesis, agent_dimension. Zero engine/model.
"""
from __future__ import annotations

KILL_TERMINAL_CLASS = {
    "K-AUTHORITY": "STOP", "K-SEMANTIC": "STOP", "K-ZERO": "STOP", "K-SELECT": "STOP",
    "K-SC01": "STOP", "K-REPLAY": "STOP", "K-COMPAT": "STOP", "K-SCHEMA": "STOP",
    "K-CB0": "STOP", "K-SCOPE": "STOP", "K-DATA": "STOP",
    "K-SC02": "REVISE", "K-THRESHOLD": "REVISE", "K-BUDGET": "REVISE",
}
# kills whose firing falsifies the architecture hypothesis (vs. safety/scope/compat kills)
FALSIFICATION_KILLS = {"K-SEMANTIC", "K-ZERO", "K-SELECT", "K-SC01", "K-SC02"}

REQUIRED_GATES = (
    "step3_exit_all_items", "replay_r0_three_target", "replay_r1_q02", "replay_r2_q02",
    "mutation_isolation", "negatives_explicit", "compat_no_side_effect",
)
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

TERMINAL_KEYS = ("disposition", "reason", "experiment_validity",
                 "architecture_hypothesis", "agent_dimension")


def _tuple(disposition, reason, validity, arch, agent, detail):
    return {"disposition": disposition, "reason": reason, "experiment_validity": validity,
            "architecture_hypothesis": arch, "agent_dimension": agent, "detail": detail}


def _invalid(detail: str) -> dict:
    # A malformed census: STOP is untrustworthy and pins are unknowable.
    return _tuple("REVISE", "EXPERIMENT_INVALID", "INVALID", "UNRESOLVED", "UNRESOLVED", detail)


def _validate_kills_census(evidence: dict) -> tuple[dict | None, list[str], list[str]]:
    """Return (invalid_result_or_None, fired_stop, fired_revise).

    A complete well-formed census is the precondition for trusting STOP.
    """
    if "kills" not in evidence:
        return _invalid("missing mandatory input section 'kills'"), [], []
    kills = evidence["kills"]
    if not isinstance(kills, list):
        return _invalid(f"section 'kills' has wrong type {type(kills).__name__}"), [], []
    ids_seen: list[str] = []
    fired_stop, fired_revise = [], []
    for k in kills:
        if not isinstance(k, dict) or not isinstance(k.get("id"), str) \
                or not isinstance(k.get("fired"), bool):
            return _invalid(f"malformed kill record {k!r}"), [], []
        kid = k["id"]
        if kid not in KILL_TERMINAL_CLASS:
            return _invalid(f"unknown kill id {kid!r}"), [], []
        if kid in ids_seen:
            return _invalid(f"duplicate kill record for {kid}"), [], []
        ids_seen.append(kid)
        if k["fired"]:
            (fired_stop if KILL_TERMINAL_CLASS[kid] == "STOP" else fired_revise).append(kid)
    missing = sorted(set(KILL_TERMINAL_CLASS) - set(ids_seen))
    if missing:
        return _invalid(f"incomplete kills census; missing {missing}"), [], []
    extra = sorted(set(ids_seen) - set(KILL_TERMINAL_CLASS))
    if extra:  # unreachable (unknown-id caught above) but explicit for the census contract
        return _invalid(f"extra kill ids {extra}"), [], []
    return None, fired_stop, fired_revise


def _arch(fired_stop: list[str], fired_revise: list[str]) -> str:
    return "CONTRADICTED" if (set(fired_stop) | set(fired_revise)) & FALSIFICATION_KILLS \
        else "NOT_CONTRADICTED"


def _agent(evidence: dict) -> str:
    return "TESTED" if evidence.get("thresholds", {}).get("dual_model_arms_pass") is True \
        else "NOT_TESTED/UNRESOLVED"


def derive(evidence: dict) -> dict:
    # ---- 1. STOP trustworthiness precondition: a complete well-formed kills census ----
    invalid, fired_stop, fired_revise = _validate_kills_census(evidence)
    if invalid is not None:
        return invalid
    # ---- 2. STOP-class kill dominates everything else (single semantics) --------------
    if fired_stop:
        return _tuple("STOP", "STOP_CLASS_KILL", "VALID",
                      _arch(fired_stop, fired_revise), _agent(evidence), sorted(fired_stop))
    # ---- 3. validate the remaining sections (STOP already excluded) -------------------
    for section in MANDATORY_INPUT_SECTIONS:
        if section == "kills":
            continue
        if section not in evidence:
            return _invalid(f"missing mandatory input section {section!r}")
        if not isinstance(evidence[section], _SECTION_TYPES[section]):
            return _invalid(f"section {section!r} has wrong type "
                            f"{type(evidence[section]).__name__}")
    for tk, tv in evidence["thresholds"].items():
        if not isinstance(tv, bool):
            return _invalid(f"threshold {tk!r} value is not bool: {tv!r}")
    for g, gv in evidence["gates"].items():
        if gv is not None and not isinstance(gv, bool):
            return _invalid(f"gate {g!r} value is not bool/None: {gv!r}")
    for state in evidence["allowlisted_states"]:
        if state not in NON_BLOCKING_ALLOWLIST:
            return _invalid(f"state {state!r} not in pre-registered allowlist")
    gates = evidence["gates"]
    for g in REQUIRED_GATES:
        if g not in gates:
            return _invalid(f"missing mandatory gate input {g!r}")
    # ---- 4. REVISE precedence --------------------------------------------------------
    if evidence["invalidations"]:
        return _tuple("REVISE", "EXPERIMENT_INVALID", "INVALID", "NOT_CONTRADICTED",
                      _agent(evidence), list(evidence["invalidations"]))
    if fired_revise:
        return _tuple("REVISE", "REVISE_CLASS_KILL", "UNRESOLVED",
                      _arch(fired_stop, fired_revise), _agent(evidence), sorted(fired_revise))
    thresholds = evidence["thresholds"]
    unmet = [g for g in REQUIRED_GATES if gates.get(g) is not True]
    unmet += [t for t, ok in thresholds.items() if ok is not True]
    unmet += [f"missing:{t}" for t in MANDATORY_THRESHOLD_KEYS if t not in thresholds]
    if unmet:
        return _tuple("REVISE", "THRESHOLD_UNMET", "UNRESOLVED", "NOT_CONTRADICTED",
                      _agent(evidence), sorted(unmet))
    return _tuple("PROCEED_TO_ADR_CANDIDATES", "ALL_PREREQUISITES_MET", "VALID",
                  "NOT_CONTRADICTED", _agent(evidence), [])


def validate_declared(evidence: dict, declared: dict) -> dict:
    """Compare the COMPLETE terminal tuple: disposition, reason, experiment_validity,
    architecture_hypothesis, agent_dimension."""
    derived = derive(evidence)
    mismatches = {k: {"declared": declared.get(k), "derived": derived[k]}
                  for k in TERMINAL_KEYS if k in declared and declared[k] != derived[k]}
    ok = not mismatches
    return {"derived": {k: derived[k] for k in TERMINAL_KEYS},
            "declared": declared, "consistent": ok,
            "verdict": "ACCEPT" if ok else derived["reason"], "mismatches": mismatches}


def full_kill_census(fired: dict[str, bool] | None = None) -> list[dict]:
    fired = fired or {}
    return [{"id": kid, "fired": bool(fired.get(kid, False))} for kid in KILL_TERMINAL_CLASS]


def _full(**kw) -> dict:
    base = {"kills": full_kill_census(), "gates": {g: True for g in REQUIRED_GATES},
            "thresholds": {t: True for t in MANDATORY_THRESHOLD_KEYS},
            "invalidations": [], "allowlisted_states": []}
    base.update(kw)
    return base


CLOSURE_TERMINAL = {
    "disposition": "REVISE", "reason": "THRESHOLD_UNMET", "experiment_validity": "UNRESOLVED",
    "architecture_hypothesis": "NOT_CONTRADICTED", "agent_dimension": "NOT_TESTED/UNRESOLVED",
}


def closure_evidence() -> dict:
    return _full(
        gates={"step3_exit_all_items": False, "replay_r0_three_target": False,
               "replay_r1_q02": False, "replay_r2_q02": False, "mutation_isolation": True,
               "negatives_explicit": True, "compat_no_side_effect": True},
        thresholds={"dual_model_arms_pass": False},
        allowlisted_states=["agent_dimension=NOT_TESTED/UNRESOLVED", "R3=UNRESOLVED",
                            "R4=NOT_TESTED", "evidencegraph_identity=UNRESOLVED"])


def selftest() -> tuple[list[str], list[str]]:
    fails: list[str] = []
    counterexamples: list[str] = []

    def expect(label, ev, disp, reason=None, validity=None, arch=None, agent=None):
        r = derive(ev)
        bad = (r["disposition"] != disp
               or (reason and r["reason"] != reason)
               or (validity and r["experiment_validity"] != validity)
               or (arch and r["architecture_hypothesis"] != arch)
               or (agent and r["agent_dimension"] != agent))
        counterexamples.append(f"{label}: {r['disposition']}/{r['reason']}/"
                               f"{r['experiment_validity']}/{r['architecture_hypothesis']}/"
                               f"{r['agent_dimension']} :: {r['detail']}")
        if bad:
            fails.append(f"{label}: got {r}")

    # STOP precedence over invalidation + unknown state + missing threshold + malformed others
    expect("stop>all", _full(
        kills=full_kill_census({"K-AUTHORITY": True}),
        gates={g: False for g in REQUIRED_GATES}, thresholds={},
        invalidations=["score invalidated"], allowlisted_states=["made_up_state"]),
        "STOP", "STOP_CLASS_KILL", "VALID", "NOT_CONTRADICTED")
    # falsification-class STOP kill -> architecture CONTRADICTED
    expect("stop-falsifies", _full(kills=full_kill_census({"K-SEMANTIC": True})),
           "STOP", "STOP_CLASS_KILL", "VALID", "CONTRADICTED")
    # invalidation (no kill) -> REVISE/EXPERIMENT_INVALID
    expect("invalidation", _full(invalidations=["x"]),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    # REVISE-class kill
    expect("revise-kill", _full(kills=full_kill_census({"K-SC02": True})),
           "REVISE", "REVISE_CLASS_KILL", "UNRESOLVED", "CONTRADICTED")
    # threshold unmet (a gate other than the model arm; dual arm still passed -> agent TESTED)
    expect("threshold-unmet",
           _full(gates={**{g: True for g in REQUIRED_GATES}, "replay_r2_q02": False},
                 allowlisted_states=["R3=UNRESOLVED"]),
           "REVISE", "THRESHOLD_UNMET", "UNRESOLVED", "NOT_CONTRADICTED", "TESTED")
    # fail-closed: missing mandatory dual_model_arms_pass
    expect("missing-dual-arms", _full(thresholds={}),
           "REVISE", "THRESHOLD_UNMET", "UNRESOLVED")
    # census completeness: empty kill inventory -> INVALID (regression #1)
    expect("empty-kill-census", _full(kills=[]),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    # census: missing one id / extra id / duplicate -> INVALID
    expect("kills-missing-one", _full(kills=full_kill_census()[:-1]),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    expect("kills-extra-id", _full(kills=full_kill_census() + [{"id": "K-BOGUS", "fired": False}]),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    dup = full_kill_census() + [{"id": "K-ZERO", "fired": False}]
    expect("kills-duplicate", _full(kills=dup),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    # STOP + unknown allowlist state -> STOP dominates (regression #2)
    expect("stop+unknown-state",
           _full(kills=full_kill_census({"K-COMPAT": True}), allowlisted_states=["totally_bogus"]),
           "STOP", "STOP_CLASS_KILL", "VALID", "NOT_CONTRADICTED")
    # type errors
    expect("type-error-fired", _full(kills=[{"id": kid, "fired": ("yes" if kid == "K-ZERO" else False)}
                                            for kid in KILL_TERMINAL_CLASS]),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    expect("type-error-threshold", _full(thresholds={"dual_model_arms_pass": "true"}),
           "REVISE", "EXPERIMENT_INVALID", "INVALID")
    # PROCEED only when all hold
    expect("proceed", _full(allowlisted_states=["product/P-GATE=NOT_TESTED/UNCHANGED"]),
           "PROCEED_TO_ADR_CANDIDATES", "ALL_PREREQUISITES_MET", "VALID",
           "NOT_CONTRADICTED", "TESTED")
    # full closure terminal tuple
    r = derive(closure_evidence())
    counterexamples.append("CLOSURE: " + "/".join(str(r[k]) for k in TERMINAL_KEYS))
    if {k: r[k] for k in TERMINAL_KEYS} != CLOSURE_TERMINAL:
        fails.append(f"closure-terminal-tuple: {r}")

    # validate_declared full-tuple checks
    vd = validate_declared(closure_evidence(), CLOSURE_TERMINAL)
    if not vd["consistent"]:
        fails.append(f"closure-validate_declared: {vd}")
    # regression #3: declared reason/status pin errors are rejected
    wrong_reason = {**CLOSURE_TERMINAL, "reason": "EXPERIMENT_INVALID"}
    if validate_declared(closure_evidence(), wrong_reason)["consistent"]:
        fails.append("declared-wrong-reason accepted")
    wrong_validity = {**CLOSURE_TERMINAL, "experiment_validity": "VALID"}
    if validate_declared(closure_evidence(), wrong_validity)["consistent"]:
        fails.append("declared-wrong-validity accepted")
    wrong_arch = {**CLOSURE_TERMINAL, "architecture_hypothesis": "CONTRADICTED"}
    if validate_declared(closure_evidence(), wrong_arch)["consistent"]:
        fails.append("declared-wrong-arch accepted")
    return fails, counterexamples


if __name__ == "__main__":
    import sys
    fails, examples = selftest()
    print("counterexample outputs (disposition/reason/validity/arch/agent :: detail):")
    for e in examples:
        print("  " + e)
    print("\ndisposition validator fail-closed self-check:",
          "PASS" if not fails else "FAIL\n  " + "\n  ".join(fails))
    sys.exit(0 if not fails else 1)
