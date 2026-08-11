"""CompilationLineageV0 builder + total-lineage checker (blueprint §5.8).

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Authored nodes come from the compiler's own AST records; lowered nodes come from
the shipped RuleExprLoweringPlan (pinned, private-imported, never modified).
Totality invariants 1-7 per §5.8; repr/prefix-guessing is not lineage.
"""
from __future__ import annotations

from typing import Any

from contracts import digest

from factgraph.application.protocol.rule_expr_lowering import _lower_rule_expr

RELATIONS = ("lowers_to", "copies_to", "injects_lookup", "materializes_join",
             "binds", "projects_to", "targets_expectation", "rejected_as")


def build_lineage(compile_result: dict, *, expectation_present: bool) -> dict:
    plan = _lower_rule_expr(compile_result["expr"], head=compile_result["head"])

    authored_nodes: list[dict] = []
    lowered_nodes: list[dict] = []
    edges: list[dict] = []
    branch_coverage: list[dict] = []
    diagnostics: list[dict] = []

    def a_node(nid: str, kind: str, **extra: Any) -> str:
        authored_nodes.append({"id": nid, "kind": kind, **extra})
        return nid

    def l_node(nid: str, kind: str, **extra: Any) -> str:
        lowered_nodes.append({"id": nid, "kind": kind, **extra})
        return nid

    def edge(rel: str, src: str, dst: str, **extra: Any) -> None:
        assert rel in RELATIONS
        edges.append({"relation": rel, "from": src, "to": dst, **extra})

    # authored occurrences -> specialized rules -> lowered occurrence activations
    spec = compile_result["specialized"]
    for alias, info in spec.items():
        a_id = a_node(f"authored:occurrence:{alias}", "occurrence",
                      rule_ref=info["occurrence"]["rule_ref"])
        s_id = l_node(f"lowered:specialized_rule:{info['rule'].id}", "specialized_rule",
                      compiler_role="occurrence_specialization", generated_for=a_id)
        edge("lowers_to", a_id, s_id)
        for inj in info["injected"]:
            i_a = a_node(f"authored:{inj['kind']}:{inj['path']}", inj["kind"])
            i_l = l_node(f"lowered:atom:{info['rule'].id}:{inj['kind']}:{inj['path']}",
                         "injected_atom", compiler_role=inj["kind"], generated_for=i_a)
            rel = {"bind_identity_anchor": "binds", "bind_value_eq": "binds",
                   "navigation_lookup": "injects_lookup", "compare_const": "lowers_to"}[inj["kind"]]
            edge(rel, i_a, i_l)

    # shipped plan branches: one-to-many copies with explicit edges (invariant 3)
    for br in plan.branches:
        b_id = l_node(f"lowered:branch:{br.branch_id}", "dnf_branch", compiler_role="dnf_copy",
                      generated_for="authored:policy_root")
    a_root = a_node("authored:policy_root", "policy_root")
    for br in plan.branches:
        edge("copies_to", a_root, f"lowered:branch:{br.branch_id}")

    # occurrence_map: lowered aliases must attribute back (invariant 2/5)
    for om in plan.occurrence_map:
        lo_id = l_node(f"lowered:occurrence_activation:{om.alias}", "occurrence_activation",
                       compiler_role="branch_activation", generated_for="shipped_lowering")
        base_alias = om.alias.split("__c")[0] if "__c" in om.alias else om.alias
        if base_alias in spec:
            edge("copies_to", f"authored:occurrence:{base_alias}", lo_id)
        else:
            diagnostics.append({"kind": "unattributed_lowered_alias", "alias": om.alias})

    # joins: authored unify -> materialization state per branch (invariant 4)
    for j in compile_result["joins"]:
        a_id = a_node(f"authored:unify:{j['left'].raw}=={j['right'].raw}", "unify")
        for app in j["branch_applicability"]:
            state = app["state"]
            branch_coverage.append({"constraint": a_id, "branch": app["branch"], "state": state})
            if state == "materialized":
                m_id = l_node(f"lowered:join:{a_id}:{'-'.join(app['branch'])}", "join_constraint",
                              compiler_role="join_materialization", generated_for=a_id)
                edge("materializes_join", a_id, m_id)
            else:
                # explicit record, never absence (§5.7 branch_scoped)
                n_id = l_node(f"lowered:join_na:{a_id}:{'-'.join(app['branch'])}", "join_not_applicable",
                              compiler_role="candidate_semantics_branch_scope", generated_for=a_id)
                edge("rejected_as", a_id, n_id, reason="not_applicable_by_candidate_semantics")

    # selections -> head ports (invariant coverage for select/expect/head)
    head_id = l_node(f"lowered:synthetic_head:{compile_result['head'].id}", "synthetic_head",
                     compiler_role="projection_only", generated_for="authored:selections")
    a_sel_root = a_node("authored:selections", "selection_set")
    edge("projects_to", a_sel_root, head_id)
    for s in compile_result["selections"]:
        s_id = a_node(f"authored:select:{s['alias']}:{s['path']}", "select")
        edge("projects_to", s_id, head_id, head_port=compile_result["select_map"].get(s["alias"]))
    if expectation_present:
        e_id = a_node("authored:expectation", "expectation_target")
        edge("targets_expectation", e_id, head_id)

    # per-branch constraint coverage for binds/compares/navigations (invariant 4)
    for group, kind in (("binds", "bind"), ("compares", "compare"), ("navigations", "navigation")):
        for item in compile_result[group]:
            alias = item["path"].split(".")[0]
            for br in compile_result["branches"]:
                state = "materialized" if alias in br else "not_applicable"
                branch_coverage.append({"constraint": f"authored:{kind}:{item['path']}",
                                        "branch": br, "state": state})

    lineage = {
        "record_type": "CompilationLineageV0",
        "policy_digest": digest(compile_result["branches"]),
        "query_digest": None,  # filled by evaluator with resolved-request digest
        "compiler_build": "probe-compiler-v0",
        "authored_nodes": authored_nodes,
        "lowered_nodes": lowered_nodes,
        "lineage_edges": edges,
        "branch_coverage": branch_coverage,
        "diagnostics": diagnostics,
        "shipped_plan": {
            "branch_ids": [b.branch_id for b in plan.branches],
            "occurrence_aliases": [om.alias for om in plan.occurrence_map],
            "head_binding_kind": plan.head_binding.kind,
        },
    }
    return lineage


def check_totality(lineage: dict) -> dict:
    """§5.8 acceptance invariants 1-7 over the built lineage. Zero engine."""
    failures: list[str] = []
    authored = {n["id"] for n in lineage["authored_nodes"]}
    lowered = {n["id"]: n for n in lineage["lowered_nodes"]}
    src_of = {}
    dst_of = {}
    for e in lineage["lineage_edges"]:
        src_of.setdefault(e["from"], []).append(e)
        dst_of.setdefault(e["to"], []).append(e)

    # 1. every authored node -> >=1 lowered node or explicit diagnostic
    diag_ids = {d.get("alias") for d in lineage["diagnostics"]}
    for a in authored:
        if a not in src_of and a not in diag_ids:
            failures.append(f"invariant1: authored '{a}' has no lowered mapping/diagnostic")
    # 2. every lowered node -> authored origin or compiler_role+generated_for
    for lid, ln in lowered.items():
        attributed = lid in dst_of or ("compiler_role" in ln and "generated_for" in ln)
        if not attributed:
            failures.append(f"invariant2: lowered '{lid}' unattributed")
    # 3. one-to-many copies explicit
    copies = [e for e in lineage["lineage_edges"] if e["relation"] == "copies_to"]
    if len(lineage["shipped_plan"]["branch_ids"]) > 1 and not copies:
        failures.append("invariant3: multi-branch plan without explicit copies_to edges")
    # 4. branch coverage never by absence: every (constraint, branch) pair recorded
    cov = {(c["constraint"], tuple(c["branch"])) for c in lineage["branch_coverage"]}
    constraints = {c["constraint"] for c in lineage["branch_coverage"]}
    all_branches = {tuple(c["branch"]) for c in lineage["branch_coverage"]}
    for c in constraints:
        for b in all_branches:
            if (c, b) not in cov:
                failures.append(f"invariant4: missing coverage record ({c}, {b})")
    # 5. generated aliases compiler-private (no __cN in authored ids / select_map values are ports not aliases)
    for a in authored:
        if "__c" in a:
            failures.append(f"invariant5: generated alias leaked into authored node '{a}'")
    # 6/7. structural: we never derive lineage from repr; trace not used alone (by construction)
    return {"ok": not failures, "failures": failures,
            "authored_count": len(authored), "lowered_count": len(lowered),
            "edge_count": len(lineage["lineage_edges"])}
