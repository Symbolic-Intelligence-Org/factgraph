from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factgraph.adapters.souffle.tsv_v1 import tsv_cell_v1_decode
from factgraph.adapters.souffle.where_compile import (
    BranchWitnessRelationSpec,
    QueryWitnessLayout,
    build_query_witness_layout,
    compile_where_to_per_branch_witness_dl,
    extract_where_variables,
    query_rel_for_where,
)
from factgraph.core.derivation.candidates import DerivationOutput
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store import builders as store_builders
from factgraph.core.store._support import (
    SOUFFLE_WITNESS_KIND,
    BindingItems,
    BindingSupportCapture,
    ProjectedFact,
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
) -> list[DerivationOutput]:
    from factgraph.adapters.souffle.package import ExportOptions, export_package
    from factgraph.adapters.souffle.runner import run_package

    query_rel = query_rel_for_where(where)

    if isinstance(head, dict) and head.get("callee_kind") == "entity_type":
        entity_spec = store_builders.entity_spec_from_head(
            store,
            entity_type=target_pred_id,
            head=head,
        )
        where_variables = extract_where_variables(where)
        query_variables = list(entity_spec["head_vars"])
        missing_vars = [
            value
            for value in entity_spec["head_vars"]
            if isinstance(value, str) and value.startswith("$") and value not in where_variables
        ]
        if missing_vars:
            raise WhereValidationError(
                f"head entity vars reference unbound where variables: {missing_vars}"
            )

        query_support_rows = _run_query_and_read_support_rows(
            store=store,
            out_dir_factory=lambda tmpdir: Path(tmpdir) / "engine_eval_pkg",
            where=where,
            query_variables=query_variables,
            query_rel=query_rel,
            export_options=ExportOptions(),
            run_package=run_package,
            export_package=export_package,
            root_result_kind="entity",
        )
        if query_support_rows is None:
            with tempfile.TemporaryDirectory() as tmpdir:
                out_dir = Path(tmpdir) / "engine_eval_pkg"
                bindings = _run_query_and_read_bindings(
                    store=store,
                    out_dir=out_dir,
                    where=where,
                    query_variables=query_variables,
                    query_rel=query_rel,
                    export_options=ExportOptions(),
                    run_package=run_package,
                    export_package=export_package,
                )
            if not bindings:
                return []
            return store_builders.entity_derivation_outputs_from_bindings(
                store,
                derivation_id=derivation_id,
                version=version,
                entity_spec=entity_spec,
                bindings=bindings,
            )

        if not query_support_rows:
            return []
        return store_builders.entity_derivation_outputs_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            entity_spec=entity_spec,
            rows=query_support_rows,
        )

    schema_pred = store_builders.find_schema_pred(store, target_pred_id)
    arg_specs = None
    if schema_pred is not None:
        arg_specs = schema_pred.get("arg_specs")
        if not isinstance(arg_specs, list) or not arg_specs:
            raise WhereValidationError("target predicate arg_specs must be non-empty list")
        if not isinstance(head_vars, list) or len(head_vars) != len(arg_specs):
            raise WhereValidationError("head_vars length must match target arg_specs")
    elif not isinstance(head_vars, list) or not head_vars:
        raise WhereValidationError("head_vars must be non-empty list")

    where_variables = extract_where_variables(where)
    query_variables = list(head_vars)
    missing_vars = [
        value
        for value in head_vars
        if isinstance(value, str) and value.startswith("$") and value not in where_variables
    ]
    if missing_vars:
        raise WhereValidationError(f"head_vars reference unbound where variables: {missing_vars}")

    query_support_rows = _run_query_and_read_support_rows(
        store=store,
        out_dir_factory=lambda tmpdir: Path(tmpdir) / "engine_eval_pkg",
        where=where,
        query_variables=query_variables,
        query_rel=query_rel,
        export_options=ExportOptions(),
        run_package=run_package,
        export_package=export_package,
        root_result_kind="fact",
    )
    if query_support_rows is None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "engine_eval_pkg"
            bindings = _run_query_and_read_bindings(
                store=store,
                out_dir=out_dir,
                where=where,
                query_variables=query_variables,
                query_rel=query_rel,
                export_options=ExportOptions(),
                run_package=run_package,
                export_package=export_package,
            )
        if not bindings:
            return []
        if schema_pred is None:
            return store_builders.query_style_derivation_outputs_from_bindings(
                store,
                derivation_id=derivation_id,
                version=version,
                target_pred_id=target_pred_id,
                head_vars=head_vars,
                bindings=bindings,
            )
        return store_builders.derivation_outputs_from_bindings(
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
    if schema_pred is None:
        return store_builders.query_style_derivation_outputs_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            target_pred_id=target_pred_id,
            head_vars=head_vars,
            rows=query_support_rows,
        )
    return store_builders.derivation_outputs_from_bindings(
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
    query_variables: list[str],
    query_rel: str,
    export_options: Any,
    export_package: Any,
    run_package: Any,
    root_result_kind: str,
) -> list[BindingSupportCapture] | None:
    witness_layout = build_query_witness_layout(where, query_variables=query_variables)
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
                "query_variables": query_variables,
                "include_pred_witness_columns": True,
            },
        )
        witness_program = compile_where_to_per_branch_witness_dl(
            schema_ir=store.schema_ir,
            where=where,
            query_rel=query_rel,
            query_variables=query_variables,
        )
        (out_dir / "rules" / "idb.dl").write_text(
            witness_program.text, encoding="utf-8", newline="\n"
        )
        _rewrite_query_outputs_map(
            manifest_path,
            [query_rel, *(rel.relation_name for rel in witness_program.branch_relations)],
        )
        _capture_projected_domain_view(store, out_dir, manifest_path, witnesses=True)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs_map = manifest.get("outputs_map", {})
        query_outputs = outputs_map.get("__query__") if isinstance(outputs_map, dict) else None
        expected_outputs = [
            query_rel,
            *(rel.relation_name for rel in witness_program.branch_relations),
        ]
        if query_outputs != expected_outputs:
            raise WhereValidationError("query outputs_map is missing or invalid")

        run_manifest_path = run_package(out_dir, ["__query__"], engine="souffle")
        run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        engine_mode = run_manifest.get("engine_mode")
        exit_code = run_manifest.get("exit_code")
        if engine_mode != "souffle":
            raise WhereValidationError(
                "engine evaluate requires souffle execution (runner fell back to noop)"
            )
        if exit_code != 0:
            raise WhereValidationError(
                f"engine evaluate failed with non-zero exit_code: {exit_code}"
            )

        parsed_rows = _read_branch_witness_rows(
            out_dir / "outputs", witness_program.branch_relations
        )
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
    query_variables: list[str],
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
            "query_variables": query_variables,
        },
    )
    _capture_projected_domain_view(store, out_dir, manifest_path, witnesses=False)
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
        raise WhereValidationError(
            "engine evaluate requires souffle execution (runner fell back to noop)"
        )
    if exit_code != 0:
        raise WhereValidationError(f"engine evaluate failed with non-zero exit_code: {exit_code}")

    out_path = out_dir / "outputs" / f"{query_rel}.out.facts"
    return _read_query_bindings(out_path, query_variables)


def _capture_projected_domain_view(
    store: Any, out_dir: Path, manifest_path: Path, *, witnesses: bool
) -> None:
    """Lower canonical Entity domains into this private, read-only query program.

    Public package exports retain their ledger contract. Runtime queries instead
    use chosen, visible Identity bundles, including their opaque virtual witnesses.
    No synthetic assertion is appended to the ledger or the exported claim files.
    """
    from factgraph.adapters.souffle.package import _digest_for_paths
    from factgraph.adapters.souffle.pred_norm import normalize_pred_id
    from factgraph.adapters.souffle.souffle_view_gen import generate_view_dl, witness_rel_name
    from factgraph.adapters.souffle.where_compile import _text_to_symbol
    from factgraph.core.view.projector import _project_entity_domains_with_witness

    domains = _project_entity_domains_with_witness(store.ledger, store.schema_ir)
    schema = {
        **store.schema_ir,
        "predicates": [
            predicate for predicate in store.schema_ir["predicates"]
            if predicate["pred_id"] not in domains
        ],
    }
    lines = [generate_view_dl(schema, include_witness_views=witnesses)]
    for predicate, rows in sorted(domains.items()):
        relation = normalize_pred_id(predicate)
        witness_relation = witness_rel_name(relation)
        lines.extend((f".decl {relation}(E:symbol)", f".output {relation}"))
        if witnesses:
            lines.append(f".decl {witness_relation}(E:symbol, WA:symbol)")
        for row in rows:
            entity = _text_to_symbol(row.fact_tuple[0])
            lines.append(f"{relation}({entity}).")
            if witnesses:
                witness = _text_to_symbol(row.asrt_id)
                lines.append(f"{witness_relation}({entity}, {witness}).")
    view_path = out_dir / "rules" / "view.dl"
    view_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["digests"]["rules_digest"] = _digest_for_paths(
        [view_path, out_dir / "rules" / "idb.dl"], out_dir
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8", newline="\n",
    )


def _rewrite_query_outputs_map(manifest_path: Path, query_outputs: list[str]) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs_map = manifest.get("outputs_map")
    if not isinstance(outputs_map, dict):
        raise WhereValidationError("query outputs_map is missing or invalid")
    outputs_map["__query__"] = list(query_outputs)
    entrypoints = manifest.get("entrypoints")
    if isinstance(entrypoints, list) and "__query__" not in entrypoints:
        entrypoints.append("__query__")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )


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
            binding_items = normalize_binding_items(
                {var: value for var, value in zip(variables, cells)}
            )
            witness_atoms: list[tuple[str, str]] = []
            case_indexes: set[int] = set()
            for spec, value in zip(pred_columns, cells[len(variables) :]):
                if value == "":
                    continue
                if not isinstance(value, str):
                    raise WhereValidationError(
                        f"witness column must decode to string for {spec.pred_condition_key}"
                    )
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


def _read_branch_witness_rows(
    outputs_dir: Path,
    branch_relations: tuple[BranchWitnessRelationSpec, ...],
) -> list[_ParsedWitnessRow]:
    parsed: list[_ParsedWitnessRow] = []
    for relation in branch_relations:
        out_path = outputs_dir / f"{relation.relation_name}.out.facts"
        parsed.extend(_read_query_witness_rows(out_path, relation.layout))
    parsed.sort(
        key=lambda row: (
            row.binding_items,
            row.selected_case_index,
            row.witness_atoms,
        )
    )
    return parsed


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
            store=store,
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
    store: Any,
    where: list[Any],
    binding_items: BindingItems,
    root_result_kind: str,
    selected_case_index: int,
    witness_ids_by_atom_key: dict[str, set[str]],
) -> ProofReceipt:
    binding = binding_dict_from_items(binding_items)
    # Keep selected witness rows keyed by their *predicate occurrence* until
    # the complete support binding has been reconstructed.  One body may use
    # the same predicate more than once (for example two independent Person
    # occurrences joined by a Policy field-navigation comparison).  Collapsing
    # those rows to ``pred_id`` here makes the later occurrence accidentally
    # re-use the first occurrence's witness.
    witness_facts_by_condition = _build_synthetic_witness_facts_by_condition(
        store=store,
        where=where,
        binding=binding,
        selected_case_index=selected_case_index,
        witness_ids_by_atom_key=witness_ids_by_atom_key,
    )
    # ``build_support_artifact_for_binding`` intentionally keeps its stable
    # predicate-keyed input contract.  Build that compatibility view only
    # after the occurrence-sensitive binding has been recovered.
    witness_facts = _group_witness_facts_by_predicate(
        where=where,
        selected_case_index=selected_case_index,
        witness_facts_by_condition=witness_facts_by_condition,
    )
    support_binding = _extend_binding_from_witness_facts(
        where=where,
        binding=binding,
        selected_case_index=selected_case_index,
        witness_facts_by_condition=witness_facts_by_condition,
    )
    native_like = build_support_artifact_for_binding(
        capture_witness_metadata=True,
        where=where,
        binding=support_binding,
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
        witness_capture_version=native_like.witness_capture_version,
    )


def _build_synthetic_witness_facts_by_condition(
    *,
    store: Any,
    where: list[Any],
    binding: dict[str, Any],
    selected_case_index: int,
    witness_ids_by_atom_key: dict[str, set[str]],
) -> dict[str, list[ProjectedFact]]:
    branches = _normalize_where_branches(where)
    try:
        branch = branches[selected_case_index]
    except IndexError as exc:
        raise WhereValidationError(
            f"selected witness branch out of range: {selected_case_index}"
        ) from exc

    witness_facts_by_condition: dict[str, list[ProjectedFact]] = {}
    # Resolve origin from the actual projected inventory, not ID syntax. The
    # inventory is read during capture; the public report never reprojects it.
    from factgraph.core.store import Store
    from factgraph.core.view.projector import project_view_facts_with_witness

    projected_inventory = (
        project_view_facts_with_witness(store.ledger, store.schema_ir)
        if isinstance(store, Store) else {}
    )
    for condition_index, atom in enumerate(branch):
        if not isinstance(atom, tuple) or not atom or atom[0] != "pred":
            continue
        _, pred_id, terms = atom
        pred_condition_key = make_pred_condition_key(selected_case_index, condition_index, pred_id)
        asrt_ids = witness_ids_by_atom_key.get(pred_condition_key)
        if not asrt_ids:
            raise WhereValidationError(
                f"missing witness ids for selected predicate atom: {pred_condition_key}"
            )
        facts: list[ProjectedFact] = []
        for asrt_id in sorted(asrt_ids):
            projected = _projected_fact_from_claim(store, pred_id=pred_id, asrt_id=asrt_id)
            if projected is None:
                projected = next(
                    (fact for fact in projected_inventory.get(pred_id, ()) if fact.asrt_id == asrt_id),
                    None,
                )
            if projected is None:
                projected = ProjectedFact(
                    asrt_id=asrt_id,
                    fact_tuple=_ground_terms(terms, binding),
                )
            facts.append(projected)
        witness_facts_by_condition[pred_condition_key] = facts
    return witness_facts_by_condition


def _group_witness_facts_by_predicate(
    *,
    where: list[Any],
    selected_case_index: int,
    witness_facts_by_condition: dict[str, list[ProjectedFact]],
) -> dict[str, list[ProjectedFact]]:
    """Return the legacy predicate-keyed witness view for receipt assembly.

    Receipt construction still discovers all matching facts by predicate and
    grounded terms, so this view deliberately retains every selected fact.
    The occurrence-keyed view remains the authority for deriving hidden
    bindings before that step.
    """

    branches = _normalize_where_branches(where)
    try:
        branch = branches[selected_case_index]
    except IndexError as exc:
        raise WhereValidationError(
            f"selected witness branch out of range: {selected_case_index}"
        ) from exc

    witness_facts: dict[str, list[ProjectedFact]] = {}
    for condition_index, atom in enumerate(branch):
        if not isinstance(atom, tuple) or not atom or atom[0] != "pred":
            continue
        _, pred_id, _terms = atom
        pred_condition_key = make_pred_condition_key(selected_case_index, condition_index, pred_id)
        facts = witness_facts_by_condition.get(pred_condition_key)
        if not facts:
            raise WhereValidationError(
                f"missing witness facts for selected predicate atom: {pred_condition_key}"
            )
        witness_facts.setdefault(pred_id, []).extend(facts)
    return witness_facts


def _extend_binding_from_witness_facts(
    *,
    where: list[Any],
    binding: dict[str, Any],
    selected_case_index: int,
    witness_facts_by_condition: dict[str, list[ProjectedFact]],
) -> dict[str, Any]:
    branches = _normalize_where_branches(where)
    try:
        branch = branches[selected_case_index]
    except IndexError as exc:
        raise WhereValidationError(
            f"selected witness branch out of range: {selected_case_index}"
        ) from exc

    # Souffle symbols cross the TSV boundary as strings. Reconstruct typed
    # bindings from the selected witnesses first, then require the transport
    # spelling to equal the existing exporter codec. Never parse by guessing a
    # value's appearance, nor weaken joins between two real witness values.
    out: dict[str, Any] = {}
    for condition_index, atom in enumerate(branch):
        if not isinstance(atom, tuple) or not atom or atom[0] != "pred":
            continue
        _, pred_id, terms = atom
        pred_condition_key = make_pred_condition_key(selected_case_index, condition_index, pred_id)
        facts = witness_facts_by_condition.get(pred_condition_key)
        if not facts:
            raise WhereValidationError(
                f"missing witness facts for selected predicate atom: {pred_condition_key}"
            )
        _bind_terms_from_fact(terms, facts[0].fact_tuple, out)
    from factgraph.adapters.souffle.package import _atom_to_str

    for term, supplied in binding.items():
        if term not in out:
            out[term] = supplied
            continue
        canonical = out[term]
        if isinstance(supplied, str):
            agrees = supplied == _atom_to_str(canonical)
        else:
            agrees = type(supplied) is type(canonical) and supplied == canonical
        if not agrees:
            raise WhereValidationError(f"witness fact binding conflict for {term}")
    return out


def _bind_terms_from_fact(terms: Any, fact_tuple: tuple[Any, ...], binding: dict[str, Any]) -> None:
    if not isinstance(terms, list):
        raise WhereValidationError("pred atom terms must be list")
    if len(terms) != len(fact_tuple):
        raise WhereValidationError(
            f"witness fact arity mismatch: expected {len(terms)}, got {len(fact_tuple)}"
        )
    for term, value in zip(terms, fact_tuple):
        if not isinstance(term, str) or not term.startswith("$"):
            if term != value:
                raise WhereValidationError(
                    f"witness fact constant mismatch: expected {term}, got {value}"
                )
            continue
        existing = binding.get(term)
        if existing is not None and existing != value:
            raise WhereValidationError(f"witness fact binding conflict for {term}")
        binding[term] = value


def _projected_fact_from_claim(store: Any, *, pred_id: str, asrt_id: str) -> ProjectedFact | None:
    ledger = getattr(store, "ledger", None)
    get_claim = getattr(ledger, "get_claim", None)
    if not callable(get_claim):
        return None
    claim = get_claim(asrt_id)
    if claim is None:
        return None
    if getattr(claim, "pred_id", None) != pred_id:
        raise WhereValidationError(
            f"witness claim predicate mismatch for {asrt_id}: expected {pred_id}, got {claim.pred_id}"
        )
    values = [claim.e_ref]
    for term in claim.rest_terms:
        if not isinstance(term, tuple) or len(term) != 2:
            raise WhereValidationError(f"malformed rest term for witness claim: {asrt_id}")
        values.append(term[1])
    return ProjectedFact(asrt_id=asrt_id, fact_tuple=tuple(values), witness_kind="assertion")


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
