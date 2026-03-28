#!/usr/bin/env python3
"""ECSS + PyReason Demo: Boolean Mission Watch Propagation.

This demo shows the PyReason pattern that real-engine validation supports:

- boolean mission labels propagate across topology and timesteps
- uncertainty bands stay outside the PyReason rule engine as side-channel context
- the audit path still captures when a propagated label first appears

Uses adapter-local session + runner (not Store.evaluate) for clarity.
Gracefully exits if pyreason is not available.

Compare with: examples/esa_demo.py (Souffle-based, hard thresholds)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factpy_kernel.adapters.pyreason.accept import accept_pyreason_session
from factpy_kernel.adapters.pyreason.rule_ext import PyReasonRuleDef, PyReasonRuleExt
from factpy_kernel.adapters.pyreason.runner import PyReasonRunConfig, run_pyreason
from factpy_kernel.adapters.pyreason.session import PyReasonSession
from factpy_kernel.core.store.ledger import Ledger
from factpy_kernel.sdk import Entity, Field, Identity, Relationship
from factpy_kernel.sdk.compile import compile_schema_from_classes
from factpy_kernel.sdk.dsl.expr import LogicVar, Pred
from factpy_kernel.sdk.dsl.rule import Rule

start = time.time()


# ════════════════════════════════════════════════════════════════
# 1. Schema: ECSS Mission Watch Labels
# ════════════════════════════════════════════════════════════════


class Mission(Entity):
    mission_id: str = Identity(primary_key=True)
    disposal_watch: str = Field(cardinality="single")
    passivation_watch: str = Field(cardinality="single")


class MissionPhase(Relationship):
    """Mission-to-mission propagation path."""

    from_entity = Mission
    to_entity = Mission
    phase_link: str = Field(cardinality="single")


schema_ir = compile_schema_from_classes([Mission, MissionPhase])
print(f"[{time.time()-start:.1f}s] Schema: {len(schema_ir['predicates'])} predicates")


# ════════════════════════════════════════════════════════════════
# 2. Session: Boolean Seeds + Side-Channel Uncertainty
# ════════════════════════════════════════════════════════════════

session = PyReasonSession(schema_ir)

uncertainty_observations = {
    "SENTINEL7": {
        "disposal_estimate_band": [0.85, 0.95],
        "passivation_readiness_band": [1.0, 1.0],
    },
    "DEBRIS_X": {
        "disposal_estimate_band": [0.60, 0.75],
        "passivation_readiness_band": [0.70, 0.80],
    },
}

with session.batch() as tx:
    sentinel = tx.entity(Mission, mission_id="SENTINEL7")
    debris_x = tx.entity(Mission, mission_id="DEBRIS_X")

    sentinel.disposal_watch.set(
        "true",
        bound=[1.0, 1.0],
        meta={"source": "ESA_orbital_model_v3", "mode": "boolean_seed"},
    )
    sentinel.passivation_watch.set(
        "true",
        bound=[1.0, 1.0],
        meta={"source": "telemetry_confirmed", "mode": "boolean_seed"},
    )

    tx.relationship(
        MissionPhase,
        from_entity=sentinel,
        to_entity=debris_x,
        phase_link="true",
        bound=[1.0, 1.0],
        meta={"source": "phase_review_chain"},
    )

    tx.commit()

print(f"[{time.time()-start:.1f}s] Boolean seeds written:")
print("  SENTINEL7 disposal_watch=true")
print("  SENTINEL7 passivation_watch=true")
print("  phase_link(SENTINEL7 -> DEBRIS_X)=true")
print("  Annotation templates:", len(session.annotation_templates))
print("\n  Side-channel uncertainty observations (NOT fed into PyReason seeds):")
for mission_id, observations in uncertainty_observations.items():
    print(
        "   ",
        mission_id,
        f"disposal={observations['disposal_estimate_band']}",
        f"passivation={observations['passivation_readiness_band']}",
    )


# ════════════════════════════════════════════════════════════════
# 3. Rules: Boolean Label Propagation
# ════════════════════════════════════════════════════════════════

x = LogicVar("x")
y = LogicVar("y")

rules = [
    PyReasonRuleDef(
        rule=Rule(
            id="disposal_watch_propagation",
            version="1.0",
            select=[Pred("mission:disposal_watch", x)],
            where=[
                Pred("mission:disposal_watch", y),
                Pred("mission_phase:phase_link", y, x),
            ],
        ),
        ext=PyReasonRuleExt(timestep_delay=1),
    ),
    PyReasonRuleDef(
        rule=Rule(
            id="passivation_watch_propagation",
            version="1.0",
            select=[Pred("mission:passivation_watch", x)],
            where=[
                Pred("mission:passivation_watch", y),
                Pred("mission_phase:phase_link", y, x),
            ],
        ),
        ext=PyReasonRuleExt(timestep_delay=1),
    ),
]

print(f"\n[{time.time()-start:.1f}s] Rules defined:")
print("  1. disposal_watch(Y) + phase_link(Y,X) -> disposal_watch(X) [delay=1]")
print("  2. passivation_watch(Y) + phase_link(Y,X) -> passivation_watch(X) [delay=1]")


# ════════════════════════════════════════════════════════════════
# 4. Run PyReason
# ════════════════════════════════════════════════════════════════

try:
    result = run_pyreason(
        session,
        rule_defs=rules,
        config=PyReasonRunConfig(timesteps=3, atom_trace=True),
    )
except Exception as exc:
    print(f"\n[NOTE] PyReason execution failed: {exc}")
    print("This is expected if pyreason is not installed or has numba issues.")
    print("\nWhat this demo shows on a working PyReason installation:")
    print("  - boolean disposal/passivation watch labels propagate from SENTINEL7 to DEBRIS_X")
    print("  - the propagation is temporal/topological, not fuzzy payload transport")
    print("  - uncertainty bands remain side-channel audit context outside the rule engine")
    sys.exit(0)


# ════════════════════════════════════════════════════════════════
# 5. Results: Active Labels per Timestep
# ════════════════════════════════════════════════════════════════

derived = result.derived_session
interp = result.interpretation.get_dict()

print(f"\n[{time.time()-start:.1f}s] Reasoning complete ({result.elapsed_seconds:.1f}s)")
print(f"  Derived facts: {len(derived.node_facts)} node, {len(derived.edge_facts)} edge")

print(f"\n{'='*60}")
print("MISSION WATCH PROPAGATION")
print(f"{'='*60}")

for t in sorted(interp.keys()):
    active_labels: list[str] = []
    for component, preds in sorted(interp[t].items()):
        labels = sorted(pred_name for pred_name, (lo, hi) in preds.items() if lo == 1.0 and hi == 1.0)
        if labels:
            active_labels.append(f"{component}: {', '.join(labels)}")
    if not active_labels:
        continue
    print(f"\n  Timestep {t}:")
    for line in active_labels:
        print(f"    {line}")


# ════════════════════════════════════════════════════════════════
# 6. Accept + Annotations
# ════════════════════════════════════════════════════════════════

ledger = Ledger()
accept_result = accept_pyreason_session(ledger, derived)
print(
    f"\n[{time.time()-start:.1f}s] Accepted: "
    f"{len(accept_result.node_asrt_ids)} assertions, {accept_result.annotation_count} annotations"
)


# ════════════════════════════════════════════════════════════════
# 7. Summary
# ════════════════════════════════════════════════════════════════

print(f"\n{'='*60}")
print("ECSS + PYREASON VALUE PROPOSITION")
print(f"{'='*60}")
print("  Traditional ECSS (esa_demo.py):")
print("    hard threshold -> binary compliance conclusion")
print("    no temporal spread across a mission-topology graph")
print()
print("  PyReason ECSS (this demo):")
print("    boolean watch labels spread across mission phase links over time")
print("    trace/audit can show when DEBRIS_X first inherited each watch label")
print("    disposal/passivation uncertainty remains visible as side-channel context")
print("    instead of pretending PyReason transports fuzzy payload intervals")
print(f"{'='*60}")
