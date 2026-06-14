"""ProbLog emitter/runner for diagnostic companion programs."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import tempfile
from pathlib import Path
import re
from typing import Any

from factgraph.adapters.problog._parsing import _split_top_level_args
from factgraph.adapters.problog.problog_engine import run_problog
from factgraph.adapters.problog.problog_export import (
    ProbLogExportError,
    _compile_atom,
    _to_problog_literal,
    _to_problog_var,
    export_problog,
)
from factgraph.application.explain.diagnostic_projection import (
    BranchCompanion,
    CompanionAtom,
    CompanionCompare,
    CompanionLiteral,
    CompanionProgram,
    CompanionTerm,
    CompanionWitness,
    Wildcard,
)
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprLoweringPlan,
    _materialize_adapter_derivation_plan,
)
from factgraph.core.rules.where_ast import Const, Var


_ANSWER_RE = re.compile(r"^(?P<query>.+?):\s*(?P<probability>[0-9.eE+-]+)\s*$")


class DiagnosticProbLogError(Exception):
    pass


@dataclass(frozen=True)
class DiagnosticAtomProbability:
    branch_id: str
    atom_index: int
    verdict: str
    probability: float
    blocked_by: str | None = None


@dataclass(frozen=True)
class DiagnosticWitnessProbability:
    branch_id: str
    atom_index: int
    terms: tuple[Any, ...]
    probability: float


@dataclass(frozen=True)
class DiagnosticProbLogResult:
    atom_probabilities: tuple[DiagnosticAtomProbability, ...] = ()
    witnesses: tuple[DiagnosticWitnessProbability, ...] = ()
    branch_probabilities: Mapping[str, float] = field(default_factory=dict)
    occurrence_probabilities: Mapping[tuple[str, str], float] = field(default_factory=dict)
    head_probabilities: Mapping[str, float] = field(default_factory=dict)


def emit_diagnostic_problog(
    store: Any,
    plan: RuleExprLoweringPlan,
    program: CompanionProgram,
    *,
    uncertainty_projection: Mapping[str, Any] | None = None,
) -> str:
    """Emit a full ProbLog program containing the canonical fact base plus diagnostics."""
    if not isinstance(program, CompanionProgram):
        raise DiagnosticProbLogError("program must be CompanionProgram")
    compiled, _traces = _materialize_adapter_derivation_plan(plan, engine="problog")
    if len(compiled.heads) != 1:
        raise DiagnosticProbLogError("diagnostic problog requires exactly one compiled head")
    head = compiled.heads[0]
    rule_spec = {
        "derivation_id": compiled.derivation_id,
        "version": compiled.version,
        "target_pred_id": head.target_pred_id,
        "head_vars": list(head.head_var_names),
        "where": compiled.body_ir,
        "head": compiled.head_spec,
        "engine_ext": compiled.engine_ext,
        "query_pred": "answer",
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir) / "diagnostic_base.pl"
        export_problog(
            store,
            rule_spec,
            base_path,
            uncertainty_projection=dict(uncertainty_projection or {}),
        )
        base = base_path.read_text(encoding="utf-8")
    return base.rstrip() + "\n\n" + _emit_companion_program(program)


def run_diagnostic_problog(program_text: str, *, timeout: int = 30) -> DiagnosticProbLogResult:
    if not isinstance(program_text, str) or not program_text.strip():
        raise DiagnosticProbLogError("program_text must be non-empty string")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "diagnostic.pl"
        path.write_text(program_text, encoding="utf-8")
        raw = run_problog(path, timeout=timeout, trace=False)
    return parse_diagnostic_problog_output(raw)


def parse_diagnostic_problog_output(raw_output: str) -> DiagnosticProbLogResult:
    atoms: list[DiagnosticAtomProbability] = []
    witnesses: list[DiagnosticWitnessProbability] = []
    branches: dict[str, float] = {}
    occurrences: dict[tuple[str, str], float] = {}
    heads: dict[str, float] = {}
    for raw_line in raw_output.splitlines():
        match = _ANSWER_RE.match(raw_line.strip())
        if match is None:
            continue
        query = match.group("query").strip()
        probability = float(match.group("probability"))
        if probability <= 0.0:
            continue
        name, args = _parse_query(query)
        if name == "expl":
            if len(args) == 3:
                atoms.append(
                    DiagnosticAtomProbability(
                        branch_id=str(args[0]),
                        atom_index=int(args[1]),
                        verdict=str(args[2]),
                        probability=probability,
                    )
                )
            elif len(args) == 4:
                atoms.append(
                    DiagnosticAtomProbability(
                        branch_id=str(args[0]),
                        atom_index=int(args[1]),
                        verdict=str(args[2]),
                        probability=probability,
                        blocked_by=str(args[3]),
                    )
                )
            continue
        if name == "expl_wit" and len(args) >= 3:
            witnesses.append(
                DiagnosticWitnessProbability(
                    branch_id=str(args[0]),
                    atom_index=int(args[1]),
                    terms=tuple(args[2:]),
                    probability=probability,
                )
            )
            continue
        if name == "expl_branch" and len(args) == 1:
            branches[str(args[0])] = probability
            continue
        if name == "expl_head" and len(args) == 1:
            heads[str(args[0])] = probability
            continue
        if name == "expl_occ" and len(args) == 2:
            occurrences[(str(args[0]), str(args[1]))] = probability
            continue
    return DiagnosticProbLogResult(
        atom_probabilities=tuple(atoms),
        witnesses=tuple(witnesses),
        branch_probabilities=branches,
        occurrence_probabilities=occurrences,
        head_probabilities=heads,
    )


def _emit_companion_program(program: CompanionProgram) -> str:
    lines: list[str] = []
    for branch in program.branches:
        lines.extend(_emit_branch(branch))
    lines.extend(
        [
            "expl('__none__', -1, 'not_reached', '__none__') :- fail.",
            "expl_wit('__none__', -1, '__none__') :- fail.",
            "expl_wit('__none__', -1, '__none__', '__none__') :- fail.",
            "expl_head('__none__') :- fail.",
        ]
    )
    queries = [
        "query(expl(_, _, _)).",
        "query(expl(_, _, _, _)).",
        "query(expl_wit(_, _, _)).",
        "query(expl_wit(_, _, _, _)).",
        "query(expl_head(_)).",
        "query(expl_branch(_)).",
        "query(expl_occ(_, _)).",
    ]
    return "\n".join([*lines, *queries]) + "\n"


def _emit_branch(branch: BranchCompanion) -> list[str]:
    lines: list[str] = []
    branch_lit = _to_problog_literal(branch.branch_id)
    for var, body in branch.bound_defs.items():
        if body:
            lines.append(f"{_bound_predicate(branch.branch_id, var)} :- {_body(body)}.")
    for atom in branch.atoms:
        holds_body = _body(atom.holds_body)
        lines.append(
            f"expl({branch_lit}, {atom.atom_index}, 'holds')"
            + (f" :- {holds_body}." if holds_body else ".")
        )
        fails_body = _body(atom.fails_body)
        lines.append(
            f"expl({branch_lit}, {atom.atom_index}, 'fails')"
            + (f" :- {fails_body}." if fails_body else ".")
        )
        for not_reached in atom.not_reached:
            blocked = _to_problog_literal(not_reached.var)
            bound_name = _bound_predicate(branch.branch_id, not_reached.var)
            if not_reached.var in branch.bound_defs:
                lines.append(f"expl({branch_lit}, {atom.atom_index}, 'not_reached', {blocked}) :- \\+({bound_name}).")
            else:
                lines.append(f"expl({branch_lit}, {atom.atom_index}, 'not_reached', {blocked}).")
        if atom.witness is not None:
            witness_line = _witness_rule(branch.branch_id, atom.atom_index, atom.witness, atom.holds_body)
            if witness_line is not None:
                lines.append(witness_line)
    branch_body = _body(branch.branch_body)
    lines.append(f"expl_branch({branch_lit})" + (f" :- {branch_body}." if branch_body else "."))
    if branch.head_body:
        head_body = _body(branch.head_body)
        lines.append(f"expl_head({branch_lit})" + (f" :- {head_body}." if head_body else "."))
    for alias, body in branch.occ_bodies.items():
        occ_body = _body(body)
        lines.append(
            f"expl_occ({branch_lit}, {_to_problog_literal(alias)})"
            + (f" :- {occ_body}." if occ_body else ".")
        )
    return lines


def _witness_rule(
    branch_id: str,
    atom_index: int,
    witness: CompanionWitness,
    body: tuple[CompanionAtom, ...],
) -> str | None:
    terms = tuple(_term(term) for term in witness.terms)
    if not terms:
        return None
    head = f"expl_wit({_to_problog_literal(branch_id)}, {atom_index}, {', '.join(terms)})"
    rendered_body = _body(body)
    return head + (f" :- {rendered_body}." if rendered_body else ".")


def _bound_predicate(branch_id: str, var: str) -> str:
    safe_branch = re.sub(r"[^A-Za-z0-9_]", "_", branch_id).strip("_") or "branch"
    raw_var = var[1:] if var.startswith("$") else var
    safe_var = re.sub(r"[^A-Za-z0-9_]", "_", raw_var).strip("_") or "var"
    return f"bound_{safe_branch}_{safe_var}"


def _body(atoms: tuple[CompanionAtom, ...]) -> str:
    return ", ".join(_atom(atom) for atom in atoms)


def _atom(atom: CompanionAtom) -> str:
    if isinstance(atom, CompanionLiteral):
        call = _literal(atom)
        return f"\\+({call})" if atom.negated else call
    if isinstance(atom, CompanionCompare):
        call = _compare(atom)
        return f"\\+({call})" if atom.negated else call
    raise DiagnosticProbLogError(f"unsupported companion atom: {atom!r}")


def _literal(atom: CompanionLiteral) -> str:
    if len(atom.terms) == 1:
        return f"edb_fact(_, {_to_problog_literal(atom.pred_id)}, {_term(atom.terms[0])}, _)"
    if len(atom.terms) == 2:
        return f"edb_fact(_, {_to_problog_literal(atom.pred_id)}, {_term(atom.terms[0])}, {_term(atom.terms[1])})"
    raise DiagnosticProbLogError(f"companion literal arity > 2 is not supported: {atom.pred_id}")


def _compare(atom: CompanionCompare) -> str:
    lhs = _value_for_compile(atom.lhs)
    rhs = _value_for_compile(atom.rhs)
    try:
        return _compile_atom((atom.op, lhs, rhs))
    except ProbLogExportError as exc:
        raise DiagnosticProbLogError(str(exc)) from exc


def _value_for_compile(term: CompanionTerm) -> Any:
    if isinstance(term, Var):
        return term.name
    if isinstance(term, Const):
        return term.value
    if isinstance(term, Wildcard):
        return "_"
    raise DiagnosticProbLogError(f"unsupported companion term: {term!r}")


def _term(term: CompanionTerm) -> str:
    if isinstance(term, Var):
        return _to_problog_var(term.name)
    if isinstance(term, Const):
        return _to_problog_literal(term.value)
    if isinstance(term, Wildcard):
        return "_"
    raise DiagnosticProbLogError(f"unsupported companion term: {term!r}")


def _parse_query(query: str) -> tuple[str, list[Any]]:
    name, sep, rest = query.partition("(")
    if not sep or not rest.endswith(")"):
        raise DiagnosticProbLogError(f"unsupported diagnostic query row: {query!r}")
    args = [_parse_term(arg) for arg in _split_top_level_args(rest[:-1])]
    return name.strip(), args


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


__all__ = [
    "DiagnosticAtomProbability",
    "DiagnosticProbLogError",
    "DiagnosticProbLogResult",
    "DiagnosticWitnessProbability",
    "emit_diagnostic_problog",
    "parse_diagnostic_problog_output",
    "run_diagnostic_problog",
]
