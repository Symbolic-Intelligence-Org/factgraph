from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from factgraph.adapters.problog.diagnostic_emit import (
    DiagnosticAtomProbability,
    DiagnosticProbLogResult,
    DiagnosticWitnessProbability,
)
from factgraph.adapters.souffle.package import ExportOptions, export_package
from factgraph.adapters.souffle.pred_norm import normalize_pred_id
from factgraph.adapters.souffle.runner import run_package
from factgraph.adapters.souffle.tsv_v1 import tsv_cell_v1_decode
from factgraph.adapters.souffle.where_compile import SOUFFLE_MAX_SUPPORTED_ARITY
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


class SouffleReachExplainError(Exception):
    pass


class SouffleReachExplainUnsupported(SouffleReachExplainError):
    pass


@dataclass(frozen=True)
class _ReachRelation:
    name: str
    branch_id: str
    atom_index: int
    columns: tuple[str, ...]
    var_columns: tuple[str, ...]


@dataclass(frozen=True)
class _BranchReachPlan:
    branch_id: str
    atoms: tuple[tuple[Any, ...], ...]
    reaches: tuple[_ReachRelation, ...]
    seed_vars: tuple[str, ...]
    seed_values: Mapping[str, Any]
    truncated_at: int | None = None
    truncated_arity: int | None = None


@dataclass(frozen=True)
class _ReachProgram:
    text: str
    branches: tuple[_BranchReachPlan, ...]
    entrypoints: tuple[str, ...]
    seed_vars: tuple[str, ...]
    seed_values: Mapping[str, Any]


def souffle_reach_explain_to_evidence_graph(
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
) -> EvidenceGraph:
    program = _build_reach_program(plan, row_bindings)
    result = _run_reach_program(store, program)
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
        probabilistic=False,
    )


def _build_reach_program(plan: RuleExprLoweringPlan, row_bindings: Mapping[str, Any]) -> _ReachProgram:
    if not isinstance(plan, RuleExprLoweringPlan):
        raise SouffleReachExplainError("plan must be RuleExprLoweringPlan")
    compiled, _traces = _materialize_adapter_derivation_plan(plan, engine="souffle")
    branches = _normalize_compiled_body(compiled.body_ir)
    if len(branches) != len(plan.branches):
        raise SouffleReachExplainError("materialized branch count does not match lowering plan")
    global_seed_values = _seed_values_for_row(plan, row_bindings)
    global_seed_values = transitively_expand_seed(global_seed_values, branches)
    if not global_seed_values:
        raise SouffleReachExplainUnsupported("souffle reach explain requires at least one row seed binding")
    lines: list[str] = []

    branch_plans: list[_BranchReachPlan] = []
    entrypoints: list[str] = []
    for branch_index, atoms in enumerate(branches):
        branch_id = plan.branches[branch_index].branch_id
        branch_seed_values = _branch_seed_values(global_seed_values, atoms)
        branch_plan, branch_lines = _emit_branch_reaches(
            branch_id=branch_id,
            atoms=tuple(atoms),
            seed_values=branch_seed_values,
        )
        branch_plans.append(branch_plan)
        lines.extend(branch_lines)
        entrypoints.extend(reach.name for reach in branch_plan.reaches)
    return _ReachProgram(
        text="\n".join(lines).rstrip() + "\n",
        branches=tuple(branch_plans),
        entrypoints=tuple(entrypoints),
        seed_vars=tuple(sorted(global_seed_values)),
        seed_values=global_seed_values,
    )


def _emit_branch_reaches(
    *,
    branch_id: str,
    atoms: tuple[tuple[Any, ...], ...],
    seed_values: Mapping[str, Any],
) -> tuple[_BranchReachPlan, list[str]]:
    if not atoms:
        raise SouffleReachExplainUnsupported("reach explain requires non-empty branch bodies")
    lines: list[str] = []
    reaches: list[_ReachRelation] = []
    seed_vars = tuple(sorted(seed_values))
    bound_vars: list[str] = list(seed_vars)
    previous_relation = f"fg_reach_seed_{_safe_suffix(branch_id)}"
    previous_args = [_var(var) for var in seed_vars]
    seed_cols = ", ".join(f"{_col(var)}:symbol" for var in seed_vars)
    seed_args = ", ".join(_symbol(str(seed_values[var])) for var in seed_vars)

    lines.append(f".decl {previous_relation}({seed_cols})")
    lines.append(f"{previous_relation}({seed_args}).")
    lines.append("")

    for atom_index, atom in enumerate(atoms):
        _ensure_supported_atom(atom)
        next_bound_vars = list(bound_vars)
        atom_clause = _compile_reach_atom(
            atom,
            bound_vars=set(bound_vars),
            next_bound_vars=next_bound_vars,
        )
        rel_name = f"fg_reach_{_safe_suffix(branch_id)}_{atom_index}"
        var_columns = tuple(next_bound_vars)
        columns = var_columns
        if len(columns) > SOUFFLE_MAX_SUPPORTED_ARITY:
            return _BranchReachPlan(
                branch_id=branch_id,
                atoms=atoms,
                reaches=tuple(reaches),
                seed_vars=seed_vars,
                seed_values=dict(seed_values),
                truncated_at=atom_index,
                truncated_arity=len(columns),
            ), lines
        decl_cols = ", ".join(f"{_col(col)}:symbol" for col in columns)
        head_args = [_var(var) for var in var_columns]
        body_terms = [f"{previous_relation}({', '.join(previous_args)})", atom_clause]
        lines.append(f".decl {rel_name}({decl_cols})")
        lines.append(f".output {rel_name}")
        lines.append(f"{rel_name}({', '.join(head_args)}) :- {', '.join(body_terms)}.")
        lines.append("")
        reaches.append(
            _ReachRelation(
                name=rel_name,
                branch_id=branch_id,
                atom_index=atom_index,
                columns=columns,
                var_columns=var_columns,
            )
        )
        bound_vars = next_bound_vars
        previous_relation = rel_name
        previous_args = head_args

    return _BranchReachPlan(
        branch_id=branch_id,
        atoms=atoms,
        reaches=tuple(reaches),
        seed_vars=seed_vars,
        seed_values=dict(seed_values),
        truncated_at=None,
        truncated_arity=None,
    ), lines


def _compile_reach_atom(
    atom: tuple[Any, ...],
    *,
    bound_vars: set[str],
    next_bound_vars: list[str],
) -> str:
    kind = atom[0]
    if kind == "pred":
        if len(atom) != 3 or not isinstance(atom[2], list):
            raise SouffleReachExplainUnsupported("pred atom must be ('pred', pred_id, [terms...])")
        _kind, pred_id, terms = atom
        rel_name = normalize_pred_id(str(pred_id))
        args: list[str] = []
        for term in terms:
            args.append(_term_for_relation(term))
            if _is_var(term) and term not in next_bound_vars:
                next_bound_vars.append(term)
        return f"{rel_name}({', '.join(args)})"
    if kind in {"eq", "ne", "gt", "ge", "lt", "le"}:
        return _compile_compare(kind, atom[1], atom[2], bound_vars=bound_vars, next_bound_vars=next_bound_vars)
    if kind == "not":
        inner = _simple_not_inner(atom)
        if inner[0] == "pred":
            if len(inner) != 3 or not isinstance(inner[2], list):
                raise SouffleReachExplainUnsupported("not(pred) inner pred must use list terms")
            rel_name = normalize_pred_id(str(inner[1]))
            args = [_term_for_relation(term) for term in inner[2]]
            _require_bound_vars(inner, bound_vars)
            return f"!{rel_name}({', '.join(args)})"
        if inner[0] in {"eq", "ne", "gt", "ge", "lt", "le"}:
            _require_bound_vars(inner, bound_vars)
            return _compile_compare(
                _complement_compare_op(inner[0]),
                inner[1],
                inner[2],
                bound_vars=bound_vars,
                next_bound_vars=next_bound_vars,
                allow_bind=False,
            )
    raise SouffleReachExplainUnsupported(f"unsupported materialized atom kind for reach explain: {kind}")


def _compile_compare(
    kind: str,
    lhs: Any,
    rhs: Any,
    *,
    bound_vars: set[str],
    next_bound_vars: list[str],
    allow_bind: bool = True,
) -> str:
    lhs_var = _is_var(lhs)
    rhs_var = _is_var(rhs)
    if kind == "eq" and allow_bind:
        if lhs_var and lhs not in bound_vars and not rhs_var:
            next_bound_vars.append(lhs)
        elif (rhs_var and rhs not in bound_vars and not lhs_var) or (
            lhs_var and rhs_var and lhs in bound_vars and rhs not in bound_vars
        ):
            next_bound_vars.append(rhs)
        elif lhs_var and rhs_var and rhs in bound_vars and lhs not in bound_vars:
            next_bound_vars.append(lhs)
    _require_compare_bound(kind, lhs, rhs, bound_vars=set(next_bound_vars), allow_bind=allow_bind)
    op = {"eq": "=", "ne": "!=", "gt": ">", "ge": ">=", "lt": "<", "le": "<="}[kind]
    numeric = kind in {"gt", "ge", "lt", "le"}
    return f"{_term_for_compare(lhs, numeric=numeric)} {op} {_term_for_compare(rhs, numeric=numeric)}"


def _run_reach_program(store: Any, program: _ReachProgram) -> DiagnosticProbLogResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        package_dir = Path(tmpdir) / "pkg"
        query_where = _bootstrap_query_where(program)
        query_variables = sorted({var for atom in query_where for var in _vars_in_atom(atom)})
        manifest_path = export_package(
            store,
            package_dir,
            ExportOptions(package_kind="inference"),
            query={
                "where": query_where,
                "query_rel": "fg_reach_bootstrap",
                "query_variables": query_variables,
                "include_pred_witness_columns": False,
            },
        )
        idb_path = package_dir / "rules" / "idb.dl"
        idb_path.write_text(program.text, encoding="utf-8", newline="\n")
        _extend_manifest_outputs(manifest_path, program.entrypoints)
        run_manifest_path = run_package(package_dir, list(program.entrypoints), engine="souffle")
        run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        if run_manifest.get("engine_mode") != "souffle":
            raise SouffleReachExplainUnsupported("souffle reach explain requires souffle execution")
        exit_code = run_manifest.get("exit_code")
        if exit_code != 0:
            raise SouffleReachExplainUnsupported(f"souffle reach explain failed with non-zero exit_code: {exit_code}")
        return _parse_reach_outputs(package_dir / "outputs", program)


def _bootstrap_query_where(program: _ReachProgram) -> list[Any]:
    first_branch = program.branches[0] if program.branches else None
    if first_branch is None or not first_branch.atoms:
        raise SouffleReachExplainUnsupported("reach explain requires at least one branch atom")
    return list(first_branch.atoms)


def _parse_reach_outputs(outputs_dir: Path, program: _ReachProgram) -> DiagnosticProbLogResult:
    atoms: list[DiagnosticAtomProbability] = []
    witnesses: list[DiagnosticWitnessProbability] = []
    branches: dict[str, float] = {}
    for branch in program.branches:
        previous_rows: list[dict[str, str]] = [_seed_row(branch.seed_values)]
        reach_matches: dict[int, list[dict[str, str]]] = {}
        failed_at: int | None = None
        failure_row: dict[str, str] | None = None
        for reach in branch.reaches:
            rows = [_row_to_mapping(reach.columns, row) for row in _read_output(outputs_dir, reach.name)]
            matching = _matching_rows(rows, branch.seed_values)
            if matching:
                reach_matches[reach.atom_index] = matching
                previous_rows = matching
                continue
            if previous_rows:
                failed_at = reach.atom_index
                failure_row = previous_rows[0]
                break
            failed_at = reach.atom_index
            failure_row = None
            break

        if failed_at is None and branch.truncated_at is not None:
            raise SouffleReachExplainUnsupported(
                "souffle reach relation arity exceeds supported limit before branch outcome was known: "
                f"branch {branch.branch_id} atom {branch.truncated_at} "
                f"arity={branch.truncated_arity}, limit={SOUFFLE_MAX_SUPPORTED_ARITY}"
            )

        if failed_at is None and branch.reaches:
            terminal_rows = reach_matches.get(branch.reaches[-1].atom_index, ())
            terminal_row = terminal_rows[0] if terminal_rows else None
            for reach in branch.reaches:
                atoms.append(DiagnosticAtomProbability(reach.branch_id, reach.atom_index, "holds", 1.0))
                _append_witness(
                    witnesses,
                    branch_id=reach.branch_id,
                    atom_index=reach.atom_index,
                    atom=branch.atoms[reach.atom_index],
                    row=terminal_row,
                )
            branches[branch.branch_id] = 1.0
            continue

        prefix_row = failure_row
        for atom_index, atom in enumerate(branch.atoms):
            if failed_at is not None and atom_index < failed_at:
                atoms.append(DiagnosticAtomProbability(branch.branch_id, atom_index, "holds", 1.0))
                _append_witness(
                    witnesses,
                    branch_id=branch.branch_id,
                    atom_index=atom_index,
                    atom=atom,
                    row=prefix_row,
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
        occurrence_probabilities={},
    )


def _append_witness(
    witnesses: list[DiagnosticWitnessProbability],
    *,
    branch_id: str,
    atom_index: int,
    atom: tuple[Any, ...],
    row: Mapping[str, str] | None,
) -> None:
    if row is None:
        return
    witness_terms = _witness_terms(atom, row)
    if witness_terms is None:
        return
    witnesses.append(DiagnosticWitnessProbability(branch_id, atom_index, witness_terms, 1.0))


def _witness_terms(atom: tuple[Any, ...], row: Mapping[str, str]) -> tuple[Any, ...] | None:
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


def _resolve_term(term: Any, row: Mapping[str, str]) -> Any:
    if _is_var(term):
        return row.get(term, "<unbound>")
    return term


def _seed_row(seed_values: Mapping[str, Any]) -> dict[str, str]:
    return {key: str(value) for key, value in seed_values.items()}


def _row_to_mapping(columns: Sequence[str], row: Sequence[str]) -> dict[str, str]:
    return {column: value for column, value in zip(columns, row, strict=False)}


def _matching_rows(rows: Sequence[Mapping[str, str]], seed_values: Mapping[str, Any]) -> list[dict[str, str]]:
    out = [
        dict(row)
        for row in rows
        if all(str(row.get(seed_var)) == str(seed_value) for seed_var, seed_value in seed_values.items())
    ]
    out.sort(key=lambda row: tuple((key, row[key]) for key in sorted(row)))
    return out


def _read_output(outputs_dir: Path, rel_name: str) -> list[list[str]]:
    path = outputs_dir / f"{rel_name}.out.facts"
    if not path.exists():
        return []
    rows: list[list[str]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            rows.append([tsv_cell_v1_decode(cell) for cell in line.split("\t")])
    return rows


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
        raise SouffleReachExplainUnsupported("reach explain branch has no row seed variable")
    return out


def _public_value(value: Any) -> Any:
    if isinstance(value, Mapping) and "value" in value:
        return value["value"]
    return value


def _normalize_compiled_body(body_ir: object) -> list[list[tuple[Any, ...]]]:
    if not isinstance(body_ir, list) or not body_ir:
        raise SouffleReachExplainError("compiled body_ir must be non-empty list")
    if all(_is_atom_tuple(item) for item in body_ir):
        return [list(body_ir)]  # type: ignore[list-item]
    if all(isinstance(item, list) for item in body_ir):
        return [list(branch) for branch in body_ir]  # type: ignore[list-item]
    raise SouffleReachExplainError("compiled body_ir must be one-level AND or two-level OR")


def _ensure_supported_atom(atom: tuple[Any, ...]) -> None:
    if not _is_atom_tuple(atom):
        raise SouffleReachExplainUnsupported("materialized atom must be tuple")
    if _contains_aggregate(atom):
        raise SouffleReachExplainUnsupported("aggregate atoms are deferred for souffle reach explain S1")
    kind = atom[0]
    if kind in {"pred", "eq", "ne", "gt", "ge", "lt", "le"}:
        return
    if kind == "not":
        _simple_not_inner(atom)
        return
    raise SouffleReachExplainUnsupported(f"unsupported materialized atom kind for souffle reach explain S1: {kind}")


def _simple_not_inner(atom: tuple[Any, ...]) -> tuple[Any, ...]:
    body = atom[1] if len(atom) > 1 else None
    if not isinstance(body, list) or len(body) != 1 or not _is_atom_tuple(body[0]):
        raise SouffleReachExplainUnsupported("only simple single-atom not bodies are supported in S1")
    inner = body[0]
    if inner[0] not in {"pred", "eq", "ne", "gt", "ge", "lt", "le"}:
        raise SouffleReachExplainUnsupported("only not(pred) and not(compare) are supported in S1")
    if _contains_aggregate(inner):
        raise SouffleReachExplainUnsupported("aggregate not bodies are deferred for S1")
    return inner


def _require_bound_vars(atom: tuple[Any, ...], bound_vars: set[str]) -> None:
    missing = sorted(var for var in _vars_in_atom(atom) if var not in bound_vars)
    if missing:
        raise SouffleReachExplainUnsupported("negated atom variables must be bound before not: " + ", ".join(missing))


def _require_compare_bound(kind: str, lhs: Any, rhs: Any, *, bound_vars: set[str], allow_bind: bool) -> None:
    missing = [term for term in (lhs, rhs) if _is_var(term) and term not in bound_vars]
    if missing:
        raise SouffleReachExplainUnsupported(f"{kind} variables must be bound before filter: {missing}")
    if not allow_bind and any(_is_var(term) and term not in bound_vars for term in (lhs, rhs)):
        raise SouffleReachExplainUnsupported(f"{kind} in negated compare cannot bind variables")


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


def _is_atom_tuple(value: object) -> bool:
    return isinstance(value, tuple) and bool(value) and isinstance(value[0], str)


def _is_var(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("$")


def _term_for_relation(term: Any) -> str:
    if _is_var(term):
        return _var(term)
    if isinstance(term, bool):
        # Match the canonical EDB literal encoding (where_compile._literal_to_text):
        # a bool field value is stored as the symbol "true"/"false", NOT Python
        # str(True)="True" — otherwise a bool relation atom (e.g. project:active(p, True))
        # matches zero EDB rows and reports a false culprit.
        return _symbol("true" if term else "false")
    return _symbol(str(term))


def _term_for_compare(term: Any, *, numeric: bool) -> str:
    if _is_var(term):
        raw = _var(term)
        return f"to_number({raw})" if numeric else raw
    if isinstance(term, bool):
        return "1" if term else "0"
    if isinstance(term, (int, float)):
        return str(term)
    return _symbol(str(term))


def _complement_compare_op(kind: str) -> str:
    return {"eq": "ne", "ne": "eq", "gt": "le", "ge": "lt", "lt": "ge", "le": "gt"}[kind]


def _extend_manifest_outputs(manifest_path: Path, entrypoints: Sequence[str]) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs_map = manifest.setdefault("outputs_map", {})
    existing_entrypoints = manifest.setdefault("entrypoints", [])
    for entrypoint in entrypoints:
        outputs_map[entrypoint] = [entrypoint]
        if entrypoint not in existing_entrypoints:
            existing_entrypoints.append(entrypoint)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )


def _var(name: str) -> str:
    raw = name.removeprefix("$")
    safe = re.sub(r"[^A-Za-z0-9_]", "_", raw).strip("_") or "v"
    if safe[0].isdigit():
        safe = f"v_{safe}"
    return f"V_{safe.upper()}"


def _col(name: str) -> str:
    return _var(name)[2:]


def _symbol(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _safe_suffix(value: str) -> str:
    raw = value.removeprefix("$")
    safe = re.sub(r"[^A-Za-z0-9_]", "_", raw).strip("_") or "x"
    if safe[0].isdigit():
        safe = f"v_{safe}"
    return safe.lower()


__all__ = [
    "SouffleReachExplainError",
    "SouffleReachExplainUnsupported",
    "souffle_reach_explain_to_evidence_graph",
]
