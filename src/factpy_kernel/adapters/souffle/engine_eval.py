from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from factpy_kernel.adapters.souffle.tsv_v1 import tsv_cell_v1_decode
from factpy_kernel.adapters.souffle.where_compile import extract_where_variables, query_rel_for_where
from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store import builders as store_builders


def evaluate_store_engine(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: list[Any],
    where: list[Any],
    temporal_view: str = "record",
    materialize_as: str | None = None,
    head: dict[str, Any] | None = None,
    id_policy: Any | None = None,
) -> list[CandidateSet]:
    if temporal_view not in {"record", "current"}:
        raise ValueError("temporal_view must be 'record' or 'current'")
    effective_materialize_as = materialize_as
    if effective_materialize_as is None and isinstance(head, dict):
        effective_materialize_as = "record" if head.get("callee_kind") == "entity_type" else "fact"

    from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
    from factpy_kernel.adapters.souffle.runner import run_package

    if effective_materialize_as == "record":
        record_spec = store_builders.record_materialize_spec_from_head(
            store,
            record_type=target_pred_id,
            head=head,
            id_policy=id_policy,
        )
        where_variables = extract_where_variables(where)
        missing_vars = [
            value
            for value in record_spec["head_vars"]
            if isinstance(value, str) and value.startswith("$") and value not in where_variables
        ]
        if missing_vars:
            raise WhereValidationError(f"head record vars reference unbound where variables: {missing_vars}")

        query_rel = query_rel_for_where(where)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "engine_eval_pkg"
            bindings = _run_query_and_read_bindings(
                store=store,
                out_dir=out_dir,
                where=where,
                where_variables=where_variables,
                temporal_view=temporal_view,
                query_rel=query_rel,
                export_options=ExportOptions(),
                run_package=run_package,
                export_package=export_package,
            )

        if not bindings:
            return []
        return store_builders.record_candidates_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            record_spec=record_spec,
            bindings=bindings,
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

    query_rel = query_rel_for_where(where)
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "engine_eval_pkg"
        bindings = _run_query_and_read_bindings(
            store=store,
            out_dir=out_dir,
            where=where,
            where_variables=where_variables,
            temporal_view=temporal_view,
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


def _run_query_and_read_bindings(
    *,
    store: Any,
    out_dir: Path,
    where: list[Any],
    where_variables: list[str],
    temporal_view: str,
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
            "temporal_view": temporal_view,
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
