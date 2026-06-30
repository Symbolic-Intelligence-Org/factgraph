from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factgraph.adapters.souffle.pred_norm import normalize_pred_id
from factgraph.adapters.souffle.tsv_v1 import write_tsv
from factgraph.core.policy.policy_ir import (
    build_policy_ir_v1,
    canonicalize_policy_ir_jcs,
    policy_digest,
)
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factgraph.adapters.souffle.where_compile import (
    compile_where_to_query_dl,
    query_rel_for_where,
)
from factgraph.core.schema.schema_ir import canonicalize_schema_ir_jcs, schema_digest
from factgraph.core.store.runtime import Store
from factgraph.adapters.souffle.souffle_view_gen import generate_view_dl

# The audit ledgers are engine-neutral and store-derived. Their builders live in
# factgraph.audit.package_export (single source of truth); the audit branch below
# reuses them so the audit package this adapter writes stays byte-identical while the
# logic is reachable without Souffle. _latest_run_id / _protocol_version are the
# store/schema-pure manifest helpers shared by both export paths.
from factgraph.audit.package_export import (
    _latest_run_id,
    _protocol_version,
    write_audit_artifacts,
)

_WHERE_ATOM_TAGS = {
    "pred",
    "ruleref",
    "eq",
    "ne",
    "gt",
    "ge",
    "lt",
    "le",
    "in",
    "not",
    "add",
    "sub",
    "neg",
    "addc",
    "mulc",
}


@dataclass(frozen=True)
class ExportOptions:
    package_kind: str = "inference"
    target_engine: str = "souffle"
    dialect_version: str = "v1"
    policy_mode: str = "edb"

    def __post_init__(self) -> None:
        if self.package_kind not in {"inference", "audit"}:
            raise ValueError("package_kind must be inference|audit")
        if not isinstance(self.target_engine, str) or not self.target_engine:
            raise ValueError("target_engine must be non-empty string")
        if not isinstance(self.dialect_version, str) or not self.dialect_version:
            raise ValueError("dialect_version must be non-empty string")
        if self.policy_mode not in {"edb", "idb"}:
            raise ValueError("policy_mode must be edb|idb")


def export_package(
    store: Store,
    out_dir: Path,
    options: ExportOptions,
    query: dict[str, Any] | None = None,
    *,
    certainty_summaries: dict[str, dict[str, Any]] | None = None,
    provenance_trees: dict[str, dict[str, Any]] | None = None,
    provenance_statuses: dict[str, dict[str, Any]] | None = None,
    evidence_graphs: dict[str, dict[str, Any]] | None = None,
    provenance_timelines: dict[str, dict[str, Any]] | None = None,
) -> Path:
    if not isinstance(store, Store):
        raise TypeError("store must be Store")
    if not isinstance(options, ExportOptions):
        raise TypeError("options must be ExportOptions")
    if certainty_summaries is not None and not isinstance(certainty_summaries, dict):
        raise TypeError("certainty_summaries must be dict[str, dict] | None")
    if provenance_trees is not None and not isinstance(provenance_trees, dict):
        raise TypeError("provenance_trees must be dict[str, dict] | None")
    if provenance_statuses is not None and not isinstance(provenance_statuses, dict):
        raise TypeError("provenance_statuses must be dict[str, dict] | None")
    if evidence_graphs is not None and not isinstance(evidence_graphs, dict):
        raise TypeError("evidence_graphs must be dict[str, dict] | None")
    if provenance_timelines is not None and not isinstance(provenance_timelines, dict):
        raise TypeError("provenance_timelines must be dict[str, dict] | None")

    package_dir = Path(out_dir)
    schema_dir = package_dir / "schema"
    policy_dir = package_dir / "policy"
    facts_dir = package_dir / "facts"
    rules_dir = package_dir / "rules"
    outputs_dir = package_dir / "outputs"
    audit_dir = package_dir / "audit"

    for p in [schema_dir, policy_dir, facts_dir, rules_dir, outputs_dir]:
        p.mkdir(parents=True, exist_ok=True)
    if options.package_kind == "audit":
        audit_dir.mkdir(parents=True, exist_ok=True)

    schema_bytes = canonicalize_schema_ir_jcs(store.schema_ir)
    (schema_dir / "schema_ir.json").write_text(
        schema_bytes.decode("utf-8"), encoding="utf-8", newline="\n"
    )

    policy_ir = build_policy_ir_v1(
        store.schema_ir,
        policy_mode=options.policy_mode,
        generated_at=0,
    )
    policy_ir_bytes = canonicalize_policy_ir_jcs(policy_ir)
    policy_ir_path = policy_dir / "policy_ir.json"
    policy_ir_path.write_text(
        policy_ir_bytes.decode("utf-8"), encoding="utf-8", newline="\n"
    )

    policy_rules_path = policy_dir / "policy_rules.dl"
    policy_rules_path.write_text(
        _build_policy_rules_dl(options.policy_mode),
        encoding="utf-8",
        newline="\n",
    )

    view_dl = generate_view_dl(
        store.schema_ir,
        include_active_rule=(options.policy_mode != "idb"),
        include_witness_views=bool(query and query.get("include_pred_witness_columns")),
    )
    (rules_dir / "view.dl").write_text(view_dl, encoding="utf-8", newline="\n")

    outputs_map = _outputs_map(store)
    idb_text = ""
    if query is not None:
        if not isinstance(query, dict):
            raise TypeError("query must be dict")
        where = query.get("where")
        if not isinstance(where, list):
            raise ValueError("query.where must be list")
        query_rel = query.get("query_rel")
        if query_rel is None:
            query_rel = query_rel_for_where(where)
        if not isinstance(query_rel, str) or not query_rel:
            raise ValueError("query.query_rel must be non-empty string")
        # Q8 Phase 2 (Slice 6) + Slice 7C / Q6-A (c.1) + N-3:
        # FileAuthoringRegistry was deleted in Slice 7C. Caller-provided
        # in-memory ruleref resolvers (objects implementing
        # `registry.resolve(rule_id, version)` per `core/rules/ruleref_common.py`)
        # may be passed through the `query.registry` field if the where
        # contains `ruleref` atoms. Callers without ruleref atoms can leave
        # `registry` as None. The unchanged shared helper enforces the
        # protocol; N-3 prevents broadening this beyond Souffle adapter.
        registry = query.get("registry")
        idb_text = compile_where_to_query_dl(
            schema_ir=store.schema_ir,
            where=where,
            query_rel=query_rel,
            query_variables=query.get("query_variables"),
            include_pred_witness_columns=bool(query.get("include_pred_witness_columns")),
            registry=registry,
        )
        outputs_map["__query__"] = [query_rel]

    (rules_dir / "idb.dl").write_text(idb_text, encoding="utf-8", newline="\n")

    audit_files: dict[str, str] = {}
    if options.package_kind == "audit":
        audit_files = write_audit_artifacts(
            store,
            audit_dir,
            policy_mode=options.policy_mode,
            certainty_summaries=certainty_summaries,
            provenance_trees=provenance_trees,
            provenance_statuses=provenance_statuses,
            evidence_graphs=evidence_graphs,
            provenance_timelines=provenance_timelines,
        )

    (
        claim_rows,
        claim_arg_rows,
        meta_str_rows,
        meta_time_rows,
        meta_int_rows,
        meta_float_rows,
        meta_bool_rows,
        revokes_rows,
    ) = _build_fact_rows(store)

    claim_path = facts_dir / "claim.facts"
    claim_arg_path = facts_dir / "claim_arg.facts"
    meta_str_path = facts_dir / "meta_str.facts"
    meta_time_path = facts_dir / "meta_time.facts"
    meta_int_path = facts_dir / "meta_int.facts"
    meta_float_path = facts_dir / "meta_float.facts"
    meta_bool_path = facts_dir / "meta_bool.facts"
    revokes_path = facts_dir / "revokes.facts"

    write_tsv(claim_path, claim_rows)
    write_tsv(claim_arg_path, claim_arg_rows)
    write_tsv(meta_str_path, meta_str_rows)
    write_tsv(meta_time_path, meta_time_rows)
    write_tsv(meta_int_path, meta_int_rows)
    write_tsv(meta_float_path, meta_float_rows)
    write_tsv(meta_bool_path, meta_bool_rows)
    write_tsv(revokes_path, revokes_rows)

    schema_digest_token = schema_digest(store.schema_ir)
    policy_digest_token = policy_digest(policy_ir)

    edb_files = [
        claim_path,
        claim_arg_path,
        meta_str_path,
        meta_time_path,
        meta_int_path,
        meta_float_path,
        meta_bool_path,
        revokes_path,
    ]
    rules_files = [rules_dir / "idb.dl", rules_dir / "view.dl"]

    manifest = {
        "export_version": "v2",
        "package_kind": options.package_kind,
        "protocol_version": _protocol_version(store.schema_ir),
        "generated_at": time.time_ns(),
        "run_id": _latest_run_id(store),
        "target_engine": options.target_engine,
        "dialect_version": options.dialect_version,
        "policy_mode": options.policy_mode,
        "digests": {
            "schema_digest": schema_digest_token,
            "policy_digest": policy_digest_token,
            "edb_digest": _digest_for_paths(edb_files, package_dir),
            "rules_digest": _digest_for_paths(rules_files, package_dir),
        },
        "paths": {
            "schema": "schema/schema_ir.json",
            "policy": "policy/policy_ir.json",
            "facts": {
                "claim": "facts/claim.facts",
                "claim_arg": "facts/claim_arg.facts",
                "meta_str": "facts/meta_str.facts",
                "meta_time": "facts/meta_time.facts",
                "meta_int": "facts/meta_int.facts",
                "meta_float": "facts/meta_float.facts",
                "meta_bool": "facts/meta_bool.facts",
                "revokes": "facts/revokes.facts",
            },
            "rules": {
                "view": "rules/view.dl",
                "idb": "rules/idb.dl",
            },
            "outputs": "outputs",
            "audit": "audit" if options.package_kind == "audit" else None,
            "audit_files": audit_files if options.package_kind == "audit" else None,
        },
        "entrypoints": _entrypoints(store),
        "outputs_map": outputs_map,
    }

    manifest_path = package_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )

    return manifest_path


def _build_fact_rows(
    store: Store,
) -> tuple[
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
]:
    claim_rows: list[list[str]] = []
    for claim in store.ledger.claims:
        tup_digest = sha256_token(canonical_bytes_tup_v1(claim.rest_terms))
        claim_rows.append([claim.asrt_id, claim.pred_id, claim.e_ref, tup_digest])

    claim_arg_rows = [
        [row.asrt_id, str(row.idx), _atom_to_str(row.val_atom), row.tag]
        for row in store.ledger.claim_args
    ]

    meta_str_rows = [
        [row.asrt_id, row.key, _atom_to_str(row.value)]
        for row in store.ledger.find_meta(kind="str")
    ]
    meta_time_rows = [
        [row.asrt_id, row.key, _atom_to_str(row.value)]
        for row in store.ledger.find_meta(kind="time")
    ]
    meta_int_rows = [
        [row.asrt_id, row.key, _atom_to_str(row.value)]
        for row in store.ledger.find_meta(kind="int")
    ]
    meta_float_rows = [
        [row.asrt_id, row.key, _float_to_meta_str(row.value)]
        for row in store.ledger.find_meta(kind="float")
    ]
    meta_bool_rows = [
        [row.asrt_id, row.key, _atom_to_str(row.value)]
        for row in store.ledger.find_meta(kind="bool")
    ]
    revokes_rows = [
        [row.revoker_asrt_id, row.revoked_asrt_id] for row in store.ledger.revokes
    ]

    return (
        sorted(claim_rows),
        sorted(claim_arg_rows),
        sorted(meta_str_rows),
        sorted(meta_time_rows),
        sorted(meta_int_rows),
        sorted(meta_float_rows),
        sorted(meta_bool_rows),
        sorted(revokes_rows),
    )


def _atom_to_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    raise TypeError(f"cannot encode non-atomic TSV value: {type(value).__name__}")


def _float_to_meta_str(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, float):
        raise TypeError(f"cannot encode non-float meta value: {type(value).__name__}")
    return repr(value)


def _digest_for_paths(paths: list[Path], root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        hasher.update(rel)
        hasher.update(b"\x00")
        hasher.update(payload)
    return f"sha256:{hasher.hexdigest()}"


def _entrypoints(store: Store) -> list[str]:
    predicates = store.schema_ir.get("predicates") if isinstance(store.schema_ir, dict) else None
    if not isinstance(predicates, list):
        return []
    out: list[str] = []
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        pred_id = pred.get("pred_id")
        if isinstance(pred_id, str) and pred_id:
            out.append(pred_id)
    return sorted(set(out))


def _outputs_map(store: Store) -> dict[str, list[str]]:
    predicates = store.schema_ir.get("predicates") if isinstance(store.schema_ir, dict) else None
    if not isinstance(predicates, list):
        return {}

    out: dict[str, list[str]] = {}
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        pred_id = pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        engine_pred = normalize_pred_id(pred_id)
        out[pred_id] = [engine_pred]
    return out


def _build_policy_rules_dl(policy_mode: str) -> str:
    if policy_mode == "edb":
        return ""
    return (
        ".decl active(A:symbol)\n"
        "active(A) :- claim(A,_,_,_), !revokes(_,A).\n"
    )


def _json_where_to_ir(where_json: Any) -> Any:
    if isinstance(where_json, list):
        if where_json and isinstance(where_json[0], str) and where_json[0] in _WHERE_ATOM_TAGS:
            return tuple(_json_where_to_ir(item) for item in where_json)
        return [_json_where_to_ir(item) for item in where_json]
    if isinstance(where_json, dict):
        return {key: _json_where_to_ir(value) for key, value in where_json.items()}
    return where_json
