from __future__ import annotations

from typing import Any, Literal, cast

from factgraph.core.rules.ruleref_types import NativeRuleRefResolution
from factgraph.core.rules.where_eval import (
    AggregateNoValue,
    WhereValidationError,
    _cmp_holds,
    _coerce_arith_int,
    _coerce_cmp_int,
    _exists_not_body,
    _normalize_not_body,
    _resolve_eval_term,
    _where_ast_gate_enabled,
)
from factgraph.core.store._support import (
    NonFactStep,
    PredWitness,
    ProjectedFact,
    ProofReceipt,
    RuleRefEdge,
    WitnessCapture,
    make_non_fact_step_key,
    make_pred_condition_key,
    normalize_asrt_ids,
    normalize_binding_items,
    normalize_detail_items,
)


def build_support_artifact_for_binding(
    *,
    where: list[Any],
    binding: dict[str, Any],
    witness_facts: dict[str, list[ProjectedFact]],
    root_result_kind: str,
    selected_case_index: int,
    rule_ref_edges: tuple[RuleRefEdge, ...] = (),
    capture_witness_metadata: bool = False,
) -> ProofReceipt:
    if not isinstance(capture_witness_metadata, bool):
        raise TypeError("capture_witness_metadata must be bool")
    pred_witnesses: list[PredWitness] = []
    non_fact_steps: list[NonFactStep] = []

    branches = _normalize_where_branches(where)
    branch = _require_selected_branch(branches, selected_case_index)
    for edge in rule_ref_edges:
        if not edge.ruleref_condition_key.startswith(f"c{selected_case_index}."):
            raise WhereValidationError("rule_ref_edges must belong to selected branch")

    for condition_index, atom in enumerate(branch):
        if not isinstance(atom, tuple) or not atom:
            raise WhereValidationError("invalid atom structure")
        kind = atom[0]
        if kind == "pred":
            pred_witnesses.append(
                _build_pred_witness(
                    case_index=selected_case_index,
                    condition_index=condition_index,
                    atom=atom,
                    binding=binding,
                    witness_facts=witness_facts,
                    capture_witness_metadata=capture_witness_metadata,
                )
            )
            continue
        non_fact_steps.append(
            _build_non_fact_step(
                case_index=selected_case_index,
                condition_index=condition_index,
                atom=atom,
                binding=binding,
            )
        )

    return ProofReceipt(
        witness_capture_version=1 if capture_witness_metadata else None,
        kind="native_binding_v1",
        root_result_kind=_validate_root_result_kind(root_result_kind),
        binding_items=normalize_binding_items(binding),
        pred_witnesses=tuple(sorted(pred_witnesses, key=lambda row: row.pred_condition_key)),
        non_fact_steps=tuple(
            sorted(non_fact_steps, key=lambda row: (row.step_key, row.kind, row.status, row.details))
        ),
        rule_refs=tuple(sorted({edge.rule_ref_id for edge in rule_ref_edges})),
        rule_ref_edges=tuple(
            sorted(
                rule_ref_edges,
                key=lambda edge: (
                    edge.ruleref_condition_key,
                    edge.rule_ref_id,
                    edge.rule_ref_version,
                    edge.child_support_digest or "",
                ),
            )
        ),
    )


def derive_rule_ref_edges_for_binding(
    *,
    where: list[Any],
    binding: dict[str, Any],
    rule_ref_resolutions: tuple[NativeRuleRefResolution, ...],
    selected_case_index: int,
) -> tuple[RuleRefEdge, ...]:
    resolution_by_key = {row.ruleref_condition_key: row for row in rule_ref_resolutions}
    edges: list[RuleRefEdge] = []
    branches = _normalize_where_branches(where)
    branch = _require_selected_branch(branches, selected_case_index)

    for condition_index, atom in enumerate(branch):
        if not isinstance(atom, tuple) or not atom or atom[0] != "ruleref":
            continue
        ruleref_condition_key = make_non_fact_step_key(selected_case_index, condition_index, "ruleref")
        resolution = resolution_by_key.get(ruleref_condition_key)
        if resolution is None:
            raise WhereValidationError(f"missing rule_ref_resolution for {ruleref_condition_key}")
        grounded = _ground_terms(atom[3], binding, error_message="ruleref atom terms must be list")
        if grounded is None:
            raise WhereValidationError(f"selected branch contains ungroundable ruleref: {ruleref_condition_key}")
        matches = [row for row in resolution.row_supports if row.row_terms == grounded]
        if not matches:
            raise WhereValidationError(f"selected branch lacks row_support match for {ruleref_condition_key}")
        if len(matches) > 1:
            raise WhereValidationError(f"multiple row_support matches for {ruleref_condition_key}")
        row_support = matches[0]
        edges.append(
            RuleRefEdge(
                ruleref_condition_key=ruleref_condition_key,
                rule_ref_id=resolution.rule_ref_id,
                rule_ref_version=resolution.rule_ref_version,
                child_support_digest=row_support.child_support_digest,
                unresolved_reason=row_support.unresolved_reason,
            )
        )

    return tuple(
        sorted(
            edges,
            key=lambda edge: (
                edge.ruleref_condition_key,
                edge.rule_ref_id,
                edge.rule_ref_version,
                edge.child_support_digest or "",
            ),
        )
    )


def find_winning_case_index(
    *,
    where: list[Any],
    binding: dict[str, Any],
    witness_facts: dict[str, list[ProjectedFact]],
    rule_ref_resolutions: tuple[NativeRuleRefResolution, ...],
) -> int:
    branches = _normalize_where_branches(where)
    resolution_by_key = {row.ruleref_condition_key: row for row in rule_ref_resolutions}
    view_facts = _view_facts_from_witness_facts(witness_facts)
    ast_gate_on = _where_ast_gate_enabled()
    for case_index, branch in enumerate(branches):
        if _branch_satisfies(
            case_index=case_index,
            branch=branch,
            binding=binding,
            witness_facts=witness_facts,
            view_facts=view_facts,
            resolution_by_key=resolution_by_key,
            ast_gate_on=ast_gate_on,
        ):
            return case_index
    raise WhereValidationError("no satisfying branch for final binding")


def find_matching_case_indexes(
    *,
    where: list[Any],
    binding: dict[str, Any],
    witness_facts: dict[str, list[ProjectedFact]],
    rule_ref_resolutions: tuple[NativeRuleRefResolution, ...],
) -> tuple[int, ...]:
    """Return every satisfied DNF case for one final binding.

    The existing public Check/Explain behavior intentionally keeps using
    :func:`find_winning_case_index`.  Product V2 branch-witness capture opts
    into this complete inventory before result-row de-duplication so two
    independent proof paths for the same projected row are not collapsed.
    """

    branches = _normalize_where_branches(where)
    resolution_by_key = {row.ruleref_condition_key: row for row in rule_ref_resolutions}
    view_facts = _view_facts_from_witness_facts(witness_facts)
    ast_gate_on = _where_ast_gate_enabled()
    return tuple(
        case_index
        for case_index, branch in enumerate(branches)
        if _branch_satisfies(
            case_index=case_index,
            branch=branch,
            binding=binding,
            witness_facts=witness_facts,
            view_facts=view_facts,
            resolution_by_key=resolution_by_key,
            ast_gate_on=ast_gate_on,
        )
    )


def _build_pred_witness(
    *,
    case_index: int,
    condition_index: int,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    witness_facts: dict[str, list[ProjectedFact]],
    capture_witness_metadata: bool,
) -> PredWitness:
    _, pred_id, terms = atom
    if not isinstance(pred_id, str) or not pred_id:
        raise WhereValidationError("pred atom pred_id must be non-empty string")
    grounded_terms = _ground_terms(terms, binding, error_message="pred atom terms must be list")
    if grounded_terms is None:
        raise WhereValidationError(f"selected branch contains ungroundable pred atom: {pred_id}")

    matches: dict[str, WitnessCapture] = {}
    for projected in witness_facts.get(pred_id, []):
        if tuple(projected.fact_tuple) == grounded_terms:
            item = WitnessCapture(
                witness_ref=projected.asrt_id,
                kind=projected.witness_kind,
                predicate_id=pred_id,
                terms=tuple(projected.fact_tuple),
            )
            previous = matches.setdefault(projected.asrt_id, item)
            if previous != item:
                raise WhereValidationError("conflicting captured witness metadata")
    if not matches:
        raise WhereValidationError(f"selected branch lacks predicate witness for {pred_id}")

    return PredWitness(
        pred_condition_key=make_pred_condition_key(case_index, condition_index, pred_id),
        asrt_ids=normalize_asrt_ids(tuple(matches)),
        witnesses=tuple(matches[ref] for ref in sorted(matches)) if capture_witness_metadata else None,
    )


def _build_non_fact_step(
    *,
    case_index: int,
    condition_index: int,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
) -> NonFactStep:
    kind = atom[0]
    status = "satisfied"
    details = normalize_detail_items(
        {
            "atom_repr": repr(atom),
            "binding": [[key, value] for key, value in normalize_binding_items(binding)],
        }
    )

    if kind == "not":
        status = "no_match"

    return NonFactStep(
        step_key=make_non_fact_step_key(case_index, condition_index, str(kind)),
        kind=str(kind),
        status=status,
        details=details,
    )


def _normalize_where_branches(where: list[Any]) -> list[list[tuple[Any, ...]]]:
    if not isinstance(where, list) or not where:
        raise WhereValidationError("where must be non-empty list")
    if all(isinstance(item, tuple) for item in where):
        return [list(where)]
    if all(isinstance(item, list) for item in where):
        out: list[list[tuple[Any, ...]]] = []
        for branch in where:
            if not isinstance(branch, list) or not all(isinstance(atom, tuple) for atom in branch):
                raise WhereValidationError("where OR branch must contain atom tuples")
            out.append(list(branch))
        return out
    raise WhereValidationError("where must be one-level AND or two-level OR-of-AND")


def _branch_satisfies(
    *,
    case_index: int,
    branch: list[tuple[Any, ...]],
    binding: dict[str, Any],
    witness_facts: dict[str, list[ProjectedFact]],
    view_facts: dict[str, list[tuple[Any, ...]]],
    resolution_by_key: dict[str, NativeRuleRefResolution],
    ast_gate_on: bool,
) -> bool:
    for condition_index, atom in enumerate(branch):
        if not _atom_satisfies(
            case_index=case_index,
            condition_index=condition_index,
            atom=atom,
            binding=binding,
            witness_facts=witness_facts,
            view_facts=view_facts,
            resolution_by_key=resolution_by_key,
            ast_gate_on=ast_gate_on,
        ):
            return False
    return True


def _atom_satisfies(
    *,
    case_index: int,
    condition_index: int,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    witness_facts: dict[str, list[ProjectedFact]],
    view_facts: dict[str, list[tuple[Any, ...]]],
    resolution_by_key: dict[str, NativeRuleRefResolution],
    ast_gate_on: bool,
) -> bool:
    kind = atom[0]
    if kind == "pred":
        return _pred_atom_satisfies(atom=atom, binding=binding, witness_facts=witness_facts)
    if kind == "ruleref":
        return _ruleref_atom_satisfies(
            case_index=case_index,
            condition_index=condition_index,
            atom=atom,
            binding=binding,
            resolution_by_key=resolution_by_key,
        )
    if kind == "eq":
        return _eq_atom_satisfies(atom=atom, binding=binding, view_facts=view_facts, ast_gate_on=ast_gate_on)
    if kind == "in":
        return _in_atom_satisfies(atom=atom, binding=binding)
    if kind == "ne":
        return _ne_atom_satisfies(atom=atom, binding=binding, view_facts=view_facts, ast_gate_on=ast_gate_on)
    if kind in {"gt", "ge", "lt", "le"}:
        return _cmp_atom_satisfies(atom=atom, binding=binding, view_facts=view_facts, ast_gate_on=ast_gate_on)
    if kind in {"add", "sub", "neg", "addc", "mulc"}:
        return _arith_atom_satisfies(atom=atom, binding=binding, view_facts=view_facts, ast_gate_on=ast_gate_on)
    if kind == "not":
        return _not_atom_satisfies(atom=atom, binding=binding, view_facts=view_facts)
    raise WhereValidationError(f"unsupported atom kind in support capture: {kind}")


def _pred_atom_satisfies(
    *,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    witness_facts: dict[str, list[ProjectedFact]],
) -> bool:
    _, pred_id, terms = atom
    if not isinstance(pred_id, str) or not pred_id:
        raise WhereValidationError("pred atom pred_id must be non-empty string")
    grounded_terms = _ground_terms(terms, binding, error_message="pred atom terms must be list")
    if grounded_terms is None:
        return False
    return any(tuple(projected.fact_tuple) == grounded_terms for projected in witness_facts.get(pred_id, ()))


def _ruleref_atom_satisfies(
    *,
    case_index: int,
    condition_index: int,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    resolution_by_key: dict[str, NativeRuleRefResolution],
) -> bool:
    if len(atom) != 4:
        raise WhereValidationError("ruleref atom must be ('ruleref', rule_id, version, [terms...])")
    ruleref_condition_key = make_non_fact_step_key(case_index, condition_index, "ruleref")
    resolution = resolution_by_key.get(ruleref_condition_key)
    if resolution is None:
        raise WhereValidationError(f"missing rule_ref_resolution for {ruleref_condition_key}")
    grounded = _ground_terms(atom[3], binding, error_message="ruleref atom terms must be list")
    if grounded is None:
        return False
    matches = [row for row in resolution.row_supports if row.row_terms == grounded]
    if len(matches) > 1:
        raise WhereValidationError(f"multiple row_support matches for {ruleref_condition_key}")
    return len(matches) == 1


def _eq_atom_satisfies(
    *,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    view_facts: dict[str, list[tuple[Any, ...]]],
    ast_gate_on: bool,
) -> bool:
    _, lhs, rhs = atom
    lhs_known, lhs_value = _resolve_eval_term(binding, lhs, view_facts, ast_gate_on=ast_gate_on)
    rhs_known, rhs_value = _resolve_eval_term(binding, rhs, view_facts, ast_gate_on=ast_gate_on)
    if lhs_value is AggregateNoValue or rhs_value is AggregateNoValue:
        return False
    return lhs_known and rhs_known and lhs_value == rhs_value


def _in_atom_satisfies(*, atom: tuple[Any, ...], binding: dict[str, Any]) -> bool:
    _, var, values = atom
    if not isinstance(values, list):
        raise WhereValidationError("in atom values must be list")
    return isinstance(var, str) and var in binding and binding[var] in set(values)


def _ne_atom_satisfies(
    *,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    view_facts: dict[str, list[tuple[Any, ...]]],
    ast_gate_on: bool,
) -> bool:
    _, lhs, rhs = atom
    lhs_known, lhs_value = _resolve_eval_term(binding, lhs, view_facts, ast_gate_on=ast_gate_on)
    rhs_known, rhs_value = _resolve_eval_term(binding, rhs, view_facts, ast_gate_on=ast_gate_on)
    if lhs_value is AggregateNoValue or rhs_value is AggregateNoValue:
        return False
    return lhs_known and rhs_known and lhs_value != rhs_value


def _cmp_atom_satisfies(
    *,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    view_facts: dict[str, list[tuple[Any, ...]]],
    ast_gate_on: bool,
) -> bool:
    kind, lhs, rhs = atom
    lhs_known, lhs_value_raw = _resolve_eval_term(binding, lhs, view_facts, ast_gate_on=ast_gate_on)
    rhs_known, rhs_value_raw = _resolve_eval_term(binding, rhs, view_facts, ast_gate_on=ast_gate_on)
    if lhs_value_raw is AggregateNoValue or rhs_value_raw is AggregateNoValue:
        return False
    if not lhs_known or not rhs_known:
        return False
    lhs_value = _coerce_cmp_int(lhs_value_raw, kind)
    rhs_value = _coerce_cmp_int(rhs_value_raw, kind)
    return _cmp_holds(kind, lhs_value, rhs_value)


def _arith_atom_satisfies(
    *,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    view_facts: dict[str, list[tuple[Any, ...]]],
    ast_gate_on: bool,
) -> bool:
    kind = atom[0]
    z = atom[1]
    if not isinstance(z, str) or z not in binding:
        return False

    if kind == "add":
        _, _, x, y = atom
        xv = _resolved_arith_value(binding, x, kind, view_facts=view_facts, ast_gate_on=ast_gate_on)
        yv = _resolved_arith_value(binding, y, kind, view_facts=view_facts, ast_gate_on=ast_gate_on)
        if xv is None or yv is None:
            return False
        result = xv + yv
    elif kind == "sub":
        _, _, x, y = atom
        xv = _resolved_arith_value(binding, x, kind, view_facts=view_facts, ast_gate_on=ast_gate_on)
        yv = _resolved_arith_value(binding, y, kind, view_facts=view_facts, ast_gate_on=ast_gate_on)
        if xv is None or yv is None:
            return False
        result = xv - yv
    elif kind == "neg":
        _, _, x = atom
        xv = _resolved_arith_value(binding, x, kind, view_facts=view_facts, ast_gate_on=ast_gate_on)
        if xv is None:
            return False
        result = -xv
    elif kind == "addc":
        _, _, x, c = atom
        xv = _resolved_arith_value(binding, x, kind, view_facts=view_facts, ast_gate_on=ast_gate_on)
        if xv is None:
            return False
        result = xv + _coerce_arith_int(c, kind)
    elif kind == "mulc":
        _, _, x, c = atom
        xv = _resolved_arith_value(binding, x, kind, view_facts=view_facts, ast_gate_on=ast_gate_on)
        if xv is None:
            return False
        result = xv * _coerce_arith_int(c, kind)
    else:
        raise WhereValidationError(f"unsupported arithmetic atom kind: {kind}")

    return _coerce_arith_int(binding[z], kind) == result


def _not_atom_satisfies(
    *,
    atom: tuple[Any, ...],
    binding: dict[str, Any],
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> bool:
    _, not_body = atom
    not_branches = _normalize_not_body(not_body)
    return not _exists_not_body(view_facts, dict(binding), not_branches, ast_gate_on=True)


def _resolved_arith_value(
    binding: dict[str, Any],
    term: Any,
    kind: str,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    ast_gate_on: bool,
) -> int | None:
    known, value = _resolve_eval_term(binding, term, view_facts, ast_gate_on=ast_gate_on)
    if value is AggregateNoValue:
        return None
    if not known:
        return None
    return _coerce_arith_int(value, kind)


def _ground_terms(
    terms: Any,
    binding: dict[str, Any],
    *,
    error_message: str,
) -> tuple[Any, ...] | None:
    if not isinstance(terms, list):
        raise WhereValidationError(error_message)
    grounded: list[Any] = []
    for term in terms:
        if isinstance(term, str) and term.startswith("$"):
            if term not in binding:
                return None
            grounded.append(binding[term])
            continue
        grounded.append(term)
    return tuple(grounded)


def _view_facts_from_witness_facts(
    witness_facts: dict[str, list[ProjectedFact]],
) -> dict[str, list[tuple[Any, ...]]]:
    view_facts: dict[str, list[tuple[Any, ...]]] = {}
    for pred_id, rows in witness_facts.items():
        facts: list[tuple[Any, ...]] = []
        for projected in rows:
            if not isinstance(projected, ProjectedFact):
                raise WhereValidationError(f"witness_facts[{pred_id!r}] must contain ProjectedFact rows")
            facts.append(tuple(projected.fact_tuple))
        view_facts[pred_id] = facts
    return view_facts


def _require_selected_branch(
    branches: list[list[tuple[Any, ...]]],
    selected_case_index: int,
) -> list[tuple[Any, ...]]:
    if isinstance(selected_case_index, bool) or not isinstance(selected_case_index, int):
        raise WhereValidationError("selected_case_index must be int")
    if selected_case_index < 0 or selected_case_index >= len(branches):
        raise WhereValidationError("selected_case_index out of range")
    return branches[selected_case_index]


def _validate_root_result_kind(value: str) -> Literal["fact", "entity", "row"]:
    if value not in {"fact", "entity", "row"}:
        raise WhereValidationError("root_result_kind must be 'fact', 'entity', or 'row'")
    return cast(Literal["fact", "entity", "row"], value)


__all__ = [
    "build_support_artifact_for_binding",
    "derive_rule_ref_edges_for_binding",
    "find_matching_case_indexes",
    "find_winning_case_index",
]
