from __future__ import annotations

import base64
import binascii
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock
from time import time_ns
from typing import Any, Mapping
from uuid import uuid4

from factgraph.adapters.problog.rule_ext import resolve_problog_engine_ext
from factgraph.adapters.souffle.package import ExportOptions, export_package
from factgraph.authoring.derivation_compile import (
    AuthoringDerivationCompileError,
    compile_authoring_derivation_v1,
)
from factgraph.authoring.rules import compile_authoring_rule_v1
from factgraph.application.protocol import EvaluateResult, EvaluateRow, ResultFingerprint
from factgraph.application.protocol.evaluate_result import (
    _candidate_set_to_evaluate_row,
    _claim_arguments_for_row,
    _claim_name_for_row_result,
    _claim_repr_for_row_result,
    _evidence_ref_fact_digest_for_row,
    _evidence_ref_id_for_row_result,
    _evidence_ref_result_id_for_row_result,
    _evidence_ref_row_id_for_row,
    _legacy_candidate_payload_for_row_result,
    _row_digest_for,
    canonical_bytes_for_evaluate,
    closed_head_digest_for,
    expr_digest_for_payload,
    new_run_id,
    result_digest_for,
    result_id_for,
    rule_set_digest_for_entries,
    config_digest_for,
    view_snapshot_digest_for_parts,
)
from factgraph.application.protocol.rule import Rule as ApplicationRule
from factgraph.core.derivation.accept import AcceptOptions, AcceptResult
from factgraph.core.derivation.candidates import CONFIDENCE_KINDS, CandidateSet
from factgraph.core.evidence.write_protocol import add_field, retract_by_asrt, set_field
from factgraph.core.mapping.canon import MappingConflictError, MappingResolution
from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules._trace_nl import render_rule_run_nl_explain
from factgraph.core.rules._trace_narrative import render_rule_run_narrative
from factgraph.core.rules.rule_ir import RuleCompileError, RuleRegistry, RuleSpec, run_rule, run_rule_with_trace
from factgraph.core.rules._trace import summarize_rule_trace_artifact_dict
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.core.semantics import SemanticsProfile
from factgraph.core.store import builders
from factgraph.core.store._artifact_sidecar import FileArtifactSidecar
from factgraph.core.store._candidate_evidence_tree import (
    build_candidate_evidence_tree,
    build_degraded_candidate_evidence_tree,
)
from factgraph.core.store._candidate_evidence_tree_narrative import (
    render_candidate_evidence_tree_narrative,
)
from factgraph.core.store._candidate_evidence_tree_nl import (
    render_candidate_evidence_tree_nl_explain,
)
from factgraph.core.store._candidate_evidence_tree_summary import (
    summarize_candidate_evidence_tree_dict,
)
from factgraph.core.store._support import (
    _DEGRADED_SUPPORT_KINDS,
    _PROVENANCE_BEARING_SUPPORT_KINDS,
    _WITNESS_BEARING_SUPPORT_KINDS,
    PYREASON_PROVENANCE_KIND,
    SOUFFLE_WITNESS_KIND,
)
from factgraph.core.store.runtime import Store
from factgraph.core.store.ledger import Claim, ClaimArg, Ledger, MetaRow
from factgraph.core.view.projector import (
    project_view_facts,
    project_view_facts_with_audit,
)
from factgraph.audit import build_rule_trace_detail_payload
from factgraph.audit.evidence_graph import evidence_graph_to_dict
from factgraph.sdk.store import (
    _application_plans_from_compiled_dicts,
    _compiled_plan_digest_payload,
    _head_rule_for_compiled_plans,
    _rule_set_entries_for_result,
    _view_snapshot_asrt_id_for_claim,
)
from service.static_ui import render_candidate_evidence_html, render_rule_trace_detail_html

from ._common import error_response, exception_to_error, facade_error, ok_response
from ._certainty_service import (
    _compute_all_certainty_summaries,
    _compute_certainty_summary_from_tree,
)

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
_EVALUATE_DERIVATION_ENGINES = {"native", "souffle", "problog", "pyreason"}


@dataclass
class RuntimeDerivationRecipe:
    derivation_id: str
    derivation_version: str
    target_pred_id: str
    head_vars: list[str]
    where: Any


@dataclass
class RuntimeSession:
    session_id: str
    store: Store
    ledger_path: str | None
    schema_digest: str
    opened_at_ns: int
    derivation_recipes: dict[str, RuntimeDerivationRecipe] = field(default_factory=dict)
    ephemeral_rules: list[RuleSpec] = field(default_factory=list)


class _RuntimeSessionManager:
    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, RuntimeSession] = {}

    def open(
        self,
        *,
        store: Store,
        ledger_path: str | None,
        digest: str,
    ) -> RuntimeSession:
        session = RuntimeSession(
            session_id=f"rt_{uuid4().hex}",
            store=store,
            ledger_path=ledger_path,
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
        schema_ir = _resolve_schema_ir(dto)
        digest = schema_digest(schema_ir)
        ledger_path = _optional_str(dto.get("ledger_path"), path="$.ledger_path")
        artifact_store_root = _optional_str(dto.get("artifact_store_root"), path="$.artifact_store_root")
        artifact_sidecar = FileArtifactSidecar(artifact_store_root) if artifact_store_root is not None else None
        ledger = _open_ledger(ledger_path)
        try:
            _bind_ledger_schema(ledger, digest)
        except Exception:
            ledger.close()
            raise
        store = Store(schema_ir=schema_ir, ledger=ledger, artifact_sidecar=artifact_sidecar)
        session = _SESSIONS.open(
            store=store,
            ledger_path=ledger_path,
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


def get_runtime_session_schema(session_id: str) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        return ok_response(
            result={
                "schema_digest": session.schema_digest,
                "schema_ir": session.store.schema_ir,
            }
        )
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


def explain_runtime_ref(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        kind = dto.get("kind")
        if kind not in ("candidate", "assertion", "rule_run"):
            raise facade_error(
                f"unsupported explain_ref kind: {kind!r}",
                kind="shape",
                path="$.kind",
            )
        id_ = _require_non_empty_str(dto.get("id"), path="$.id")
        if kind == "candidate":
            return _explain_ref_candidate(session, id_)
        if kind == "assertion":
            return _explain_ref_assertion(session, id_)
        return _explain_ref_rule_run(session, id_)
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_ref")
        return error_response([err])


def explain_runtime_tree(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        kind = dto.get("kind")
        if kind != "candidate":
            raise facade_error(
                f"unsupported explain_tree kind: {kind!r}",
                kind="shape",
                path="$.kind",
            )
        candidate_id = _require_non_empty_str(dto.get("id"), path="$.id")
        return _explain_tree_candidate(session, candidate_id)
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_tree")
        return error_response([err])


def explain_runtime_summary(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        kind = dto.get("kind")
        id_ = _require_non_empty_str(dto.get("id"), path="$.id")
        if kind == "rule_run":
            return ok_response(
                meta={"rule_run_id": id_},
                kind="rule_run_summary",
                summary=_get_rule_run_summary(session, id_),
            )
        if kind == "candidate":
            support_kind = session.store.get_candidate_support_kind(id_)
            if support_kind == PYREASON_PROVENANCE_KIND:
                timeline_resp = _explain_timeline_candidate(session, id_)
                timeline = timeline_resp.get("timeline")
                if timeline is not None:
                    from factgraph.core.store._candidate_provenance_timeline import (
                        summarize_candidate_provenance_timeline,
                    )

                    tl_summary = summarize_candidate_provenance_timeline(timeline)
                    return ok_response(
                        meta={"candidate_id": id_},
                        kind="candidate_provenance_timeline_summary",
                        summary=tl_summary,
                    )
            aggregation = dto.get("certainty_aggregation", "bottleneck")
            tree = _get_candidate_tree(session, id_)
            summary = summarize_candidate_evidence_tree_dict(tree)
            certainty_summary = _compute_certainty_summary_from_tree(
                session.store,
                id_,
                tree,
                aggregation=aggregation,
            )
            return ok_response(
                meta={"candidate_id": id_},
                kind="candidate_evidence_tree_summary",
                summary=summary,
                certainty_summary=certainty_summary,
            )
        raise facade_error(
            f"unsupported explain_summary kind: {kind!r}",
            kind="shape",
            path="$.kind",
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_summary")
        return error_response([err])


def explain_runtime_narrative(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        kind = dto.get("kind")
        id_ = _require_non_empty_str(dto.get("id"), path="$.id")
        if kind == "rule_run":
            return ok_response(
                meta={"rule_run_id": id_},
                kind="rule_run_narrative",
                narrative=_get_rule_run_narrative(session, id_),
            )
        if kind == "candidate":
            support_kind = session.store.get_candidate_support_kind(id_)
            if support_kind == PYREASON_PROVENANCE_KIND:
                timeline_resp = _explain_timeline_candidate(session, id_)
                timeline = timeline_resp.get("timeline")
                if timeline is not None:
                    from factgraph.core.store._candidate_provenance_timeline import (
                        render_candidate_provenance_timeline_narrative,
                    )

                    tl_narrative = render_candidate_provenance_timeline_narrative(timeline)
                    return ok_response(
                        meta={"candidate_id": id_},
                        kind="candidate_provenance_timeline_narrative",
                        narrative=tl_narrative,
                    )
            aggregation = dto.get("certainty_aggregation", "bottleneck")
            tree = _get_candidate_tree(session, id_)
            summary = summarize_candidate_evidence_tree_dict(tree)
            certainty_summary = _compute_certainty_summary_from_tree(
                session.store,
                id_,
                tree,
                aggregation=aggregation,
            )
            return ok_response(
                meta={"candidate_id": id_},
                kind="candidate_evidence_tree_narrative",
                narrative=_render_candidate_tree_narrative_from_summary(
                    summary,
                    certainty_summary=certainty_summary,
                    tree=tree,
                ),
            )
        raise facade_error(
            f"unsupported explain_narrative kind: {kind!r}",
            kind="shape",
            path="$.kind",
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_narrative")
        return error_response([err])


def explain_runtime_nl(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        kind = dto.get("kind")
        id_ = _require_non_empty_str(dto.get("id"), path="$.id")
        if kind == "rule_run":
            summary = _get_rule_run_summary(session, id_)
            narrative = _render_rule_run_narrative_from_summary(summary)
            return ok_response(
                meta={"rule_run_id": id_},
                kind="rule_run_nl_explain",
                explain_nl=render_rule_run_nl_explain(summary, narrative, locale="en"),
            )
        if kind == "candidate":
            support_kind = session.store.get_candidate_support_kind(id_)
            if support_kind == PYREASON_PROVENANCE_KIND:
                timeline_resp = _explain_timeline_candidate(session, id_)
                timeline = timeline_resp.get("timeline")
                if timeline is not None:
                    from factgraph.core.store._candidate_provenance_timeline import (
                        render_candidate_provenance_timeline_narrative,
                        render_candidate_provenance_timeline_nl_explain,
                        summarize_candidate_provenance_timeline,
                    )

                    tl_summary = summarize_candidate_provenance_timeline(timeline)
                    tl_narrative = render_candidate_provenance_timeline_narrative(timeline)
                    return ok_response(
                        meta={"candidate_id": id_},
                        kind="candidate_provenance_timeline_nl_explain",
                        explain_nl=render_candidate_provenance_timeline_nl_explain(
                            tl_summary,
                            tl_narrative,
                            locale="en",
                        ),
                    )
            aggregation = dto.get("certainty_aggregation", "bottleneck")
            tree = _get_candidate_tree(session, id_)
            summary = summarize_candidate_evidence_tree_dict(tree)
            certainty_summary = _compute_certainty_summary_from_tree(
                session.store,
                id_,
                tree,
                aggregation=aggregation,
            )
            narrative = _render_candidate_tree_narrative_from_summary(
                summary,
                certainty_summary=certainty_summary,
                tree=tree,
            )
            return ok_response(
                meta={"candidate_id": id_},
                kind="candidate_evidence_tree_nl_explain",
                explain_nl=render_candidate_evidence_tree_nl_explain(summary, narrative, locale="en"),
            )
        raise facade_error(
            f"unsupported explain_nl kind: {kind!r}",
            kind="shape",
            path="$.kind",
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_nl")
        return error_response([err])


def explain_runtime_steps(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    """Return ordered explain-steps for a candidate (all engines)."""
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        kind = dto.get("kind")
        if kind != "candidate":
            raise facade_error(
                f"unsupported explain_steps kind: {kind!r}",
                kind="shape",
                path="$.kind",
            )
        candidate_id = _require_non_empty_str(dto.get("id"), path="$.id")
        support_kind = session.store.get_candidate_support_kind(candidate_id)

        if support_kind == PYREASON_PROVENANCE_KIND:
            from factgraph.core.store._candidate_provenance_timeline import (
                build_candidate_provenance_steps,
            )

            timeline_resp = _explain_timeline_candidate(session, candidate_id)
            timeline = timeline_resp.get("timeline")
            if timeline is None:
                raise facade_error(
                    "no timeline available for pyreason candidate",
                    kind="not_found",
                    path="$.id",
                )
            steps = build_candidate_provenance_steps(timeline)
        else:
            from factgraph.core.store._candidate_evidence_tree_steps import (
                build_candidate_evidence_steps,
            )

            tree = _get_candidate_tree(session, candidate_id)
            steps = build_candidate_evidence_steps(tree)

        return ok_response(
            meta={"candidate_id": candidate_id},
            kind="candidate_evidence_steps",
            candidate_id=candidate_id,
            engine=support_kind,
            steps=steps,
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_steps")
        return error_response([err])


# --- NEW: PyReason timeline explain endpoints ---
# Blueprint: 2026-03-30_pyreason-runtime-explain-timeline.md (D-PT4)


def explain_runtime_timeline(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    """Return CandidateProvenanceTimeline for pyreason candidates."""
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        kind = dto.get("kind")
        if kind != "candidate":
            raise facade_error(
                f"unsupported explain_timeline kind: {kind!r}",
                kind="shape",
                path="$.kind",
            )
        candidate_id = _require_non_empty_str(dto.get("id"), path="$.id")
        return _explain_timeline_candidate(session, candidate_id)
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_timeline")
        return error_response([err])


def explain_runtime_timeline_summary(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    """Return timeline summary for pyreason candidates."""
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        kind = dto.get("kind")
        if kind != "candidate":
            raise facade_error(
                f"unsupported explain_timeline_summary kind: {kind!r}",
                kind="shape",
                path="$.kind",
            )
        candidate_id = _require_non_empty_str(dto.get("id"), path="$.id")
        timeline_resp = _explain_timeline_candidate(session, candidate_id)
        timeline = timeline_resp.get("timeline")
        if timeline is None:
            raise facade_error("timeline not available", kind="explain_timeline")
        from factgraph.core.store._candidate_provenance_timeline import (
            summarize_candidate_provenance_timeline,
        )

        summary = summarize_candidate_provenance_timeline(timeline)
        return ok_response(
            kind="candidate_provenance_timeline_summary",
            summary=summary,
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_timeline_summary")
        return error_response([err])


def explain_runtime_timeline_narrative(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    """Return timeline narrative for pyreason candidates."""
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        kind = dto.get("kind")
        if kind != "candidate":
            raise facade_error(
                f"unsupported explain_timeline_narrative kind: {kind!r}",
                kind="shape",
                path="$.kind",
            )
        candidate_id = _require_non_empty_str(dto.get("id"), path="$.id")
        timeline_resp = _explain_timeline_candidate(session, candidate_id)
        timeline = timeline_resp.get("timeline")
        if timeline is None:
            raise facade_error("timeline not available", kind="explain_timeline")
        from factgraph.core.store._candidate_provenance_timeline import (
            render_candidate_provenance_timeline_narrative,
        )

        narrative = render_candidate_provenance_timeline_narrative(timeline)
        return ok_response(
            kind="candidate_provenance_timeline_narrative",
            narrative=narrative,
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_timeline_narrative")
        return error_response([err])


def _explain_timeline_candidate(session: Any, candidate_id: str) -> dict[str, Any]:
    """Internal helper: build timeline for a pyreason candidate."""
    from factgraph.adapters.pyreason.provenance import pyreason_trace_from_dict
    from factgraph.core.store._candidate_provenance_timeline import (
        build_candidate_provenance_timeline,
    )
    from factgraph.core.store._support import PYREASON_PROVENANCE_KIND

    support_digest = session.store.get_candidate_support_digest(candidate_id)
    if support_digest is None:
        raise _runtime_explain_not_found(
            handle_kind="candidate_id",
            handle_value=candidate_id,
            path="$.id",
        )
    support_kind = session.store.get_candidate_support_kind(candidate_id)
    if support_kind is None:
        raise _runtime_explain_not_found(
            handle_kind="candidate_id",
            handle_value=candidate_id,
            path="$.id",
        )
    if support_kind != PYREASON_PROVENANCE_KIND:
        raise facade_error(
            f"explain-timeline requires pyreason_provenance_v1, got {support_kind}",
            kind="explain_not_supported",
        )

    provenance = session.store.explain_provenance(support_digest)
    if not isinstance(provenance, dict):
        raise _runtime_explain_not_found(
            handle_kind="support_digest",
            handle_value=support_digest,
            path="$.id",
        )
    if provenance.get("engine") != "pyreason":
        raise facade_error(
            "explain-timeline requires pyreason provenance envelope",
            kind="explain_not_supported",
        )
    payload = provenance.get("payload")
    if not isinstance(payload, dict):
        raise facade_error("invalid pyreason provenance payload", kind="explain_timeline")

    candidate_payload = _candidate_payload_for_candidate_id(session, candidate_id)
    if candidate_payload is None:
        raise facade_error(
            f"candidate payload not available for explain-timeline: {candidate_id}",
            kind="explain_not_supported",
        )

    timeline = build_candidate_provenance_timeline(
        candidate_id=candidate_id,
        trace=pyreason_trace_from_dict(payload),
        candidate_payload=candidate_payload,
    )
    return ok_response(
        kind="candidate_provenance_timeline",
        timeline=timeline,
    )


def explain_runtime_support(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        support_digest = _require_non_empty_str(dto.get("support_digest"), path="$.support_digest")
        explain = session.store.explain_support(support_digest)
        if explain is None:
            raise _runtime_explain_not_found(
                handle_kind="support_digest",
                handle_value=support_digest,
                path="$.support_digest",
            )
        return ok_response(
            meta={"support_digest": support_digest},
            explain=_to_jsonable(explain),
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_support")
        return error_response([err])


def explain_runtime_rule_trace(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        rule_run_id = _require_non_empty_str(dto.get("rule_run_id"), path="$.rule_run_id")
        explain = session.store.explain_rule_trace(rule_run_id)
        if explain is None:
            raise _runtime_explain_not_found(
                handle_kind="rule_run_id",
                handle_value=rule_run_id,
                path="$.rule_run_id",
            )
        return ok_response(
            meta={"rule_run_id": rule_run_id},
            explain=_to_jsonable(explain),
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="query_explain_rule_trace")
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
        if "temporal_view" in dto:
            # TODO: Runtime temporal_view is still blocked for derivation/rule flows.
            # Snapshot read views (.at/.version) are already implemented in sdk.facade.
            # Re-enable this only when runtime temporal write semantics are defined.
            raise facade_error(
                "temporal_view is removed; runtime view now always uses active projection",
                kind="shape",
                path="$.temporal_view",
            )
        include_audit = _resolve_include_audit(dto.get("include_audit"), path="$.include_audit")
        _reject_runtime_read_policy(dto)
        if include_audit:
            projected_facts, audit = project_view_facts_with_audit(
                session.store.ledger,
                session.store.schema_ir,
            )
            view = {
                "facts": _to_jsonable(projected_facts),
                "audit": asdict(audit),
            }
        else:
            projected_facts = project_view_facts(
                session.store.ledger,
                session.store.schema_ir,
            )
            view = {
                "facts": _to_jsonable(projected_facts),
            }
        return ok_response(
            meta={
                "pred_count": len(projected_facts),
                "total_tuple_count": sum(len(rows) for rows in projected_facts.values()),
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
        if "temporal_view" in dto:
            # TODO: Runtime temporal_view is still blocked for derivation/rule flows.
            # Snapshot read views (.at/.version) are already implemented in sdk.facade.
            # Re-enable this only when runtime temporal write semantics are defined.
            raise facade_error(
                "temporal_view is removed from runtime rule execution",
                kind="shape",
                path="$.temporal_view",
            )
        capture_trace = dto.get("capture_trace", False)
        if not isinstance(capture_trace, bool):
            raise facade_error("capture_trace must be bool", kind="shape", path="$.capture_trace")
        compiled = compile_authoring_rule_v1(normalized_rule, schema_ir=session.store.schema_ir)
        # Q8 Phase 2 (Slice 6): FS-saved rule loading removed. Active registry
        # is populated only from session ephemeral rules (in-memory).
        active_registry = RuleRegistry()
        _apply_ephemeral_rules(active_registry, session)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )
        if capture_trace:
            traced = run_rule_with_trace(
                session.store,
                rule_spec,
                active_registry,
            )
            result: dict[str, Any] = {
                "rule_id": compiled["rule_id"],
                "version": compiled["version"],
                "rows": [_jsonable_row(row) for row in traced.rows],
                "trace": {"rule_run_id": traced.rule_run_id},
            }
            return ok_response(result=result)
        rows = run_rule(
            session.store,
            rule_spec,
            active_registry,
        )
        return ok_response(
            result={
                "rule_id": compiled["rule_id"],
                "version": compiled["version"],
                "rows": [_jsonable_row(row) for row in rows],
            }
        )
    except Exception as exc:
        err = exception_to_error(exc)
        err = _enrich_runtime_error_for_agent(err, exc)
        return error_response([err])


def evaluate_runtime_derivation(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        if isinstance(dto, dict) and "temporal_view" in dto:
            # TODO: Runtime temporal_view is still blocked for derivation/rule flows.
            # Snapshot read views (.at/.version) are already implemented in sdk.facade.
            # Re-enable this only when runtime temporal write semantics are defined.
            raise facade_error(
                "temporal_view is removed from runtime inference evaluation",
                kind="shape",
                path="$.temporal_view",
            )
        if isinstance(dto, dict) and "body_confidences" in dto:
            raise facade_error(
                "body_confidences is not accepted in runtime inference evaluation; "
                "use ProbLogRuleExt.case_probabilities or future SemanticsProfile.rule_projection.problog",
                kind="shape",
                path="$.body_confidences",
            )
        if isinstance(dto, dict) and "engine_ext" in dto:
            raise facade_error(
                "engine_ext is not accepted in runtime inference evaluation; "
                "use future SemanticsProfile.rule_projection",
                kind="shape",
                path="$.engine_ext",
            )
        if isinstance(dto, dict) and "semantics_profile" in dto:
            raise facade_error(
                "semantics_profile is not accepted in runtime inference evaluation; use semantics",
                kind="shape",
                path="$.semantics_profile",
            )
        mode = _resolve_runtime_derivation_engine(dto)
        semantics_profile = _resolve_runtime_semantics_profile(dto, mode=mode)
        compiled = _compile_runtime_derivation(dto, schema_ir=session.store.schema_ir)
        limit = _optional_limit(dto.get("limit"), path="$.limit")
        # Q8 Phase 2 (Slice 6): FS-saved rule loading removed; certainty
        # confidence-kind resolver no longer constructed because no concrete
        # reader implements the Protocol after FileAuthoringRegistry.read_rule_spec
        # is gone. Slice 7C: registry_root propagation removed entirely
        # (N-2 amendment); only ephemeral in-memory rules survive.
        active_registry = None
        certainty_resolver = None
        if session.ephemeral_rules:
            active_registry = RuleRegistry()
            _apply_ephemeral_rules(active_registry, session)
        runtime_engine_ext = _resolve_runtime_derivation_engine_ext(compiled, mode=mode)
        candidates = session.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=list(compiled["head_vars"]),
            where=list(compiled["where"]),
            mode=mode,
            head=compiled.get("head"),
            registry=active_registry,
            confidence_kind_resolver=certainty_resolver,
            engine_ext=runtime_engine_ext,
            semantics_profile=semantics_profile,
        )
        result = _evaluate_result_from_candidates(
            session,
            candidates=candidates,
            compiled=compiled,
            mode=mode,
            semantics_profile=semantics_profile,
        )
        returned_rows = result.rows if limit is None else result.rows[:limit]
        return ok_response(
            meta={
                "mode": mode,
                "result_id": result.result_id,
                "row_count": len(result.rows),
                "returned_count": len(returned_rows),
                "truncated": len(returned_rows) != len(result.rows),
            },
            evaluation=_evaluate_result_to_dict(result, rows=returned_rows) | {
                "inference_id": compiled["derivation_id"],
                "version": compiled["version"],
                "target_pred_id": compiled["target_pred_id"],
            },
        )
    except Exception as exc:
        err = _runtime_exception_to_error(exc, default_kind="inference_evaluate")
        err = _enrich_runtime_error_for_agent(err, exc)
        return error_response([err])


def _resolve_runtime_derivation_engine_ext(compiled: dict[str, Any], *, mode: str) -> object | None:
    if mode != "problog":
        return compiled.get("engine_ext")
    return resolve_problog_engine_ext(
        where=compiled.get("where"),
        engine_ext=compiled.get("engine_ext"),
        legacy_body_confidences=compiled.get("body_confidences"),
    )


def accept_runtime_derivation(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    try:
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        raise facade_error(
            "runtime inference accept was removed by the T5 EvaluateResult hard-cut; "
            "evaluate returns rows and evidence anchors, not public CandidateSet payloads",
            kind="removed",
            path="$",
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
        certainty_map: dict[str, dict[str, Any]] | None = None
        provenance_map: dict[str, dict[str, Any]] | None = None
        provenance_status_map: dict[str, dict[str, Any]] | None = None
        evidence_graph_map: dict[str, dict[str, Any]] | None = None
        provenance_timeline_map: dict[str, dict[str, Any]] | None = None
        if package_kind == "audit":
            certainty_map = _compute_all_certainty_summaries(
                session.store,
                get_candidate_tree=lambda cid: _get_candidate_tree(session, cid),
            )
            provenance_map, provenance_status_map = _materialize_provenance_trees(session)
            evidence_graph_map = _materialize_evidence_graphs(
                session,
                provenance_trees=provenance_map,
            )
            provenance_timeline_map = _materialize_provenance_timelines(session)
        export_package(
            session.store,
            out_dir,
            ExportOptions(package_kind=package_kind),
            query=query,
            certainty_summaries=certainty_map,
            provenance_trees=provenance_map,
            provenance_statuses=provenance_status_map,
            evidence_graphs=evidence_graph_map,
            provenance_timelines=provenance_timeline_map,
        )
        return ok_response(
            package={
                "out_dir": out_dir,
                "package_kind": package_kind,
                "manifest_path": str(Path(out_dir) / "manifest.json"),
            }
        )
    except Exception as exc:
        err = exception_to_error(exc)
        err = _enrich_runtime_error_for_agent(err, exc)
        return error_response([err])


def register_ephemeral_rule(session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
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
        compiled = compile_authoring_rule_v1(normalized_rule, schema_ir=session.store.schema_ir)
        unknown_preds = _validate_ephemeral_rule_preds(
            compiled["where"],
            session.store.schema_ir,
        )
        if unknown_preds:
            raise facade_error(
                f"unknown predicate in rule where: {unknown_preds[0]}",
                kind="rule_ast_validate",
                path="$.rule.where",
                details={
                    "error_code": "unknown_predicate",
                    "missing_pred_id": unknown_preds[0],
                    "remediation_hint": "verify_pred_id_via_GET_sessions_schema",
                },
            )
        rs = RuleSpec(
            rule_id=str(compiled["rule_id"]),
            version=str(compiled.get("version", "v1")),
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )
        key = (rs.rule_id, rs.version)
        existing_idx = next(
            (i for i, r in enumerate(session.ephemeral_rules) if (r.rule_id, r.version) == key),
            None,
        )
        if existing_idx is not None:
            session.ephemeral_rules[existing_idx] = rs
            reg_status = "replaced"
        else:
            session.ephemeral_rules.append(rs)
            reg_status = "registered"
        return ok_response(
            result={
                "rule_id": rs.rule_id,
                "version": rs.version,
                "status": reg_status,
                "total_ephemeral": len(session.ephemeral_rules),
            }
        )
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def list_ephemeral_rules(session_id: str) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        return ok_response(
            result={
                "ephemeral_rules": [
                    {"rule_id": rs.rule_id, "version": rs.version}
                    for rs in session.ephemeral_rules
                ],
                "total": len(session.ephemeral_rules),
            }
        )
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def get_runtime_session_rules(
    session_id: str,
    include_spec: bool = False,
) -> dict[str, Any]:
    # Q8 Phase 2 (Slice 6): FS-backed rule listing removed. The function now
    # surfaces only session ephemeral rules. `fs_count: 0` is preserved in the
    # response for caller compatibility.
    try:
        session = _require_session(session_id)
        rule_map: dict[tuple[str, str], dict[str, Any]] = {}

        ephemeral_count = 0
        for rs in session.ephemeral_rules:
            entry: dict[str, Any] = {
                "rule_id": rs.rule_id,
                "version": rs.version,
                "source": "ephemeral",
            }
            if include_spec:
                entry["select_vars"] = list(rs.select_vars)
                entry["where"] = list(rs.where)
                entry["expose"] = rs.expose
            rule_map[(rs.rule_id, rs.version)] = entry
            ephemeral_count += 1

        return ok_response(
            result={
                "rules": list(rule_map.values()),
                "total": len(rule_map),
                "fs_count": 0,
                "ephemeral_count": ephemeral_count,
            }
        )
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def list_runtime_candidates(
    session_id: str,
    pred_id_filter: str | None = None,
) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        candidates: list[dict[str, Any]] = []
        for candidate_id in session.store.list_candidate_ids():
            pred_id = session.store.get_candidate_pred_id(candidate_id) or ""
            if pred_id_filter is not None and pred_id != pred_id_filter:
                continue
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "pred_id": pred_id,
                    "support_kind": session.store.get_candidate_support_kind(candidate_id) or "",
                }
            )
        return ok_response(
            result={
                "candidates": candidates,
                "total": len(candidates),
            }
        )
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def clear_ephemeral_rules(session_id: str) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        count = len(session.ephemeral_rules)
        session.ephemeral_rules.clear()
        return ok_response(result={"cleared": count})
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def _resolve_schema_ir(dto: dict[str, Any]) -> dict[str, Any]:
    # Slice 7C / Q6-A (b.3): `registry_root` / `override_registry_root` are
    # rejected at the service input layer with the established removed-envelope
    # error shape. Runtime sessions now require inline `schema_ir`.
    raw_registry_root = dto.get("registry_root")
    if raw_registry_root is not None:
        raise facade_error(
            "registry_root= was removed by A20(E) / Q6-A; "
            "provide inline schema_ir or use workspace-based loading",
            kind="registry_root_removed",
            path="$.registry_root",
        )
    raw_override_registry_root = dto.get("override_registry_root")
    if raw_override_registry_root is not None:
        raise facade_error(
            "override_registry_root= was removed by A20(E) / Q6-A; "
            "provide inline schema_ir or use workspace-based loading",
            kind="registry_root_removed",
            path="$.override_registry_root",
        )
    raw_schema_ir = dto.get("schema_ir")
    if raw_schema_ir is None:
        raise facade_error(
            "schema_ir is required",
            kind="shape",
            path="$",
        )
    if not isinstance(raw_schema_ir, dict):
        raise facade_error("schema_ir must be object", kind="shape", path="$.schema_ir")
    return dict(raw_schema_ir)


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


def _compile_runtime_derivation(dto: Any, *, schema_ir: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(dto, dict):
        raise facade_error("dto must be object", kind="shape", path="$")
    if "derivation" in dto:
        raise facade_error("use top-level inference, not derivation", kind="shape", path="$.inference")
    inference = dto.get("inference")
    if isinstance(inference, str):
        raise facade_error(
            "string inference DSL is not supported in service v1; send structured inference object",
            kind="string_dsl_unsupported",
            path="$.inference",
            details={"strategy": "object_inference_only", "input_kind": "string"},
        )
    if not isinstance(inference, dict):
        raise facade_error("inference must be object", kind="shape", path="$.inference")
    if "mode" in inference:
        raise facade_error(
            "inference.mode is not accepted; use call-site engine selection",
            kind="shape",
            path="$.inference.mode",
        )
    if "body_confidences" in inference:
        raise facade_error(
            "inference.body_confidences is not accepted; "
            "use ProbLogRuleExt.case_probabilities or future SemanticsProfile.rule_projection.problog",
            kind="shape",
            path="$.inference.body_confidences",
        )
    if "engine_ext" in inference:
        raise facade_error(
            "inference.engine_ext is not accepted; use future SemanticsProfile.rule_projection",
            kind="shape",
            path="$.inference.engine_ext",
        )
    if "semantics" in inference:
        raise facade_error(
            "inference.semantics is not accepted in B; Track 3 / E owns runtime consumption",
            kind="shape",
            path="$.inference.semantics",
        )
    if "semantics_profile" in inference:
        raise facade_error(
            "inference.semantics_profile is not accepted in B; Track 3 / E owns runtime consumption",
            kind="shape",
            path="$.inference.semantics_profile",
        )
    normalized = dict(inference)
    for key in ("where", "body"):
        raw_where = normalized.get(key)
        if isinstance(raw_where, str):
            raise facade_error(
                "string where DSL is not supported in service v1; send structured where IR",
                kind="string_dsl_unsupported",
                path=f"$.inference.{key}",
                details={"strategy": "structured_where_ir_only", "input_kind": "string"},
            )
        if key in normalized:
            normalized[key] = _json_where_to_ir(normalized[key])
    return compile_authoring_derivation_v1(normalized, schema_ir=schema_ir)


def _resolve_runtime_derivation_engine(dto: Any) -> str:
    if not isinstance(dto, dict):
        raise facade_error("dto must be object", kind="shape", path="$")
    if "mode" in dto:
        raise facade_error(
            "top-level mode is not accepted for inference evaluation; use engine",
            kind="shape",
            path="$.mode",
        )
    raw = dto.get("engine", "native")
    if not isinstance(raw, str) or raw not in _EVALUATE_DERIVATION_ENGINES:
        allowed = ", ".join(sorted(_EVALUATE_DERIVATION_ENGINES))
        raise facade_error(
            f"engine must be one of: {allowed}",
            kind="shape",
            path="$.engine",
        )
    return raw


def _resolve_runtime_semantics_profile(dto: Any, *, mode: str) -> SemanticsProfile | None:
    if not isinstance(dto, dict) or "semantics" not in dto:
        return None
    raw = dto.get("semantics")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise facade_error("semantics must be object", kind="shape", path="$.semantics")
    if any(key in raw for key in ("type", "case_probabilities", "timestep_delay", "head_bound")):
        raise facade_error(
            "service semantics accepts SemanticsProfile shape only in Track 2",
            kind="shape",
            path="$.semantics",
        )
    if mode not in {"problog", "pyreason"}:
        raise facade_error(
            f"engine='{mode}' does not consume SemanticsProfile",
            kind="shape",
            path="$.semantics",
        )
    try:
        profile = SemanticsProfile(**raw)
    except Exception as exc:
        raise facade_error(str(exc), kind="shape", path="$.semantics") from exc
    if profile.engine != mode:
        raise facade_error(
            f"SemanticsProfile.engine='{profile.engine}' does not match engine='{mode}'",
            kind="shape",
            path="$.semantics",
        )
    return profile


def _runtime_exception_to_error(exc: Exception, *, default_kind: str) -> dict[str, Any]:
    err = exception_to_error(exc)
    if err["kind"] == "runtime":
        if isinstance(exc, AuthoringDerivationCompileError):
            err["kind"] = "authoring_derivation_compile"
        else:
            err["kind"] = default_kind
    return err


def _enrich_runtime_error_for_agent(err: dict[str, Any], exc: Exception) -> dict[str, Any]:
    """Add stable agent-facing fields without changing the top-level kind."""
    msg = str(exc)
    extra: dict[str, Any] = {}
    if "unknown predicate in where:" in msg:
        pred_id = msg.split("unknown predicate in where:", 1)[-1].strip()
        extra = {
            "error_code": "unknown_predicate",
            "missing_pred_id": pred_id,
            "remediation_hint": "verify_pred_id_via_GET_sessions_schema",
        }
    elif "unknown RuleRef:" in msg:
        ref = msg.split("unknown RuleRef:", 1)[-1].strip()
        extra = {
            "error_code": "unknown_rule_ref",
            "missing_rule_ref": ref,
            "remediation_hint": "register_referenced_rule_first_or_check_fs_registry",
        }
    elif "RuleRef target must be expose=True:" in msg:
        ref = msg.split("RuleRef target must be expose=True:", 1)[-1].strip()
        extra = {
            "error_code": "rule_not_expose",
            "rule_ref_id": ref,
            "remediation_hint": "add_expose_true_to_rule_definition",
        }
    if not extra:
        return err
    enriched = dict(err)
    enriched["details"] = {**(err.get("details") or {}), **extra}
    return enriched


def _runtime_explain_not_found(*, handle_kind: str, handle_value: str, path: str) -> Exception:
    return facade_error(
        f"runtime explain artifact not found for {handle_kind}: {handle_value}",
        kind="runtime_explain_not_found",
        path=path,
        details={handle_kind: handle_value},
    )


def _runtime_explain_not_supported(*, candidate_id: str, support_kind: str) -> Exception:
    return facade_error(
        f"runtime tree explain only supports tree-bearing or degraded candidate support, got: {support_kind}",
        kind="runtime_explain_not_supported",
        path="$.id",
        details={"candidate_id": candidate_id, "support_kind": support_kind},
    )


def _get_candidate_tree(session: RuntimeSession, candidate_id: str) -> dict[str, Any]:
    from factgraph.adapters.problog.provenance import (
        problog_trace_from_dict,
        problog_trace_to_candidate_evidence_tree,
    )
    from factgraph.core.store._support import PROBLOG_PROVENANCE_KIND

    support_digest = session.store.get_candidate_support_digest(candidate_id)
    if support_digest is None:
        raise _runtime_explain_not_found(
            handle_kind="candidate_id",
            handle_value=candidate_id,
            path="$.id",
        )
    support_kind = session.store.get_candidate_support_kind(candidate_id)
    if support_kind not in _WITNESS_BEARING_SUPPORT_KINDS:
        if support_kind is None:
            raise _runtime_explain_not_found(
                handle_kind="candidate_id",
                handle_value=candidate_id,
                path="$.id",
            )
        if support_kind in _DEGRADED_SUPPORT_KINDS:
            return build_degraded_candidate_evidence_tree(
                candidate_id=candidate_id,
                support_digest=support_digest,
                support_kind=support_kind,
            )
        if support_kind == PROBLOG_PROVENANCE_KIND:
            provenance = session.store.explain_provenance(support_digest)
            if not isinstance(provenance, dict):
                raise _runtime_explain_not_found(
                    handle_kind="support_digest",
                    handle_value=support_digest,
                    path="$.id",
                )
            if provenance.get("engine") != "problog":
                raise facade_error(
                    "invalid problog provenance envelope for candidate explain-tree",
                    kind="runtime",
                    path="$.id",
                )
            payload = provenance.get("payload")
            if not isinstance(payload, dict):
                raise facade_error(
                    "problog provenance payload must be object",
                    kind="runtime",
                    path="$.id",
                )
            candidate_payload = _candidate_payload_for_candidate_id(session, candidate_id)
            if candidate_payload is None:
                raise facade_error(
                    f"candidate payload not available for explain-tree: {candidate_id}",
                    kind="explain_not_supported",
                    path="$.id",
                )
            return problog_trace_to_candidate_evidence_tree(
                problog_trace_from_dict(payload),
                candidate_id=candidate_id,
                candidate_payload=candidate_payload,
                support_digest=support_digest,
                support_kind=support_kind,
            )
        raise _runtime_explain_not_supported(candidate_id=candidate_id, support_kind=support_kind)
    support = session.store.explain_support(support_digest)
    if support is None:
        raise _runtime_explain_not_found(
            handle_kind="support_digest",
            handle_value=support_digest,
            path="$.id",
        )
    return build_candidate_evidence_tree(
        candidate_id=candidate_id,
        support_digest=support_digest,
        support_kind=support_kind,
        support=support,
        assertion_lookup=lambda asrt_id: _runtime_assertion_detail_for_tree(session.store.ledger, asrt_id),
        support_lookup=session.store.explain_support,
    )


def _explain_tree_candidate(session: RuntimeSession, candidate_id: str) -> dict[str, Any]:
    tree = _get_candidate_tree(session, candidate_id)
    return ok_response(
        meta={"candidate_id": candidate_id},
        kind="candidate_evidence_tree",
        tree=_to_jsonable(tree),
    )


def _explain_ref_candidate(session: RuntimeSession, candidate_id: str) -> dict[str, Any]:
    support_digest = session.store.get_candidate_support_digest(candidate_id)
    if support_digest is None:
        raise _runtime_explain_not_found(
            handle_kind="candidate_id",
            handle_value=candidate_id,
            path="$.id",
        )
    support_kind = session.store.get_candidate_support_kind(candidate_id)
    if support_kind in _DEGRADED_SUPPORT_KINDS:
        return ok_response(
            meta={"candidate_id": candidate_id},
            kind="candidate",
            explain={
                "candidate_id": candidate_id,
                "support_digest": support_digest,
                "support_kind": support_kind,
                "witness_status": "degraded",
            },
        )
    if support_kind in _PROVENANCE_BEARING_SUPPORT_KINDS:
        explain_detail = session.store.explain_provenance(support_digest)
        if explain_detail is None:
            raise _runtime_explain_not_found(
                handle_kind="support_digest",
                handle_value=support_digest,
                path="$.id",
            )
        return ok_response(
            meta={"candidate_id": candidate_id},
            kind="candidate",
            explain={
                "candidate_id": candidate_id,
                "support_digest": support_digest,
                "support_kind": support_kind,
                "provenance": _to_jsonable(explain_detail),
            },
        )
    explain_detail = session.store.explain_support(support_digest)
    explain: dict[str, Any] = {
        "candidate_id": candidate_id,
        "support_digest": support_digest,
    }
    if explain_detail is not None:
        explain["support"] = _to_jsonable(explain_detail)
    return ok_response(
        meta={"candidate_id": candidate_id},
        kind="candidate",
        explain=explain,
    )


def _explain_ref_assertion(session: RuntimeSession, asrt_id: str) -> dict[str, Any]:
    claim = session.store.ledger.get_claim(asrt_id)
    if claim is None:
        raise _runtime_explain_not_found(
            handle_kind="asrt_id",
            handle_value=asrt_id,
            path="$.id",
        )
    is_active = not session.store.ledger.has_active_revocation(asrt_id)
    revoker = session.store.ledger.find_revoker(asrt_id) if not is_active else None
    explain: dict[str, Any] = {
        "asrt_id": asrt_id,
        "pred_id": claim.pred_id,
        "e_ref": claim.e_ref,
        "is_active": is_active,
    }
    if revoker is not None:
        explain["revoker_asrt_id"] = revoker
    return ok_response(
        meta={"asrt_id": asrt_id},
        kind="assertion",
        explain=explain,
    )


def _explain_ref_rule_run(session: RuntimeSession, rule_run_id: str) -> dict[str, Any]:
    explain = session.store.explain_rule_trace(rule_run_id)
    if explain is None:
        raise _runtime_explain_not_found(
            handle_kind="rule_run_id",
            handle_value=rule_run_id,
            path="$.id",
        )
    return ok_response(
        meta={"rule_run_id": rule_run_id},
        kind="rule_run",
        explain=_to_jsonable(explain),
    )


def _get_rule_run_summary(session: RuntimeSession, rule_run_id: str) -> dict[str, Any]:
    raw_resp = _explain_ref_rule_run(session, rule_run_id)
    raw_explain = raw_resp.get("explain")
    if not isinstance(raw_explain, dict):
        raise facade_error(
            "rule_run explain payload must be object",
            kind="runtime",
            path="$.explain",
        )
    return summarize_rule_trace_artifact_dict(raw_explain)


def _get_rule_run_narrative(session: RuntimeSession, rule_run_id: str) -> dict[str, Any]:
    return _render_rule_run_narrative_from_summary(_get_rule_run_summary(session, rule_run_id))


def _get_rule_run_detail_payload(session: RuntimeSession, rule_run_id: str) -> dict[str, Any]:
    raw_resp = _explain_ref_rule_run(session, rule_run_id)
    raw_explain = raw_resp.get("explain")
    if not isinstance(raw_explain, dict):
        raise facade_error(
            "rule_run explain payload must be object",
            kind="runtime",
            path="$.explain",
        )
    return build_rule_trace_detail_payload(raw_explain, rule_run_id=rule_run_id)


def _get_candidate_tree_summary(session: RuntimeSession, candidate_id: str) -> dict[str, Any]:
    return summarize_candidate_evidence_tree_dict(_get_candidate_tree(session, candidate_id))


def _get_candidate_tree_narrative(session: RuntimeSession, candidate_id: str) -> dict[str, Any]:
    tree = _get_candidate_tree(session, candidate_id)
    return _render_candidate_tree_narrative_from_summary(
        _get_candidate_tree_summary(session, candidate_id),
        tree=tree,
    )


def _render_rule_run_narrative_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return render_rule_run_narrative(summary, locale="en")


def _render_candidate_tree_narrative_from_summary(
    summary: dict[str, Any],
    *,
    certainty_summary: dict[str, Any] | None = None,
    tree: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return render_candidate_evidence_tree_narrative(
        summary,
        certainty_summary=certainty_summary,
        tree=tree,
        locale="en",
    )


def render_runtime_candidate_evidence_html(session_id: str, candidate_id: str) -> str:
    session = _require_session(session_id)
    tree = _get_candidate_tree(session, candidate_id)
    narrative = _get_candidate_tree_narrative(session, candidate_id)
    return render_candidate_evidence_html(tree, narrative=narrative)


def render_runtime_rule_trace_html(session_id: str, rule_run_id: str) -> str:
    session = _require_session(session_id)
    detail = _get_rule_run_detail_payload(session, rule_run_id)
    narrative = _get_rule_run_narrative(session, rule_run_id)
    return render_rule_trace_detail_html(
        detail,
        assertion_lookup=lambda asrt_id: _runtime_assertion_detail_for_tree(session.store.ledger, asrt_id),
        narrative=narrative,
    )


def _session_to_dict(session: RuntimeSession) -> dict[str, Any]:
    ledger = session.store.ledger
    return {
        "session_id": session.session_id,
        "ledger_path": session.ledger_path,
        "schema_digest": session.schema_digest,
        "opened_at_ns": session.opened_at_ns,
        "counts": {
            "claims": len(ledger.claims),
            "claim_args": len(ledger.claim_args),
            "meta_rows": len(ledger.meta_rows),
            "revokes": len(ledger.revokes),
        },
    }


def _cache_derivation_recipe(
    session: RuntimeSession,
    *,
    candidates: list[CandidateSet],
    compiled: dict[str, Any],
) -> None:
    run_ids = {candidate.run_id for candidate in candidates if candidate.run_id}
    if not run_ids:
        return
    recipe = RuntimeDerivationRecipe(
        derivation_id=str(compiled["derivation_id"]),
        derivation_version=str(compiled["version"]),
        target_pred_id=str(compiled["target_pred_id"]),
        head_vars=list(compiled["head_vars"]),
        where=deepcopy(compiled["where"]),
    )
    for run_id in run_ids:
        session.derivation_recipes[run_id] = recipe


def _materialize_provenance_trees(
    session: RuntimeSession,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Materialize Souffle provenance plus per-candidate status rows."""
    import tempfile

    from factgraph.adapters.souffle.provenance import run_package_provenance
    from factgraph.adapters.souffle.runner import run_package
    from factgraph.adapters.souffle.tsv_v1 import tsv_cell_v1_decode
    from factgraph.adapters.souffle.where_compile import (
        _expand_ruleref_relations_for_query_export,
        _schema_pred_type_domains,
        extract_where_variables,
    )

    accepted_candidates = _accepted_candidate_provenance_rows(session)
    if not accepted_candidates:
        return {}, {}

    by_run_id: dict[str, list[dict[str, Any]]] = {}
    provenance_trees: dict[str, dict[str, Any]] = {}
    provenance_statuses: dict[str, dict[str, Any]] = {}
    for row in accepted_candidates:
        candidate_id = row["candidate_id"]
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            provenance_statuses[candidate_id] = {
                "status": "missing_recipe",
                "reason": "no run_id found",
                "engine": "souffle",
                "truncated": False,
            }
            continue
        if run_id not in session.derivation_recipes:
            provenance_statuses[candidate_id] = {
                "status": "missing_recipe",
                "reason": "no cached recipe for run_id",
                "engine": "souffle",
                "truncated": False,
            }
            continue
        by_run_id.setdefault(run_id, []).append(row)

    if not by_run_id:
        return provenance_trees, provenance_statuses

    for run_id, candidate_rows in by_run_id.items():
        recipe = session.derivation_recipes[run_id]
        try:
            pred_type_domains = _schema_pred_type_domains(session.store.schema_ir)
            # Slice 7C (N-2): FS-saved rule registry was already removed in
            # Slice 6; this slice drops the lingering recipe.registry_root
            # field. ruleref relations passed to the export use no registry.
            expanded = _expand_ruleref_relations_for_query_export(
                where=recipe.where,
                registry=None,
                pred_type_domains=pred_type_domains,
            )
            query_variables = extract_where_variables(expanded.rewritten_where)
            with tempfile.TemporaryDirectory() as tmp_dir:
                package_dir = Path(tmp_dir) / "provenance"
                query_rel = f"__prov_{run_id[:16]}__"
                export_package(
                    session.store,
                    package_dir,
                    ExportOptions(package_kind="inference"),
                    query={
                        "where": recipe.where,
                        "query_rel": query_rel,
                    },
                )
                run_manifest_path = run_package(package_dir, ["__query__"], engine="souffle")
                run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
                if run_manifest.get("engine_mode") != "souffle" or run_manifest.get("exit_code") != 0:
                    for row in candidate_rows:
                        provenance_statuses[row["candidate_id"]] = {
                            "status": "export_failed",
                            "reason": "Souffle query execution failed",
                            "engine": "souffle",
                            "truncated": False,
                        }
                    continue

                out_path = package_dir / "outputs" / f"{query_rel}.out.facts"
                if not out_path.exists():
                    for row in candidate_rows:
                        provenance_statuses[row["candidate_id"]] = {
                            "status": "no_matching_row",
                            "reason": "Souffle produced no output",
                            "engine": "souffle",
                            "truncated": False,
                        }
                    continue
                binding_to_query: dict[tuple[str, ...], str] = {}
                with out_path.open("r", encoding="utf-8") as handle:
                    for raw_line in handle:
                        line = raw_line.rstrip("\n")
                        if not line:
                            continue
                        row_values = tuple(tsv_cell_v1_decode(cell) for cell in line.split("\t"))
                        binding_to_query[row_values] = _souffle_query_text(query_rel, row_values)

                if not binding_to_query:
                    for row in candidate_rows:
                        provenance_statuses[row["candidate_id"]] = {
                            "status": "no_matching_row",
                            "reason": "Souffle produced no output",
                            "engine": "souffle",
                            "truncated": False,
                        }
                    continue

                for row in candidate_rows:
                    candidate_id = row["candidate_id"]
                    binding = _candidate_binding_for_recipe(
                        recipe,
                        accepted_args=row["accepted_args"],
                        query_variables=query_variables,
                    )
                    if binding is None:
                        provenance_statuses[candidate_id] = {
                            "status": "no_matching_row",
                            "reason": "candidate terms could not be mapped to query variables",
                            "engine": "souffle",
                            "truncated": False,
                        }
                        continue
                    query_text = binding_to_query.get(binding)
                    if query_text is None:
                        provenance_statuses[candidate_id] = {
                            "status": "no_matching_row",
                            "reason": "candidate not found in query output",
                            "engine": "souffle",
                            "truncated": False,
                        }
                        continue
                    try:
                        trees = run_package_provenance(package_dir, [query_text])
                    except Exception as exc:
                        provenance_statuses[candidate_id] = {
                            "status": "explain_failed",
                            "reason": str(exc)[:200],
                            "engine": "souffle",
                            "truncated": False,
                        }
                        continue
                    if not trees:
                        provenance_statuses[candidate_id] = {
                            "status": "explain_failed",
                            "reason": "no proof tree returned",
                            "engine": "souffle",
                            "truncated": False,
                        }
                        continue
                    tree_dict = _proof_tree_to_dict(trees[0])
                    truncated = _tree_has_subproof(tree_dict.get("root"))
                    provenance_trees[candidate_id] = tree_dict
                    provenance_statuses[candidate_id] = {
                        "status": "present",
                        "engine": "souffle",
                        "truncated": truncated,
                    }
        except Exception:
            for row in candidate_rows:
                provenance_statuses[row["candidate_id"]] = {
                    "status": "export_failed",
                    "reason": "query-bearing package export failed",
                    "engine": "souffle",
                    "truncated": False,
                }
            continue

    return provenance_trees, provenance_statuses


def _materialize_evidence_graphs(
    session: RuntimeSession,
    *,
    provenance_trees: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Materialize additive audit-package EvidenceGraph rows where possible."""
    from factgraph.adapters.problog.provenance import (
        problog_trace_from_dict,
        problog_trace_to_evidence_graph,
    )
    from factgraph.adapters.pyreason.provenance import (
        pyreason_trace_from_dict,
        pyreason_trace_to_evidence_graph,
    )
    from factgraph.adapters.souffle.provenance import (
        souffle_proof_tree_from_dict,
        souffle_proof_tree_to_evidence_graph,
    )

    graphs: dict[str, dict[str, Any]] = {}
    for row in _accepted_candidate_claim_rows(session):
        candidate_id = row["candidate_id"]
        support_kind = row.get("support_kind")
        if not isinstance(support_kind, str) or not support_kind:
            continue

        try:
            if support_kind == SOUFFLE_WITNESS_KIND:
                tree_dict = provenance_trees.get(candidate_id)
                if not isinstance(tree_dict, dict):
                    continue
                proof_tree = souffle_proof_tree_from_dict(tree_dict)
                graph = souffle_proof_tree_to_evidence_graph(
                    proof_tree,
                    candidate_id=candidate_id,
                    support_kind=support_kind,
                )
            elif support_kind in _PROVENANCE_BEARING_SUPPORT_KINDS:
                support_digest = row.get("support_digest")
                if not isinstance(support_digest, str) or not support_digest:
                    continue
                provenance = session.store.explain_provenance(support_digest)
                if not isinstance(provenance, dict):
                    continue
                payload = provenance.get("payload")
                if not isinstance(payload, dict):
                    continue
                candidate_payload = _candidate_payload_from_claim(row["claim"])
                engine = provenance.get("engine")
                if engine == "pyreason":
                    graph = pyreason_trace_to_evidence_graph(
                        pyreason_trace_from_dict(payload),
                        candidate_id=candidate_id,
                        candidate_payload=candidate_payload,
                        support_kind=support_kind,
                    )
                elif engine == "problog":
                    graph = problog_trace_to_evidence_graph(
                        problog_trace_from_dict(payload),
                        candidate_id=candidate_id,
                        candidate_payload=candidate_payload,
                        support_kind=support_kind,
                    )
                else:
                    continue
            else:
                continue
        except Exception:
            continue

        graphs[candidate_id] = evidence_graph_to_dict(graph)

    return graphs


def _materialize_provenance_timelines(
    session: RuntimeSession,
) -> dict[str, dict[str, Any]]:
    """Materialize additive audit-package CandidateProvenanceTimeline rows where possible."""
    from factgraph.adapters.pyreason.provenance import pyreason_trace_from_dict
    from factgraph.core.store._candidate_provenance_timeline import (
        build_candidate_provenance_timeline,
    )
    from factgraph.core.store._support import PYREASON_PROVENANCE_KIND

    timelines: dict[str, dict[str, Any]] = {}
    for row in _accepted_candidate_claim_rows(session):
        candidate_id = row["candidate_id"]
        support_kind = row.get("support_kind")
        if support_kind != PYREASON_PROVENANCE_KIND:
            continue
        support_digest = row.get("support_digest")
        if not isinstance(support_digest, str) or not support_digest:
            continue

        try:
            provenance = session.store.explain_provenance(support_digest)
            if not isinstance(provenance, dict):
                continue
            payload = provenance.get("payload")
            if not isinstance(payload, dict):
                continue
            candidate_payload = _candidate_payload_from_claim(row["claim"])
            timelines[candidate_id] = build_candidate_provenance_timeline(
                candidate_id=candidate_id,
                trace=pyreason_trace_from_dict(payload),
                candidate_payload=candidate_payload,
            )
        except Exception:
            continue

    return timelines


def _accepted_candidate_provenance_rows(session: RuntimeSession) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": row["candidate_id"],
            "run_id": row["run_id"],
            "accepted_args": row["accepted_args"],
        }
        for row in _accepted_candidate_claim_rows(session)
    ]


def _accepted_candidate_claim_rows(session: RuntimeSession) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    for claim in sorted(session.store.ledger.claims, key=lambda item: item.asrt_id):
        candidate_id = _candidate_meta_str(session, claim.asrt_id, "candidate_id")
        run_id = _candidate_meta_str(session, claim.asrt_id, "run_id")
        if candidate_id is None or candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate_id)
        rows.append(
            {
                "candidate_id": candidate_id,
                "run_id": run_id,
                "accepted_args": _claim_query_args(claim),
                "claim": claim,
                "support_digest": session.store.get_candidate_support_digest(candidate_id),
                "support_kind": session.store.get_candidate_support_kind(candidate_id),
            }
        )
    return rows


def _candidate_meta_str(session: RuntimeSession, asrt_id: str, key: str) -> str | None:
    for row in session.store.ledger.find_meta(asrt_id=asrt_id, key=key, kind="str"):
        if isinstance(row.value, str) and row.value:
            return row.value
    return None


def _claim_query_args(claim: Claim) -> list[str]:
    args = [claim.e_ref]
    args.extend(str(value) for _tag, value in claim.rest_terms)
    return args


def _candidate_payload_from_claim(claim: Claim) -> dict[str, Any]:
    terms: list[dict[str, Any]] = [{"kind": "entity_ref", "value": claim.e_ref}]
    for tag, value in claim.rest_terms:
        if tag == "entity_ref":
            terms.append({"kind": "entity_ref", "value": str(value)})
            continue
        terms.append({"kind": "literal", "tag": tag, "value": value})
    return {
        "pred_id": claim.pred_id,
        "terms": terms,
    }


def _candidate_payload_for_candidate_id(
    session: RuntimeSession,
    candidate_id: str,
) -> dict[str, Any] | None:
    for claim in sorted(session.store.ledger.claims, key=lambda item: item.asrt_id):
        if _candidate_meta_str(session, claim.asrt_id, "candidate_id") != candidate_id:
            continue
        return _candidate_payload_from_claim(claim)
    return None


def _candidate_binding_for_recipe(
    recipe: RuntimeDerivationRecipe,
    *,
    accepted_args: list[str],
    query_variables: list[str],
) -> tuple[str, ...] | None:
    if len(recipe.head_vars) != len(accepted_args):
        return None
    binding_by_var = {var: value for var, value in zip(recipe.head_vars, accepted_args)}
    if any(var not in binding_by_var for var in query_variables):
        return None
    return tuple(binding_by_var[var] for var in query_variables)


def _souffle_query_text(relation: str, args: tuple[str, ...]) -> str:
    if not args:
        return f"{relation}()"
    rendered_args = ", ".join(json.dumps(arg, ensure_ascii=False) for arg in args)
    return f"{relation}({rendered_args})"


def _tree_has_subproof(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    if node.get("node_type") == "subproof":
        return True
    children = node.get("children")
    if not isinstance(children, list):
        return False
    return any(_tree_has_subproof(child) for child in children if isinstance(child, dict))


def _proof_tree_to_dict(tree: Any) -> dict[str, Any]:
    return asdict(tree)


def _runtime_assertion_detail_for_tree(ledger: Ledger, asrt_id: str) -> dict[str, Any] | None:
    claim = ledger.get_claim(asrt_id)
    if claim is None:
        return None
    claim_args = [
        {
            "idx": row.idx,
            "val": "" if row.val_atom is None else str(row.val_atom),
            "tag": row.tag,
        }
        for row in ledger.find_claim_args(asrt_id=asrt_id)
    ]
    claim_args.sort(key=lambda row: (row["idx"], row["tag"], row["val"]))
    result: dict[str, Any] = {
        "asrt_id": asrt_id,
        "claim": {
            "asrt_id": asrt_id,
            "pred_id": claim.pred_id,
            "e_ref": claim.e_ref,
        },
        "claim_args": claim_args,
    }
    _FACT_META_STR_KEYS = ("source", "source_loc", "approved_by", "trace_id", "note")
    flat_meta: dict[str, str] = {}
    for _key in _FACT_META_STR_KEYS:
        _rows = ledger.find_meta(asrt_id=asrt_id, key=_key, kind="str")
        if _rows:
            flat_meta[_key] = str(_rows[0].value)
    if flat_meta:
        result["flat_meta"] = flat_meta
    return result


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


def _apply_ephemeral_rules(registry: RuleRegistry, session: RuntimeSession) -> None:
    """Merge session ephemeral rules into an active registry.

    Q8 Phase 2 (Slice 6): FS-saved rule loading was removed, so ephemeral rules
    are the only source of rule registrations here. Duplicate (rule_id, version)
    registrations within ephemeral_rules raise RuleCompileError and are silently
    skipped.
    """
    for rs in session.ephemeral_rules:
        try:
            registry.register(rs)
        except RuleCompileError:
            pass


def _validate_ephemeral_rule_preds(
    compiled_where: list[Any],
    schema_ir: dict[str, Any],
) -> list[str]:
    """Return unknown pred_ids referenced by pred-atoms in compiled where IR."""
    predicates = schema_ir.get("predicates", [])
    known = {
        pred.get("pred_id")
        for pred in predicates
        if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str)
    }
    unknown: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, (tuple, list)) and node:
            if node[0] == "pred" and len(node) >= 2:
                pred_id = node[1]
                if isinstance(pred_id, str) and pred_id not in known and pred_id not in unknown:
                    unknown.append(pred_id)
            else:
                for child in node:
                    _walk(child)

    _walk(compiled_where)
    return unknown


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


def _evaluate_result_from_candidates(
    session: RuntimeSession,
    *,
    candidates: list[CandidateSet],
    compiled: dict[str, Any],
    mode: str,
    semantics_profile: SemanticsProfile | None,
) -> EvaluateResult:
    app_plans = _application_plans_from_compiled_dicts((compiled,), mode=mode)
    head = _head_rule_for_compiled_plans(app_plans)
    run_id = new_run_id()
    expr_digest = expr_digest_for_payload(
        "compiled_derivation_plans",
        {"plans": [_compiled_plan_digest_payload(plan) for plan in app_plans]},
    )
    rule_set_digest = rule_set_digest_for_entries(_rule_set_entries_for_result(app_plans, head=head))
    view_snapshot_digest = _runtime_view_snapshot_digest(session)
    config_digest = config_digest_for(semantics_profile)
    result_id = result_id_for(
        run_id=run_id,
        expr_digest=expr_digest,
        rule_set_digest=rule_set_digest,
        view_snapshot_digest=view_snapshot_digest,
        config_digest=config_digest,
        engine=mode,
        head_id=head.id,
        head_content_digest=head.content_digest,
    )
    closed_head_digest = closed_head_digest_for(head)
    rows = tuple(
        _candidate_set_to_evaluate_row(
            candidate,
            head=head,
            result_id=result_id,
            run_id=run_id,
            closed_head_digest=closed_head_digest,
            claim_name=head.id,
        )
        for candidate in candidates
    )
    result_digest = result_digest_for(
        result_id=result_id,
        run_id=run_id,
        row_digests=tuple(_row_digest_for(row, result_id=result_id, claim_name=head.id) for row in rows),
        head_id=head.id,
        head_content_digest=head.content_digest,
        engine=mode,
        engine_version=None,
        adapter_version=None,
        expr_digest=expr_digest,
        rule_set_digest=rule_set_digest,
        view_snapshot_digest=view_snapshot_digest,
        config_digest=config_digest,
    )
    fingerprint = ResultFingerprint(
        expr_digest=expr_digest,
        rule_set_digest=rule_set_digest,
        view_snapshot_digest=view_snapshot_digest,
        config_digest=config_digest,
        result_digest=result_digest,
        run_id=run_id,
    )
    return EvaluateResult(
        result_id=result_id,
        rows=rows,
        head=head,
        engine=mode,
        evaluated_at=time_ns(),
        fingerprint=fingerprint,
        engine_meta={"engine_version": None, "adapter_version": None},
    )


def _runtime_view_snapshot_digest(session: RuntimeSession) -> str:
    ledger = session.store.ledger
    db_id = ledger.get_ledger_meta("db_id")
    if db_id is None:
        db_id = "mem:" + sha256_hex(canonical_bytes_for_evaluate("runtime_evaluate_mem_db_v1", session.schema_digest))
    base_tx_id = ledger.get_ledger_meta("head_tx_id")
    if base_tx_id is None:
        base_tx_id = "tx:" + sha256_hex(
            canonical_bytes_for_evaluate(
                "runtime_evaluate_mem_tx_v1",
                {
                    "claims": [
                        {
                            "asrt_id": claim.asrt_id,
                            "e_ref": claim.e_ref,
                            "pred_id": claim.pred_id,
                            "rest_terms": claim.rest_terms,
                        }
                        for claim in sorted(ledger.find_claims(), key=lambda item: item.asrt_id)
                    ],
                    "revokes": [
                        {
                            "revoked_asrt_id": revoke.revoked_asrt_id,
                            "revoker_asrt_id": revoke.revoker_asrt_id,
                        }
                        for revoke in sorted(
                            ledger.revokes,
                            key=lambda item: (item.revoked_asrt_id, item.revoker_asrt_id),
                        )
                    ],
                    "schema_digest": session.schema_digest,
                },
            )
        )
    active_asrt_ids = tuple(
        _view_snapshot_asrt_id_for_claim(claim)
        for claim in sorted(ledger.find_claims(), key=lambda item: item.asrt_id)
        if not ledger.has_active_revocation(claim.asrt_id)
    )
    return view_snapshot_digest_for_parts(
        db_id=db_id,
        base_tx_id=base_tx_id,
        schema_digest=session.schema_digest,
        asrt_ids=active_asrt_ids,
    )


def _evaluate_result_to_dict(result: EvaluateResult, *, rows: tuple[EvaluateRow, ...] | None = None) -> dict[str, Any]:
    selected_rows = result.rows if rows is None else rows
    fingerprint = result.fingerprint
    return {
        "result_id": result.result_id,
        "run_id": fingerprint.run_id,
        "rows": [_evaluate_row_to_dict(row, result) for row in selected_rows],
        "head": _application_rule_to_dict(result.head),
        "engine": result.engine,
        "engine_version": result.engine_meta["engine_version"],
        "adapter_version": result.engine_meta["adapter_version"],
        "expr_digest": fingerprint.expr_digest,
        "rule_set_digest": fingerprint.rule_set_digest,
        "view_snapshot_digest": fingerprint.view_snapshot_digest,
        "config_digest": fingerprint.config_digest,
        "evaluated_at": _to_jsonable(result.evaluated_at),
        "result_digest": fingerprint.result_digest,
        "row_count": len(result.rows),
    }


def _evaluate_row_to_dict(row: EvaluateRow, result: EvaluateResult) -> dict[str, Any]:
    return {
        "row_id": row.row_id,
        "bindings": _to_jsonable(_legacy_candidate_payload_for_row_result(row, result)),
        "claim": {
            "kind": row.kind,
            "name": _claim_name_for_row_result(row, result),
            "arguments": _to_jsonable(_claim_arguments_for_row(row)),
            "repr": _claim_repr_for_row_result(row, result),
            "digest": row.digest,
        },
        "raw_kind": row.raw_kind,
        "bound": list(row.bound) if row.bound is not None else None,
        "evidence_ref": {
            "ref_id": _evidence_ref_id_for_row_result(row, result),
            "result_id": _evidence_ref_result_id_for_row_result(row, result),
            "row_id": _evidence_ref_row_id_for_row(row),
            "fact_digest": _evidence_ref_fact_digest_for_row(row),
            "closed_head_digest": row.closed_head_digest,
        },
    }


def _application_rule_to_dict(rule: ApplicationRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "version": rule.version,
        "desc": rule.desc,
        "content_digest": rule.content_digest,
        "ports": {name: var.name for name, var in rule.ports.items()},
        "where": [repr(atom) for atom in rule.when],
    }


def _candidate_to_dict(candidate: CandidateSet) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "candidate_key": candidate.candidate_key,
        "candidate_kind": candidate.candidate_kind,
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
        confidence=_optional_candidate_confidence(value.get("confidence"), path=f"{path}.confidence"),
        confidence_kind=_candidate_confidence_kind(
            value.get("confidence_kind", "none"),
            path=f"{path}.confidence_kind",
        ),
        candidate_id=_optional_str_or_none(value.get("candidate_id"), path=f"{path}.candidate_id") or "",
        candidate_key=_optional_str_or_none(value.get("candidate_key"), path=f"{path}.candidate_key") or "",
        candidate_kind=_require_non_empty_str(value.get("candidate_kind"), path=f"{path}.candidate_kind"),
    )


def _optional_candidate_confidence(value: Any, *, path: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, float):
        raise facade_error("confidence must be float or null", kind="shape", path=path)
    return value


def _candidate_confidence_kind(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise facade_error("confidence_kind must be non-empty string", kind="shape", path=path)
    if value not in CONFIDENCE_KINDS:
        allowed = ", ".join(sorted(CONFIDENCE_KINDS))
        raise facade_error(
            f"confidence_kind must be one of: {allowed}",
            kind="shape",
            path=path,
        )
    return value


def _candidate_payload_from_dict(value: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise facade_error("payload must be object", kind="shape", path=path)
    payload = dict(value)
    if isinstance(payload.get("terms"), list):
        payload["terms"] = _normalize_candidate_terms(payload.get("terms"), path=f"{path}.terms")
        pred_id = payload.get("pred_id")
        if pred_id is not None:
            payload["pred_id"] = _require_non_empty_str(pred_id, path=f"{path}.pred_id")
        return payload
    if isinstance(payload.get("entity_type"), str) and isinstance(payload.get("identity_fields"), list):
        payload["entity_type"] = _require_non_empty_str(payload.get("entity_type"), path=f"{path}.entity_type")
        payload["identity_fields"] = [
            _require_non_empty_str(item, path=f"{path}.identity_fields[]")
            for item in payload.get("identity_fields", [])
        ]
        resolved_identity = payload.get("resolved_identity")
        if resolved_identity is None:
            resolved_identity = {}
        if not isinstance(resolved_identity, dict):
            raise facade_error("resolved_identity must be object", kind="shape", path=f"{path}.resolved_identity")
        payload["resolved_identity"] = dict(resolved_identity)
        missing_identity_fields = payload.get("missing_identity_fields")
        if missing_identity_fields is None:
            missing_identity_fields = []
        if not isinstance(missing_identity_fields, list):
            raise facade_error(
                "missing_identity_fields must be list",
                kind="shape",
                path=f"{path}.missing_identity_fields",
            )
        payload["missing_identity_fields"] = [
            _require_non_empty_str(item, path=f"{path}.missing_identity_fields[]")
            for item in missing_identity_fields
        ]
        if "identity_types" in payload:
            identity_types = payload.get("identity_types")
            if not isinstance(identity_types, dict):
                raise facade_error("identity_types must be object", kind="shape", path=f"{path}.identity_types")
            payload["identity_types"] = {
                _require_non_empty_str(k, path=f"{path}.identity_types.key"): _require_non_empty_str(
                    v,
                    path=f"{path}.identity_types[{k}]",
                )
                for k, v in identity_types.items()
            }
        if "proposed_entity_ref" in payload and payload.get("proposed_entity_ref") is not None:
            payload["proposed_entity_ref"] = _require_non_empty_str(
                payload.get("proposed_entity_ref"),
                path=f"{path}.proposed_entity_ref",
            )
        return payload
    raise facade_error(
        "payload must be v2 fact payload (pred_id+terms) or v2 entity payload",
        kind="shape",
        path=path,
    )


def _accept_options_from_dto(value: Any, *, path: str) -> AcceptOptions:
    if value is None:
        return AcceptOptions()
    if not isinstance(value, dict):
        raise facade_error("options must be object", kind="shape", path=path)
    unknown = sorted(set(value.keys()) - {"approved_by", "note", "dry_run", "identity_override"})
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
    identity_override = _optional_dict(value.get("identity_override"), path=f"{path}.identity_override")
    return AcceptOptions(
        approved_by=approved_by,
        note=note,
        dry_run=dry_run,
        identity_override=identity_override,
    )


def _accept_result_to_dict(result: AcceptResult) -> dict[str, Any]:
    return {
        "candidate_id": result.candidate_id,
        "candidate_key": result.candidate_key,
        "run_id": result.run_id,
        "accepted_count": result.accepted_count,
        "skipped_count": result.skipped_count,
        "written_assertions": _to_jsonable(result.written_assertions),
        "skipped_reason_counts": dict(result.skipped_reason_counts),
        "diagnostics_contract_version": result.diagnostics_contract_version,
        "diagnostics": _to_jsonable(result.diagnostics),
        "entity_ref": result.entity_ref,
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


def _reject_runtime_read_policy(dto: dict[str, Any]) -> None:
    if "view_name" in dto:
        raise facade_error(
            "view_name was removed; runtime view-facts always uses active projection",
            kind="shape",
            path="$.view_name",
        )
    if "view" in dto:
        raise facade_error(
            "view was removed; runtime view-facts always uses active projection",
            kind="shape",
            path="$.view",
        )
    if "policy" in dto:
        raise facade_error(
            "ReadPolicy was removed. Use raw_kind / bound for uncertainty inputs.",
            kind="shape",
            path="$.policy",
        )


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
    if isinstance(value, Mapping):
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


def _normalize_candidate_terms(value: Any, *, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise facade_error("terms must be list", kind="shape", path=path)
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(value):
        item_path = f"{path}[{idx}]"
        if not isinstance(item, dict):
            raise facade_error("term must be object", kind="shape", path=item_path)
        kind = item.get("kind")
        if kind == "entity_ref":
            out.append(
                {
                    "kind": "entity_ref",
                    "value": _require_non_empty_str(item.get("value"), path=f"{item_path}.value"),
                }
            )
            continue
        if kind == "candidate_ref":
            out.append(
                {
                    "kind": "candidate_ref",
                    "candidate_key": _require_non_empty_str(item.get("candidate_key"), path=f"{item_path}.candidate_key"),
                }
            )
            continue
        if kind == "literal":
            tag = _require_non_empty_str(item.get("tag"), path=f"{item_path}.tag")
            out.append({"kind": "literal", "tag": tag, "value": _normalize_tagged_value(tag, item.get("value"), path=f"{item_path}.value")})
            continue
        raise facade_error("unsupported term kind", kind="shape", path=f"{item_path}.kind")
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
