#!/usr/bin/env python3
"""DORA ICT Incident Classification & Vendor Compliance Demo.

Generates dora_demo_output/ with audit package, static site, provenance,
and human-readable summary. Demonstrates factpy as a cross-domain
auditable reasoning framework beyond space (ECSS).

Usage:
    PYTHONPATH=src python examples/dora_demo.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Bootstrap
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
from factpy_kernel.sdk.dsl.rule import RuleRef
from factpy_kernel.authoring import FileAuthoringRegistry
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
from factpy_kernel.audit.static_ui import render_audit_static_site
from factpy_kernel.adapters.souffle.provenance import run_package_provenance
from factpy_kernel.adapters.souffle.runner import run_package

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "dora_demo_output"


# ═══════════════════════════════════════════════════════════════
# 1. Schema
# ═══════════════════════════════════════════════════════════════

class ICTIncident(Entity):
    """An ICT incident subject to DORA classification."""
    incident_id: str = Identity(primary_key=True)
    locale: str = Identity()
    description: str = Field(cardinality="single")
    affected_clients: str = Field(cardinality="single")
    financial_impact_eur: str = Field(cardinality="single")
    duration_hours: str = Field(cardinality="single")
    reporting_status: str = Field(cardinality="single")

class DORAThreshold(Entity):
    """DORA regulatory thresholds for incident classification."""
    threshold_id: str = Identity(primary_key=True)
    locale: str = Identity()
    client_threshold: str = Field(cardinality="single")
    financial_threshold_eur: str = Field(cardinality="single")
    duration_threshold_hours: str = Field(cardinality="single")

class ICTVendor(Entity):
    """Third-party ICT service provider subject to DORA vendor management."""
    vendor_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")
    has_audit_rights: str = Field(cardinality="single")
    has_exit_strategy: str = Field(cardinality="single")
    has_subcontracting_controls: str = Field(cardinality="single")


# ═══════════════════════════════════════════════════════════════
# 2. Rules
# ═══════════════════════════════════════════════════════════════

def define_rules(sdk: SDKStore) -> list[Rule]:
    rules = []

    with sdk_vars(
        "inc", "thr", "vendor",
        "clients", "amount", "hours",
        "client_thr", "amount_thr", "duration_thr",
        "status", "audit_rights", "exit_strategy", "subcontracting",
    ) as (
        inc, thr, vendor,
        clients, amount, hours,
        client_thr, amount_thr, duration_thr,
        status, audit_rights, exit_strategy, subcontracting,
    ):
        # --- Incident threshold breaches ---

        client_breach = Rule(
            id="q.dora_client_breach",
            version="1.0.0",
            select=[inc, clients],
            where=[
                Pred("ict_incident:affected_clients", inc, clients),
                Pred("dora_threshold:client_threshold", thr, client_thr),
                clients >= client_thr,
            ],
            expose=True,
            condition_weights={"b0.a0": 0.9, "b0.a1": 0.3},
        )
        rules.append(client_breach)

        financial_breach = Rule(
            id="q.dora_financial_breach",
            version="1.0.0",
            select=[inc, amount],
            where=[
                Pred("ict_incident:financial_impact_eur", inc, amount),
                Pred("dora_threshold:financial_threshold_eur", thr, amount_thr),
                amount >= amount_thr,
            ],
            expose=True,
            condition_weights={"b0.a0": 0.8, "b0.a1": 0.4},
        )
        rules.append(financial_breach)

        duration_breach = Rule(
            id="q.dora_duration_breach",
            version="1.0.0",
            select=[inc, hours],
            where=[
                Pred("ict_incident:duration_hours", inc, hours),
                Pred("dora_threshold:duration_threshold_hours", thr, duration_thr),
                hours >= duration_thr,
            ],
            expose=True,
            condition_weights={"b0.a0": 0.7, "b0.a1": 0.5},
        )
        rules.append(duration_breach)

        # --- Major incident = ANY breach (OR branches) ---

        major_incident = Rule(
            id="q.dora_major_incident",
            version="1.0.0",
            select=[inc, status],
            where=[
                [RuleRef(client_breach)(inc, clients), status == "major"],
                [RuleRef(financial_breach)(inc, amount), status == "major"],
                [RuleRef(duration_breach)(inc, hours), status == "major"],
            ],
            expose=True,
        )
        rules.append(major_incident)

        # --- Reporting compliance ---

        reporting_compliant = Rule(
            id="q.dora_reporting_compliant",
            version="1.0.0",
            select=[inc, status],
            where=[
                Pred("ict_incident:reporting_status", inc, status),
                status == "reported_within_4h",
            ],
            expose=True,
            condition_weights={"b0.a0": 1.0},
        )
        rules.append(reporting_compliant)

        reporting_noncompliant = Rule(
            id="q.dora_reporting_noncompliant",
            version="1.0.0",
            select=[inc, status],
            where=[
                Pred("ict_incident:reporting_status", inc, status),
                status == "late_report",
            ],
            expose=True,
            condition_weights={"b0.a0": 1.0},
        )
        rules.append(reporting_noncompliant)

        # --- Vendor compliance ---

        vendor_compliant = Rule(
            id="q.dora_vendor_compliant",
            version="1.0.0",
            select=[vendor, status],
            where=[
                Pred("ict_vendor:has_audit_rights", vendor, audit_rights),
                audit_rights == "yes",
                Pred("ict_vendor:has_exit_strategy", vendor, exit_strategy),
                exit_strategy == "yes",
                Pred("ict_vendor:has_subcontracting_controls", vendor, subcontracting),
                subcontracting == "yes",
                status == "compliant",
            ],
            expose=True,
            condition_weights={"b0.a0": 0.8, "b0.a2": 0.9, "b0.a4": 0.7},
        )
        rules.append(vendor_compliant)

        vendor_noncompliant_no_exit = Rule(
            id="q.dora_vendor_noncompliant_no_exit",
            version="1.0.0",
            select=[vendor, status],
            where=[
                Pred("ict_vendor:has_exit_strategy", vendor, exit_strategy),
                exit_strategy == "no",
                status == "non_compliant_missing_exit_strategy",
            ],
            expose=True,
            condition_weights={"b0.a0": 1.0},
        )
        rules.append(vendor_noncompliant_no_exit)

    return rules


# ═══════════════════════════════════════════════════════════════
# 3. Data
# ═══════════════════════════════════════════════════════════════

INCIDENTS = [
    {
        "id": "INC-2026-042",
        "description": "Payment gateway outage affecting retail banking",
        "affected_clients": "15000",
        "financial_impact_eur": "2300000",
        "duration_hours": "6",
        "reporting_status": "reported_within_4h",
        "meta": {"confidence": 0.92},
    },
    {
        "id": "INC-2026-043",
        "description": "Core banking system degradation",
        "affected_clients": "45000",
        "financial_impact_eur": "5100000",
        "duration_hours": "12",
        "reporting_status": "late_report",
        "meta": {"confidence": 0.85},
    },
    {
        "id": "INC-2026-044",
        "description": "Minor email delivery delay",
        "affected_clients": "200",
        "financial_impact_eur": "5000",
        "duration_hours": "1",
        "reporting_status": "reported_within_4h",
        "meta": {"confidence": 0.98},
    },
]

THRESHOLDS = {
    "client_threshold": "10000",
    "financial_threshold_eur": "1000000",
    "duration_threshold_hours": "4",
}

VENDORS = [
    {
        "id": "VENDOR-A",
        "name": "Acme Cloud Services",
        "has_audit_rights": "yes",
        "has_exit_strategy": "yes",
        "has_subcontracting_controls": "yes",
    },
    {
        "id": "VENDOR-B",
        "name": "QuickPay Gateway",
        "has_audit_rights": "yes",
        "has_exit_strategy": "no",
        "has_subcontracting_controls": "yes",
    },
]


# ═══════════════════════════════════════════════════════════════
# 4. Main
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 70)
    print("DORA ICT Incident Classification & Vendor Compliance Demo")
    print("=" * 70)

    # --- Setup ---
    sdk = SDKStore([ICTIncident, DORAThreshold, ICTVendor])
    all_rules = define_rules(sdk)

    registry_dir = tempfile.mkdtemp(prefix="dora_demo_")
    registry = FileAuthoringRegistry(Path(registry_dir))
    registry.upsert_schema_ir(sdk.schema_ir)
    for rule in all_rules:
        registry.register_rule_spec(sdk._compile_rule_input(rule))

    print(f"\nRules registered: {len(all_rules)}")
    for r in all_rules:
        print(f"  {r.id}")

    # --- Seed entities ---
    with sdk.batch() as tx:
        for inc_data in INCIDENTS:
            e = tx.entity(ICTIncident, incident_id=inc_data["id"], locale="en")
            e.description.set(inc_data["description"])
            e.affected_clients.set(inc_data["affected_clients"])
            e.financial_impact_eur.set(inc_data["financial_impact_eur"])
            e.duration_hours.set(inc_data["duration_hours"])
            e.reporting_status.set(inc_data["reporting_status"])

        thr = tx.entity(DORAThreshold, threshold_id="DORA-2025", locale="en")
        thr.client_threshold.set(THRESHOLDS["client_threshold"])
        thr.financial_threshold_eur.set(THRESHOLDS["financial_threshold_eur"])
        thr.duration_threshold_hours.set(THRESHOLDS["duration_threshold_hours"])

        for v_data in VENDORS:
            v = tx.entity(ICTVendor, vendor_id=v_data["id"], locale="en")
            v.name.set(v_data["name"])
            v.has_audit_rights.set(v_data["has_audit_rights"])
            v.has_exit_strategy.set(v_data["has_exit_strategy"])
            v.has_subcontracting_controls.set(v_data["has_subcontracting_controls"])

        tx.commit()

    # --- Runtime session ---
    reset_runtime_sessions_for_tests()
    session_resp = open_runtime_session({"registry_root": registry_dir})
    session_id = session_resp["session"]["session_id"]

    # Write incident facts
    for inc_data in INCIDENTS:
        e_ref = sdk.ref(ICTIncident, incident_id=inc_data["id"], locale="en")
        meta = inc_data.get("meta", {})
        for pred_suffix, value in [
            ("affected_clients", inc_data["affected_clients"]),
            ("financial_impact_eur", inc_data["financial_impact_eur"]),
            ("duration_hours", inc_data["duration_hours"]),
            ("reporting_status", inc_data["reporting_status"]),
        ]:
            write_runtime_fact(session_id, {
                "pred_id": f"ict_incident:{pred_suffix}",
                "e_ref": e_ref,
                "rest_terms": [["string", value]],
                "meta": meta if pred_suffix == "affected_clients" else {},
            }, kind="add")

    # Write threshold facts
    thr_ref = sdk.ref(DORAThreshold, threshold_id="DORA-2025", locale="en")
    for pred_suffix, value in THRESHOLDS.items():
        write_runtime_fact(session_id, {
            "pred_id": f"dora_threshold:{pred_suffix}",
            "e_ref": thr_ref,
            "rest_terms": [["string", value]],
        }, kind="add")

    # Write vendor facts
    for v_data in VENDORS:
        v_ref = sdk.ref(ICTVendor, vendor_id=v_data["id"], locale="en")
        for pred_suffix in ["has_audit_rights", "has_exit_strategy", "has_subcontracting_controls"]:
            write_runtime_fact(session_id, {
                "pred_id": f"ict_vendor:{pred_suffix}",
                "e_ref": v_ref,
                "rest_terms": [["string", v_data[pred_suffix]]],
            }, kind="add")

    print(f"\nFacts written: {len(INCIDENTS)} incidents + 1 threshold set + {len(VENDORS)} vendors")

    # --- Evaluate ---
    summary_lines: list[str] = []
    summary_lines.append("DORA ICT Incident Classification & Vendor Compliance")
    summary_lines.append("=" * 55)

    derivations = [
        ("drv.major", "q.dora_major_incident", "ict_incident:reporting_status",
         "$inc", "$status", "Major Incident Classification"),
        ("drv.reporting_ok", "q.dora_reporting_compliant", "ict_incident:reporting_status",
         "$inc", "$status", "Reporting Compliance (within 4h)"),
        ("drv.reporting_late", "q.dora_reporting_noncompliant", "ict_incident:reporting_status",
         "$inc", "$status", "Reporting Non-Compliance (late)"),
        ("drv.vendor_ok", "q.dora_vendor_compliant", "ict_vendor:has_audit_rights",
         "$vendor", "$status", "Vendor Compliance"),
        ("drv.vendor_bad", "q.dora_vendor_noncompliant_no_exit", "ict_vendor:has_exit_strategy",
         "$vendor", "$status", "Vendor Non-Compliance (missing exit strategy)"),
    ]

    all_candidates = []

    for drv_id, rule_id, target, var1, var2, label in derivations:
        ev = evaluate_runtime_derivation(session_id, {
            "derivation": {
                "derivation_id": drv_id,
                "version": "1.0.0",
                "target": target,
                "head_vars": [var1, var2],
                "where": [["ruleref", rule_id, "1.0.0", [var1, var2]]],
                "mode": "native",
            }
        })

        print(f"\n{label}:")
        summary_lines.append(f"\n{label}:")
        if ev["ok"] and ev["evaluation"]["candidates"]:
            for cand in ev["evaluation"]["candidates"]:
                terms = cand["payload"]["terms"]
                entity_ref = terms[0]["value"]
                # Extract entity ID from ref
                entity_short = entity_ref.split(":")[-1][:20] if ":" in entity_ref else entity_ref[:20]
                result = terms[1]["value"]
                ck = cand.get("confidence_kind", "none")
                line = f"  {entity_short}... → {result} (confidence_kind={ck})"
                print(line)
                summary_lines.append(line)
                all_candidates.append(cand)
            print(f"  Total: {len(ev['evaluation']['candidates'])}")
            summary_lines.append(f"  Total: {len(ev['evaluation']['candidates'])}")

            # Show certainty for first candidate
            cid = ev["evaluation"]["candidates"][0]["candidate_id"]
            sm = explain_runtime_summary(session_id, {"kind": "candidate", "id": cid})
            if sm["ok"]:
                cs = sm.get("certainty_summary")
                if cs:
                    line = f"  Certainty: aggregate={cs['aggregate_certainty']} ({cs['aggregation']})"
                    print(line)
                    summary_lines.append(line)
        else:
            line = "  (no matches)"
            print(line)
            summary_lines.append(line)

    # --- Accept all candidates ---
    print(f"\n{'=' * 70}")
    print("Accepting candidates...")
    for cand in all_candidates:
        resp = accept_runtime_derivation(session_id, {"candidate": cand})
        if resp["ok"]:
            print(f"  ✅ Accepted {cand['candidate_id'][:30]}...")

    # --- Prepare output directory ---
    for subdir in ["audit", "site", "provenance"]:
        d = OUTPUT_DIR / subdir
        if d.exists():
            shutil.rmtree(d)

    audit_dir = str(OUTPUT_DIR / "audit")
    site_dir = str(OUTPUT_DIR / "site")
    provenance_dir = OUTPUT_DIR / "provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)

    # --- Export audit package ---
    export_resp = export_runtime_package(session_id, {
        "out_dir": audit_dir,
        "package_kind": "audit",
    })
    print(f"\nAudit export: ok={export_resp['ok']}")

    # --- Provenance for flat rules ---
    provenance_rules_to_query = [
        ("q.dora_client_breach", "client_breach"),
        ("q.dora_reporting_noncompliant", "reporting_noncompliant"),
        ("q.dora_vendor_compliant", "vendor_compliant"),
        ("q.dora_vendor_noncompliant_no_exit", "vendor_noncompliant"),
    ]

    print("\nProvenance Artifacts:")
    for rule_id, label in provenance_rules_to_query:
        rule_obj = next((r for r in all_rules if r.id == rule_id), None)
        if rule_obj is None:
            continue
        try:
            compiled_where = sdk._compile_rule_input(rule_obj)["where"]
            pkg_dir = tempfile.mkdtemp(prefix=f"dora_prov_{label}_")
            prov_export = export_runtime_package(session_id, {
                "out_dir": pkg_dir,
                "package_kind": "inference",
                "query": {
                    "where": compiled_where,
                    "query_rel": f"{label}_query",
                    "registry_root": registry_dir,
                },
            })
            if not prov_export["ok"]:
                continue

            run_package(Path(pkg_dir), ["__query__"], engine="souffle")
            out_path = Path(pkg_dir) / "outputs" / f"{label}_query.out.facts"
            if not out_path.exists():
                continue
            rows = [l.split("\t") for l in out_path.read_text().splitlines() if l.strip()]
            if not rows:
                continue

            # Query first row
            query_text = f"{label}_query(" + ", ".join(f'"{v}"' for v in rows[0]) + ")"
            trees = run_package_provenance(Path(pkg_dir), [query_text])
            if trees:
                tree = trees[0]
                tree_dict = {
                    "query": tree.query,
                    "root": _node_to_dict(tree.root),
                    "rules": tree.rules,
                }
                out_file = provenance_dir / f"{label}.json"
                out_file.write_text(json.dumps(tree_dict, indent=2, ensure_ascii=False))
                print(f"  - {label}.json: relation={tree.root.relation} "
                      f"rule_number={tree.root.rule_number} child_count={len(tree.root.children)}")
                summary_lines.append(f"  Provenance: {label}.json")
        except Exception as exc:
            print(f"  - {label}: skipped ({type(exc).__name__}: {exc})")

    # --- Static site ---
    render_audit_static_site(audit_dir, site_dir)
    site_pages = list(Path(site_dir).rglob("*.html"))
    print(f"\nStatic site: {len(site_pages)} pages")

    # --- Audit query ---
    pkg = load_audit_package(audit_dir)
    aq = AuditQuery(pkg)
    candidates = aq.list_candidates()
    print(f"Audit candidates: {len(candidates)}")

    summary_lines.append(f"\nAudit Bundle:")
    summary_lines.append(f"  accepted_candidates={len(candidates)}")
    summary_lines.append(f"  site_pages={len(site_pages)}")
    summary_lines.append(f"  site_index={OUTPUT_DIR / 'site' / 'index.html'}")

    # --- Write summary ---
    summary_path = OUTPUT_DIR / "summary.txt"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    close_runtime_session(session_id)
    reset_runtime_sessions_for_tests()

    print(f"\n{'=' * 70}")
    print("DORA Demo Complete")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Site:   {OUTPUT_DIR / 'site' / 'index.html'}")
    print(f"  Summary: {summary_path}")
    print(f"{'=' * 70}")


def _node_to_dict(node) -> dict:
    d = {
        "node_type": node.node_type,
        "relation": node.relation,
        "args": list(node.args),
    }
    if node.rule_number:
        d["rule_number"] = node.rule_number
    if node.children:
        d["children"] = [_node_to_dict(c) for c in node.children]
    return d


if __name__ == "__main__":
    main()
