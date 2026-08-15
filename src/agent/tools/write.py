from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..draft import FactDraft
from ..errors import AgentContractError, AgentRuntimeError
from ..session import AgentSession
from ._entity_ref import encode_entity_ref
from ._runtime_api import RuntimeAPI, require_ok


@dataclass(frozen=True)
class WriteRequest:
    draft_id: str
    kind: Literal["set", "add"] = "set"
    pred_id: str = ""
    e_ref: str = ""
    rest_terms: list[list[Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dto(self) -> dict[str, Any]:
        dto: dict[str, Any] = {
            "pred_id": self.pred_id,
            "e_ref": self.e_ref,
            "rest_terms": list(self.rest_terms),
        }
        if self.meta:
            dto["meta"] = dict(self.meta)
        return dto


@dataclass(frozen=True)
class WriteResult:
    draft_id: str
    kind: str
    assertion_id: str


@dataclass(frozen=True)
class WriteError:
    draft_id: str
    kind: str
    error_kind: str
    error_path: str
    error_message: str


@dataclass(frozen=True)
class RetractRequest:
    asrt_id: str
    note: str | None = None
    confirmed_by: str | None = None
    trace_id: str | None = None

    def to_dto(self, *, agent_id: str) -> dict[str, Any]:
        if not isinstance(self.asrt_id, str) or not self.asrt_id:
            raise AgentContractError("asrt_id must be non-empty string")
        if not isinstance(agent_id, str) or not agent_id:
            raise AgentContractError("agent_id must be non-empty string")
        if self.note is not None and (not isinstance(self.note, str) or not self.note):
            raise AgentContractError("note must be non-empty string when provided")
        if self.confirmed_by is not None and (
            not isinstance(self.confirmed_by, str) or not self.confirmed_by
        ):
            raise AgentContractError("confirmed_by must be non-empty string when provided")
        if self.trace_id is not None and (not isinstance(self.trace_id, str) or not self.trace_id):
            raise AgentContractError("trace_id must be non-empty string when provided")
        meta: dict[str, Any] = {"approved_by": self.confirmed_by or agent_id}
        if self.confirmed_by and self.confirmed_by != agent_id:
            meta["agent_executor"] = agent_id
        if self.note:
            meta["note"] = self.note
        if self.trace_id:
            meta["trace_id"] = self.trace_id
        dto: dict[str, Any] = {"asrt_id": self.asrt_id}
        if meta:
            dto["meta"] = meta
        return dto


@dataclass(frozen=True)
class RetractResult:
    revoked_asrt_id: str
    revoker_asrt_id: str


@dataclass(frozen=True)
class RetractError:
    asrt_id: str
    error_kind: str
    error_message: str


def draft_to_write_request(
    draft: FactDraft,
    *,
    schema_ir: dict[str, Any],
    kind: Literal["set", "add"] = "set",
    agent_id: str,
    confirmed_by: str | None = None,
    bundle_id: str | None = None,
) -> WriteRequest:
    if not isinstance(draft, FactDraft):
        raise AgentContractError("draft must be FactDraft")
    if kind not in {"set", "add"}:
        raise AgentContractError("kind must be set|add")
    if not isinstance(schema_ir, dict):
        raise AgentContractError("schema_ir must be object")
    if not isinstance(agent_id, str) or not agent_id:
        raise AgentContractError("agent_id must be non-empty string")
    if confirmed_by is not None and (not isinstance(confirmed_by, str) or not confirmed_by):
        raise AgentContractError("confirmed_by must be non-empty string when provided")
    if bundle_id is not None and (not isinstance(bundle_id, str) or not bundle_id):
        raise AgentContractError("bundle_id must be non-empty string when provided")

    e_ref = encode_entity_ref(
        schema_ir,
        entity_type=draft.entity_type,
        identity=draft.entity_identity,
    )
    meta: dict[str, Any] = {"approved_by": confirmed_by or agent_id}
    if confirmed_by and confirmed_by != agent_id:
        meta["agent_executor"] = agent_id
    # Extraction confidence is workflow-local review information.  Core write
    # metadata deliberately rejects it, and a confidence score must never be
    # silently reinterpreted as a probabilistic ``raw_kind``/``bound`` fact.
    # A caller that needs run-local uncertainty must construct the explicit
    # Scenario semantic input instead of writing it into the durable ledger.
    if draft.source:
        meta["source"] = draft.source
    if draft.source_loc:
        meta["source_loc"] = draft.source_loc
    if draft.note:
        meta["note"] = draft.note
    if bundle_id:
        meta["trace_id"] = bundle_id
    return WriteRequest(
        draft_id=draft.draft_id,
        kind=kind,
        pred_id=draft.pred_id,
        e_ref=e_ref,
        rest_terms=[[tag, value] for tag, value in draft.field_values],
        meta=meta,
    )


class WriteTools:
    """Structured write/retract helpers over runtime write surfaces."""

    def __init__(self, *, runtime_api: RuntimeAPI, session: AgentSession) -> None:
        self._runtime = runtime_api
        self._session = session

    @property
    def runtime_api(self) -> RuntimeAPI:
        return self._runtime

    @property
    def session(self) -> AgentSession:
        return self._session

    @property
    def _runtime_session_id(self) -> str:
        runtime_session_id = self._session.runtime_session_id
        if not isinstance(runtime_session_id, str) or not runtime_session_id:
            raise AgentRuntimeError(
                "AgentSession is not bound to a runtime session",
                kind="runtime_session_missing",
            )
        return runtime_session_id

    def commit_draft(
        self,
        draft: FactDraft,
        *,
        kind: Literal["set", "add"] = "set",
        bundle_id: str | None = None,
        confirmed_by: str | None = None,
    ) -> WriteResult | WriteError:
        if not isinstance(draft, FactDraft):
            raise AgentContractError("draft must be FactDraft")
        if draft.status != "confirmed":
            raise AgentContractError("draft.status must be confirmed")
        if kind not in {"set", "add"}:
            raise AgentContractError("kind must be set|add")
        try:
            request = draft_to_write_request(
                draft,
                schema_ir=self._resolve_schema_ir(),
                kind=kind,
                agent_id=self._agent_id(),
                confirmed_by=confirmed_by,
                bundle_id=bundle_id,
            )
        except AgentRuntimeError as exc:
            return _write_error_from_exception(draft.draft_id, kind, exc)
        response = self._runtime.write_fact(self._runtime_session_id, request.to_dto(), kind=kind)
        if response.get("ok") is True:
            write = response.get("write")
            if not isinstance(write, dict):
                raise AgentContractError("runtime write response must include write object")
            return WriteResult(
                draft_id=draft.draft_id,
                kind=_require_non_empty_str(write.get("kind"), "write.kind"),
                assertion_id=_require_non_empty_str(write.get("assertion_id"), "write.assertion_id"),
            )
        return _write_error_from_response(draft.draft_id, kind, response)

    def commit_many(
        self,
        drafts: list[FactDraft],
        *,
        kind: Literal["set", "add"] = "set",
        bundle_id: str | None = None,
        confirmed_by: str | None = None,
    ) -> list[WriteResult | WriteError]:
        if not isinstance(drafts, list):
            raise AgentContractError("drafts must be list")
        return [
            self.commit_draft(
                draft,
                kind=kind,
                bundle_id=bundle_id,
                confirmed_by=confirmed_by,
            )
            for draft in drafts
        ]

    def retract(self, request: RetractRequest) -> RetractResult | RetractError:
        if not isinstance(request, RetractRequest):
            raise AgentContractError("request must be RetractRequest")
        try:
            response = self._runtime.retract_fact(
                self._runtime_session_id,
                request.to_dto(agent_id=self._agent_id()),
            )
        except AgentRuntimeError as exc:
            return RetractError(
                asrt_id=request.asrt_id,
                error_kind=exc.kind,
                error_message=str(exc),
            )
        if response.get("ok") is True:
            write = response.get("write")
            if not isinstance(write, dict):
                raise AgentContractError("runtime retract response must include write object")
            return RetractResult(
                revoked_asrt_id=request.asrt_id,
                revoker_asrt_id=_require_non_empty_str(write.get("assertion_id"), "write.assertion_id"),
            )
        kind, _path, message = _error_details_from_response(response, default_message="runtime retract failed")
        return RetractError(
            asrt_id=request.asrt_id,
            error_kind=kind,
            error_message=message,
        )

    def _resolve_schema_ir(self) -> dict[str, Any]:
        bootstrap = self._session.bootstrap_spec
        if bootstrap is not None:
            schema_ir = bootstrap.open_dto.get("schema_ir")
            if isinstance(schema_ir, dict):
                return dict(schema_ir)
        response = require_ok(self._runtime.get_schema(self._runtime_session_id))
        result = response.get("result", {})
        if not isinstance(result, dict):
            raise AgentRuntimeError("runtime schema response must include result object")
        schema_ir = result.get("schema_ir")
        if not isinstance(schema_ir, dict):
            raise AgentRuntimeError("runtime schema response must include schema_ir")
        return dict(schema_ir)

    def _agent_id(self) -> str:
        scope = self._session.scope
        if scope is None:
            return "agent"
        return scope.agent_id


def _write_error_from_response(draft_id: str, kind: str, response: dict[str, Any]) -> WriteError:
    error_kind, error_path, error_message = _error_details_from_response(
        response,
        default_message="runtime write failed",
    )
    return WriteError(
        draft_id=draft_id,
        kind=kind,
        error_kind=error_kind,
        error_path=error_path,
        error_message=error_message,
    )


def _write_error_from_exception(draft_id: str, kind: str, exc: AgentRuntimeError) -> WriteError:
    return WriteError(
        draft_id=draft_id,
        kind=kind,
        error_kind=exc.kind,
        error_path=exc.path,
        error_message=str(exc),
    )


def _error_details_from_response(
    response: dict[str, Any],
    *,
    default_message: str,
) -> tuple[str, str, str]:
    if not isinstance(response, dict):
        raise AgentContractError("runtime response must be object")
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        err0 = errors[0] if isinstance(errors[0], dict) else {}
        details = err0.get("details")
        if isinstance(details, dict) and isinstance(details.get("message"), str):
            message = details["message"]
        else:
            message = str(err0.get("message") or err0.get("details") or default_message)
        return (
            str(err0.get("kind", "runtime")),
            str(err0.get("path", "$")),
            message,
        )
    return ("runtime", "$", default_message)


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value
