"""Experimental Policy-AST-v0 compiler: per-occurrence specialized Rule synthesis.

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Compile order is fixed by blueprint §5.4.3:
    Policy body -> bind constraints -> Policy-owned field lookup/comparison
    -> projection-only synthetic head -> native evaluation -> expectation.

Design (bridges authored occurrence-qualified addressing onto the shipped
port-name-addressed projection head, without touching src/**):
  * every authored occurrence lowers to ONE compiler-generated shipped Rule
    whose ports carry occurrence-qualified names (``m__person``), so the
    projection head is never ambiguous across occurrences;
  * bind on an entity port  -> identity-anchor atom  Pred(person:name, [v, Const])
    bind on a value port    -> CmpAtom("eq", v, Const)
  * field navigation        -> injected lookup atom + optional comparison
  * unify(path, path)       -> shipped RuleJoinConstraint on qualified ports
  * SC-01 candidates: ``reject_on_partial`` fails JOIN_ENDPOINT_NOT_TOTAL before
    any shipped lowering; ``branch_scoped`` proceeds and the per-branch join
    applicability is recorded explicitly in lineage (never by absence).
Shipped lowerer/materializer are pinned, private-imported, never modified.
"""
from __future__ import annotations

import itertools
from typing import Any

from contracts import (
    DNF_BRANCH_LIMIT_EXCEEDED,
    FIELD_NAVIGATION_RESTRICTED,
    FIELD_NAVIGATION_UNKNOWN_FIELD,
    JOIN_ENDPOINT_NOT_TOTAL,
    NAVIGATION_BRANCH_UNBOUND,
    PATH_UNRESOLVED_ALIAS,
    RESERVED_NAMESPACE_PREFIXES,
    SYNTHETIC_QUERY_NAMESPACE_COLLISION,
    ProbeError,
)

from factgraph.sdk import Rule  # application.protocol.Rule re-export (sdk/__init__.py)
from factgraph.application.protocol.rule import RuleOccurrence
from factgraph.application.protocol.rule_expr import RuleExpr
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var

_DNF_LIMIT = 32  # mirrors shipped rule_expr_lowering._DNF_BRANCH_LIMIT (pinned observed)


def _snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _class_name(entity_type: str) -> str:
    return "".join(part.capitalize() for part in entity_type.split("_"))


# ---------------------------------------------------------------- catalog (AC-21)

def validate_catalog(world: dict) -> None:
    """ProbeManagedCatalogValidatorV0 @ catalog_validation_pre_lowering. 0 engine."""
    for spec in world.get("rules", ()):  # authored rule ids
        rid = spec["rule_id"]
        for prefix in RESERVED_NAMESPACE_PREFIXES:
            if rid == prefix or rid.startswith(prefix + ":"):
                raise ProbeError(
                    SYNTHETIC_QUERY_NAMESPACE_COLLISION,
                    stage="catalog_validation_pre_lowering",
                    diagnostics=[rid],
                    owner="ProbeManagedCatalogValidatorV0",
                )


# ------------------------------------------------------- AST walk / branch algebra

def _walk_occurrences(node: dict) -> list[dict]:
    if "occurrence" in node:
        return [node["occurrence"]]
    for key in ("all", "any"):
        if key in node:
            out: list[dict] = []
            for child in node[key]:
                out.extend(_walk_occurrences(child))
            return out
    return []


def ast_branches(node: dict) -> list[frozenset[str]]:
    """Author-level DNF branch enumeration: each branch = set of occurrence aliases."""
    if "occurrence" in node:
        return [frozenset([node["occurrence"]["alias"]])]
    if "all" in node:
        parts = [ast_branches(c) for c in node["all"] if _contributes(c)]
        if not parts:
            return [frozenset()]
        combos = []
        for combo in itertools.product(*parts):
            merged: frozenset[str] = frozenset()
            for c in combo:
                merged = merged | c
            combos.append(merged)
        return combos
    if "any" in node:
        out: list[frozenset[str]] = []
        for c in node["any"]:
            out.extend(ast_branches(c))
        return out
    return [frozenset()]


def _contributes(node: dict) -> bool:
    return any(k in node for k in ("occurrence", "all", "any"))


def _collect_constraints(node: dict, out: list[dict]) -> None:
    for key in ("all", "any"):
        if key in node:
            for child in node[key]:
                _collect_constraints(child, out)
    for key in ("compare", "unify"):
        if key in node:
            out.append({key: node[key]})


# ------------------------------------------------------------------ path resolution

class _Path:
    __slots__ = ("alias", "port", "field")

    def __init__(self, raw: str):
        parts = raw.split(".")
        if len(parts) == 2:
            self.alias, self.port, self.field = parts[0], parts[1], None
        elif len(parts) == 3:
            self.alias, self.port, self.field = parts[0], parts[1], parts[2]
        else:
            raise ProbeError("PATH_SYNTAX", stage="resolution", diagnostics=[raw])

    @property
    def raw(self) -> str:
        base = f"{self.alias}.{self.port}"
        return base if self.field is None else f"{base}.{self.field}"


def _resolve_path(path_raw: str, occ_index: dict[str, dict]) -> _Path:
    p = _Path(path_raw)
    if p.alias not in occ_index:
        raise ProbeError(PATH_UNRESOLVED_ALIAS, stage="resolution", diagnostics=[path_raw])
    spec = occ_index[p.alias]
    if p.port not in spec["rule_spec"]["ports"]:
        raise ProbeError("PATH_UNKNOWN_PORT", stage="resolution", diagnostics=[path_raw])
    return p


# --------------------------------------------------------- navigation validation

def _validate_navigation(
    p: _Path, world: dict, grants: list[str], branches: list[frozenset[str]]
) -> None:
    grant_key = p.raw
    entity_types = {et["name"]: et for et in world.get("entity_types", ())}
    # port -> entity type by naming convention (port name == entity type name)
    etype = entity_types.get(p.port)
    if etype is None:
        raise ProbeError(FIELD_NAVIGATION_UNKNOWN_FIELD, stage="resolution",
                         diagnostics=[p.raw, f"port '{p.port}' is not an entity port"])
    declared = {f["name"] for f in etype.get("fields", ())}
    fact_preds = {f[0] for f in world.get("facts", ()) if len(f) >= 3}
    if p.field not in declared and p.field not in fact_preds:
        raise ProbeError(FIELD_NAVIGATION_UNKNOWN_FIELD, stage="resolution",
                         diagnostics=[p.raw])
    if grant_key not in (grants or []):
        raise ProbeError(FIELD_NAVIGATION_RESTRICTED, stage="resolution",
                         diagnostics=[p.raw])
    for br in branches:
        if p.alias not in br:
            raise ProbeError(NAVIGATION_BRANCH_UNBOUND, stage="resolution",
                             diagnostics=[p.raw, f"unbound in branch {sorted(br)}"])


# --------------------------------------------------------------- rule specialization

def _base_atoms(rule_spec: dict, world: dict, alias: str) -> tuple[tuple, dict[str, Var]]:
    """Base body for one occurrence: exists + fact-field atom, qualified port vars."""
    ports = rule_spec["ports"]
    pred = rule_spec["from_facts"]
    entity_types = {et["name"]: et for et in world.get("entity_types", ())}
    lookup_types = {n for n, et in entity_types.items() if et.get("identity") not in (None, "value")}
    port_vars = {p: Var(f"${alias}__{p}") for p in ports}
    subject_port = ports[0]
    atoms: list = []
    if subject_port in lookup_types:
        cls = _class_name(subject_port)
        atoms.append(PredAtom(f"{cls}:exists", [port_vars[subject_port]]))
        atoms.append(PredAtom(f"{_snake(cls)}:{pred}",
                              [port_vars[subject_port]] + [port_vars[p] for p in ports[1:]]))
    else:
        # scalar world: singleton World subject
        w = Var(f"${alias}__world")
        atoms.append(PredAtom("World:exists", [w]))
        atoms.append(PredAtom(f"world:{pred}", [w] + [port_vars[p] for p in ports]))
    return tuple(atoms), port_vars


def compile_policy(fixture: dict, resolution: dict, *, candidate_semantics: str | None = None) -> dict:
    """AST -> specialized shipped Rules + RuleExpr + projection head + compile records."""
    prof = fixture["profile"]
    world = fixture["world"]
    ast = prof["policy"]["ast"]
    validate_catalog(world)

    rule_specs = {r["rule_id"]: r for r in world.get("rules", ())}
    occurrences = _walk_occurrences(ast)
    occ_index: dict[str, dict] = {}
    for occ in occurrences:
        if occ["rule_ref"] not in rule_specs:
            raise ProbeError("UNKNOWN_RULE_REF", stage="resolution", diagnostics=[occ["rule_ref"]])
        occ_index[occ["alias"]] = {"occurrence": occ, "rule_spec": rule_specs[occ["rule_ref"]]}

    branches = ast_branches(ast)
    limit_state = "within_limit" if len(branches) <= _DNF_LIMIT else "exceeded"
    publish_check = {
        "owner": "ProbeProfileCapabilityValidatorV0",
        "stage": "profile_publish_freeze",
        "branch_count": len(branches),
        "limit": _DNF_LIMIT,
        "state": limit_state,
    }
    if limit_state == "exceeded":
        raise ProbeError(DNF_BRANCH_LIMIT_EXCEEDED, stage="profile_publish_freeze",
                         diagnostics=[f"branch_count={len(branches)}", f"limit={_DNF_LIMIT}"],
                         owner="ProbeProfileCapabilityValidatorV0", publish_check=publish_check)

    constraints: list[dict] = []
    _collect_constraints(ast, constraints)

    # classify constraints; navigation validation happens BEFORE lowering (§5.5)
    binds = []  # from bind_templates + resolved slots
    for tpl in prof.get("bind_templates", ()):
        slot_val = resolution["normalized_slot_values"][tpl["slot"]]
        binds.append({"path": _resolve_path(tpl["path"], occ_index), "value": slot_val})

    compares, joins, navigations = [], [], []
    for c in constraints:
        if "unify" in c:
            left = _resolve_path(c["unify"]["left"]["path"], occ_index)
            right = _resolve_path(c["unify"]["right"]["path"], occ_index)
            join_rec = {"left": left, "right": right, "authored": c["unify"],
                        "branch_applicability": []}
            for br in branches:
                applicable = left.alias in br and right.alias in br
                join_rec["branch_applicability"].append(
                    {"branch": sorted(br),
                     "state": "materialized" if applicable else "not_applicable_by_candidate_semantics"})
            if candidate_semantics == "reject_on_partial" and any(
                a["state"] != "materialized" for a in join_rec["branch_applicability"]
            ):
                raise ProbeError(JOIN_ENDPOINT_NOT_TOTAL, stage="join_totality_pre_lowering",
                                 diagnostics=[f"{left.raw}=={right.raw}"])
            joins.append(join_rec)
        elif "compare" in c:
            cmp = c["compare"]
            left = _resolve_path(cmp["left"]["path"], occ_index)
            if left.field is not None:
                _validate_navigation(left, world, prof.get("field_path_grants"), branches)
                navigations.append({"path": left, "op": cmp["op"], "const": cmp["right"]["value"]})
            else:
                compares.append({"path": left, "op": cmp["op"], "const": cmp["right"]["value"]})

    # selections: navigation selections must reuse a Policy-materialized variable (§5.5)
    selections = []
    for tpl in prof.get("select_templates", ()):
        p = _resolve_path(tpl["path"], occ_index)
        if p.field is not None:
            if not any(n["path"].raw == p.raw for n in navigations):
                raise ProbeError("FIELD_NAVIGATION_WOULD_FILTER_RESULT", stage="resolution",
                                 diagnostics=[p.raw])
        selections.append({"alias": tpl["alias"], "path": p})

    # ---- specialize one shipped Rule per occurrence -------------------------
    entity_types = {et["name"]: et for et in world.get("entity_types", ())}
    specialized: dict[str, dict] = {}
    op_map = {">": "gt", ">=": "ge", "<": "lt", "<=": "le", "==": "eq", "!=": "ne"}
    for alias, info in occ_index.items():
        atoms, port_vars = _base_atoms(info["rule_spec"], world, alias)
        atoms = list(atoms)
        injected: list[dict] = []
        for b in binds:
            if b["path"].alias != alias:
                continue
            port = b["path"].port
            val = b["value"]
            if "entity" in (val or {}):
                et = entity_types.get(port)
                if et is not None and et.get("identity") not in (None, "value"):
                    idf = et["identity"]
                    cls = _class_name(port)
                    atoms.append(PredAtom(f"{_snake(cls)}:{idf}", [port_vars[port], Const(val["id"])]))
                    injected.append({"kind": "bind_identity_anchor", "path": b["path"].raw, "value": val["id"]})
                else:
                    atoms.append(CmpAtom("eq", port_vars[port], Const(val["id"])))
                    injected.append({"kind": "bind_value_eq", "path": b["path"].raw, "value": val["id"]})
            else:
                atoms.append(CmpAtom("eq", port_vars[port], Const(val["value"])))
                injected.append({"kind": "bind_value_eq", "path": b["path"].raw, "value": val["value"]})
        for cp in compares:
            if cp["path"].alias != alias:
                continue
            atoms.append(CmpAtom(op_map[cp["op"]], port_vars[cp["path"].port], Const(cp["const"])))
            injected.append({"kind": "compare_const", "path": cp["path"].raw, "op": cp["op"]})
        for nav in navigations:
            if nav["path"].alias != alias:
                continue
            base_port = nav["path"].port
            fld = nav["path"].field
            cls = _class_name(base_port)
            nav_var = Var(f"${alias}__{base_port}__{fld}")
            atoms.append(PredAtom(f"{_snake(cls)}:{fld}", [port_vars[base_port], nav_var]))
            atoms.append(CmpAtom(op_map[nav["op"]], nav_var, Const(nav["const"])))
            port_vars[f"{base_port}__{fld}"] = nav_var
            injected.append({"kind": "navigation_lookup", "path": nav["path"].raw, "op": nav["op"]})
        qualified_ports = {f"{alias}__{p}": v for p, v in port_vars.items()}
        rule = Rule(id=f"probe__{info['rule_spec']['rule_id']}__{alias}",
                    when=tuple(atoms), ports=qualified_ports)
        specialized[alias] = {"rule": rule, "injected": injected,
                              "occurrence": info["occurrence"], "qualified_ports": qualified_ports}

    # ---- RuleExpr assembly --------------------------------------------------
    def build(node: dict):
        if "occurrence" in node:
            alias = node["occurrence"]["alias"]
            return specialized[alias]["rule"].as_(alias)
        if "all" in node:
            expr = None
            for child in node["all"]:
                if not _contributes(child):
                    continue
                sub = build(child)
                expr = sub if expr is None else (expr & sub)
            return expr
        if "any" in node:
            expr = None
            for child in node["any"]:
                sub = build(child)
                expr = sub if expr is None else (expr | sub)
            return expr
        raise ProbeError("AST_NODE_UNSUPPORTED", stage="resolution", diagnostics=[str(node)])

    expr = build(ast)
    if isinstance(expr, RuleOccurrence):
        expr = RuleExpr.all(expr)  # single-occurrence policy: lift to RuleExpr for shipped lowering
    for j in joins:
        l, r = j["left"], j["right"]
        lo = specialized[l.alias]["rule"].as_(l.alias)
        ro = specialized[r.alias]["rule"].as_(r.alias)
        expr = expr.join(lo.port(f"{l.alias}__{l.port}").eq(ro.port(f"{r.alias}__{r.port}")))

    # ---- projection-only synthetic head (§5.4.3 / §6.7) ---------------------
    if selections:
        head_ports = [f"{s['path'].alias}__{s['path'].port}" if s["path"].field is None
                      else f"{s['path'].alias}__{s['path'].port}__{s['path'].field}"
                      for s in selections]
        select_map = {s["alias"]: hp for s, hp in zip(selections, head_ports)}
    else:
        first_alias = occurrences[0]["alias"]
        first_port = occ_index[first_alias]["rule_spec"]["ports"][0]
        head_ports = [f"{first_alias}__{first_port}"]
        select_map = {}
    head = Rule.projection(*head_ports)

    return {
        "expr": expr,
        "head": head,
        "select_map": select_map,
        "specialized": specialized,
        "joins": joins,
        "navigations": [
            {"path": n["path"].raw, "op": n["op"], "const": n["const"]} for n in navigations
        ],
        "compares": [{"path": c["path"].raw, "op": c["op"]} for c in compares],
        "binds": [{"path": b["path"].raw} for b in binds],
        "branches": [sorted(b) for b in branches],
        "publish_check": publish_check,
        "selections": [{"alias": s["alias"], "path": s["path"].raw} for s in selections],
        "query_mode": prof.get("query_mode", "rows"),
        "candidate_semantics": candidate_semantics,
    }
