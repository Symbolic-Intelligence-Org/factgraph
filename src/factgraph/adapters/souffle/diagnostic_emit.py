"""Souffle emitter/runner for diagnostic companion programs."""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from factgraph.adapters.problog.diagnostic_emit import (
    DiagnosticAtomProbability,
    DiagnosticProbLogResult,
    DiagnosticWitnessProbability,
)
from factgraph.adapters.souffle.package import ExportOptions, export_package
from factgraph.adapters.souffle.pred_norm import normalize_pred_id
from factgraph.adapters.souffle.runner import run_package
from factgraph.adapters.souffle.tsv_v1 import tsv_cell_v1_decode
from factgraph.application.explain.diagnostic_projection import (
    BranchCompanion,
    CompanionAtom,
    CompanionCompare,
    CompanionLiteral,
    CompanionProgram,
    CompanionTerm,
    Wildcard,
)
from factgraph.core.rules.where_ast import Const, Var


_DX_PREFIX = "dx_expl"


class DiagnosticSouffleError(Exception):
    pass


def emit_diagnostic_souffle(program: CompanionProgram) -> str:
    if not isinstance(program, CompanionProgram):
        raise DiagnosticSouffleError("program must be CompanionProgram")
    lines: list[str] = []
    lines.extend(
        [
            ".decl dx_expl(Branch:symbol, Atom:symbol, Verdict:symbol)",
            ".output dx_expl",
            ".decl dx_expl_nr(Branch:symbol, Atom:symbol, Verdict:symbol, BlockedBy:symbol)",
            ".output dx_expl_nr",
            ".decl dx_expl_branch(Branch:symbol)",
            ".output dx_expl_branch",
            ".decl dx_expl_occ(Branch:symbol, Alias:symbol)",
            ".output dx_expl_occ",
            "",
        ]
    )
    for branch in program.branches:
        lines.extend(_emit_branch(branch))
    return "\n".join(lines).rstrip() + "\n"


def run_diagnostic_souffle(store: Any, program: CompanionProgram) -> DiagnosticProbLogResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        package_dir = Path(tmpdir) / "pkg"
        export_package(store, package_dir, ExportOptions(package_kind="inference"), query=None)
        idb_path = package_dir / "rules" / "idb.dl"
        idb_text = idb_path.read_text(encoding="utf-8")
        idb_path.write_text(idb_text.rstrip() + "\n\n" + emit_diagnostic_souffle(program), encoding="utf-8", newline="\n")
        entrypoints = _diagnostic_entrypoints(program)
        _extend_manifest_outputs(package_dir / "manifest.json", entrypoints)
        run_package(package_dir, entrypoints, engine="souffle")
        return parse_diagnostic_souffle_outputs(package_dir / "outputs", program)


def parse_diagnostic_souffle_outputs(outputs_dir: Path, program: CompanionProgram) -> DiagnosticProbLogResult:
    outputs = Path(outputs_dir)
    atoms: list[DiagnosticAtomProbability] = []
    witnesses: list[DiagnosticWitnessProbability] = []
    branches: dict[str, float] = {}
    occurrences: dict[tuple[str, str], float] = {}

    for row in _read_output(outputs, "dx_expl"):
        if len(row) != 3:
            raise DiagnosticSouffleError(f"invalid dx_expl row: {row!r}")
        atoms.append(DiagnosticAtomProbability(branch_id=row[0], atom_index=int(row[1]), verdict=row[2], probability=1.0))
    for row in _read_output(outputs, "dx_expl_nr"):
        if len(row) != 4:
            raise DiagnosticSouffleError(f"invalid dx_expl_nr row: {row!r}")
        atoms.append(
            DiagnosticAtomProbability(
                branch_id=row[0],
                atom_index=int(row[1]),
                verdict=row[2],
                probability=1.0,
                blocked_by=row[3],
            )
        )
    for row in _read_output(outputs, "dx_expl_branch"):
        if len(row) != 1:
            raise DiagnosticSouffleError(f"invalid dx_expl_branch row: {row!r}")
        branches[row[0]] = 1.0
    for row in _read_output(outputs, "dx_expl_occ"):
        if len(row) != 2:
            raise DiagnosticSouffleError(f"invalid dx_expl_occ row: {row!r}")
        occurrences[(row[0], row[1])] = 1.0

    witness_names = _witness_relation_names(program)
    for rel_name, branch_id, atom_index in witness_names:
        for row in _read_output(outputs, rel_name):
            witnesses.append(
                DiagnosticWitnessProbability(
                    branch_id=branch_id,
                    atom_index=atom_index,
                    terms=tuple(row),
                    probability=1.0,
                )
            )

    return DiagnosticProbLogResult(
        atom_probabilities=tuple(atoms),
        witnesses=tuple(witnesses),
        branch_probabilities=branches,
        occurrence_probabilities=occurrences,
    )


def _emit_branch(branch: BranchCompanion) -> list[str]:
    lines: list[str] = []
    branch_lit = _symbol(branch.branch_id)
    for var, body in branch.bound_defs.items():
        rel = _bound_relation(branch.branch_id, var)
        lines.append(f".decl {rel}(T:symbol)")
        if body:
            lines.append(f'{rel}("t") :- {_body(body)}.')
        lines.append("")

    for atom in branch.atoms:
        atom_lit = _symbol(str(atom.atom_index))
        holds_body = _body(atom.holds_body)
        lines.append(
            f"dx_expl({branch_lit}, {atom_lit}, \"holds\")"
            + (f" :- {holds_body}." if holds_body else ".")
        )
        fails_body = _body(atom.fails_body)
        lines.append(
            f"dx_expl({branch_lit}, {atom_lit}, \"fails\")"
            + (f" :- {fails_body}." if fails_body else ".")
        )
        for not_reached in atom.not_reached:
            blocked = _symbol(not_reached.var)
            if not_reached.var in branch.bound_defs:
                rel = _bound_relation(branch.branch_id, not_reached.var)
                lines.append(
                    f"dx_expl_nr({branch_lit}, {atom_lit}, \"not_reached\", {blocked}) :- !{rel}(\"t\")."
                )
            else:
                lines.append(f"dx_expl_nr({branch_lit}, {atom_lit}, \"not_reached\", {blocked}).")
        if atom.witness is not None:
            rel = _witness_relation(branch.branch_id, atom.atom_index)
            arity = len(atom.witness.terms)
            if arity:
                cols = ", ".join(f"T{idx}:symbol" for idx in range(arity))
                lines.append(f".decl {rel}({cols})")
                lines.append(f".output {rel}")
                head_terms = ", ".join(_term(term, for_relation=True) for term in atom.witness.terms)
                body = _body(atom.holds_body)
                lines.append(f"{rel}({head_terms})" + (f" :- {body}." if body else "."))
        lines.append("")

    branch_body = _body(branch.branch_body)
    lines.append(f"dx_expl_branch({branch_lit})" + (f" :- {branch_body}." if branch_body else "."))
    for alias, body_atoms in branch.occ_bodies.items():
        body = _body(body_atoms)
        lines.append(
            f"dx_expl_occ({branch_lit}, {_symbol(alias)})"
            + (f" :- {body}." if body else ".")
        )
    lines.append("")
    return lines


def _body(atoms: tuple[CompanionAtom, ...]) -> str:
    return ", ".join(_atom(atom) for atom in atoms)


def _atom(atom: CompanionAtom) -> str:
    if isinstance(atom, CompanionLiteral):
        call = _literal(atom)
        return f"!{call}" if atom.negated else call
    if isinstance(atom, CompanionCompare):
        return _compare(atom)
    raise DiagnosticSouffleError(f"unsupported companion atom: {atom!r}")


def _literal(atom: CompanionLiteral) -> str:
    rel = normalize_pred_id(atom.pred_id)
    args = ", ".join(_term(term, for_relation=True) for term in atom.terms)
    return f"{rel}({args})"


def _compare(atom: CompanionCompare) -> str:
    op = _comparison_op(atom.op, negated=atom.negated)
    numeric = _compare_uses_numeric_terms(atom)
    lhs = _cmp_term(atom.lhs, numeric=numeric)
    rhs = _cmp_term(atom.rhs, numeric=numeric)
    return f"{lhs} {op} {rhs}"


def _comparison_op(op: str, *, negated: bool) -> str:
    mapping = {"eq": "=", "ne": "!=", "gt": ">", "ge": ">=", "lt": "<", "le": "<="}
    if op not in mapping:
        raise DiagnosticSouffleError(f"unsupported compare op: {op!r}")
    if not negated:
        return mapping[op]
    complements = {"eq": "!=", "ne": "=", "gt": "<=", "ge": "<", "lt": ">=", "le": ">"}
    return complements[op]


def _compare_uses_numeric_terms(atom: CompanionCompare) -> bool:
    if atom.op not in {"eq", "ne"}:
        return True
    return _term_is_numeric(atom.lhs) or _term_is_numeric(atom.rhs)


def _term_is_numeric(term: CompanionTerm) -> bool:
    return isinstance(term, Const) and isinstance(term.value, (bool, int, float))


def _cmp_term(term: CompanionTerm, *, numeric: bool) -> str:
    if isinstance(term, Var):
        raw = _var(term.name)
        return f"to_number({raw})" if numeric else raw
    if isinstance(term, Const):
        if isinstance(term.value, bool):
            return "1" if term.value else "0"
        if isinstance(term.value, (int, float)):
            return str(term.value)
        return _symbol(str(term.value))
    if isinstance(term, Wildcard):
        raise DiagnosticSouffleError("wildcard is not supported in compare atom")
    raise DiagnosticSouffleError(f"unsupported companion term: {term!r}")


def _term(term: CompanionTerm, *, for_relation: bool) -> str:
    if isinstance(term, Var):
        return _var(term.name)
    if isinstance(term, Const):
        return _symbol(str(term.value))
    if isinstance(term, Wildcard):
        return "_"
    raise DiagnosticSouffleError(f"unsupported companion term: {term!r}")


def _var(name: str) -> str:
    raw = name[1:] if name.startswith("$") else name
    safe = re.sub(r"[^A-Za-z0-9_]", "_", raw).strip("_") or "v"
    if safe[0].isdigit():
        safe = f"v_{safe}"
    return f"V_{safe.upper()}"


def _symbol(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _safe_suffix(value: str) -> str:
    raw = value[1:] if value.startswith("$") else value
    safe = re.sub(r"[^A-Za-z0-9_]", "_", raw).strip("_") or "x"
    return safe.lower()


def _bound_relation(branch_id: str, var: str) -> str:
    return f"{_DX_PREFIX}_bound_{_safe_suffix(branch_id)}_{_safe_suffix(var)}"


def _witness_relation(branch_id: str, atom_index: int) -> str:
    return f"{_DX_PREFIX}_wit_{_safe_suffix(branch_id)}_{atom_index}"


def _diagnostic_entrypoints(program: CompanionProgram) -> list[str]:
    out = ["dx_expl", "dx_expl_nr", "dx_expl_branch", "dx_expl_occ"]
    out.extend(name for name, _branch, _idx in _witness_relation_names(program))
    return out


def _witness_relation_names(program: CompanionProgram) -> list[tuple[str, str, int]]:
    out: list[tuple[str, str, int]] = []
    for branch in program.branches:
        for atom in branch.atoms:
            if atom.witness is not None and atom.witness.terms:
                out.append((_witness_relation(branch.branch_id, atom.atom_index), branch.branch_id, atom.atom_index))
    return out


def _extend_manifest_outputs(manifest_path: Path, entrypoints: list[str]) -> None:
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


__all__ = [
    "DiagnosticSouffleError",
    "emit_diagnostic_souffle",
    "parse_diagnostic_souffle_outputs",
    "run_diagnostic_souffle",
]
