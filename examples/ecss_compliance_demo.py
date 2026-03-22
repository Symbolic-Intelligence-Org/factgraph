"""
ECSS Compliance Demo: ESSB-ST-U-007 Space Debris Mitigation

End-to-end verification that factpy can encode and audit ECSS compliance rules.
Uses existing SDK/Service API — no core code changes.

Scenario: A LEO mission "SENTINEL-7" with:
  - Disposal success probability: 92% (threshold: 90%)
  - Collision probability: 0.0005 (threshold: 0.001)
  - Passivation: all energy sources depleted

Expected result: all checks pass → mission is compliant.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from pprint import pprint

# Ensure src/ is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factpy_kernel.sdk import (
    SDKStore,
    Entity,
    Identity,
    Field,
    Rule,
    Pred,
    vars as sdk_vars,
)
from factpy_kernel.authoring import FileAuthoringRegistry
from factpy_kernel.domains.ecss import (
    extend_schema_ir_with_ecss_uncertainty_predicates,
    extend_schema_ir_with_ecss_vcd_predicates,
    ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
    ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
    ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
    ECSS_COMPLIANCE_STATUS_PRED_ID,
    ECSS_REQUIREMENT_PRED_ID,
    ECSS_VERIFICATION_METHOD_PRED_ID,
)
from factpy_kernel.service.runtime_v1 import (
    open_runtime_session,
    close_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
    evaluate_runtime_derivation,
    explain_runtime_summary,
    explain_runtime_narrative,
    explain_runtime_nl,
    export_runtime_package,
    accept_runtime_derivation,
)
from factpy_kernel.audit import AuditQuery, load_audit_package

# ──────────────────────────────────────────────────────────────
# 1. Schema: Mission entity with ECSS predicates
# ──────────────────────────────────────────────────────────────

class Mission(Entity):
    mission_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")
    orbit_type: str = Field(cardinality="single")
    passivation_status: str = Field(cardinality="single")

sdk = SDKStore([Mission])

# Extend schema with ECSS uncertainty predicates (disposal/collision probability)
schema_ir = extend_schema_ir_with_ecss_uncertainty_predicates(sdk.schema_ir)
schema_ir = extend_schema_ir_with_ecss_vcd_predicates(schema_ir)
sdk = SDKStore([Mission], schema_ir=schema_ir)

print("=== Schema ready ===")
ecss_preds = [p["pred_id"] for p in sdk.schema_ir["predicates"] if p["pred_id"].startswith("ecss:")]
print(f"  ECSS predicates registered: {ecss_preds}")

# ──────────────────────────────────────────────────────────────
# 2. Rules: ESSB-ST-U-007 compliance checks
# ──────────────────────────────────────────────────────────────

# Rule 1: Disposal probability check
# "disposal success probability >= threshold"
with sdk_vars("m", "prob", "threshold") as (m, prob, threshold):
    disposal_check_rule = Rule(
        id="q.essb_u007_disposal_check",
        version="1.0.0",
        select=[m, prob],
        where=[
            Pred(ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID, m, prob),
            Pred(ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID, m, threshold),
            prob >= threshold,
        ],
        expose=True,
        condition_weights={
            "b0.a0": 0.8,   # disposal probability importance
            "b0.a1": 0.5,   # threshold importance
        },
    )

# Rule 2: Collision probability check
# "collision probability <= threshold"
with sdk_vars("m", "prob", "threshold") as (m, prob, threshold):
    collision_check_rule = Rule(
        id="q.essb_u007_collision_check",
        version="1.0.0",
        select=[m, prob],
        where=[
            Pred(ECSS_COLLISION_PROBABILITY_PPM_PRED_ID, m, prob),
            Pred(ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID, m, threshold),
            threshold >= prob,  # collision prob must be BELOW threshold
        ],
        expose=True,
        condition_weights={
            "b0.a0": 0.9,   # collision probability importance
            "b0.a1": 0.4,   # threshold importance
        },
    )

print("\n=== Rules defined ===")
print(f"  {disposal_check_rule.id}: disposal success probability >= threshold")
print(f"  {collision_check_rule.id}: collision probability <= threshold")

# ──────────────────────────────────────────────────────────────
# 3. Registry: register rules
# ──────────────────────────────────────────────────────────────

registry_dir = tempfile.mkdtemp(prefix="ecss_demo_")
registry = FileAuthoringRegistry(Path(registry_dir))
registry.upsert_schema_ir(sdk.schema_ir)
registry.register_rule_spec(sdk._compile_rule_input(disposal_check_rule))
registry.register_rule_spec(sdk._compile_rule_input(collision_check_rule))

print(f"\n=== Registry ready: {registry_dir} ===")

# ──────────────────────────────────────────────────────────────
# 4. Data: SENTINEL-7 mission facts
# ──────────────────────────────────────────────────────────────

with sdk.batch() as tx:
    s7 = tx.entity(Mission, mission_id="SENTINEL-7", locale="en")
    s7.name.set("Sentinel-7 LEO Observatory")
    s7.orbit_type.set("LEO")
    s7.passivation_status.set("complete")
    tx.commit()

mission_ref = sdk.ref(Mission, mission_id="SENTINEL-7", locale="en")

print(f"\n=== Mission entity created: {mission_ref} ===")

# ──────────────────────────────────────────────────────────────
# 5. Runtime: write facts + evaluate
# ──────────────────────────────────────────────────────────────

reset_runtime_sessions_for_tests()
session_resp = open_runtime_session({"registry_root": registry_dir})
session_id = session_resp["session"]["session_id"]

# Write ECSS uncertainty facts
# Disposal success probability: 92% = 920000 ppm
write_runtime_fact(session_id, {
    "pred_id": ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
    "e_ref": mission_ref,
    "rest_terms": [["int", 920000]],
    "meta": {"confidence": 0.85},  # confidence in the probability estimate
}, kind="add")

# Disposal threshold: 90% = 900000 ppm
write_runtime_fact(session_id, {
    "pred_id": ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
    "e_ref": mission_ref,
    "rest_terms": [["int", 900000]],
}, kind="add")

# Collision probability: 0.05% = 500 ppm
write_runtime_fact(session_id, {
    "pred_id": ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
    "e_ref": mission_ref,
    "rest_terms": [["int", 500]],
    "meta": {"confidence": 0.7},  # lower confidence in collision estimate
}, kind="add")

# Collision threshold: 0.1% = 1000 ppm
write_runtime_fact(session_id, {
    "pred_id": ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
    "e_ref": mission_ref,
    "rest_terms": [["int", 1000]],
}, kind="add")

print(f"\n=== Facts written ===")
print(f"  Disposal probability: 920000 ppm (92%), confidence=0.85")
print(f"  Disposal threshold:   900000 ppm (90%)")
print(f"  Collision probability: 500 ppm (0.05%), confidence=0.70")
print(f"  Collision threshold:   1000 ppm (0.1%)")

# ──────────────────────────────────────────────────────────────
# 6. Evaluate: disposal check
# ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("EVALUATING: Disposal Success Probability Check")
print("=" * 60)

eval_disposal = evaluate_runtime_derivation(session_id, {
    "derivation": {
        "derivation_id": "drv.disposal_check",
        "version": "1.0.0",
        "target": ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
        "head_vars": ["$m", "$prob"],
        "where": [
            ["ruleref", "q.essb_u007_disposal_check", "1.0.0", ["$m", "$prob"]],
        ],
        "mode": "native",
    }
})

if eval_disposal["ok"] and eval_disposal["evaluation"]["candidates"]:
    disposal_cand = eval_disposal["evaluation"]["candidates"][0]
    disposal_cid = disposal_cand["candidate_id"]
    print(f"  ✅ Disposal check PASSED")
    print(f"  candidate_id: {disposal_cid}")
    print(f"  confidence_kind: {disposal_cand['confidence_kind']}")

    # Explain
    summary = explain_runtime_summary(session_id, {"kind": "candidate", "id": disposal_cid})
    if summary["ok"]:
        print(f"\n  --- Evidence Tree Summary ---")
        s = summary["summary"]
        print(f"  support_kind: {s.get('support_kind')}")
        print(f"  witness_assertion_count: {s.get('witness_assertion_count')}")
        print(f"  rule_ref_count: {s.get('rule_ref_count')}")
        cs = summary.get("certainty_summary")
        if cs:
            print(f"\n  --- Certainty Summary ---")
            print(f"  aggregate_certainty: {cs['aggregate_certainty']}")
            print(f"  aggregation: {cs['aggregation']}")
            for c in cs["conditions"]:
                print(f"    {c['atom_key']}: weight={c['weight']}, impact={c['impact']}")

    narrative = explain_runtime_narrative(session_id, {"kind": "candidate", "id": disposal_cid})
    if narrative["ok"]:
        narr = narrative["narrative"]
        print(f"\n  --- Narrative ---")
        for key in ["headline", "overview_lines", "evidence_lines", "rule_chain_lines", "certainty_lines"]:
            val = narr.get(key)
            if val:
                if isinstance(val, list):
                    for line in val:
                        print(f"  [{key}] {line}")
                else:
                    print(f"  [{key}] {val}")
else:
    print(f"  ❌ Disposal check FAILED or no candidates")
    print(f"  Response: {eval_disposal}")

# ──────────────────────────────────────────────────────────────
# 7. Evaluate: collision check
# ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("EVALUATING: Collision Probability Check")
print("=" * 60)

eval_collision = evaluate_runtime_derivation(session_id, {
    "derivation": {
        "derivation_id": "drv.collision_check",
        "version": "1.0.0",
        "target": ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
        "head_vars": ["$m", "$prob"],
        "where": [
            ["ruleref", "q.essb_u007_collision_check", "1.0.0", ["$m", "$prob"]],
        ],
        "mode": "native",
    }
})

if eval_collision["ok"] and eval_collision["evaluation"]["candidates"]:
    collision_cand = eval_collision["evaluation"]["candidates"][0]
    collision_cid = collision_cand["candidate_id"]
    print(f"  ✅ Collision check PASSED")
    print(f"  candidate_id: {collision_cid}")
    print(f"  confidence_kind: {collision_cand['confidence_kind']}")

    summary = explain_runtime_summary(session_id, {"kind": "candidate", "id": collision_cid})
    if summary["ok"]:
        cs = summary.get("certainty_summary")
        if cs:
            print(f"\n  --- Certainty Summary ---")
            print(f"  aggregate_certainty: {cs['aggregate_certainty']}")
            for c in cs["conditions"]:
                print(f"    {c['atom_key']}: weight={c['weight']}, impact={c['impact']}")

    nl = explain_runtime_nl(session_id, {"kind": "candidate", "id": collision_cid})
    if nl["ok"]:
        print(f"\n  --- NL Explanation ---")
        for i, p in enumerate(nl["explain_nl"]["paragraphs"], 1):
            print(f"  [{i}] {p[:150]}...")
else:
    print(f"  ❌ Collision check FAILED or no candidates")
    print(f"  Response: {eval_collision}")

# ──────────────────────────────────────────────────────────────
# 8. Audit: export + round-trip
# ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("AUDIT ROUND-TRIP")
print("=" * 60)

# Accept candidates
if eval_disposal["ok"] and eval_disposal["evaluation"]["candidates"]:
    accept_runtime_derivation(session_id, {"candidates": eval_disposal["evaluation"]["candidates"]})
if eval_collision["ok"] and eval_collision["evaluation"]["candidates"]:
    accept_runtime_derivation(session_id, {"candidates": eval_collision["evaluation"]["candidates"]})

# Export audit package
audit_dir = tempfile.mkdtemp(prefix="ecss_audit_")
export_resp = export_runtime_package(session_id, {
    "out_dir": audit_dir,
    "package_kind": "audit",
})
print(f"  Export: ok={export_resp['ok']}")

# Load and query
pkg = load_audit_package(audit_dir)
aq = AuditQuery(pkg)

candidates = aq.list_candidates()
print(f"  Audit candidates: {len(candidates)}")

for cand_row in candidates:
    cid = cand_row["candidate_id"]
    cs = aq.get_candidate_certainty_summary(cid)
    if cs:
        print(f"  {cid[:40]}... certainty={cs['aggregate_certainty']}")

# ──────────────────────────────────────────────────────────────
# 9. Static site
# ──────────────────────────────────────────────────────────────

from factpy_kernel.audit.static_ui import render_audit_static_site

site_dir = tempfile.mkdtemp(prefix="ecss_site_")
render_audit_static_site(audit_dir, site_dir)

site_files = sorted(Path(site_dir).rglob("*.html"))
print(f"\n  Static site: {len(site_files)} pages at {site_dir}")
for f in site_files[:10]:
    print(f"    {f.relative_to(site_dir)}")

# ──────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────

close_runtime_session(session_id)
reset_runtime_sessions_for_tests()

print("\n" + "=" * 60)
print("ECSS COMPLIANCE DEMO COMPLETE")
print("=" * 60)
print(f"\nStatic audit site: {site_dir}")
print("Open candidate_evidence/*.html in a browser to see the evidence tree.")
