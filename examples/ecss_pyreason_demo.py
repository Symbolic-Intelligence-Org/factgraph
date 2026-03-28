#!/usr/bin/env python3
"""ECSS + PyReason Demo: Fuzzy Disposal Probability with Temporal Refinement.

Extends the ECSS compliance scenario with PyReason's interval semantics:
- Disposal probability expressed as fuzzy bound [lo, hi] instead of point value
- Temporal refinement: bounds tighten across mission phases (timesteps)
- Compliance status derived from bound propagation, not hard threshold

Uses adapter-local session + runner (not Store.evaluate) for clarity.
Gracefully exits if pyreason is not available.

Compare with: examples/esa_demo.py (Souffle-based, hard thresholds)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factpy_kernel.sdk import Entity, Identity, Field, Relationship
from factpy_kernel.sdk.compile import compile_schema_from_classes
from factpy_kernel.adapters.pyreason.session import PyReasonSession
from factpy_kernel.adapters.pyreason.accept import accept_pyreason_session
from factpy_kernel.adapters.pyreason.rule_ext import (
    PyReasonFactDef,
    PyReasonRuleDef,
    PyReasonRuleExt,
)
from factpy_kernel.adapters.pyreason.runner import PyReasonRunConfig, run_pyreason
from factpy_kernel.sdk.dsl.expr import LogicVar, Pred
from factpy_kernel.sdk.dsl.rule import Rule
from factpy_kernel.core.store.ledger import Ledger

start = time.time()


# ════════════════════════════════════════════════════════════════
# 1. Schema: ECSS Mission with Fuzzy Estimates
# ════════════════════════════════════════════════════════════════

class Mission(Entity):
    mission_id: str = Identity(primary_key=True)
    disposal_estimate: str = Field(cardinality="single")
    passivation_ok: str = Field(cardinality="single")
    compliant: str = Field(cardinality="single")
    high_confidence: str = Field(cardinality="single")


class MissionPhase(Relationship):
    """Temporal link: mission evolves through phases."""
    from_entity = Mission
    to_entity = Mission
    phase_link: str = Field(cardinality="single")


schema_ir = compile_schema_from_classes([Mission, MissionPhase])
print(f"[{time.time()-start:.1f}s] Schema: {len(schema_ir['predicates'])} predicates")


# ════════════════════════════════════════════════════════════════
# 2. Session: Write Facts with Fuzzy Bounds
# ════════════════════════════════════════════════════════════════

session = PyReasonSession(schema_ir)

with session.batch() as tx:
    sentinel = tx.entity(Mission, mission_id="SENTINEL7")

    # Disposal probability: initial fuzzy estimate [85%, 95%]
    # (uncertainty in orbital decay models)
    sentinel.disposal_estimate.set("true", bound=[0.85, 0.95],
        meta={"source": "ESA_orbital_model_v3", "analyst": "Mission Control"})

    # Passivation: definitely complete
    sentinel.passivation_ok.set("true", bound=[1.0, 1.0],
        meta={"source": "telemetry_confirmed"})

    # Another mission with lower confidence
    debris_x = tx.entity(Mission, mission_id="DEBRIS_X")
    debris_x.disposal_estimate.set("true", bound=[0.60, 0.75],
        meta={"source": "legacy_model", "analyst": "External Review"})
    debris_x.passivation_ok.set("true", bound=[0.7, 0.8],
        meta={"source": "partial_telemetry"})

    # Phase link: SENTINEL7 refines DEBRIS_X estimates
    tx.relationship(MissionPhase, from_entity=sentinel, to_entity=debris_x,
                    phase_link="0.9", bound=[0.9, 0.9])

    tx.commit()

print(f"[{time.time()-start:.1f}s] Facts written:")
print(f"  SENTINEL7 disposal: bound=[0.85, 0.95] (high initial confidence)")
print(f"  DEBRIS_X disposal:  bound=[0.60, 0.75] (low initial confidence)")
print(f"  Annotation templates: {len(session.annotation_templates)}")


# ════════════════════════════════════════════════════════════════
# 3. PyReason Rules: Compliance via Bound Propagation
# ════════════════════════════════════════════════════════════════

x = LogicVar("x")
y = LogicVar("y")

rules = [
    # Rule 1: If disposal estimate has high bounds → mission is compliant
    # (PyReason propagates the bound interval, not a boolean)
    PyReasonRuleDef(
        rule=Rule(
            id="disposal_compliance",
            version="1.0",
            select=[Pred("mission:compliant", x)],
            where=[
                Pred("mission:disposal_estimate", x),
                Pred("mission:passivation_ok", x),
            ],
        ),
        ext=PyReasonRuleExt(timestep_delay=0),
    ),
    # Rule 2: Phase-linked missions propagate confidence (with delay)
    # If mission A is compliant, linked mission B gains confidence
    PyReasonRuleDef(
        rule=Rule(
            id="phase_confidence_propagation",
            version="1.0",
            select=[Pred("mission:high_confidence", y)],
            where=[
                Pred("mission:compliant", x),
                Pred("mission_phase:phase_link", x, y),
            ],
        ),
        ext=PyReasonRuleExt(timestep_delay=1),
    ),
]

initial_facts = [
    PyReasonFactDef(
        atom="disposal_estimate(SENTINEL7)",
        name="sentinel7_disposal",
        start=0, end=3,
        bound=[0.85, 0.95],
    ),
    PyReasonFactDef(
        atom="passivation_ok(SENTINEL7)",
        name="sentinel7_passivation",
        start=0, end=3,
        bound=[1.0, 1.0],
    ),
    PyReasonFactDef(
        atom="disposal_estimate(DEBRIS_X)",
        name="debrisx_disposal",
        start=0, end=3,
        bound=[0.60, 0.75],
    ),
    PyReasonFactDef(
        atom="passivation_ok(DEBRIS_X)",
        name="debrisx_passivation",
        start=0, end=3,
        bound=[0.70, 0.80],
    ),
]

print(f"\n[{time.time()-start:.1f}s] Rules defined:")
print("  1. disposal_compliance: disposal_estimate + passivation_ok → compliant")
print("  2. phase_confidence_propagation: compliant(A) + phase_link(A,B) → high_confidence(B) [delay=1]")


# ════════════════════════════════════════════════════════════════
# 4. Run PyReason (requires pyreason==3.0.0)
# ════════════════════════════════════════════════════════════════

try:
    result = run_pyreason(
        session,
        rule_defs=rules,
        fact_defs=initial_facts,
        config=PyReasonRunConfig(timesteps=3, atom_trace=True),
    )
except Exception as exc:
    print(f"\n[NOTE] PyReason execution failed: {exc}")
    print("This is expected if pyreason is not installed or has numba issues.")
    print("\nWhat this demo would show with a working PyReason installation:")
    print("  - SENTINEL7 becomes compliant at t=0 with bound [0.85, 0.95]")
    print("    (interval propagation: disposal [0.85,0.95] AND passivation [1.0,1.0])")
    print("  - DEBRIS_X gains high_confidence at t=1 via phase link propagation")
    print("    (confidence flows through the mission phase relationship)")
    print("  - The bound width tells you HOW CONFIDENT the compliance assessment is:")
    print("    SENTINEL7: width=0.10 (fairly confident)")
    print("    DEBRIS_X:  width=0.15 (less confident, needs more data)")
    print("  - Traditional ECSS (esa_demo.py) can only say 'compliant/non_compliant'")
    print("    PyReason says 'compliant with confidence interval [0.85, 0.95]'")
    sys.exit(0)


# ════════════════════════════════════════════════════════════════
# 5. Results: Interpretation per Timestep
# ════════════════════════════════════════════════════════════════

derived = result.derived_session
interp = result.interpretation.get_dict()

print(f"\n[{time.time()-start:.1f}s] Reasoning complete ({result.elapsed_seconds:.1f}s)")
print(f"  Derived facts: {len(derived.node_facts)} node, {len(derived.edge_facts)} edge")

print(f"\n{'='*60}")
print("COMPLIANCE STATE EVOLUTION (PyReason interval semantics)")
print(f"{'='*60}")

for t in sorted(interp.keys()):
    print(f"\n  Timestep {t}:")
    for component, preds in interp[t].items():
        for pred_name, (lo, hi) in preds.items():
            if lo == 0.0 and hi == 0.0:
                continue
            width = hi - lo
            confidence_label = "HIGH" if width < 0.15 else "MEDIUM" if width < 0.30 else "LOW"
            print(f"    {component}.{pred_name} = [{lo:.2f}, {hi:.2f}] (width={width:.2f}, {confidence_label} confidence)")


# ════════════════════════════════════════════════════════════════
# 6. Accept + Annotations
# ════════════════════════════════════════════════════════════════

ledger = Ledger()
accept_result = accept_pyreason_session(ledger, derived)
print(f"\n[{time.time()-start:.1f}s] Accepted: {len(accept_result.node_asrt_ids)} assertions, {accept_result.annotation_count} annotations")


# ════════════════════════════════════════════════════════════════
# 7. Summary
# ════════════════════════════════════════════════════════════════

print(f"\n{'='*60}")
print("ECSS + PYREASON VALUE PROPOSITION")
print(f"{'='*60}")
print("  Traditional ECSS (esa_demo.py):")
print("    disposal_prob >= 900000 PPM → 'compliant' (binary)")
print("    confidence = fixed input metadata, not derived")
print()
print("  PyReason ECSS (this demo):")
print("    disposal_estimate ∈ [0.85, 0.95] → 'compliant' with bound propagation")
print("    confidence = EMERGENT from interval width (narrow = confident)")
print("    temporal refinement: bounds tighten across mission phases")
print("    audit trail shows WHEN and WHY confidence changed")
print(f"{'='*60}")
