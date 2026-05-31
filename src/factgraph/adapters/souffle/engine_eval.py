from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factgraph.adapters.souffle.tsv_v1 import tsv_cell_v1_decode
from factgraph.adapters.souffle.where_compile import (
    QueryWitnessLayout,
    build_query_witness_layout,
    extract_where_variables,
    query_rel_for_where,
)
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store import builders as store_builders
from factgraph.core.store._support import (
    BindingItems,
    BindingSupportCapture,
    ProjectedFact,
    SOUFFLE_WITNESS_KIND,
    ProofReceipt,
    binding_dict_from_items,
    compute_support_digest,
    make_pred_condition_key,
    normalize_binding_items,
)
from factgraph.core.store._support_capture import build_support_artifact_for_binding


@dataclass(frozen=True)
class _ParsedWitnessRow:
    binding_items: BindingItems
    selected_case_index: int
    witness_atoms: tuple[tuple[str, str], ...]

    def binding_dict(self) -> dict[str, Any]:
        return binding_dict_from_items(self.binding_items)


def evaluate_store_engine(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: list[Any],
    where: list[Any],
    head: dict[str, Any] | None = None,
) -> list[CandidateSet]:
    from factgraph.adapters.souffle.package import ExportOptions, export_package
    from factgraph.adapters.souffle.runner import run_package

    query_rel = query_rel_for_where(where)
    query_support_rows = _run_query_and_read_support_rows(
        store=store,
        out_dir_factory=lambda tmpdir: Path(tmpdir) / "engine_eval_pkg",
        where=where,
        query_rel=query_rel,
        export_options=ExportOptions(),
        run_package=run_package,
        export_package=export_package,
        root_result_kind="entity"
        if isinstance(head, dict) and head.get("callee_kind") == "entity_type"
        else "fact",
    )

    if isinstance(head, dict) and head.get("callee_kind") == "entity_type":
        entity_spec = store_builders.entity_spec_from_head(
            store,
            entity_type=target_pred_id,
            head=head,
        )
        where_variables = extract_where_variables(where)
        missing_vars = [
            value
            for value in entity_spec["head_vars"]
            if isinstance(value, str) and value.startswith("$") and value not in where_variables
        ]
        if missing_vars:
            raise WhereValidationError(f"head entity vars reference unbound where variables: {missing_vars}")

        if query_support_rows is None:
            with tempfile.TemporaryDirectory() as tmpdir:
                out_dir = Path(tmpdir) / "engine_eval_pkg"
                bindings = _run_query_and_read_bindings(
                    store=store,
                    out_dir=out_dir,
                    where=where,
                    where_variables=where_variables,
                    query_rel=query_rel,
                    export_options=ExportOptions(),
                    run_package=run_package,
                    export_package=export_package,
                )
            if not bindings:
                return []
            return store_builders.entity_candidates_from_bindings(
                store,
                derivation_id=derivation_id,
                version=version,
                entity_spec=entity_spec,
                bindings=bindings,
            )

        if not query_support_rows:
            return []
        return store_builders.entity_candidates_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            entity_spec=entity_spec,
            rows=query_support_rows,
        )

    schema_pred = store_builders.find_schema_pred(store, target_pred_id)
    if schema_pred is None:
        raise WhereValidationError(f"target predicate not found: {target_pred_id}")

    arg_specs = schema_pred.get("arg_specs")
    if not isinstance(arg_specs, list) or not arg_specs:
        raise WhereValidationError("target predicate arg_specs must be non-empty list")

    if not isinstance(head_vars, list) or len(head_vars) != len(arg_specs):
        raise WhereValidationError("head_vars length must match target arg_specs")

    where_variables = extract_where_variables(where)
    missing_vars = [
        value
        for value in head_vars
        if isinstance(value, str) and value.startswith("$") and value not in where_variables
    ]
    if missing_vars:
        raise WhereValidationError(f"head_vars reference unbound where variables: {missing_vars}")

    if query_support_rows is None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "engine_eval_pkg"
            bindings = _run_query_and_read_bindings(
                store=store,
                out_dir=out_dir,
                where=where,
                where_variables=where_variables,
                query_rel=query_rel,
                export_options=ExportOptions(),
                run_package=run_package,
                export_package=export_package,
            )
        if not bindings:
            return []
        return store_builders.candidates_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            target_pred_id=target_pred_id,
            arg_specs=arg_specs,
            head_vars=head_vars,
            schema_pred=schema_pred,
            bindings=bindings,
        )

    if not query_support_rows:
        return []
    return store_builders.candidates_from_bindings(
        store,
        derivation_id=derivation_id,
        version=version,
        target_pred_id=target_pred_id,
        arg_specs=arg_specs,
        head_vars=head_vars,
        schema_pred=schema_pred,
        rows=query_support_rows,
    )


def _run_query_and_read_support_rows(
    *,
    store: Any,
    out_dir_factory: Any,
    where: list[Any],
    query_rel: str,
    export_options: Any,
    export_package: Any,
    run_package: Any,
    root_result_kind: str,
) -> list[BindingSupportCapture] | None:
    witness_layout = build_query_witness_layout(where)
    if not witness_layout.pred_witness_columns:
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = out_dir_factory(tmpdir)
        manifest_path = export_package(
            store,
            out_dir,
            export_options,
            query={
                "where": where,
                "query_rel": query_rel,
                "include_pred_witness_columns": True,
            },
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs_map = manifest.get("outputs_map", {})
        query_outputs = outputs_map.get("__query__") if isinstance(outputs_map, dict) else None
        if query_outputs != [query_rel]:
            raise WhereValidationError("query outputs_map is missing or invalid")

        run_manifest_path = run_package(out_dir, ["__query__"], engine="souffle")
        run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        engine_mode = run_manifest.get("engine_mode")
        exit_code = run_manifest.get("exit_code")
        if engine_mode != "souffle":
            raise WhereValidationError("engine evaluate requires souffle execution (runner fell back to noop)")
        if exit_code != 0:
            raise WhereValidationError(f"engine evaluate failed with non-zero exit_code: {exit_code}")

        out_path = out_dir / "outputs" / f"{query_rel}.out.facts"
        parsed_rows = _read_query_witness_rows(out_path, witness_layout)
        return _build_support_rows_from_witness_rows(
            store=store,
            where=where,
            root_result_kind=root_result_kind,
            parsed_rows=parsed_rows,
        )


def _run_query_and_read_bindings(
    *,
    store: Any,
    out_dir: Path,
    where: list[Any],
    where_variables: list[str],
    query_rel: str,
    export_options: Any,
    export_package: Any,
    run_package: Any,
) -> list[dict[str, Any]]:
    manifest_path = export_package(
        store,
        out_dir,
        export_options,
        query={
            "where": where,
            "query_rel": query_rel,
        },
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs_map = manifest.get("outputs_map", {})
    query_outputs = outputs_map.get("__query__") if isinstance(outputs_map, dict) else None
    if query_outputs != [query_rel]:
        raise WhereValidationError("query outputs_map is missing or invalid")

    run_manifest_path = run_package(out_dir, ["__query__"], engine="souffle")
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    engine_mode = run_manifest.get("engine_mode")
    exit_code = run_manifest.get("exit_code")
    if engine_mode != "souffle":
        raise WhereValidationError("engine evaluate requires souffle execution (runner fell back to noop)")
    if exit_code != 0:
        raise WhereValidationError(f"engine evaluate failed with non-zero exit_code: {exit_code}")

    out_path = out_dir / "outputs" / f"{query_rel}.out.facts"
    return _read_query_bindings(out_path, where_variables)


def _read_query_bindings(out_path: Path, variables: list[str]) -> list[dict[str, Any]]:
    if not out_path.exists():
        raise WhereValidationError(f"missing query output file: {out_path}")

    rows: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    with out_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if line == "":
                continue
            cells = [tsv_cell_v1_decode(cell) for cell in line.split("\t")]
            if len(cells) != len(variables):
                raise WhereValidationError(
                    f"query output arity mismatch: expected {len(variables)}, got {len(cells)}"
                )
            binding = {var: value for var, value in zip(variables, cells)}
            key = tuple((var, binding[var]) for var in variables)
            if key in seen:
                continue
            seen.add(key)
            rows.append(binding)

    rows.sort(key=lambda row: tuple((key, row[key]) for key in sorted(row)))
    return rows


def _read_query_witness_rows(
    out_path: Path,
    witness_layout: QueryWitnessLayout,
) -> list[_ParsedWitnessRow]:
    if not out_path.exists():
        raise WhereValidationError(f"missing query output file: {out_path}")

    variables = list(witness_layout.query_variables)
    pred_columns = list(witness_layout.pred_witness_columns)
    expected_arity = len(variables) + len(pred_columns)
    seen: set[tuple[BindingItems, int, tuple[tuple[str, str], ...]]] = set()
    rows: list[_ParsedWitnessRow] = []
    with out_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if line == "":
                continue
            cells = [tsv_cell_v1_decode(cell) for cell in line.split("\t")]
            if len(cells) != expected_arity:
                raise WhereValidationError(
                    f"witness query output arity mismatch: expected {expected_arity}, got {len(cells)}"
                )
            binding_items = normalize_binding_items({var: value for var, value in zip(variables, cells)})
            witness_atoms: list[tuple[str, str]] = []
            case_indexes: set[int] = set()
            for spec, value in zip(pred_columns, cells[len(variables) :]):
                if value == "":
                    continue
                if not isinstance(value, str):
                    raise WhereValidationError(f"witness column must decode to string for {spec.pred_condition_key}")
                witness_atoms.append((spec.pred_condition_key, value))
                case_indexes.add(spec.case_index)
            if not case_indexes:
                raise WhereValidationError("witness row does not identify a satisfying branch")
            if len(case_indexes) != 1:
                raise WhereValidationError("witness row spans multiple OR branches")
            selected_case_index = min(case_indexes)
            witness_atoms_tuple = tuple(sorted(witness_atoms))
            key = (binding_items, selected_case_index, witness_atoms_tuple)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                _ParsedWitnessRow(
                    binding_items=binding_items,
                    selected_case_index=selected_case_index,
                    witness_atoms=witness_atoms_tuple,
                )
            )

    rows.sort(
        key=lambda row: (
            row.binding_items,
            row.selected_case_index,
            row.witness_atoms,
        )
    )
    return rows


def _build_support_rows_from_witness_rows(
    *,
    store: Any,
    where: list[Any],
    root_result_kind: str,
    parsed_rows: list[_ParsedWitnessRow],
) -> list[BindingSupportCapture]:
    grouped: dict[tuple[BindingItems, int], dict[str, set[str]]] = {}
    for row in parsed_rows:
        group = grouped.setdefault((row.binding_items, row.selected_case_index), {})
        for pred_condition_key, asrt_id in row.witness_atoms:
            group.setdefault(pred_condition_key, set()).add(asrt_id)

    selected_by_binding: dict[BindingItems, tuple[int, dict[str, set[str]]]] = {}
    for (binding_items, case_index), witness_ids in grouped.items():
        existing = selected_by_binding.get(binding_items)
        if existing is None or case_index < existing[0]:
            selected_by_binding[binding_items] = (case_index, witness_ids)

    captures: list[BindingSupportCapture] = []
    for binding_items, (selected_case_index, witness_ids) in sorted(
        selected_by_binding.items(),
        key=lambda row: row[0],
    ):
        artifact = _build_souffle_support_artifact(
            where=where,
            binding_items=binding_items,
            root_result_kind=root_result_kind,
            selected_case_index=selected_case_index,
            witness_ids_by_atom_key=witness_ids,
        )
        support_digest = compute_support_digest(artifact)
        store._remember_support_artifact(support_digest, artifact)
        captures.append(
            BindingSupportCapture(
                binding_items=artifact.binding_items,
                support_digest=support_digest,
                support_kind=artifact.kind,
            )
        )
    captures.sort(key=lambda row: (row.binding_items, row.support_digest, row.support_kind))
    return captures


def _build_souffle_support_artifact(
    *,
    where: list[Any],
    binding_items: BindingItems,
    root_result_kind: str,
    selected_case_index: int,
    witness_ids_by_atom_key: dict[str, set[str]],
) -> ProofReceipt:
    binding = binding_dict_from_items(binding_items)
    witness_facts = _build_synthetic_witness_facts(
        where=where,
        binding=binding,
        selected_case_index=selected_case_index,
        witness_ids_by_atom_key=witness_ids_by_atom_key,
    )
    native_like = build_support_artifact_for_binding(
        where=where,
        binding=binding,
        witness_facts=witness_facts,
        root_result_kind=root_result_kind,
        selected_case_index=selected_case_index,
        rule_ref_edges=(),
    )
    return ProofReceipt(
        kind=SOUFFLE_WITNESS_KIND,
        root_result_kind=native_like.root_result_kind,
        binding_items=native_like.binding_items,
        pred_witnesses=native_like.pred_witnesses,
        non_fact_steps=native_like.non_fact_steps,
        rule_refs=native_like.rule_refs,
        rule_ref_edges=native_like.rule_ref_edges,
    )


def _build_synthetic_witness_facts(
    *,
    where: list[Any],
    binding: dict[str, Any],
    selected_case_index: int,
    witness_ids_by_atom_key: dict[str, set[str]],
) -> dict[str, list[ProjectedFact]]:
    branches = _normalize_where_branches(where)
    try:
        branch = branches[selected_case_index]
    except IndexError as exc:
        raise WhereValidationError(f"selected witness branch out of range: {selected_case_index}") from exc

    witness_facts: dict[str, list[ProjectedFact]] = {}
    for condition_index, atom in enumerate(branch):
        if not isinstance(atom, tuple) or not atom or atom[0] != "pred":
            continue
        _, pred_id, terms = atom
        pred_condition_key = make_pred_condition_key(selected_case_index, condition_index, pred_id)
        asrt_ids = witness_ids_by_atom_key.get(pred_condition_key)
        if not asrt_ids:
            raise WhereValidationError(f"missing witness ids for selected predicate atom: {pred_condition_key}")
        grounded_terms = _ground_terms(terms, binding)
        for asrt_id in sorted(asrt_ids):
            witness_facts.setdefault(pred_id, []).append(
                ProjectedFact(asrt_id=asrt_id, fact_tuple=grounded_terms)
            )
    return witness_facts


def _normalize_where_branches(where: list[Any]) -> list[list[tuple[Any, ...]]]:
    if not isinstance(where, list) or not where:
        raise WhereValidationError("where must be non-empty list")
    if all(isinstance(item, tuple) for item in where):
        return [list(where)]
    if all(isinstance(item, list) for item in where):
        branches: list[list[tuple[Any, ...]]] = []
        for branch in where:
            if not isinstance(branch, list) or not all(isinstance(atom, tuple) for atom in branch):
                raise WhereValidationError("where OR branch must contain atom tuples")
            branches.append(list(branch))
        return branches
    raise WhereValidationError("where must be one-level AND or two-level OR-of-AND")


def _ground_terms(terms: Any, binding: dict[str, Any]) -> tuple[Any, ...]:
    if not isinstance(terms, list):
        raise WhereValidationError("pred atom terms must be list")
    grounded: list[Any] = []
    for term in terms:
        if isinstance(term, str) and term.startswith("$"):
            if term not in binding:
                raise WhereValidationError(f"pred atom term is unbound in witness capture: {term}")
            grounded.append(binding[term])
        else:
            grounded.append(term)
    return tuple(grounded)
