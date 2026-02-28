from __future__ import annotations

import base64
import binascii
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from time import time_ns
from typing import Any
from uuid import uuid4

from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.authoring import FileAuthoringRegistry
from factpy_kernel.authoring.derivation_compile import (
    AuthoringDerivationCompileError,
    compile_authoring_derivation_v1,
)
from factpy_kernel.authoring.rules import compile_authoring_rule_v1
from factpy_kernel.core.derivation.accept import AcceptOptions, AcceptResult
from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.evidence.write_protocol import add_field, retract_by_asrt, set_field
from factpy_kernel.core.mapping.canon import MappingConflictError, MappingResolution
from factpy_kernel.core.rules.rule_ir import RuleRegistry, RuleSpec, run_rule
from factpy_kernel.core.schema.schema_ir import schema_digest
from factpy_kernel.core.store import builders
from factpy_kernel.core.store.runtime import Store
from factpy_kernel.core.store.ledger import Claim, ClaimArg, Ledger, MetaRow
from factpy_kernel.core.view.projector import project_view_facts, project_view_facts_with_audit

from ._common import error_response, exception_to_error, facade_error, ok_response
from ._registry_io import load_registry_schema_ir

_ATOM_TAGS = {
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


@dataclass
class RuntimeSession:
    session_id: str
    store: Store
    ledger_path: str | None
    registry_root: str | None
    schema_digest: str
    opened_at_ns: int


class _RuntimeSessionManager:
    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, RuntimeSession] = {}

    def open(
        self,
        *,
        store: Store,
        ledger_path: str | None,
        registry_root: str | None,
        digest: str,
    ) -> RuntimeSession:
        session = RuntimeSession(
            session_id=f"rt_{uuid4().hex}",
            store=store,
            ledger_path=ledger_path,
            registry_root=registry_root,
            schema_digest=digest,
            opened_at_ns=time_ns(),
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> RuntimeSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def close(self, session_id: str) -> RuntimeSession | None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            session.store.ledger.close()
        return session

    def reset_for_tests(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.store.ledger.close()


_SESSIONS = _RuntimeSessionManager()


def reset_runtime_sessions_for_tests() -> None:
    _SESSIONS.reset_for_tests()


def open_runtime_session(dto: dict[str, Any]) -> dict[str, Any]:
    try:
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        schema_ir, registry_root = _resolve_schema_ir(dto)
        digest = schema_digest(schema_ir)
        ledger_path = _optional_str(dto.get("ledger_path"), path="$.ledger_path")
        ledger = _open_ledger(ledger_path)
        try:
            _bind_ledger_schema(ledger, digest)
        except Exception:
            ledger.close()
            raise
        store = Store(schema_ir=schema_ir, ledger=ledger)
        session = _SESSIONS.open(
            store=store,
            ledger_path=ledger_path,
            registry_root=registry_root,
            digest=digest,
        )
        return ok_response(session=_session_to_dict(session))
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def get_runtime_session(session_id: str) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        return ok_response(session=_session_to_dict(session))
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def close_runtime_session(session_id: str) -> dict[str, Any]:
    try:
        if not isinstance(session_id, str) or not session_id:
            raise facade_error("session_id must be non-empty string", kind="shape", path="$.session_id")
        session = _SESSIONS.close(session_id)
        if session is None:
            raise facade_error(
                f"runtime session not found: {session_id}",
                kind="runtime_session_not_found",
                path="$.session_id",
                details={"session_id": session_id},
            )
        return ok_response(closed={"session_id": session_id})
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def write_runtime_fact(session_id: str, dto: dict[str, Any], *, kind: str) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        pred_id = _require_non_empty_str(dto.get("pred_id"), path="$.pred_id")
        e_ref = _require_non_empty_str(dto.get("e_ref"), path="$.e_ref")
        rest_terms = _normalize_rest_terms(dto.get("rest_terms"), path="$.rest_terms")
        meta = _optional_dict(dto.get("meta"), path="$.meta")
        if kind == "set":
            asrt_id = set_field(session.store.ledger, pred_id, e_ref, rest_terms, meta)
        elif kind == "add":
            asrt_id = add_field(session.store.ledger, pred_id, e_ref, rest_terms, meta)
        else:
            raise facade_error(
                f"unsupported write kind: {kind}",
                kind="shape",
                path="$.kind",
                details={"kind": kind},
            )
        return ok_response(write={"kind": kind, "assertion_id": asrt_id})
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def retract_runtime_fact(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        asrt_id = _require_non_empty_str(dto.get("asrt_id"), path="$.asrt_id")
        meta = _optional_dict(dto.get("meta"), path="$.meta")
        revoker_id = retract_by_asrt(session.store.ledger, asrt_id, meta)
        return ok_response(write={"kind": "retract", "assertion_id": revoker_id})
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def list_runtime_claims(
    session_id: str,
    *,
    pred_id: str | None = None,
    e_ref: str | None = None,
    include_meta: bool = False,
    include_args: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise facade_error("limit must be non-negative int", kind="shape", path="$.limit")
        claims = session.store.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
        if limit is not None:
            claims = claims[:limit]
        return ok_response(
            claims=[
                _claim_to_dict(
                    session.store.ledger,
                    claim,
                    include_meta=include_meta,
                    include_args=include_args,
                )
                for claim in claims
            ]
        )
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def explain_runtime_fact(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        pred_id = _require_non_empty_str(dto.get("pred_id"), path="$.pred_id")
        e_ref = _require_non_empty_str(dto.get("e_ref"), path="$.e_ref")
        val_atoms = _optional_val_atoms(dto.get("val_atoms"), path="$.val_atoms")
        explain = (
            session.store.explain_fact(pred_id, e_ref, *val_atoms)
            if val_atoms is not None
            else session.store.explain_fact(pred_id, e_ref)
        )
        return ok_response(
            meta={"pred_id": pred_id, "e_ref": e_ref},
            explain=_to_jsonable(explain),
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_fact")
        return error_response([err])


def list_runtime_conflicts(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        pred_id = _require_non_empty_str(dto.get("pred_id"), path="$.pred_id")
        e_ref = _require_non_empty_str(dto.get("e_ref"), path="$.e_ref")
        conflicts = session.store.conflicts(pred_id, e_ref)
        return ok_response(
            meta={"pred_id": pred_id, "e_ref": e_ref},
            conflicts=_to_jsonable(conflicts),
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_conflicts")
        return error_response([err])


def resolve_runtime_mapping(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        pred_id = _require_non_empty_str(dto.get("pred_id"), path="$.pred_id")
        _require_mapping_predicate(session.store, pred_id, path="$.pred_id")
        resolution = session.store.resolve_mapping(pred_id)
        return ok_response(
            meta={"pred_id": pred_id},
            mapping=_mapping_resolution_to_dict(resolution),
        )
    except MappingConflictError as exc:
        return error_response([_mapping_conflict_to_error(exc)], meta={"pred_id": dto.get("pred_id")})
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_resolve_mapping")
        return error_response([err])


def project_runtime_view_facts(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        temporal_view_core, temporal_view_public = _resolve_view_temporal_view(
            dto.get("temporal_view"),
            path="$.temporal_view",
        )
        legacy_record_visibility = _resolve_legacy_record_visibility(
            dto.get("legacy_record_visibility"),
            path="$.legacy_record_visibility",
        )
        include_audit = _resolve_include_audit(dto.get("include_audit"), path="$.include_audit")
        if include_audit:
            facts, audit = project_view_facts_with_audit(
                session.store.ledger,
                session.store.schema_ir,
                temporal_view=temporal_view_core,
                legacy_record_visibility=legacy_record_visibility,
            )
            view = {
                "facts": _to_jsonable(facts),
                "audit": asdict(audit),
            }
        else:
            facts = project_view_facts(
                session.store.ledger,
                session.store.schema_ir,
                temporal_view=temporal_view_core,
                legacy_record_visibility=legacy_record_visibility,
            )
            view = {"facts": _to_jsonable(facts)}
        return ok_response(
            meta={
                "temporal_view": temporal_view_public,
                "legacy_record_visibility": legacy_record_visibility,
                "pred_count": len(facts),
                "total_tuple_count": sum(len(rows) for rows in facts.values()),
            },
            view=view,
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_view_facts")
        return error_response([err])


def run_runtime_rule(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        raw_rule = dto.get("rule")
        if not isinstance(raw_rule, dict):
            raise facade_error("rule must be object", kind="shape", path="$.rule")
        normalized_rule = dict(raw_rule)
        if "where" in normalized_rule:
            normalized_rule["where"] = _json_where_to_ir(normalized_rule["where"])
        temporal_view = dto.get("temporal_view", "record")
        if temporal_view not in {"record", "current"}:
            raise facade_error(
                "temporal_view must be 'record' or 'current'",
                kind="shape",
                path="$.temporal_view",
            )
        compiled = compile_authoring_rule_v1(normalized_rule, schema_ir=session.store.schema_ir)
        active_registry = RuleRegistry()
        registry_root = _resolve_rule_registry_root(session, dto)
        if registry_root is not None:
            _load_registered_rules(active_registry, registry_root)
        rows = run_rule(
            session.store,
            RuleSpec(
                rule_id=compiled["rule_id"],
                version=compiled["version"],
                select_vars=list(compiled["select_vars"]),
                where=list(compiled["where"]),
                expose=bool(compiled.get("expose", False)),
            ),
            active_registry,
            temporal_view=temporal_view,
        )
        return ok_response(
            result={
                "rule_id": compiled["rule_id"],
                "version": compiled["version"],
                "rows": [_jsonable_row(row) for row in rows],
            }
        )
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def evaluate_runtime_derivation(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        compiled = _compile_runtime_derivation(dto, schema_ir=session.store.schema_ir)
        limit = _optional_limit(dto.get("limit"), path="$.limit")
        candidates = session.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=list(compiled["head_vars"]),
            where=list(compiled["where"]),
            mode=compiled["mode"],
            temporal_view=compiled["temporal_view"],
            materialize_as=compiled.get("materialize_as"),
            head=compiled.get("head"),
            id_policy=compiled.get("id_policy"),
        )
        returned_candidates = candidates if limit is None else candidates[:limit]
        return ok_response(
            meta={
                "mode": compiled["mode"],
                "temporal_view": compiled["temporal_view"],
                "candidate_count": len(candidates),
                "returned_count": len(returned_candidates),
                "truncated": len(returned_candidates) != len(candidates),
            },
            evaluation={
                "derivation_id": compiled["derivation_id"],
                "version": compiled["version"],
                "target_pred_id": compiled["target_pred_id"],
                "candidates": [_candidate_to_dict(item) for item in returned_candidates],
            },
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="derivation_evaluate")
        return error_response([err])


def accept_runtime_derivation(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        raw_candidate = dto.get("candidate")
        if not isinstance(raw_candidate, dict):
            raise facade_error("candidate must be object", kind="shape", path="$.candidate")
        candidate = _candidate_from_dict(raw_candidate, path="$.candidate")
        options = _accept_options_from_dto(dto.get("options"), path="$.options")
        result = session.store.accept(
            derivation_id=candidate.derivation_id,
            version=candidate.derivation_version,
            candidate_set=candidate,
            options=options,
        )
        return ok_response(
            meta={
                "dry_run": options.dry_run,
                "terminal": _accept_result_terminal(result),
            },
            accept=_accept_result_to_dict(result),
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="derivation_accept")
        return error_response([err])


def export_runtime_package(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        out_dir = _require_non_empty_str(dto.get("out_dir"), path="$.out_dir")
        package_kind = dto.get("package_kind", "inference")
        if package_kind not in {"inference", "audit"}:
            raise facade_error(
                "package_kind must be 'inference' or 'audit'",
                kind="shape",
                path="$.package_kind",
            )
        query = dto.get("query")
        export_package(
            session.store,
            out_dir,
            ExportOptions(package_kind=package_kind),
            query=query,
        )
        return ok_response(
            package={
                "out_dir": out_dir,
                "package_kind": package_kind,
                "manifest_path": str(Path(out_dir) / "manifest.json"),
            }
        )
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def _resolve_schema_ir(dto: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    raw_schema_ir = dto.get("schema_ir")
    raw_registry_root = dto.get("registry_root")
    if raw_schema_ir is not None and raw_registry_root is not None:
        raise facade_error(
            "provide either schema_ir or registry_root, not both",
            kind="shape",
            path="$",
        )
    if raw_schema_ir is None and raw_registry_root is None:
        raise facade_error(
            "schema_ir or registry_root is required",
            kind="shape",
            path="$",
        )
    if raw_schema_ir is not None:
        if not isinstance(raw_schema_ir, dict):
            raise facade_error("schema_ir must be object", kind="shape", path="$.schema_ir")
        return dict(raw_schema_ir), None
    registry_root = _require_non_empty_str(raw_registry_root, path="$.registry_root")
    return load_registry_schema_ir(registry_root), registry_root


def _open_ledger(ledger_path: str | None) -> Ledger:
    if ledger_path is None:
        return Ledger()
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return Ledger(path=path)


def _bind_ledger_schema(ledger: Ledger, digest: str) -> None:
    stored_digest = ledger.get_ledger_meta("schema_digest")
    if stored_digest is None:
        ledger.set_ledger_meta("schema_digest", digest)
        return
    if stored_digest != digest:
        raise facade_error(
            "schema mismatch for ledger_path",
            kind="schema_mismatch",
            path="$.ledger_path",
            details={"stored_digest": stored_digest, "current_digest": digest},
        )


def _require_session(session_id: str) -> RuntimeSession:
    if not isinstance(session_id, str) or not session_id:
        raise facade_error("session_id must be non-empty string", kind="shape", path="$.session_id")
    session = _SESSIONS.get(session_id)
    if session is None:
        raise facade_error(
            f"runtime session not found: {session_id}",
            kind="runtime_session_not_found",
            path="$.session_id",
            details={"session_id": session_id},
        )
    return session


def _resolve_rule_registry_root(session: RuntimeSession, dto: dict[str, Any]) -> str | None:
    override_registry_root = dto.get("override_registry_root")
    legacy_registry_root = dto.get("registry_root")
    if override_registry_root is not None and legacy_registry_root is not None:
        raise facade_error(
            "provide either override_registry_root or registry_root, not both",
            kind="shape",
            path="$",
        )
    if override_registry_root is not None:
        return _optional_str(override_registry_root, path="$.override_registry_root")
    if legacy_registry_root is not None:
        return _optional_str(legacy_registry_root, path="$.registry_root")
    return session.registry_root


def _compile_runtime_derivation(dto: Any, *, schema_ir: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(dto, dict):
        raise facade_error("dto must be object", kind="shape", path="$")
    derivation = dto.get("derivation")
    if isinstance(derivation, str):
        raise facade_error(
            "string derivation DSL is not supported in service v1; send structured derivation object",
            kind="string_dsl_unsupported",
            path="$.derivation",
            details={"strategy": "object_derivation_only", "input_kind": "string"},
        )
    if not isinstance(derivation, dict):
        raise facade_error("derivation must be object", kind="shape", path="$.derivation")
    normalized = dict(derivation)
    for key in ("where", "body"):
        raw_where = normalized.get(key)
        if isinstance(raw_where, str):
            raise facade_error(
                "string where DSL is not supported in service v1; send structured where IR",
                kind="string_dsl_unsupported",
                path=f"$.derivation.{key}",
                details={"strategy": "structured_where_ir_only", "input_kind": "string"},
            )
        if key in normalized:
            normalized[key] = _json_where_to_ir(normalized[key])
    return compile_authoring_derivation_v1(normalized, schema_ir=schema_ir)


def _runtime_exception_to_error(exc: Exception, *, default_kind: str) -> dict[str, Any]:
    err = exception_to_error(exc)
    if err["kind"] == "runtime":
        if isinstance(exc, AuthoringDerivationCompileError):
            err["kind"] = "authoring_derivation_compile"
        else:
            err["kind"] = default_kind
    return err


def _session_to_dict(session: RuntimeSession) -> dict[str, Any]:
    ledger = session.store.ledger
    return {
        "session_id": session.session_id,
        "ledger_path": session.ledger_path,
        "registry_root": session.registry_root,
        "schema_digest": session.schema_digest,
        "opened_at_ns": session.opened_at_ns,
        "counts": {
            "claims": len(ledger.claims),
            "claim_args": len(ledger.claim_args),
            "meta_rows": len(ledger.meta_rows),
            "revokes": len(ledger.revokes),
        },
    }


def _claim_to_dict(
    ledger: Ledger,
    claim: Claim,
    *,
    include_meta: bool,
    include_args: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "asrt_id": claim.asrt_id,
        "pred_id": claim.pred_id,
        "e_ref": claim.e_ref,
        "rest_terms": [[tag, value] for tag, value in claim.rest_terms],
        "is_revoked": ledger.has_active_revocation(claim.asrt_id),
        "revoker_asrt_id": ledger.find_revoker(claim.asrt_id),
    }
    if include_args:
        payload["claim_args"] = [_claim_arg_to_dict(row) for row in ledger.find_claim_args(asrt_id=claim.asrt_id)]
    if include_meta:
        payload["meta_rows"] = [_meta_row_to_dict(row) for row in ledger.find_meta(asrt_id=claim.asrt_id)]
    return payload


def _claim_arg_to_dict(row: ClaimArg) -> dict[str, Any]:
    return {
        "asrt_id": row.asrt_id,
        "idx": row.idx,
        "val_atom": row.val_atom,
        "tag": row.tag,
    }


def _meta_row_to_dict(row: MetaRow) -> dict[str, Any]:
    return {
        "asrt_id": row.asrt_id,
        "key": row.key,
        "kind": row.kind,
        "value": row.value,
    }


def _load_registered_rules(registry: RuleRegistry, root_dir: str) -> None:
    file_registry = FileAuthoringRegistry(Path(root_dir))
    for rule_id in file_registry.list_rule_ids():
        for version_row in file_registry.list_rule_versions(rule_id):
            version = version_row.get("version")
            if not isinstance(version, str) or not version:
                continue
            payload = file_registry.read_rule_spec(rule_id, version)
            if not isinstance(payload, dict):
                continue
            registry.register(
                RuleSpec(
                    rule_id=str(payload["rule_id"]),
                    version=str(payload["version"]),
                    select_vars=list(payload["select_vars"]),
                    where=list(_json_where_to_ir(payload["where"])),
                    expose=bool(payload.get("expose", False)),
                )
            )


def _json_where_to_ir(where_json: Any) -> Any:
    if isinstance(where_json, list):
        if where_json and isinstance(where_json[0], str) and where_json[0] in _ATOM_TAGS:
            return tuple(_json_where_to_ir(item) for item in where_json)
        return [_json_where_to_ir(item) for item in where_json]
    if isinstance(where_json, dict):
        return {key: _json_where_to_ir(value) for key, value in where_json.items()}
    return where_json


def _jsonable_row(row: tuple[Any, ...]) -> list[Any]:
    return [item for item in row]


def _candidate_to_dict(candidate: CandidateSet) -> dict[str, Any]:
    return {
        "derivation_id": candidate.derivation_id,
        "derivation_version": candidate.derivation_version,
        "run_id": candidate.run_id,
        "target": candidate.target,
        "key_tuple_digest": candidate.key_tuple_digest,
        "tup_digest": candidate.tup_digest,
        "payload": _to_jsonable(candidate.payload),
        "support_digest": candidate.support_digest,
        "support_kind": candidate.support_kind,
        "generated_at": candidate.generated_at,
        "state": candidate.state,
    }


def _candidate_from_dict(value: Any, *, path: str) -> CandidateSet:
    if not isinstance(value, dict):
        raise facade_error("candidate must be object", kind="shape", path=path)
    generated_at = value.get("generated_at")
    if not isinstance(generated_at, int) or isinstance(generated_at, bool):
        raise facade_error("generated_at must be int", kind="shape", path=f"{path}.generated_at")
    return CandidateSet(
        derivation_id=_require_non_empty_str(value.get("derivation_id"), path=f"{path}.derivation_id"),
        derivation_version=_require_non_empty_str(value.get("derivation_version"), path=f"{path}.derivation_version"),
        run_id=_require_non_empty_str(value.get("run_id"), path=f"{path}.run_id"),
        target=_require_non_empty_str(value.get("target"), path=f"{path}.target"),
        key_tuple_digest=_require_non_empty_str(value.get("key_tuple_digest"), path=f"{path}.key_tuple_digest"),
        tup_digest=_optional_str_or_none(value.get("tup_digest"), path=f"{path}.tup_digest"),
        payload=_candidate_payload_from_dict(value.get("payload"), path=f"{path}.payload"),
        support_digest=_require_non_empty_str(value.get("support_digest"), path=f"{path}.support_digest"),
        support_kind=_require_non_empty_str(value.get("support_kind"), path=f"{path}.support_kind"),
        generated_at=generated_at,
        state=_require_non_empty_str(value.get("state"), path=f"{path}.state"),
    )


def _candidate_payload_from_dict(value: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise facade_error("payload must be object", kind="shape", path=path)
    payload = dict(value)
    if payload.get("materialize_as") == "record":
        payload["record_type"] = _require_non_empty_str(payload.get("record_type"), path=f"{path}.record_type")
        payload["record_exists_pred_id"] = _require_non_empty_str(
            payload.get("record_exists_pred_id"),
            path=f"{path}.record_exists_pred_id",
        )
        if "id_policy" not in payload:
            raise facade_error("id_policy is required for record candidate", kind="shape", path=f"{path}.id_policy")
        roles = payload.get("roles")
        if not isinstance(roles, list) or not roles:
            raise facade_error("roles must be non-empty list", kind="shape", path=f"{path}.roles")
        normalized_roles: list[dict[str, Any]] = []
        for idx, role in enumerate(roles):
            role_path = f"{path}.roles[{idx}]"
            if not isinstance(role, dict):
                raise facade_error("role must be object", kind="shape", path=role_path)
            normalized_role = dict(role)
            normalized_role["pred_id"] = _require_non_empty_str(role.get("pred_id"), path=f"{role_path}.pred_id")
            if "field_name" in role:
                normalized_role["field_name"] = _require_non_empty_str(role.get("field_name"), path=f"{role_path}.field_name")
            if "type_domain" in role:
                normalized_role["type_domain"] = _require_non_empty_str(role.get("type_domain"), path=f"{role_path}.type_domain")
            normalized_role["rest_terms"] = _normalize_rest_terms(role.get("rest_terms"), path=f"{role_path}.rest_terms")
            normalized_roles.append(normalized_role)
        payload["roles"] = normalized_roles
        return payload
    payload["e_ref"] = _require_non_empty_str(payload.get("e_ref"), path=f"{path}.e_ref")
    payload["rest_terms"] = _normalize_rest_terms(payload.get("rest_terms"), path=f"{path}.rest_terms")
    return payload


def _accept_options_from_dto(value: Any, *, path: str) -> AcceptOptions:
    if value is None:
        return AcceptOptions()
    if not isinstance(value, dict):
        raise facade_error("options must be object", kind="shape", path=path)
    unknown = sorted(set(value.keys()) - {"approved_by", "note", "dry_run"})
    if unknown:
        raise facade_error(
            f"unknown accept options: {', '.join(unknown)}",
            kind="shape",
            path=f"{path}.{unknown[0]}",
        )
    approved_by = _optional_str_or_none(value.get("approved_by"), path=f"{path}.approved_by")
    note = _optional_str_or_none(value.get("note"), path=f"{path}.note")
    dry_run = value.get("dry_run", False)
    if not isinstance(dry_run, bool):
        raise facade_error("dry_run must be bool", kind="shape", path=f"{path}.dry_run")
    return AcceptOptions(approved_by=approved_by, note=note, dry_run=dry_run)


def _accept_result_to_dict(result: AcceptResult) -> dict[str, Any]:
    return {
        "materialize_id": result.materialize_id,
        "run_id": result.run_id,
        "accepted_count": result.accepted_count,
        "skipped_count": result.skipped_count,
        "written_assertions": _to_jsonable(result.written_assertions),
        "skipped_reason_counts": dict(result.skipped_reason_counts),
        "diagnostics_contract_version": result.diagnostics_contract_version,
        "diagnostics": _to_jsonable(result.diagnostics),
    }


def _accept_result_terminal(result: AcceptResult) -> bool:
    return bool(result.skipped_reason_counts.get("aborted", 0))


def _require_mapping_predicate(store: Store, pred_id: str, *, path: str) -> dict[str, Any]:
    schema_pred = builders.find_schema_pred(store, pred_id)
    if schema_pred is None:
        raise facade_error(
            f"pred_id not found in schema: {pred_id}",
            kind="shape",
            path=path,
            details={"pred_id": pred_id},
        )
    if schema_pred.get("is_mapping") is not True:
        raise facade_error(
            "pred_id must reference mapping predicate with is_mapping=true",
            kind="shape",
            path=path,
            details={"pred_id": pred_id},
        )
    return schema_pred


def _mapping_resolution_to_dict(resolution: MappingResolution) -> dict[str, Any]:
    return {
        "pred_id": resolution.pred_id,
        "chosen_map": [
            {
                "key_tuple": _to_jsonable(key_tuple),
                "value_tuple": _to_jsonable(value_tuple),
            }
            for key_tuple, value_tuple in sorted(
                resolution.chosen_map.items(),
                key=lambda item: tuple(str(part) for part in item[0]),
            )
        ],
        "candidates": [
            {
                "asrt_id": candidate.asrt_id,
                "key_tuple": _to_jsonable(candidate.key_tuple),
                "value_tuple": _to_jsonable(candidate.value_tuple),
                "source": candidate.source,
                "confidence": candidate.confidence,
                "ingested_at": candidate.ingested_at,
            }
            for candidate in resolution.candidates
        ],
        "decisions": [
            {
                "key_tuple": _to_jsonable(decision.key_tuple),
                "chosen_asrt_id": decision.chosen_asrt_id,
                "chosen_value_tuple": _to_jsonable(decision.chosen_value_tuple),
                "reason": decision.reason,
                "candidate_asrt_ids": _to_jsonable(decision.candidate_asrt_ids),
            }
            for decision in resolution.decisions
        ],
        "conflicts": _to_jsonable(resolution.conflicts),
    }


def _mapping_conflict_to_error(exc: MappingConflictError) -> dict[str, Any]:
    return {
        "kind": "mapping_conflict",
        "path": "$.pred_id",
        "details": {
            "message": str(exc),
            "conflicts": _to_jsonable(exc.conflicts),
        },
    }


def _resolve_view_temporal_view(value: Any, *, path: str) -> tuple[str, str]:
    if value is None:
        return "record", "record"
    if value == "record":
        return "record", "record"
    if value in {"active", "current"}:
        return "current", "active"
    raise facade_error(
        "temporal_view must be 'record' or 'active'",
        kind="shape",
        path=path,
    )


def _resolve_legacy_record_visibility(value: Any, *, path: str) -> str:
    if value is None:
        return "allow"
    if value not in {"allow", "audit", "deny"}:
        raise facade_error(
            "legacy_record_visibility must be 'allow', 'audit', or 'deny'",
            kind="shape",
            path=path,
        )
    return value


def _resolve_include_audit(value: Any, *, path: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise facade_error("include_audit must be bool", kind="shape", path=path)
    return value


def _optional_limit(value: Any, *, path: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise facade_error("must be non-negative int when provided", kind="shape", path=path)
    return value


def _optional_val_atoms(value: Any, *, path: str) -> list[Any] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise facade_error("val_atoms must be list", kind="shape", path=path)
    return [_normalize_val_atom(item, path=f"{path}[{idx}]") for idx, item in enumerate(value)]


def _normalize_val_atom(value: Any, *, path: str) -> Any:
    if isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[0], str) and value[0]:
        return _normalize_tagged_value(value[0], value[1], path=f"{path}[1]")
    return value


def _optional_str_or_none(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_str(value, path=path)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, bytes):
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    if isinstance(value, bytearray):
        return base64.urlsafe_b64encode(bytes(value)).decode("ascii").rstrip("=")
    if isinstance(value, memoryview):
        return base64.urlsafe_b64encode(value.tobytes()).decode("ascii").rstrip("=")
    return value


def _optional_str(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise facade_error("must be non-empty string when provided", kind="shape", path=path)
    return value


def _optional_dict(value: Any, *, path: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise facade_error("must be object when provided", kind="shape", path=path)
    return dict(value)


def _require_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise facade_error("must be non-empty string", kind="shape", path=path)
    return value


def _normalize_rest_terms(value: Any, *, path: str) -> list[tuple[str, Any]]:
    if not isinstance(value, list):
        raise facade_error("rest_terms must be list", kind="shape", path=path)
    out: list[tuple[str, Any]] = []
    for idx, item in enumerate(value):
        item_path = f"{path}[{idx}]"
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise facade_error(
                "rest_terms entry must be [tag, value]",
                kind="shape",
                path=item_path,
            )
        tag = item[0]
        if not isinstance(tag, str) or not tag:
            raise facade_error("rest_terms tag must be non-empty string", kind="shape", path=f"{item_path}[0]")
        out.append((tag, _normalize_tagged_value(tag, item[1], path=f"{item_path}[1]")))
    return out


def _normalize_tagged_value(tag: str, value: Any, *, path: str) -> Any:
    if tag != "bytes":
        return value
    if not isinstance(value, str):
        raise facade_error("bytes value must be base64url string", kind="shape", path=path)
    padded = value + ("=" * ((4 - len(value) % 4) % 4))
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise facade_error(
            f"invalid base64url bytes value: {exc}",
            kind="shape",
            path=path,
        ) from exc
