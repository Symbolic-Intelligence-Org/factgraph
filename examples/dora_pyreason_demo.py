#!/usr/bin/env python3
"""DORA + PyReason Demo: Boolean Supply-Chain Risk Propagation.

This demo uses PyReason for what the engine reliably supports in practice:

- boolean risk labels moving across a vendor dependency graph
- temporal propagation over multiple timesteps
- uncertainty and severity bands kept as side-channel audit context

Uses adapter-local session + runner (not Store.evaluate) for clarity.
Gracefully exits if pyreason is not available.

Compare with: examples/dora_demo.py (Souffle-based, hard thresholds)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factpy_kernel.adapters.pyreason.accept import accept_pyreason_session
from factpy_kernel.adapters.pyreason.rule_ext import PyReasonRuleExt
from factpy_kernel.adapters.pyreason.runner import PyReasonRunConfig, run_pyreason
from factpy_kernel.adapters.pyreason.session import PyReasonSession
from factpy_kernel.core.store.ledger import Ledger
from factpy_kernel.sdk import Entity, Field, Identity, Relationship
from factpy_kernel.sdk.compile import compile_schema_from_classes
from factpy_kernel.sdk.dsl.expr import LogicVar, Pred
from factpy_kernel.sdk.dsl.rule import Rule

start = time.time()


# ════════════════════════════════════════════════════════════════
# 1. Schema: DORA Vendor Dependency Graph
# ════════════════════════════════════════════════════════════════


class Vendor(Entity):
    vendor_id: str = Identity(primary_key=True)
    at_risk_signal: str = Field(cardinality="single")
    contingency_gap_signal: str = Field(cardinality="single")


class VendorDependency(Relationship):
    """Critical third-party dependency path."""

    from_entity = Vendor
    to_entity = Vendor
    critical_path: str = Field(cardinality="single")


schema_ir = compile_schema_from_classes([Vendor, VendorDependency])
print(f"[{time.time()-start:.1f}s] Schema: {len(schema_ir['predicates'])} predicates")


# ════════════════════════════════════════════════════════════════
# 2. Session: Boolean Seeds + Side-Channel Assessments
# ════════════════════════════════════════════════════════════════

session = PyReasonSession(schema_ir)

side_channel_assessments = {
    "ACME_CLOUD": {
        "incident_severity_band": [0.80, 0.95],
        "exit_readiness_band": [0.45, 0.60],
    },
    "PAYMENTS_GATEWAY": {
        "incident_severity_band": [0.55, 0.70],
        "exit_readiness_band": [0.30, 0.50],
    },
    "MOBILE_BANKING_APP": {
        "incident_severity_band": [0.65, 0.85],
        "exit_readiness_band": [0.75, 0.90],
    },
}

with session.batch() as tx:
    acme = tx.entity(Vendor, vendor_id="ACME_CLOUD")
    payments = tx.entity(Vendor, vendor_id="PAYMENTS_GATEWAY")
    mobile = tx.entity(Vendor, vendor_id="MOBILE_BANKING_APP")

    acme.at_risk_signal.set(
        "true",
        bound=[1.0, 1.0],
        meta={"source": "major_incident_triage", "mode": "boolean_seed"},
    )
    payments.contingency_gap_signal.set(
        "true",
        bound=[1.0, 1.0],
        meta={"source": "contract_review", "mode": "boolean_seed"},
    )

    tx.relationship(
        VendorDependency,
        from_entity=acme,
        to_entity=payments,
        critical_path="true",
        bound=[1.0, 1.0],
        meta={"source": "dependency_mapping"},
    )
    tx.relationship(
        VendorDependency,
        from_entity=payments,
        to_entity=mobile,
        critical_path="true",
        bound=[1.0, 1.0],
        meta={"source": "dependency_mapping"},
    )

    tx.commit()

print(f"[{time.time()-start:.1f}s] Boolean seeds written:")
print("  ACME_CLOUD at_risk_signal=true")
print("  PAYMENTS_GATEWAY contingency_gap_signal=true")
print("  critical_path(ACME_CLOUD -> PAYMENTS_GATEWAY)=true")
print("  critical_path(PAYMENTS_GATEWAY -> MOBILE_BANKING_APP)=true")
print("  Annotation templates:", len(session.annotation_templates))
print("\n  Side-channel assessments (NOT fed into PyReason seeds):")
for vendor_id, observations in side_channel_assessments.items():
    print(
        "   ",
        vendor_id,
        f"incident={observations['incident_severity_band']}",
        f"exit_readiness={observations['exit_readiness_band']}",
    )


# ════════════════════════════════════════════════════════════════
# 3. Rules: Boolean Risk Propagation
# ════════════════════════════════════════════════════════════════

x = LogicVar("x")
y = LogicVar("y")

rules = [
    Rule(
        id="vendor_risk_propagation",
        version="1.0",
        select=[Pred("vendor:at_risk_signal", x)],
        where=[
            Pred("vendor:at_risk_signal", y),
            Pred("vendor_dependency:critical_path", y, x),
        ],
        engine_ext=PyReasonRuleExt(timestep_delay=1),
    ),
    Rule(
        id="contingency_gap_propagation",
        version="1.0",
        select=[Pred("vendor:contingency_gap_signal", x)],
        where=[
            Pred("vendor:contingency_gap_signal", y),
            Pred("vendor_dependency:critical_path", y, x),
        ],
        engine_ext=PyReasonRuleExt(timestep_delay=1),
    ),
]

print(f"\n[{time.time()-start:.1f}s] Rules defined:")
print("  1. at_risk_signal(Y) + critical_path(Y,X) -> at_risk_signal(X) [delay=1]")
print("  2. contingency_gap_signal(Y) + critical_path(Y,X) -> contingency_gap_signal(X) [delay=1]")


# ════════════════════════════════════════════════════════════════
# 4. Run PyReason
# ════════════════════════════════════════════════════════════════

try:
    result = run_pyreason(
        session,
        rule_defs=rules,
        config=PyReasonRunConfig(timesteps=4, atom_trace=True),
    )
except Exception as exc:
    print(f"\n[NOTE] PyReason execution failed: {exc}")
    print("This is expected if pyreason is not installed or has numba issues.")
    print("\nWhat this demo shows on a working PyReason installation:")
    print("  - ACME_CLOUD's at_risk_signal propagates through the vendor dependency chain")
    print("  - PAYMENTS_GATEWAY's contingency_gap_signal propagates downstream over time")
    print("  - interval/severity assessments remain audit-side context, not propagated payloads")
    sys.exit(0)


# ════════════════════════════════════════════════════════════════
# 5. Results: Active Labels per Timestep
# ════════════════════════════════════════════════════════════════

derived = result.derived_session
interp = result.interpretation.get_dict()

print(f"\n[{time.time()-start:.1f}s] Reasoning complete ({result.elapsed_seconds:.1f}s)")
print(f"  Derived facts: {len(derived.node_facts)} node, {len(derived.edge_facts)} edge")

print(f"\n{'='*60}")
print("VENDOR RISK PROPAGATION")
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
print("DORA + PYREASON VALUE PROPOSITION")
print(f"{'='*60}")
print("  Traditional DORA (dora_demo.py):")
print("    thresholded vendor / incident findings become binary outputs")
print("    limited visibility into how risk spreads through the dependency graph")
print()
print("  PyReason DORA (this demo):")
print("    boolean risk labels move through critical vendor paths over time")
print("    trace/audit can show when each downstream vendor first became flagged")
print("    severity and exit-readiness intervals stay visible as side-channel evidence")
print("    instead of pretending PyReason propagates fuzzy numeric payloads")
print(f"{'='*60}")
