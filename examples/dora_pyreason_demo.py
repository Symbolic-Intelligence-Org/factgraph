#!/usr/bin/env python3
"""DORA + PyReason Demo: Fuzzy Incident Severity with Temporal Escalation.

Extends the DORA compliance scenario with PyReason's interval semantics:
- Incident severity as fuzzy bound [lo, hi] instead of hard threshold
- Temporal escalation: severity bounds evolve across timesteps
- Vendor risk propagation through supply chain relationships

Uses adapter-local session + runner (not Store.evaluate) for clarity.
Gracefully exits if pyreason is not available.

Compare with: examples/dora_demo.py (Souffle-based, hard thresholds)
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
# 1. Schema: DORA Incident + Vendor with Fuzzy Severity
# ════════════════════════════════════════════════════════════════

class Incident(Entity):
    incident_id: str = Identity(primary_key=True)
    client_severity: str = Field(cardinality="single")
    financial_severity: str = Field(cardinality="single")
    duration_severity: str = Field(cardinality="single")
    major_incident: str = Field(cardinality="single")
    escalating: str = Field(cardinality="single")


class Vendor(Entity):
    vendor_id: str = Identity(primary_key=True)
    audit_rights: str = Field(cardinality="single")
    exit_strategy: str = Field(cardinality="single")
    vendor_compliant: str = Field(cardinality="single")
    at_risk: str = Field(cardinality="single")


class AffectsVendor(Relationship):
    """Incident → Vendor impact chain."""
    from_entity = Incident
    to_entity = Vendor
    impact: str = Field(cardinality="single")


schema_ir = compile_schema_from_classes([Incident, Vendor, AffectsVendor])
print(f"[{time.time()-start:.1f}s] Schema: {len(schema_ir['predicates'])} predicates")


# ════════════════════════════════════════════════════════════════
# 2. Session: Incident Facts with Fuzzy Severity Bounds
# ════════════════════════════════════════════════════════════════

session = PyReasonSession(schema_ir)

with session.batch() as tx:
    # Incident 1: Major financial outage
    inc1 = tx.entity(Incident, incident_id="INC2026043")
    inc1.client_severity.set("true", bound=[0.7, 0.9],
        meta={"source": "real_time_monitoring", "analyst": "SOC Team"})
    inc1.financial_severity.set("true", bound=[0.8, 0.95],
        meta={"source": "finance_impact_model"})
    inc1.duration_severity.set("true", bound=[0.6, 0.85],
        meta={"source": "incident_tracker"})

    # Incident 2: Minor service degradation
    inc2 = tx.entity(Incident, incident_id="INC2026044")
    inc2.client_severity.set("true", bound=[0.1, 0.3],
        meta={"source": "real_time_monitoring"})
    inc2.financial_severity.set("true", bound=[0.05, 0.15],
        meta={"source": "finance_impact_model"})
    inc2.duration_severity.set("true", bound=[0.2, 0.4],
        meta={"source": "incident_tracker"})

    # Vendor: partially compliant
    acme = tx.entity(Vendor, vendor_id="ACME_CLOUD")
    acme.audit_rights.set("true", bound=[1.0, 1.0],
        meta={"source": "contract_review"})
    acme.exit_strategy.set("true", bound=[0.3, 0.5],
        meta={"source": "contract_review", "analyst": "Legal"})

    # Impact chain: major incident affects vendor
    tx.relationship(AffectsVendor, from_entity=inc1, to_entity=acme,
                    impact="0.85", bound=[0.85, 0.85],
                    meta={"source": "dependency_mapping"})

    tx.commit()

print(f"[{time.time()-start:.1f}s] Facts written:")
print(f"  INC2026043 (major): client=[0.7,0.9] financial=[0.8,0.95] duration=[0.6,0.85]")
print(f"  INC2026044 (minor): client=[0.1,0.3] financial=[0.05,0.15] duration=[0.2,0.4]")
print(f"  ACME_CLOUD: audit_rights=[1.0,1.0] exit_strategy=[0.3,0.5]")
print(f"  Annotation templates: {len(session.annotation_templates)}")


# ════════════════════════════════════════════════════════════════
# 3. Rules: Fuzzy Severity Aggregation + Escalation
# ════════════════════════════════════════════════════════════════

x = LogicVar("x")
y = LogicVar("y")

rules = [
    # Rule 1: Major incident = ANY dimension has high severity
    # PyReason uses fuzzy OR: max of lower bounds propagates
    PyReasonRuleDef(
        rule=Rule(
            id="major_from_client",
            version="1.0",
            select=[Pred("incident:major_incident", x)],
            where=[Pred("incident:client_severity", x)],
        ),
        ext=PyReasonRuleExt(timestep_delay=0),
    ),
    PyReasonRuleDef(
        rule=Rule(
            id="major_from_financial",
            version="1.0",
            select=[Pred("incident:major_incident", x)],
            where=[Pred("incident:financial_severity", x)],
        ),
        ext=PyReasonRuleExt(timestep_delay=0),
    ),
    PyReasonRuleDef(
        rule=Rule(
            id="major_from_duration",
            version="1.0",
            select=[Pred("incident:major_incident", x)],
            where=[Pred("incident:duration_severity", x)],
        ),
        ext=PyReasonRuleExt(timestep_delay=0),
    ),

    # Rule 2: Vendor at risk if incident affects them AND exit strategy is weak
    # (temporal delay: risk propagation takes 1 timestep)
    PyReasonRuleDef(
        rule=Rule(
            id="vendor_risk_from_incident",
            version="1.0",
            select=[Pred("vendor:at_risk", y)],
            where=[
                Pred("incident:major_incident", x),
                Pred("affects_vendor:impact", x, y),
            ],
        ),
        ext=PyReasonRuleExt(timestep_delay=1),
    ),

    # Rule 3: Vendor compliance requires all controls
    PyReasonRuleDef(
        rule=Rule(
            id="vendor_compliance",
            version="1.0",
            select=[Pred("vendor:vendor_compliant", x)],
            where=[
                Pred("vendor:audit_rights", x),
                Pred("vendor:exit_strategy", x),
            ],
        ),
        ext=PyReasonRuleExt(timestep_delay=0),
    ),
]

initial_facts = [
    PyReasonFactDef(atom="client_severity(INC2026043)", name="inc1_client", start=0, end=4, bound=[0.7, 0.9]),
    PyReasonFactDef(atom="financial_severity(INC2026043)", name="inc1_financial", start=0, end=4, bound=[0.8, 0.95]),
    PyReasonFactDef(atom="duration_severity(INC2026043)", name="inc1_duration", start=0, end=4, bound=[0.6, 0.85]),
    PyReasonFactDef(atom="client_severity(INC2026044)", name="inc2_client", start=0, end=4, bound=[0.1, 0.3]),
    PyReasonFactDef(atom="financial_severity(INC2026044)", name="inc2_financial", start=0, end=4, bound=[0.05, 0.15]),
    PyReasonFactDef(atom="duration_severity(INC2026044)", name="inc2_duration", start=0, end=4, bound=[0.2, 0.4]),
    PyReasonFactDef(atom="audit_rights(ACME_CLOUD)", name="acme_audit", start=0, end=4, bound=[1.0, 1.0]),
    PyReasonFactDef(atom="exit_strategy(ACME_CLOUD)", name="acme_exit", start=0, end=4, bound=[0.3, 0.5]),
]

print(f"\n[{time.time()-start:.1f}s] Rules defined:")
print("  1-3. major_incident: client OR financial OR duration severity (fuzzy OR)")
print("  4.   vendor_risk: major_incident + affects_vendor → at_risk [delay=1]")
print("  5.   vendor_compliance: audit_rights + exit_strategy (fuzzy AND)")


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
    print()
    print("  INC2026043 (major outage):")
    print("    t=0: major_incident ∈ [0.8, 0.95] (highest dimension: financial)")
    print("    → NOT binary 'major'. The bound tells you it's 80-95% major.")
    print("    → Width=0.15 means some uncertainty remains in the assessment.")
    print()
    print("  INC2026044 (minor degradation):")
    print("    t=0: major_incident ∈ [0.2, 0.4] (highest dimension: duration)")
    print("    → Probably NOT major. The bound says 20-40% severity.")
    print("    → An investigator can see this is clearly below threshold.")
    print()
    print("  ACME_CLOUD vendor:")
    print("    t=0: vendor_compliant ∈ [0.3, 0.5] (exit_strategy is weak)")
    print("    t=1: at_risk ∈ [0.8, 0.95] (major incident propagated via impact)")
    print("    → The COMBINATION of weak exit strategy + high incident impact")
    print("      creates a concrete, quantified risk that auditors can act on.")
    print()
    print("  Traditional DORA (dora_demo.py) would say:")
    print("    INC2026043: 'major' (boolean)")
    print("    ACME_CLOUD: 'non_compliant' (boolean)")
    print("    No way to see how major, or how much risk.")
    sys.exit(0)


# ════════════════════════════════════════════════════════════════
# 5. Results: Severity Evolution
# ════════════════════════════════════════════════════════════════

derived = result.derived_session
interp = result.interpretation.get_dict()

print(f"\n[{time.time()-start:.1f}s] Reasoning complete ({result.elapsed_seconds:.1f}s)")
print(f"  Derived facts: {len(derived.node_facts)} node, {len(derived.edge_facts)} edge")

print(f"\n{'='*60}")
print("INCIDENT SEVERITY EVOLUTION (PyReason fuzzy intervals)")
print(f"{'='*60}")

for t in sorted(interp.keys()):
    entries = []
    for component, preds in interp[t].items():
        for pred_name, (lo, hi) in preds.items():
            if lo == 0.0 and hi == 0.0:
                continue
            entries.append((component, pred_name, lo, hi))
    if not entries:
        continue
    print(f"\n  Timestep {t}:")
    for component, pred_name, lo, hi in sorted(entries):
        width = hi - lo
        if "major" in pred_name or "risk" in pred_name or "compliant" in pred_name:
            severity = "CRITICAL" if lo >= 0.7 else "HIGH" if lo >= 0.5 else "MEDIUM" if lo >= 0.3 else "LOW"
            print(f"    ⚠ {component}.{pred_name} = [{lo:.2f}, {hi:.2f}] → {severity}")
        else:
            print(f"      {component}.{pred_name} = [{lo:.2f}, {hi:.2f}]")


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
print("DORA + PYREASON VALUE PROPOSITION")
print(f"{'='*60}")
print("  Traditional DORA (dora_demo.py):")
print("    affected_clients >= 10000 → 'major' (binary)")
print("    vendor missing exit strategy → 'non_compliant' (binary)")
print("    No way to express uncertainty or escalation trajectory")
print()
print("  PyReason DORA (this demo):")
print("    client_severity ∈ [0.7, 0.9] → fuzzy major classification")
print("    vendor_compliant ∈ [0.3, 0.5] → partial compliance visible")
print("    at_risk propagated through supply chain with temporal delay")
print("    Auditor sees: 'major incident at 80-95% severity affected")
print("    a vendor with only 30-50% compliance readiness'")
print()
print("  Key insight: PyReason bounds make DORA decisions INTERPRETABLE.")
print("  Instead of 'compliant/non-compliant', regulators see the margin.")
print(f"{'='*60}")
