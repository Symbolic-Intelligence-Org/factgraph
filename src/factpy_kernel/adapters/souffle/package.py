from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factpy_kernel.adapters.souffle.pred_norm import normalize_pred_id
from factpy_kernel.adapters.souffle.tsv_v1 import write_tsv
from factpy_kernel.core.mapping.canon import MappingConflictError
from factpy_kernel.core.policy.policy_ir import (
    build_policy_ir_v1,
    canonicalize_policy_ir_jcs,
    policy_digest,
)
from factpy_kernel.core.protocol.digests import sha256_token
from factpy_kernel.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factpy_kernel.adapters.souffle.where_compile import (
    compile_where_to_query_dl,
    query_rel_for_where,
)
from factpy_kernel.core.rules._trace import rule_trace_artifact_to_dict
from factpy_kernel.core.schema.schema_ir import canonicalize_schema_ir_jcs, schema_digest
from factpy_kernel.core.store._support import support_artifact_to_dict
from factpy_kernel.core.store.runtime import Store
from factpy_kernel.adapters.souffle.souffle_view_gen import generate_view_dl


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
) -> Path:
    if not isinstance(store, Store):
        raise TypeError("store must be Store")
    if not isinstance(options, ExportOptions):
        raise TypeError("options must be ExportOptions")

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
        idb_text = compile_where_to_query_dl(
            schema_ir=store.schema_ir,
            where=where,
            query_rel=query_rel,
            include_pred_witness_columns=bool(query.get("include_pred_witness_columns")),
        )
        outputs_map["__query__"] = [query_rel]

    (rules_dir / "idb.dl").write_text(idb_text, encoding="utf-8", newline="\n")

    audit_files: dict[str, str] = {}
    if options.package_kind == "audit":
        run_ledger_rows, candidate_ledger_rows, accept_write_ledger_rows = _build_audit_ledgers(store)
        support_artifact_rows = _build_support_artifact_rows(store)
        rule_trace_artifact_rows = _build_rule_trace_artifact_rows(store)
        run_ledger_path = audit_dir / "run_ledger.jsonl"
        candidate_ledger_path = audit_dir / "candidate_ledger.jsonl"
        accept_write_ledger_path = audit_dir / "accept_write_ledger.jsonl"
        accept_failed_path = audit_dir / "accept_failed.jsonl"
        decision_log_path = audit_dir / "decision_log.jsonl"
        support_artifacts_path = audit_dir / "support_artifacts.jsonl"
        rule_trace_artifacts_path = audit_dir / "rule_trace_artifacts.jsonl"

        _write_jsonl(candidate_ledger_path, candidate_ledger_rows)
        _write_jsonl(accept_write_ledger_path, accept_write_ledger_rows)
        _write_jsonl(support_artifacts_path, support_artifact_rows)
        _write_jsonl(rule_trace_artifacts_path, rule_trace_artifact_rows)

        audit_files["run_ledger"] = "audit/run_ledger.jsonl"
        audit_files["candidate_ledger"] = "audit/candidate_ledger.jsonl"
        audit_files["accept_write_ledger"] = "audit/accept_write_ledger.jsonl"
        audit_files["accept_failed"] = "audit/accept_failed.jsonl"
        audit_files["support_artifacts"] = "audit/support_artifacts.jsonl"
        audit_files["rule_trace_artifacts"] = "audit/rule_trace_artifacts.jsonl"

        mapping_audit = _build_mapping_audit_payload(store, options.policy_mode)
        mapping_audit_path = audit_dir / "mapping_resolution.json"
        mapping_audit_path.write_text(
            json.dumps(mapping_audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
            newline="\n",
        )
        accept_failed_rows = _build_accept_failed_rows(store, mapping_audit)
        _write_jsonl(accept_failed_path, accept_failed_rows)
        decision_rows = _build_decision_log_rows(
            store=store,
            accept_write_rows=accept_write_ledger_rows,
            mapping_audit=mapping_audit,
        )
        _write_jsonl(decision_log_path, decision_rows)
        run_ledger_rows = _attach_decision_ids_to_run_ledger(
            run_rows=run_ledger_rows,
            decision_rows=decision_rows,
            accept_failed_rows=accept_failed_rows,
        )
        _write_jsonl(run_ledger_path, run_ledger_rows)
        audit_files["mapping_resolution"] = "audit/mapping_resolution.json"
        audit_files["decision_log"] = "audit/decision_log.jsonl"

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


def _protocol_version(schema_ir: dict) -> dict[str, str]:
    base = {
        "idref_v1": "idref_v1",
        "tup_v1": "tup_v1",
        "export_v1": "export_v1",
    }
    raw = schema_ir.get("protocol_version") if isinstance(schema_ir, dict) else None
    if not isinstance(raw, dict):
        return base
    for key in ("idref_v1", "tup_v1", "export_v1"):
        value = raw.get(key)
        if isinstance(value, str) and value:
            base[key] = value
    return base


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


def _latest_run_id(store: Store) -> str | None:
    run_rows = store.ledger.find_meta(key="run_id", kind="str")
    if not run_rows:
        return None
    return str(run_rows[-1].value)


def _build_mapping_audit_payload(store: Store, policy_mode: str) -> dict[str, Any]:
    predicates = store.schema_ir.get("predicates") if isinstance(store.schema_ir, dict) else None
    mapping_pred_ids: list[str] = []
    if isinstance(predicates, list):
        for pred in predicates:
            if not isinstance(pred, dict):
                continue
            pred_id = pred.get("pred_id")
            if isinstance(pred_id, str) and pred_id and pred.get("is_mapping") is True:
                mapping_pred_ids.append(pred_id)

    rows: list[dict[str, Any]] = []
    for pred_id in sorted(set(mapping_pred_ids)):
        row: dict[str, Any] = {
            "pred_id": pred_id,
            "policy_mode": policy_mode,
        }
        try:
            resolution = store.resolve_mapping(pred_id, policy_mode=policy_mode)
            row["status"] = "resolved"
            row["candidate_count"] = len(resolution.candidates)
            row["chosen"] = [
                {"key_tuple": list(key_tuple), "value_tuple": list(value_tuple)}
                for key_tuple, value_tuple in sorted(
                    resolution.chosen_map.items(),
                    key=lambda kv: tuple(str(part) for part in kv[0]),
                )
            ]
            row["decisions"] = [
                {
                    "key_tuple": list(decision.key_tuple),
                    "chosen_asrt_id": decision.chosen_asrt_id,
                    "chosen_value_tuple": list(decision.chosen_value_tuple),
                    "reason": decision.reason,
                    "candidate_asrt_ids": list(decision.candidate_asrt_ids),
                }
                for decision in resolution.decisions
            ]
        except MappingConflictError as exc:
            row["status"] = "conflict"
            row["error"] = str(exc)
            row["conflicts"] = exc.conflicts
        except Exception as exc:
            row["status"] = "error"
            row["error"] = str(exc)
        rows.append(row)

    return {
        "mapping_audit_version": "mapping_audit_v1",
        "generated_at": time.time_ns(),
        "policy_mode": policy_mode,
        "predicates": rows,
    }


def _build_policy_rules_dl(policy_mode: str) -> str:
    if policy_mode == "edb":
        return ""
    return (
        ".decl active(A:symbol)\n"
        "active(A) :- claim(A,_,_,_), !revokes(_,A).\n"
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            handle.write("\n")


def _build_audit_ledgers(
    store: Store,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    run_rows = _build_run_ledger_rows(store)
    accept_write_rows = _build_accept_write_ledger_rows(store)
    candidate_rows = _build_candidate_ledger_rows(accept_write_rows)
    return run_rows, candidate_rows, accept_write_rows


def _build_support_artifact_rows(store: Store) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for support_digest, artifact in store._support_artifacts.items():
        rows.append(
            {
                "support_digest": support_digest,
                **support_artifact_to_dict(artifact),
            }
        )
    return sorted(rows, key=lambda row: str(row.get("support_digest")))


def _build_rule_trace_artifact_rows(store: Store) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _rule_run_id, artifact in store._rule_trace_artifacts.items():
        rows.append(rule_trace_artifact_to_dict(artifact))
    return sorted(rows, key=lambda row: str(row.get("rule_run_id")))


def _build_candidate_ledger_rows(accept_write_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in accept_write_rows:
        key_tuple_digest = row.get("key_tuple_digest")
        cand_key_digest = row.get("cand_key_digest")
        asrt_id = row.get("asrt_id")
        candidate_id = row.get("candidate_id")
        ingested_at = row.get("ingested_at")
        if not isinstance(key_tuple_digest, str) or not key_tuple_digest:
            continue
        if not isinstance(cand_key_digest, str) or not cand_key_digest:
            continue
        if not isinstance(asrt_id, str) or not asrt_id:
            continue
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        decision_id = _accept_write_decision_id(candidate_id, asrt_id)

        rows.append(
            {
                "state": "accepted",
                "asrt_id": asrt_id,
                "pred_id": row.get("pred_id"),
                "run_id": row.get("run_id"),
                "candidate_id": candidate_id,
                "key_tuple_digest": key_tuple_digest,
                "cand_key_digest": cand_key_digest,
                "support_digest": row.get("support_digest"),
                "support_kind": row.get("support_kind"),
                "decision_id": decision_id,
                "event_source": "accept",
                "event_kind": "accept_write",
                "event_ts": ingested_at if isinstance(ingested_at, int) and not isinstance(ingested_at, bool) else None,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("cand_key_digest")),
            str(row.get("asrt_id")),
        ),
    )


def _build_accept_failed_rows(store: Store, mapping_audit: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    predicates = mapping_audit.get("predicates")
    policy_mode = mapping_audit.get("policy_mode")
    if not isinstance(predicates, list):
        return rows

    for pred_row in predicates:
        if not isinstance(pred_row, dict):
            continue
        pred_id = pred_row.get("pred_id")
        status = pred_row.get("status")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if status == "conflict":
            conflicts = pred_row.get("conflicts")
            if isinstance(conflicts, list):
                for conflict in conflicts:
                    if not isinstance(conflict, dict):
                        continue
                    candidate_asrt_ids = conflict.get("candidate_asrt_ids")
                    run_ids, candidate_ids = _collect_run_candidate_ids(
                        store,
                        candidate_asrt_ids,
                    )
                    event_ts = _collect_event_ts(store, candidate_asrt_ids)
                    decision_id = _mapping_conflict_decision_id(
                        pred_id=pred_id,
                        key_tuple=conflict.get("key_tuple"),
                    )
                    rows.append(
                        {
                            "decision_id": decision_id,
                            "event_source": "mapping",
                            "event_kind": "mapping_conflict",
                            "error_class": "mapping_conflict",
                            "pred_id": pred_id,
                            "policy_mode": policy_mode,
                            "message": pred_row.get("error"),
                            "key_tuple": conflict.get("key_tuple"),
                            "candidate_asrt_ids": candidate_asrt_ids,
                            "run_ids": run_ids,
                            "candidate_ids": candidate_ids,
                            "event_ts": event_ts,
                        }
                    )
        elif status == "error":
            decision_id = _mapping_error_decision_id(pred_id)
            rows.append(
                {
                    "decision_id": decision_id,
                    "event_source": "mapping",
                    "event_kind": "mapping_error",
                    "error_class": "mapping_error",
                    "pred_id": pred_id,
                    "policy_mode": policy_mode,
                    "message": pred_row.get("error"),
                    "run_ids": [],
                    "candidate_ids": [],
                    "event_ts": None,
                }
            )

    return sorted(
        rows,
        key=lambda row: json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _build_decision_log_rows(
    *,
    store: Store,
    accept_write_rows: list[dict[str, Any]],
    mapping_audit: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in accept_write_rows:
        candidate_id = row.get("candidate_id")
        asrt_id = row.get("asrt_id")
        decision_id = _accept_write_decision_id(candidate_id, asrt_id)
        if decision_id is None:
            continue
        ingested_at = row.get("ingested_at")
        rows.append(
            {
                "decision_id": decision_id,
                "event_source": "accept",
                "event_kind": "accept_write",
                "candidate_id": candidate_id,
                "asrt_id": asrt_id,
                "pred_id": row.get("pred_id"),
                "run_id": row.get("run_id"),
                "derived_rule_id": row.get("derived_rule_id"),
                "derived_rule_version": row.get("derived_rule_version"),
                "key_tuple_digest": row.get("key_tuple_digest"),
                "cand_key_digest": row.get("cand_key_digest"),
                "support_digest": row.get("support_digest"),
                "support_kind": row.get("support_kind"),
                "run_ids": [row.get("run_id")] if isinstance(row.get("run_id"), str) and row.get("run_id") else [],
                "candidate_ids": [candidate_id] if isinstance(candidate_id, str) and candidate_id else [],
                "event_ts": ingested_at if isinstance(ingested_at, int) and not isinstance(ingested_at, bool) else None,
            }
        )

    predicates = mapping_audit.get("predicates")
    policy_mode = mapping_audit.get("policy_mode")
    if isinstance(predicates, list):
        for pred_row in predicates:
            if not isinstance(pred_row, dict):
                continue
            pred_id = pred_row.get("pred_id")
            status = pred_row.get("status")
            if not isinstance(pred_id, str) or not pred_id:
                continue

            if status == "resolved":
                decisions = pred_row.get("decisions")
                if isinstance(decisions, list):
                    for decision in decisions:
                        if not isinstance(decision, dict):
                            continue
                        candidate_asrt_ids = decision.get("candidate_asrt_ids")
                        run_ids, candidate_ids = _collect_run_candidate_ids(
                            store,
                            candidate_asrt_ids,
                        )
                        event_ts = _collect_event_ts(store, candidate_asrt_ids)
                        decision_id = _mapping_decision_id(
                            pred_id=pred_id,
                            key_tuple=decision.get("key_tuple"),
                        )
                        rows.append(
                            {
                                "decision_id": decision_id,
                                "event_source": "mapping",
                                "event_kind": "mapping_decision",
                                "pred_id": pred_id,
                                "policy_mode": policy_mode,
                                "status": status,
                                "key_tuple": decision.get("key_tuple"),
                                "chosen_asrt_id": decision.get("chosen_asrt_id"),
                                "chosen_value_tuple": decision.get("chosen_value_tuple"),
                                "reason": decision.get("reason"),
                                "candidate_asrt_ids": candidate_asrt_ids,
                                "run_ids": run_ids,
                                "candidate_ids": candidate_ids,
                                "event_ts": event_ts,
                            }
                        )
            elif status == "conflict":
                conflicts = pred_row.get("conflicts")
                if isinstance(conflicts, list):
                    for conflict in conflicts:
                        if not isinstance(conflict, dict):
                            continue
                        candidate_asrt_ids = conflict.get("candidate_asrt_ids")
                        run_ids, candidate_ids = _collect_run_candidate_ids(
                            store,
                            candidate_asrt_ids,
                        )
                        event_ts = _collect_event_ts(store, candidate_asrt_ids)
                        decision_id = _mapping_conflict_decision_id(
                            pred_id=pred_id,
                            key_tuple=conflict.get("key_tuple"),
                        )
                        rows.append(
                            {
                                "decision_id": decision_id,
                                "event_source": "mapping",
                                "event_kind": "mapping_conflict",
                                "pred_id": pred_id,
                                "policy_mode": policy_mode,
                                "status": status,
                                "key_tuple": conflict.get("key_tuple"),
                                "candidate_values": conflict.get("candidate_values"),
                                "candidate_asrt_ids": candidate_asrt_ids,
                                "error": pred_row.get("error"),
                                "run_ids": run_ids,
                                "candidate_ids": candidate_ids,
                                "event_ts": event_ts,
                            }
                        )
            elif status == "error":
                decision_id = _mapping_error_decision_id(pred_id)
                rows.append(
                    {
                        "decision_id": decision_id,
                        "event_source": "mapping",
                        "event_kind": "mapping_error",
                        "pred_id": pred_id,
                        "policy_mode": policy_mode,
                        "status": status,
                        "error": pred_row.get("error"),
                        "run_ids": [],
                        "candidate_ids": [],
                        "event_ts": None,
                    }
                )

    return sorted(
        rows,
        key=lambda row: json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _build_run_ledger_rows(store: Store) -> list[dict[str, Any]]:
    run_map: dict[str, dict[str, Any]] = {}
    for claim in sorted(store.ledger.claims, key=lambda row: row.asrt_id):
        run_id = _meta_str(store, claim.asrt_id, "run_id")
        if run_id is None:
            continue
        entry = run_map.get(run_id)
        if entry is None:
            entry = {
                "run_id": run_id,
                "claim_count": 0,
                "candidate_ids": set(),
                "pred_ids": set(),
            }
            run_map[run_id] = entry
        entry["claim_count"] += 1
        entry["pred_ids"].add(claim.pred_id)
        candidate_id = _meta_str(store, claim.asrt_id, "candidate_id")
        if candidate_id:
            entry["candidate_ids"].add(candidate_id)

    out: list[dict[str, Any]] = []
    for run_id in sorted(run_map):
        row = run_map[run_id]
        out.append(
            {
                "run_id": run_id,
                "claim_count": row["claim_count"],
                "candidate_ids": sorted(row["candidate_ids"]),
                "pred_ids": sorted(row["pred_ids"]),
            }
        )
    return out


def _attach_decision_ids_to_run_ledger(
    run_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
    accept_failed_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    run_to_decision_ids: dict[str, set[str]] = {}
    run_to_event_ts_values: dict[str, list[int]] = {}
    run_to_source_counts: dict[str, dict[str, int]] = {}
    run_to_kind_counts: dict[str, dict[str, int]] = {}
    run_to_error_count: dict[str, int] = {}
    run_to_error_class_counts: dict[str, dict[str, int]] = {}
    run_to_error_event_kind_counts: dict[str, dict[str, int]] = {}
    run_to_error_ts_values: dict[str, list[int]] = {}
    run_to_failed_decision_ids: dict[str, set[str]] = {}
    run_to_latest_failure: dict[str, tuple[tuple[int, int, str], str | None, str | None, str | None]] = {}
    for row in decision_rows:
        if not isinstance(row, dict):
            continue
        decision_id = row.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id:
            continue
        event_source = row.get("event_source")
        source_value = event_source if isinstance(event_source, str) and event_source else None
        event_kind = row.get("event_kind")
        kind_value = event_kind if isinstance(event_kind, str) and event_kind else None
        event_ts = row.get("event_ts")
        event_ts_value = event_ts if isinstance(event_ts, int) and not isinstance(event_ts, bool) else None
        target_runs: set[str] = set()
        run_id = row.get("run_id")
        if isinstance(run_id, str) and run_id:
            target_runs.add(run_id)
        run_ids = row.get("run_ids")
        if isinstance(run_ids, list):
            for value in run_ids:
                if isinstance(value, str) and value:
                    target_runs.add(value)
        for target_run in target_runs:
            run_to_decision_ids.setdefault(target_run, set()).add(decision_id)
            if source_value is not None:
                source_counts = run_to_source_counts.setdefault(target_run, {})
                source_counts[source_value] = source_counts.get(source_value, 0) + 1
            if kind_value is not None:
                kind_counts = run_to_kind_counts.setdefault(target_run, {})
                kind_counts[kind_value] = kind_counts.get(kind_value, 0) + 1
            if event_ts_value is not None:
                run_to_event_ts_values.setdefault(target_run, []).append(event_ts_value)

    for row in accept_failed_rows:
        if not isinstance(row, dict):
            continue
        run_ids = row.get("run_ids")
        if not isinstance(run_ids, list):
            continue
        target_runs = sorted(
            {
                value
                for value in run_ids
                if isinstance(value, str) and value
            }
        )
        if not target_runs:
            continue

        error_class = row.get("error_class")
        error_class_value = error_class if isinstance(error_class, str) and error_class else None
        error_event_kind = row.get("event_kind")
        error_event_kind_value = (
            error_event_kind if isinstance(error_event_kind, str) and error_event_kind else None
        )
        error_event_ts = row.get("event_ts")
        error_event_ts_value = (
            error_event_ts if isinstance(error_event_ts, int) and not isinstance(error_event_ts, bool) else None
        )
        decision_id = row.get("decision_id")
        decision_id_value = decision_id if isinstance(decision_id, str) and decision_id else None
        message = row.get("message")
        message_value = message if isinstance(message, str) and message else None

        for target_run in target_runs:
            run_to_error_count[target_run] = run_to_error_count.get(target_run, 0) + 1
            if error_class_value is not None:
                class_counts = run_to_error_class_counts.setdefault(target_run, {})
                class_counts[error_class_value] = class_counts.get(error_class_value, 0) + 1
            if error_event_kind_value is not None:
                kind_counts = run_to_error_event_kind_counts.setdefault(target_run, {})
                kind_counts[error_event_kind_value] = kind_counts.get(error_event_kind_value, 0) + 1
            if error_event_ts_value is not None:
                run_to_error_ts_values.setdefault(target_run, []).append(error_event_ts_value)
            if decision_id_value is not None:
                run_to_failed_decision_ids.setdefault(target_run, set()).add(decision_id_value)
            latest_sort_key = (
                1 if error_event_ts_value is not None else 0,
                error_event_ts_value if error_event_ts_value is not None else -1,
                decision_id_value or "",
            )
            previous_latest = run_to_latest_failure.get(target_run)
            if previous_latest is None or latest_sort_key > previous_latest[0]:
                run_to_latest_failure[target_run] = (
                    latest_sort_key,
                    error_class_value,
                    decision_id_value,
                    message_value,
                )

    out: list[dict[str, Any]] = []
    for row in run_rows:
        run_id = row.get("run_id")
        if isinstance(run_id, str):
            decision_ids = sorted(run_to_decision_ids.get(run_id, set()))
            event_ts_values = run_to_event_ts_values.get(run_id, [])
            source_counts = dict(run_to_source_counts.get(run_id, {}))
            kind_counts = dict(run_to_kind_counts.get(run_id, {}))
            error_count = run_to_error_count.get(run_id, 0)
            error_class_counts = dict(run_to_error_class_counts.get(run_id, {}))
            error_event_kind_counts = dict(run_to_error_event_kind_counts.get(run_id, {}))
            error_ts_values = run_to_error_ts_values.get(run_id, [])
            failed_decision_ids = sorted(run_to_failed_decision_ids.get(run_id, set()))
            latest_failure = run_to_latest_failure.get(run_id)
        else:
            decision_ids = []
            event_ts_values = []
            source_counts = {}
            kind_counts = {}
            error_count = 0
            error_class_counts = {}
            error_event_kind_counts = {}
            error_ts_values = []
            failed_decision_ids = []
            latest_failure = None
        next_row = dict(row)
        next_row["decision_ids"] = decision_ids
        next_row["decision_count"] = len(decision_ids)
        next_row["event_source_counts"] = source_counts
        next_row["event_kind_counts"] = kind_counts
        next_row["error_count"] = error_count
        next_row["error_class_counts"] = error_class_counts
        next_row["error_event_kind_counts"] = error_event_kind_counts
        next_row["failed_decision_ids"] = failed_decision_ids
        next_row["has_failures"] = error_count > 0
        next_row["last_error_ts"] = max(error_ts_values) if error_ts_values else None
        next_row["failed_event_ts_min"] = min(error_ts_values) if error_ts_values else None
        next_row["failed_event_ts_max"] = max(error_ts_values) if error_ts_values else None
        if latest_failure is not None:
            next_row["last_failure_class"] = latest_failure[1]
            next_row["last_failure_decision_id"] = latest_failure[2]
            next_row["last_failure_message"] = latest_failure[3]
        else:
            next_row["last_failure_class"] = None
            next_row["last_failure_decision_id"] = None
            next_row["last_failure_message"] = None
        if event_ts_values:
            next_row["event_ts_min"] = min(event_ts_values)
            next_row["event_ts_max"] = max(event_ts_values)
        else:
            next_row["event_ts_min"] = None
            next_row["event_ts_max"] = None
        out.append(next_row)
    return out


def _build_accept_write_ledger_rows(store: Store) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for claim in sorted(store.ledger.claims, key=lambda row: row.asrt_id):
        candidate_id = _meta_str(store, claim.asrt_id, "candidate_id")
        if candidate_id is None:
            continue
        row: dict[str, Any] = {
            "candidate_id": candidate_id,
            "asrt_id": claim.asrt_id,
            "pred_id": claim.pred_id,
            "e_ref": claim.e_ref,
            "run_id": _meta_str(store, claim.asrt_id, "run_id"),
            "derived_rule_id": _meta_str(store, claim.asrt_id, "derived_rule_id"),
            "derived_rule_version": _meta_str(store, claim.asrt_id, "derived_rule_version"),
            "key_tuple_digest": _meta_str(store, claim.asrt_id, "key_tuple_digest"),
            "cand_key_digest": _meta_str(store, claim.asrt_id, "cand_key_digest"),
            "support_digest": _meta_str(store, claim.asrt_id, "support_digest"),
            "support_kind": _meta_str(store, claim.asrt_id, "support_kind"),
            "approved_by": _meta_str(store, claim.asrt_id, "approved_by"),
            "note": _meta_str(store, claim.asrt_id, "note"),
            "ingested_at": _meta_time(store, claim.asrt_id, "ingested_at"),
        }
        rows.append(row)
    return sorted(rows, key=lambda row: (str(row["candidate_id"]), str(row["asrt_id"])))


def _meta_str(store: Store, asrt_id: str, key: str) -> str | None:
    for row in store.ledger.find_meta(asrt_id=asrt_id, key=key, kind="str"):
        if isinstance(row.value, str):
            return row.value
    return None


def _meta_time(store: Store, asrt_id: str, key: str) -> int | None:
    for row in store.ledger.find_meta(asrt_id=asrt_id, key=key, kind="time"):
        if isinstance(row.value, int) and not isinstance(row.value, bool):
            return row.value
    return None


def _accept_write_decision_id(candidate_id: Any, asrt_id: Any) -> str | None:
    if not isinstance(candidate_id, str) or not candidate_id:
        return None
    if not isinstance(asrt_id, str) or not asrt_id:
        return None
    return f"accept_write:{candidate_id}:{asrt_id}"


def _collect_run_candidate_ids(store: Store, candidate_asrt_ids: Any) -> tuple[list[str], list[str]]:
    if not isinstance(candidate_asrt_ids, list):
        return [], []

    run_ids: set[str] = set()
    candidate_ids: set[str] = set()
    for asrt_id in candidate_asrt_ids:
        if not isinstance(asrt_id, str) or not asrt_id:
            continue
        run_id = _meta_str(store, asrt_id, "run_id")
        candidate_id = _meta_str(store, asrt_id, "candidate_id")
        if run_id:
            run_ids.add(run_id)
        if candidate_id:
            candidate_ids.add(candidate_id)
    return sorted(run_ids), sorted(candidate_ids)


def _collect_event_ts(store: Store, candidate_asrt_ids: Any) -> int | None:
    if not isinstance(candidate_asrt_ids, list):
        return None
    values: list[int] = []
    for asrt_id in candidate_asrt_ids:
        if not isinstance(asrt_id, str) or not asrt_id:
            continue
        value = _meta_time(store, asrt_id, "ingested_at")
        if isinstance(value, int) and not isinstance(value, bool):
            values.append(value)
    if not values:
        return None
    return max(values)


def _mapping_decision_id(pred_id: str, key_tuple: Any) -> str:
    return f"mapping_decision:{pred_id}:{_stable_key_hash(key_tuple)}"


def _mapping_conflict_decision_id(pred_id: str, key_tuple: Any) -> str:
    return f"mapping_conflict:{pred_id}:{_stable_key_hash(key_tuple)}"


def _mapping_error_decision_id(pred_id: str) -> str:
    return f"mapping_error:{pred_id}"


def _stable_key_hash(value: Any) -> str:
    payload = json.dumps(
        {"key_tuple": value},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]
