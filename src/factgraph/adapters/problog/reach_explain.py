from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from factgraph.adapters.problog._parsing import _split_top_level_args
from factgraph.adapters.problog.diagnostic_emit import (
    DiagnosticAtomProbability,
    DiagnosticProbLogResult,
    DiagnosticWitnessProbability,
)
from factgraph.adapters.problog.engine_eval import resolve_problog_timeout
from factgraph.adapters.problog.problog_engine import run_problog
from factgraph.adapters.problog.problog_export import (
    _claim_probability,
    _claim_value_term,
    _format_probability,
    _to_problog_literal,
    _to_problog_var,
)
from factgraph.application.explain.diagnostic_assemble import (
    diagnostic_problog_result_to_evidence_graph,
)
from factgraph.application.explain.diagnostic_projection import BranchCompanion, CompanionProgram
from factgraph.application.explain.evidence_tree import EvidenceGraph
from factgraph.application.protocol.certainty import Certainty
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprLoweringPlan,
    _materialize_adapter_derivation_plan,
    probe_seed_vars_by_head_port,
    transitively_expand_seed,
)
from factgraph.core.rules.where_ast import Const
from factgraph.core.view.projector import project_view_facts


class ProbLogReachExplainError(Exception):
    pass


class ProbLogReachExplainUnsupported(ProbLogReachExplainError):
    pass


@dataclass(frozen=True)
class _ReachRelation:
    name: str
    branch_id: str
    atom_index: int
    columns: tuple[str, ...]


@dataclass(frozen=True)
class _BranchReachPlan:
    branch_id: str
    atoms: tuple[tuple[Any, ...], ...]
    reaches: tuple[_ReachRelation, ...]
    seed_vars: tuple[str, ...]
    seed_values: Mapping[str, Any]
    occurrence_last_atoms: Mapping[str, int]


@dataclass(frozen=True)
class _ReachProgram:
    text: str
    branches: tuple[_BranchReachPlan, ...]
    seed_vars: tuple[str, ...]
    seed_values: Mapping[str, Any]


@dataclass(frozen=True)
class _AnswerRow:
    name: str
    args: tuple[Any, ...]
    probability: float


def problog_reach_explain_to_evidence_graph(
    store: Any,
    *,
    plan: RuleExprLoweringPlan,
    row_bindings: Mapping[str, Any],
    graph_id: str,
    engine: str,
    schema_index: object | None,
    rules_by_id: Mapping[str, Any],
    subject_binding: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
    graph_certainty: Certainty | None = None,
    uncertainty_projection: Mapping[str, Any] | None = None,
    engine_options: Mapping[str, Any] | None = None,
    input_certainty_for_goal: Any | None = None,
) -> EvidenceGraph:
    program = _build_reach_program(
        store,
        plan,
        row_bindings,
        uncertainty_projection=uncertainty_projection,
    )
    timeout = resolve_problog_timeout(dict(engine_options or {}))
    result = _run_reach_program(program, timeout=timeout)
    companion = CompanionProgram(
        anchor={key: Const(value) for key, value in program.seed_values.items()},
        branches=tuple(
            BranchCompanion(
                branch_id=branch.branch_id,
                atoms=(),
                branch_body=(),
                occ_bodies={},
                bound_defs={},
            )
            for branch in program.branches
        ),
    )
    view_facts = project_view_facts(store.ledger, store.schema_ir)
    return diagnostic_problog_result_to_evidence_graph(
        result,
        plan=plan,
        companion=companion,
        graph_id=graph_id,
        engine=engine,
        view_facts=view_facts,
        schema_index=schema_index,
        rules_by_id=rules_by_id,
        subject_binding=subject_binding,
        metadata=metadata,
        graph_certainty=graph_certainty,
        input_certainty_for_goal=input_certainty_for_goal,
    )


def _build_reach_program(
    store: Any,
    plan: RuleExprLoweringPlan,
    row_bindings: Mapping[str, Any],
    *,
    uncertainty_projection: Mapping[str, Any] | None,
) -> _ReachProgram:
    if not isinstance(plan, RuleExprLoweringPlan):
        raise ProbLogReachExplainError("plan must be RuleExprLoweringPlan")
    compiled, traces = _materialize_adapter_derivation_plan(plan, engine="problog")
    branches = _normalize_compiled_body(compiled.body_ir)
    if len(branches) != len(plan.branches):
        raise ProbLogReachExplainError("materialized branch count does not match lowering plan")
    seed_values = _seed_values_for_row(plan, row_bindings)
    seed_values = transitively_expand_seed(seed_values, branches)
    if not seed_values:
        raise ProbLogReachExplainUnsupported("problog reach explain requires at least one row seed binding")

    lines = _fact_lines(store, uncertainty_projection=uncertainty_projection)
    if lines:
        lines.append("")

    branch_plans: list[_BranchReachPlan] = []
    for branch_index, atoms in enumerate(branches):
        branch_id = plan.branches[branch_index].branch_id
        branch_seed_values = _branch_seed_values(seed_values, atoms)
        branch_plan, branch_lines = _emit_branch_reaches(
            branch_id=branch_id,
            atoms=tuple(atoms),
            seed_values=branch_seed_values,
            occurrence_last_atoms=_occurrence_last_atoms(tuple(atoms), plan.branches[branch_index], traces[branch_index]),
        )
        branch_plans.append(branch_plan)
        lines.extend(branch_lines)

    query_lines: list[str] = []
    for branch in branch_plans:
        for reach in branch.reaches:
            query_lines.append(f"query({_call(reach.name, reach.columns)}).")
    lines.extend(query_lines)
    return _ReachProgram(
        text="\n".join(lines).rstrip() + "\n",
        branches=tuple(branch_plans),
        seed_vars=tuple(sorted(seed_values)),
        seed_values=seed_values,
    )


def _fact_lines(store: Any, *, uncertainty_projection: Mapping[str, Any] | None) -> list[str]:
    projection = None if uncertainty_projection is None else dict(uncertainty_projection)
    active_claims = [
        claim
        for claim in store.ledger.claims
        if not store.ledger.has_active_revocation(claim.asrt_id)
    ]
    active_claims.sort(key=lambda row: row.asrt_id)
    lines = [
        "% generated by factpy problog reach explain",
        "edb_fact(_, _, _, _) :- fail.",
    ]
    for claim in active_claims:
        prob = _claim_probability(store, claim.asrt_id, uncertainty_projection=projection)
        value_term = _claim_value_term(claim.rest_terms)
        lines.append(
            f"{_format_probability(prob)}::edb_fact("
            f"{_to_problog_literal(claim.asrt_id)}, "
            f"{_to_problog_literal(claim.pred_id)}, "
            f"{_to_problog_literal(claim.e_ref)}, "
            f"{value_term}"
            ")."
        )
    return lines


def _emit_branch_reaches(
    *,
    branch_id: str,
    atoms: tuple[tuple[Any, ...], ...],
    seed_values: Mapping[str, Any],
    occurrence_last_atoms: Mapping[str, int],
) -> tuple[_BranchReachPlan, list[str]]:
    if not atoms:
        raise ProbLogReachExplainUnsupported("reach explain requires non-empty branch bodies")
    seed_vars = tuple(sorted(seed_values))
    seed_name = f"fg_reach_seed_{_safe_suffix(branch_id)}"
    seed_args = ", ".join(_to_problog_literal(seed_values[var]) for var in seed_vars)
    lines = [f"{seed_name}({seed_args})."]
    reaches: list[_ReachRelation] = []
    bound_vars = list(seed_vars)
    previous_name = seed_name
    previous_columns = seed_vars
    for atom_index, atom in enumerate(atoms):
        _ensure_supported_atom(atom)
        next_bound_vars = list(bound_vars)
        atom_clause = _compile_reach_atom(
            atom,
            bound_vars=set(bound_vars),
            next_bound_vars=next_bound_vars,
        )
        reach_name = f"fg_reach_{_safe_suffix(branch_id)}_{atom_index}"
        columns = tuple(next_bound_vars)
        lines.append(
            f"{_call(reach_name, columns)} :- "
            f"{_call(previous_name, previous_columns)}, {atom_clause}."
        )
        reaches.append(
            _ReachRelation(
                name=reach_name,
                branch_id=branch_id,
                atom_index=atom_index,
                columns=columns,
            )
        )
        bound_vars = next_bound_vars
        previous_name = reach_name
        previous_columns = columns
    return _BranchReachPlan(
        branch_id=branch_id,
        atoms=atoms,
        reaches=tuple(reaches),
        seed_vars=seed_vars,
        seed_values=dict(seed_values),
        occurrence_last_atoms=dict(occurrence_last_atoms),
    ), [*lines, ""]


def _compile_reach_atom(
    atom: tuple[Any, ...],
    *,
    bound_vars: set[str],
    next_bound_vars: list[str],
) -> str:
    kind = atom[0]
    if kind == "pred":
        if len(atom) != 3 or not isinstance(atom[2], list):
            raise ProbLogReachExplainUnsupported("pred atom must be ('pred', pred_id, [terms...])")
        pred_id = str(atom[1])
        terms = atom[2]
        if len(terms) == 1:
            args = ["_", _to_problog_literal(pred_id), _term_for_call(terms[0]), "_"]
        elif len(terms) == 2:
            args = ["_", _to_problog_literal(pred_id), _term_for_call(terms[0]), _term_for_call(terms[1])]
        else:
            raise ProbLogReachExplainUnsupported(f"pred atom arity > 2 is not supported: {pred_id}")
        for term in terms:
            if _is_var(term) and term not in next_bound_vars:
                next_bound_vars.append(term)
        return f"edb_fact({', '.join(args)})"
    if kind in {"eq", "ne", "gt", "ge", "lt", "le"}:
        return _compile_compare(kind, atom[1], atom[2], bound_vars=bound_vars, next_bound_vars=next_bound_vars)
    if kind == "not":
        inner = _simple_not_inner(atom)
        _require_bound_vars(inner, bound_vars)
        inner_clause = _compile_reach_atom(inner, bound_vars=bound_vars, next_bound_vars=list(next_bound_vars))
        return f"\\+({inner_clause})"
    raise ProbLogReachExplainUnsupported(f"unsupported materialized atom kind for problog reach explain: {kind}")


def _compile_compare(
    kind: str,
    lhs: Any,
    rhs: Any,
    *,
    bound_vars: set[str],
    next_bound_vars: list[str],
) -> str:
    lhs_var = _is_var(lhs)
    rhs_var = _is_var(rhs)
    if kind == "eq":
        if lhs_var and lhs not in bound_vars and not rhs_var:
            next_bound_vars.append(lhs)
        elif rhs_var and rhs not in bound_vars and not lhs_var:
            next_bound_vars.append(rhs)
        elif lhs_var and rhs_var and lhs in bound_vars and rhs not in bound_vars:
            next_bound_vars.append(rhs)
        elif lhs_var and rhs_var and rhs in bound_vars and lhs not in bound_vars:
            next_bound_vars.append(lhs)
    _require_compare_bound(kind, lhs, rhs, bound_vars=set(next_bound_vars))
    op = {"eq": "=", "ne": "\\=", "gt": ">", "ge": ">=", "lt": "<", "le": "=<"}[kind]
    return f"{_term_for_compare(lhs)} {op} {_term_for_compare(rhs)}"


def _run_reach_program(program: _ReachProgram, *, timeout: int) -> DiagnosticProbLogResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "problog_reach.pl"
        path.write_text(program.text, encoding="utf-8", newline="\n")
        raw = run_problog(path, timeout=timeout, trace=False)
    answers = _parse_answers(raw)
    return _parse_reach_answers(answers, program)


def _parse_answers(raw_output: str) -> list[_AnswerRow]:
    rows: list[_AnswerRow] = []
    for raw_line in raw_output.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        query, raw_prob = line.rsplit(":", 1)
        try:
            probability = float(raw_prob.strip())
        except ValueError:
            continue
        name, args = _parse_query(query.strip())
        rows.append(_AnswerRow(name=name, args=tuple(args), probability=probability))
    rows.sort(key=lambda row: (row.name, row.args, row.probability))
    return rows


def _parse_reach_answers(answers: Sequence[_AnswerRow], program: _ReachProgram) -> DiagnosticProbLogResult:
    by_name: dict[str, list[_AnswerRow]] = {}
    for answer in answers:
        by_name.setdefault(answer.name, []).append(answer)

    atoms: list[DiagnosticAtomProbability] = []
    witnesses: list[DiagnosticWitnessProbability] = []
    branches: dict[str, float] = {}
    occurrences: dict[tuple[str, str], float] = {}
    for branch in program.branches:
        previous_rows: list[dict[str, Any]] = [_seed_row(branch.seed_values)]
        reach_matches: dict[int, list[tuple[dict[str, Any], float]]] = {}
        failed_at: int | None = None
        failure_row: dict[str, Any] | None = None
        for reach in branch.reaches:
            rows = [
                (_row_to_mapping(reach.columns, answer.args), answer.probability)
                for answer in by_name.get(reach.name, ())
                if answer.probability > 0.0
            ]
            matching = _matching_rows(rows, branch.seed_values)
            if matching:
                reach_matches[reach.atom_index] = matching
                previous_rows = [row for row, _prob in matching]
                continue
            failed_at = reach.atom_index
            failure_row = previous_rows[0] if previous_rows else None
            break

        if failed_at is None and branch.reaches:
            terminal = _best_row(reach_matches.get(branch.reaches[-1].atom_index, ()))
            terminal_prob = _best_probability(reach_matches.get(branch.reaches[-1].atom_index, ()))
            for reach in branch.reaches:
                prob = _best_probability(reach_matches.get(reach.atom_index, ())) or terminal_prob or 1.0
                atoms.append(DiagnosticAtomProbability(reach.branch_id, reach.atom_index, "holds", prob))
                _append_witness(
                    witnesses,
                    branch_id=reach.branch_id,
                    atom_index=reach.atom_index,
                    atom=branch.atoms[reach.atom_index],
                    row=terminal,
                    probability=prob,
                )
            if terminal_prob is not None:
                branches[branch.branch_id] = terminal_prob
            # Per-occurrence OWN marginal. The reach query yields the CUMULATIVE
            # path-prefix WMC at each occurrence's last atom; divide by the prior
            # occurrence's cumulative so each occurrence reports only its own
            # contribution (own_1 × own_2 × … = the branch WMC) instead of the
            # running product of every occurrence before it. A shared probabilistic
            # fact, already counted upstream, leaves the later occurrence at a 1.0
            # marginal (it adds nothing new). Occurrences are visited in atom order.
            prev_cumulative = 1.0
            for alias, atom_index in sorted(branch.occurrence_last_atoms.items(), key=lambda item: item[1]):
                cumulative = _best_probability(reach_matches.get(atom_index, ()))
                if cumulative is None:
                    continue
                own = cumulative / prev_cumulative if prev_cumulative else cumulative
                occurrences[(branch.branch_id, alias)] = own
                prev_cumulative = cumulative
            continue

        prefix_row = failure_row
        for atom_index, atom in enumerate(branch.atoms):
            if failed_at is not None and atom_index < failed_at:
                prob = _best_probability(reach_matches.get(atom_index, ())) or 1.0
                atoms.append(DiagnosticAtomProbability(branch.branch_id, atom_index, "holds", prob))
                _append_witness(
                    witnesses,
                    branch_id=branch.branch_id,
                    atom_index=atom_index,
                    atom=atom,
                    row=prefix_row,
                    probability=prob,
                )
                continue
            if failed_at is not None and atom_index == failed_at:
                atoms.append(DiagnosticAtomProbability(branch.branch_id, atom_index, "fails", 1.0))
                _append_witness(
                    witnesses,
                    branch_id=branch.branch_id,
                    atom_index=atom_index,
                    atom=atom,
                    row=prefix_row,
                    probability=1.0,
                )
                continue
            atoms.append(
                DiagnosticAtomProbability(
                    branch.branch_id,
                    atom_index,
                    "not_reached",
                    1.0,
                    blocked_by="upstream",
                )
            )
    return DiagnosticProbLogResult(
        atom_probabilities=tuple(atoms),
        witnesses=tuple(witnesses),
        branch_probabilities=branches,
        occurrence_probabilities=occurrences,
    )


def _append_witness(
    witnesses: list[DiagnosticWitnessProbability],
    *,
    branch_id: str,
    atom_index: int,
    atom: tuple[Any, ...],
    row: Mapping[str, Any] | None,
    probability: float,
) -> None:
    if row is None:
        return
    terms = _witness_terms(atom, row)
    if terms is None:
        return
    witnesses.append(DiagnosticWitnessProbability(branch_id, atom_index, terms, probability))


def _witness_terms(atom: tuple[Any, ...], row: Mapping[str, Any]) -> tuple[Any, ...] | None:
    if atom[0] == "pred":
        terms = atom[2] if len(atom) > 2 else ()
        if not isinstance(terms, list):
            return None
        out: list[Any] = []
        for term in terms:
            if _is_var(term):
                value = row.get(term)
                if value is None:
                    return None
                out.append(value)
            else:
                out.append(term)
        return tuple(out)
    if atom[0] in {"eq", "ne", "gt", "ge", "lt", "le"}:
        return (_resolve_term(atom[1], row), _resolve_term(atom[2], row))
    return None


def _parse_query(query: str) -> tuple[str, list[Any]]:
    name, sep, rest = query.partition("(")
    if not sep or not rest.endswith(")"):
        return query.strip(), []
    return name.strip(), [_parse_term(arg) for arg in _split_top_level_args(rest[:-1])]


def _parse_term(raw: str) -> Any:
    text = raw.strip()
    if len(text) >= 2 and text[0] == "'" and text[-1] == "'":
        return text[1:-1].replace("''", "'").replace("\\\\", "\\")
    if text in {"true", "false"}:
        return text == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _row_to_mapping(columns: Sequence[str], row: Sequence[Any]) -> dict[str, Any]:
    return {column: value for column, value in zip(columns, row, strict=False)}


def _matching_rows(
    rows: Sequence[tuple[Mapping[str, Any], float]],
    seed_values: Mapping[str, Any],
) -> list[tuple[dict[str, Any], float]]:
    out = [
        (dict(row), probability)
        for row, probability in rows
        if all(str(row.get(seed_var)) == str(seed_value) for seed_var, seed_value in seed_values.items())
    ]
    out.sort(key=lambda item: (-item[1], tuple((key, item[0][key]) for key in sorted(item[0]))))
    return out


def _best_row(rows: Sequence[tuple[Mapping[str, Any], float]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return dict(rows[0][0])


def _best_probability(rows: Sequence[tuple[Mapping[str, Any], float]]) -> float | None:
    if not rows:
        return None
    return rows[0][1]


def _seed_row(seed_values: Mapping[str, Any]) -> dict[str, Any]:
    return dict(seed_values)


def _seed_values_for_row(plan: RuleExprLoweringPlan, row_bindings: Mapping[str, Any]) -> dict[str, Any]:
    seed_names_by_port = probe_seed_vars_by_head_port(plan)
    out: dict[str, Any] = {}
    for port_name, value in row_bindings.items():
        for seed_name in seed_names_by_port.get(str(port_name), ()):
            out[seed_name] = _public_value(value)
    return out


def _branch_seed_values(seed_values: Mapping[str, Any], atoms: Sequence[tuple[Any, ...]]) -> dict[str, Any]:
    branch_vars: set[str] = set()
    for atom in atoms:
        branch_vars.update(_vars_in_atom(atom))
    out = {seed_var: value for seed_var, value in seed_values.items() if seed_var in branch_vars}
    if not out:
        raise ProbLogReachExplainUnsupported("reach explain branch has no row seed variable")
    return out


def _occurrence_last_atoms(
    atoms: tuple[tuple[Any, ...], ...],
    lowered_branch: Any,
    trace: Any,
) -> dict[str, int]:
    join_indexes = {
        int(item.materialized_condition_index)
        for item in getattr(trace, "join_materializations", ())
    }
    head_link_indexes = {
        int(item.materialized_condition_index)
        for item in getattr(trace, "head_port_link_materializations", ())
    }
    aliases = tuple(getattr(lowered_branch, "occurrence_aliases", ()))
    out: dict[str, int] = {}
    for idx, atom in enumerate(atoms):
        if idx in join_indexes or idx in head_link_indexes or _is_head_atom(atom):
            continue
        alias = _alias_for_atom(atom, aliases)
        if alias is not None:
            out[alias] = idx
    return out


def _public_value(value: Any) -> Any:
    if isinstance(value, Mapping) and "value" in value:
        return value["value"]
    return value


def _normalize_compiled_body(body_ir: object) -> list[list[tuple[Any, ...]]]:
    if not isinstance(body_ir, list) or not body_ir:
        raise ProbLogReachExplainError("compiled body_ir must be non-empty list")
    if all(_is_atom_tuple(item) for item in body_ir):
        return [list(body_ir)]  # type: ignore[list-item]
    if all(isinstance(item, list) for item in body_ir):
        return [list(branch) for branch in body_ir]  # type: ignore[list-item]
    raise ProbLogReachExplainError("compiled body_ir must be one-level AND or two-level OR")


def _ensure_supported_atom(atom: tuple[Any, ...]) -> None:
    if not _is_atom_tuple(atom):
        raise ProbLogReachExplainUnsupported("materialized atom must be tuple")
    if _contains_aggregate(atom):
        raise ProbLogReachExplainUnsupported("aggregate atoms are deferred for problog reach explain M2")
    kind = atom[0]
    if kind in {"pred", "eq", "ne", "gt", "ge", "lt", "le"}:
        return
    if kind == "not":
        _simple_not_inner(atom)
        return
    raise ProbLogReachExplainUnsupported(f"unsupported materialized atom kind for problog reach explain M2: {kind}")


def _simple_not_inner(atom: tuple[Any, ...]) -> tuple[Any, ...]:
    body = atom[1] if len(atom) > 1 else None
    if not isinstance(body, list) or len(body) != 1 or not _is_atom_tuple(body[0]):
        raise ProbLogReachExplainUnsupported("only simple single-atom not bodies are supported in M2")
    inner = body[0]
    if inner[0] not in {"pred", "eq", "ne", "gt", "ge", "lt", "le"}:
        raise ProbLogReachExplainUnsupported("only not(pred) and not(compare) are supported in M2")
    if _contains_aggregate(inner):
        raise ProbLogReachExplainUnsupported("aggregate not bodies are deferred for M2")
    return inner


def _require_bound_vars(atom: tuple[Any, ...], bound_vars: set[str]) -> None:
    missing = sorted(var for var in _vars_in_atom(atom) if var not in bound_vars)
    if missing:
        raise ProbLogReachExplainUnsupported("negated atom variables must be bound before not: " + ", ".join(missing))


def _require_compare_bound(kind: str, lhs: Any, rhs: Any, *, bound_vars: set[str]) -> None:
    missing = [term for term in (lhs, rhs) if _is_var(term) and term not in bound_vars]
    if missing:
        raise ProbLogReachExplainUnsupported(f"{kind} variables must be bound before filter: {missing}")


def _vars_in_atom(atom: tuple[Any, ...]) -> set[str]:
    out: set[str] = set()

    def walk(value: Any) -> None:
        if _is_var(value):
            out.add(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(atom)
    return out


def _contains_aggregate(value: Any) -> bool:
    if isinstance(value, tuple) and value and value[0] in {"count", "sum", "min", "max", "mean"}:
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


def _is_atom_tuple(value: object) -> bool:
    return isinstance(value, tuple) and bool(value) and isinstance(value[0], str)


def _is_var(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("$")


def _call(name: str, variables: Sequence[str]) -> str:
    if not variables:
        return name
    return f"{name}({', '.join(_to_problog_var(var) for var in variables)})"


def _term_for_call(term: Any) -> str:
    if _is_var(term):
        return _to_problog_var(term)
    return _to_problog_literal(term)


def _term_for_compare(term: Any) -> str:
    if _is_var(term):
        return _to_problog_var(term)
    if isinstance(term, (int, float)) and not isinstance(term, bool):
        return repr(term)
    return _to_problog_literal(term)


def _resolve_term(term: Any, row: Mapping[str, Any]) -> Any:
    if _is_var(term):
        return row.get(term, "<unbound>")
    return term


def _safe_suffix(value: str) -> str:
    raw = value[1:] if value.startswith("$") else value
    safe = re.sub(r"[^A-Za-z0-9_]", "_", raw).strip("_") or "x"
    if safe[0].isdigit():
        safe = f"v_{safe}"
    return safe.lower()


__all__ = [
    "ProbLogReachExplainError",
    "ProbLogReachExplainUnsupported",
    "problog_reach_explain_to_evidence_graph",
]
