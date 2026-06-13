from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprEvaluationTrace,
    RuleExprLoweringBranch,
    RuleExprLoweringPlan,
    _materialize_native_derivation_plan,
    probe_seed_vars_by_head_port,
)
from factgraph.core.rules.where_ast import Const, Var


class DiagnosticProjectionError(Exception):
    pass


@dataclass(frozen=True)
class Wildcard:
    name: str = "_"


CompanionTerm: TypeAlias = Const | Var | Wildcard


@dataclass(frozen=True)
class CompanionLiteral:
    pred_id: str
    terms: tuple[CompanionTerm, ...]
    negated: bool = False


@dataclass(frozen=True)
class CompanionCompare:
    op: str
    lhs: CompanionTerm
    rhs: CompanionTerm
    negated: bool = False


CompanionAtom: TypeAlias = CompanionLiteral | CompanionCompare


@dataclass(frozen=True)
class CompanionWitness:
    terms: tuple[CompanionTerm, ...]


@dataclass(frozen=True)
class CompanionNotReached:
    var: str


@dataclass(frozen=True)
class CompanionAtomRules:
    branch_id: str
    atom_index: int
    holds_body: tuple[CompanionAtom, ...]
    fails_body: tuple[CompanionAtom, ...]
    not_reached: tuple[CompanionNotReached, ...]
    witness: CompanionWitness | None = None


@dataclass(frozen=True)
class BranchCompanion:
    branch_id: str
    atoms: tuple[CompanionAtomRules, ...]
    branch_body: tuple[CompanionAtom, ...]
    occ_bodies: Mapping[str, tuple[CompanionAtom, ...]]
    bound_defs: Mapping[str, tuple[CompanionAtom, ...]]
    head_body: tuple[CompanionAtom, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "occ_bodies", MappingProxyType(dict(self.occ_bodies)))
        object.__setattr__(self, "bound_defs", MappingProxyType(dict(self.bound_defs)))


@dataclass(frozen=True)
class CompanionProgram:
    anchor: Mapping[str, Const]
    branches: tuple[BranchCompanion, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchor", MappingProxyType(dict(self.anchor)))


def build_companion_program(
    plan: RuleExprLoweringPlan,
    row_bindings: Mapping[str, Any] | None = None,
) -> CompanionProgram:
    if not isinstance(plan, RuleExprLoweringPlan):
        raise DiagnosticProjectionError("plan must be RuleExprLoweringPlan")
    compiled, traces = _materialize_native_derivation_plan(plan)
    branches = _normalize_compiled_body(compiled.body_ir)
    anchor = _anchor_for_row(plan, row_bindings or {})
    companion_branches = tuple(
        _branch_companion(
            lowered_branch=lowered_branch,
            trace=trace,
            atoms=tuple(branch_atoms),
            anchor=anchor,
        )
        for lowered_branch, trace, branch_atoms in zip(plan.branches, traces, branches, strict=True)
    )
    return CompanionProgram(anchor=anchor, branches=companion_branches)


def _branch_companion(
    *,
    lowered_branch: RuleExprLoweringBranch,
    trace: RuleExprEvaluationTrace,
    atoms: tuple[tuple[Any, ...], ...],
    anchor: Mapping[str, Const],
) -> BranchCompanion:
    _reject_deferred_atoms(atoms)
    binder_by_var = _binder_by_var(atoms)
    bound_vars = _required_vars_for_branch(atoms, anchor)
    atom_rules = tuple(
        _atom_rules(
            branch_id=trace.branch_id,
            atom_index=idx,
            atom=atom,
            atoms=atoms,
            anchor=anchor,
            binder_by_var=binder_by_var,
        )
        for idx, atom in enumerate(atoms)
    )
    branch_body = tuple(_positive_atom(atom, anchor) for atom in atoms)
    join_indexes = {join.materialized_condition_index for join in trace.join_materializations}
    head_link_indexes = {link.materialized_condition_index for link in trace.head_port_link_materializations}
    head_indexes = _head_atom_indexes(atoms, join_indexes=join_indexes, head_link_indexes=head_link_indexes)
    occ: dict[str, list[CompanionAtom]] = {alias: [] for alias in lowered_branch.occurrence_aliases}
    for idx, atom in enumerate(atoms):
        if idx in join_indexes or idx in head_link_indexes or idx in head_indexes:
            continue
        if _is_head_atom(atom):
            continue
        alias = _alias_for_atom(atom, lowered_branch.occurrence_aliases)
        if alias is not None:
            occ.setdefault(alias, []).append(_positive_atom(atom, anchor))
    return BranchCompanion(
        branch_id=trace.branch_id,
        atoms=atom_rules,
        branch_body=branch_body,
        head_body=tuple(_positive_atom(atoms[idx], anchor) for idx in sorted(head_indexes)) or None,
        occ_bodies={alias: tuple(body) for alias, body in occ.items()},
        bound_defs={
            var: body
            for var in bound_vars
            if (body := _guard_body((var,), anchor=anchor, binder_by_var=binder_by_var))
        },
    )


def _head_atom_indexes(
    atoms: tuple[tuple[Any, ...], ...],
    *,
    join_indexes: set[int],
    head_link_indexes: set[int],
) -> set[int]:
    out: set[int] = set()
    for idx, atom in enumerate(atoms):
        if idx in join_indexes or idx in head_link_indexes:
            continue
        if _is_head_atom(atom):
            out.add(idx)
    return out


def _atom_rules(
    *,
    branch_id: str,
    atom_index: int,
    atom: tuple[Any, ...],
    atoms: tuple[tuple[Any, ...], ...],
    anchor: Mapping[str, Const],
    binder_by_var: Mapping[str, tuple[Any, ...]],
) -> CompanionAtomRules:
    required = _required_input_vars(atom, anchor)
    guard = _guard_body(required, anchor=anchor, binder_by_var=binder_by_var)
    positive = _positive_atom(atom, anchor)
    negative = _negated_atom(atom, anchor)
    witness = CompanionWitness(tuple(_term(term, anchor) for term in _atom_terms(atom))) if atom[0] == "pred" else None
    return CompanionAtomRules(
        branch_id=branch_id,
        atom_index=atom_index,
        holds_body=(*guard, positive),
        fails_body=(*guard, negative),
        not_reached=tuple(CompanionNotReached(var=var) for var in required),
        witness=witness,
    )


def _anchor_for_row(plan: RuleExprLoweringPlan, row_bindings: Mapping[str, Any]) -> dict[str, Const]:
    seed_names_by_port = probe_seed_vars_by_head_port(plan)
    out: dict[str, Const] = {}
    for port_name, value in row_bindings.items():
        for seed_name in seed_names_by_port.get(str(port_name), ()):
            out[seed_name] = Const(_public_value(value))
    return out


def _public_value(value: Any) -> Any:
    if isinstance(value, Mapping) and "value" in value:
        return value["value"]
    return value


def _guard_body(
    vars_: tuple[str, ...],
    *,
    anchor: Mapping[str, Const],
    binder_by_var: Mapping[str, tuple[Any, ...]],
) -> tuple[CompanionAtom, ...]:
    out: list[CompanionAtom] = []
    seen_atoms: set[int] = set()
    for var in vars_:
        out.extend(_bound_chain(var, anchor=anchor, binder_by_var=binder_by_var, seen_vars=set(), seen_atoms=seen_atoms))
    return tuple(out)


def _required_vars_for_branch(atoms: tuple[tuple[Any, ...], ...], anchor: Mapping[str, Const]) -> tuple[str, ...]:
    found: list[str] = []
    for atom in atoms:
        found.extend(_required_input_vars(atom, anchor))
    return tuple(dict.fromkeys(found))


def _bound_chain(
    var: str,
    *,
    anchor: Mapping[str, Const],
    binder_by_var: Mapping[str, tuple[Any, ...]],
    seen_vars: set[str],
    seen_atoms: set[int],
) -> list[CompanionAtom]:
    if var in anchor or var in seen_vars:
        return []
    seen_vars.add(var)
    binder = binder_by_var.get(var)
    if binder is None:
        return []
    out: list[CompanionAtom] = []
    for dependency in _required_input_vars(binder, anchor):
        out.extend(_bound_chain(dependency, anchor=anchor, binder_by_var=binder_by_var, seen_vars=seen_vars, seen_atoms=seen_atoms))
    key = id(binder)
    if key not in seen_atoms:
        seen_atoms.add(key)
        out.append(_positive_atom(binder, anchor))
    return out


def _binder_by_var(atoms: tuple[tuple[Any, ...], ...]) -> dict[str, tuple[Any, ...]]:
    out: dict[str, tuple[Any, ...]] = {}
    for atom in atoms:
        if atom[0] != "pred":
            continue
        for var in _vars_in_atom(atom):
            out.setdefault(var, atom)
    return out


def _required_input_vars(atom: tuple[Any, ...], anchor: Mapping[str, Const]) -> tuple[str, ...]:
    if atom[0] == "pred":
        terms = _atom_terms(atom)
        if not terms:
            return ()
        return tuple(var for var in _vars_in_atom(terms[0]) if var not in anchor)
    return tuple(var for var in _vars_in_atom(atom) if var not in anchor)


def _positive_atom(atom: tuple[Any, ...], anchor: Mapping[str, Const]) -> CompanionAtom:
    return _companion_atom(atom, anchor, negated=False)


def _negated_atom(atom: tuple[Any, ...], anchor: Mapping[str, Const]) -> CompanionAtom:
    if atom[0] == "not":
        inner = _not_inner_atoms(atom)
        if len(inner) != 1:
            raise DiagnosticProjectionError("not atom companion negation requires exactly one inner atom")
        return _positive_atom(inner[0], anchor)
    if atom[0] == "pred":
        terms = tuple(_term_for_negated_pred(term, anchor) for term in _atom_terms(atom))
        return CompanionLiteral(pred_id=str(atom[1]), terms=terms, negated=True)
    return _companion_atom(atom, anchor, negated=True)


def _companion_atom(atom: tuple[Any, ...], anchor: Mapping[str, Const], *, negated: bool) -> CompanionAtom:
    kind = atom[0]
    if kind == "pred":
        return CompanionLiteral(pred_id=str(atom[1]), terms=tuple(_term(term, anchor) for term in _atom_terms(atom)), negated=negated)
    if kind in {"eq", "ne", "gt", "ge", "lt", "le"}:
        return CompanionCompare(op=str(kind), lhs=_term(atom[1], anchor), rhs=_term(atom[2], anchor), negated=negated)
    if kind == "not":
        inner = _not_inner_atoms(atom)
        if len(inner) != 1:
            raise DiagnosticProjectionError("not atom companion requires exactly one inner atom")
        return _companion_atom(inner[0], anchor, negated=not negated)
    raise DiagnosticProjectionError(f"unsupported atom kind for diagnostic companion: {kind}")


def _term_for_negated_pred(term: Any, anchor: Mapping[str, Const]) -> CompanionTerm:
    if isinstance(term, str) and term.startswith("$") and term not in anchor:
        return Wildcard()
    return _term(term, anchor)


def _term(term: Any, anchor: Mapping[str, Const]) -> CompanionTerm:
    if isinstance(term, str) and term.startswith("$"):
        return anchor.get(term, Var(term))
    return Const(term)


def _atom_terms(atom: tuple[Any, ...]) -> tuple[Any, ...]:
    if atom[0] == "pred":
        terms = atom[2] if len(atom) > 2 else ()
        if not isinstance(terms, (list, tuple)) or isinstance(terms, (str, bytes)):
            return ()
        return tuple(terms)
    if atom[0] in {"eq", "ne", "gt", "ge", "lt", "le"}:
        return (atom[1], atom[2])
    if atom[0] == "not":
        return tuple(_not_inner_atoms(atom))
    return tuple(atom[1:])


def _not_inner_atoms(atom: tuple[Any, ...]) -> tuple[tuple[Any, ...], ...]:
    body = atom[1] if len(atom) > 1 else ()
    if not isinstance(body, list):
        raise DiagnosticProjectionError("not atom body must be lowered list")
    inner: list[tuple[Any, ...]] = []
    for item in body:
        if not _is_atom_tuple(item):
            raise DiagnosticProjectionError("not atom body must contain lowered atoms")
        if item[0] != "pred":
            raise DiagnosticProjectionError("not atom companion only supports EDB predicate bodies")
        inner.append(item)
    return tuple(inner)


def _reject_deferred_atoms(atoms: tuple[tuple[Any, ...], ...]) -> None:
    for atom in atoms:
        if _contains_aggregate(atom):
            raise DiagnosticProjectionError("aggregate terms are not supported by diagnostic companion projection yet")
        if atom and atom[0] in {"ruleref", "rule_ref"}:
            raise DiagnosticProjectionError("ruleref atoms are not supported by diagnostic companion projection yet")


_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}


def _contains_aggregate(value: Any) -> bool:
    if (
        isinstance(value, tuple)
        and len(value) == 3
        and isinstance(value[0], str)
        and value[0] in _AGGREGATE_KINDS
        and isinstance(value[2], list)
    ):
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains_aggregate(item) for item in value)
    return False


def _alias_for_atom(atom: tuple[Any, ...], aliases: tuple[str, ...]) -> str | None:
    variables = _vars_in_atom(atom)
    for alias in aliases:
        prefix = f"${alias}__"
        if any(var.startswith(prefix) for var in variables):
            return alias
    return None


def _is_head_atom(atom: tuple[Any, ...]) -> bool:
    return any(var.startswith("$__head__") for var in _vars_in_atom(atom))


def _vars_in_atom(value: Any) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, str) and value.startswith("$"):
        return (value,)
    if isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_vars_in_atom(item))
    return tuple(dict.fromkeys(found))


def _normalize_compiled_body(body_ir: object) -> list[list[tuple[Any, ...]]]:
    if not isinstance(body_ir, list) or not body_ir:
        raise DiagnosticProjectionError("compiled body_ir must be non-empty list")
    if all(_is_atom_tuple(item) for item in body_ir):
        return [list(body_ir)]  # type: ignore[list-item]
    if all(isinstance(item, list) for item in body_ir):
        return [list(branch) for branch in body_ir]  # type: ignore[list-item]
    raise DiagnosticProjectionError("compiled body_ir must be one-level AND or two-level OR")


def _is_atom_tuple(value: object) -> bool:
    return isinstance(value, tuple) and bool(value) and isinstance(value[0], str)


__all__ = [
    "BranchCompanion",
    "CompanionAtom",
    "CompanionAtomRules",
    "CompanionCompare",
    "CompanionLiteral",
    "CompanionNotReached",
    "CompanionProgram",
    "CompanionTerm",
    "CompanionWitness",
    "DiagnosticProjectionError",
    "Wildcard",
    "build_companion_program",
]
