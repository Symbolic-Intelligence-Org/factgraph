from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib import parse, request

from factpy.service import rules_v1
from factpy.service import runtime_v1

from ..errors import AgentContractError, AgentRuntimeError


class RuntimeAPI(Protocol):
    def open_session(self, dto: dict[str, Any]) -> dict[str, Any]: ...
    def get_session(self, session_id: str) -> dict[str, Any]: ...
    def get_schema(self, session_id: str) -> dict[str, Any]: ...
    def write_fact(self, session_id: str, dto: dict[str, Any], *, kind: str) -> dict[str, Any]: ...
    def retract_fact(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]: ...
    def list_claims(
        self,
        session_id: str,
        *,
        pred_id: str | None = None,
        e_ref: str | None = None,
        include_meta: bool = False,
        include_args: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]: ...
    def list_rules(self, session_id: str, *, include_spec: bool = False) -> dict[str, Any]: ...
    def validate_rule(self, dto: dict[str, Any]) -> dict[str, Any]: ...
    def compile_rule_preview(self, dto: dict[str, Any]) -> dict[str, Any]: ...
    def register_ephemeral_rule(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]: ...
    def list_ephemeral_rules(self, session_id: str) -> dict[str, Any]: ...
    def clear_ephemeral_rules(self, session_id: str) -> dict[str, Any]: ...
    def list_candidates(self, session_id: str, *, pred_id_filter: str | None = None) -> dict[str, Any]: ...
    def explain_summary(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]: ...
    def explain_steps(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]: ...
    def explain_tree(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]: ...
    def explain_timeline(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]: ...
    def evaluate_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]: ...
    def accept_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]: ...
    def close_session(self, session_id: str) -> dict[str, Any]: ...


class LocalRuntimeAPI:
    """Direct in-process adapter over service runtime_v1 helpers."""

    def open_session(self, dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.open_runtime_session(dto)

    def get_session(self, session_id: str) -> dict[str, Any]:
        return runtime_v1.get_runtime_session(session_id)

    def get_schema(self, session_id: str) -> dict[str, Any]:
        return runtime_v1.get_runtime_session_schema(session_id)

    def write_fact(self, session_id: str, dto: dict[str, Any], *, kind: str) -> dict[str, Any]:
        return runtime_v1.write_runtime_fact(session_id, dto, kind=kind)

    def retract_fact(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.retract_runtime_fact(session_id, dto)

    def list_claims(
        self,
        session_id: str,
        *,
        pred_id: str | None = None,
        e_ref: str | None = None,
        include_meta: bool = False,
        include_args: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return runtime_v1.list_runtime_claims(
            session_id,
            pred_id=pred_id,
            e_ref=e_ref,
            include_meta=include_meta,
            include_args=include_args,
            limit=limit,
        )

    def list_rules(self, session_id: str, *, include_spec: bool = False) -> dict[str, Any]:
        return runtime_v1.get_runtime_session_rules(session_id, include_spec=include_spec)

    def validate_rule(self, dto: dict[str, Any]) -> dict[str, Any]:
        return rules_v1.validate_rule(dto)

    def compile_rule_preview(self, dto: dict[str, Any]) -> dict[str, Any]:
        return rules_v1.compile_rule_preview(dto)

    def register_ephemeral_rule(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.register_ephemeral_rule(session_id, dto)

    def list_ephemeral_rules(self, session_id: str) -> dict[str, Any]:
        return runtime_v1.list_ephemeral_rules(session_id)

    def clear_ephemeral_rules(self, session_id: str) -> dict[str, Any]:
        return runtime_v1.clear_ephemeral_rules(session_id)

    def list_candidates(self, session_id: str, *, pred_id_filter: str | None = None) -> dict[str, Any]:
        return runtime_v1.list_runtime_candidates(session_id, pred_id_filter=pred_id_filter)

    def explain_summary(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.explain_runtime_summary(session_id, dto)

    def explain_steps(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.explain_runtime_steps(session_id, dto)

    def explain_tree(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.explain_runtime_tree(session_id, dto)

    def explain_timeline(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.explain_runtime_timeline(session_id, dto)

    def evaluate_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.evaluate_runtime_derivation(session_id, dto)

    def accept_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.accept_runtime_derivation(session_id, dto)

    def close_session(self, session_id: str) -> dict[str, Any]:
        return runtime_v1.close_runtime_session(session_id)


class HttpRuntimeAPI:
    """Minimal HTTP transport over service v1 routes."""

    def __init__(
        self,
        runtime_api_base: str,
        *,
        api_key: str | None = None,
        api_key_header: str = "X-FactPy-API-Key",
    ) -> None:
        if not isinstance(runtime_api_base, str) or not runtime_api_base:
            raise AgentContractError("runtime_api_base must be non-empty string")
        self._base = runtime_api_base.rstrip("/")
        self._rules_base = (
            self._base[: -len("/runtime")]
            if self._base.endswith("/runtime")
            else self._base
        )
        self._extra_headers: dict[str, str] = {}
        if api_key is not None:
            if not isinstance(api_key, str) or not api_key:
                raise AgentContractError("api_key must be non-empty string when provided")
            if not isinstance(api_key_header, str) or not api_key_header:
                raise AgentContractError("api_key_header must be non-empty string")
            self._extra_headers[api_key_header] = api_key

    def open_session(self, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/sessions/open", dto)

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._get_json(f"/sessions/{session_id}")

    def get_schema(self, session_id: str) -> dict[str, Any]:
        return self._get_json(f"/sessions/{session_id}/schema")

    def write_fact(self, session_id: str, dto: dict[str, Any], *, kind: str) -> dict[str, Any]:
        return self._post_json(f"/sessions/{session_id}/writes/{kind}", dto)

    def retract_fact(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(f"/sessions/{session_id}/writes/retract", dto)

    def list_claims(
        self,
        session_id: str,
        *,
        pred_id: str | None = None,
        e_ref: str | None = None,
        include_meta: bool = False,
        include_args: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "include_meta": str(include_meta).lower(),
            "include_args": str(include_args).lower(),
        }
        if pred_id is not None:
            params["pred_id"] = pred_id
        if e_ref is not None:
            params["e_ref"] = e_ref
        if limit is not None:
            params["limit"] = str(limit)
        return self._get_json(f"/sessions/{session_id}/claims", params=params)

    def list_rules(self, session_id: str, *, include_spec: bool = False) -> dict[str, Any]:
        return self._get_json(
            f"/sessions/{session_id}/rules",
            params={"include_spec": str(include_spec).lower()},
        )

    def validate_rule(self, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json_to_base(self._rules_base, "/rules/validate", dto)

    def compile_rule_preview(self, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json_to_base(self._rules_base, "/rules/compile-preview", dto)

    def register_ephemeral_rule(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(f"/sessions/{session_id}/ephemeral-rules", dto)

    def list_ephemeral_rules(self, session_id: str) -> dict[str, Any]:
        return self._get_json(f"/sessions/{session_id}/ephemeral-rules")

    def clear_ephemeral_rules(self, session_id: str) -> dict[str, Any]:
        return self._delete_json(f"/sessions/{session_id}/ephemeral-rules")

    def list_candidates(self, session_id: str, *, pred_id_filter: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if pred_id_filter is not None:
            params["pred_id"] = pred_id_filter
        return self._get_json(f"/sessions/{session_id}/candidates", params=params)

    def explain_summary(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(f"/sessions/{session_id}/queries/explain-summary", dto)

    def explain_steps(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(f"/sessions/{session_id}/queries/explain-steps", dto)

    def explain_tree(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(f"/sessions/{session_id}/queries/explain-tree", dto)

    def explain_timeline(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(f"/sessions/{session_id}/queries/explain-timeline", dto)

    def evaluate_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(f"/sessions/{session_id}/inferences/evaluate", dto)

    def accept_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(f"/sessions/{session_id}/inferences/accept", dto)

    def close_session(self, session_id: str) -> dict[str, Any]:
        return self._delete_json(f"/sessions/{session_id}")

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base}{path}"
        if params:
            url = f"{url}?{parse.urlencode(params)}"
        req = request.Request(url, headers=self._headers(), method="GET")
        return self._load(req)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json_to_base(self._base, path, payload)

    def _post_json_to_base(self, base: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            f"{base}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers({"Content-Type": "application/json"}),
            method="POST",
        )
        return self._load(req)

    def _delete_json(self, path: str) -> dict[str, Any]:
        req = request.Request(f"{self._base}{path}", headers=self._headers(), method="DELETE")
        return self._load(req)

    def _headers(self, base: dict[str, str] | None = None) -> dict[str, str]:
        headers = dict(base or {})
        headers.update(self._extra_headers)
        return headers

    def _load(self, req: request.Request) -> dict[str, Any]:
        try:
            with request.urlopen(req) as resp:  # noqa: S310 - explicit local/service endpoint usage
                raw = resp.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise AgentRuntimeError("runtime response must be object")
        return data


def resolve_runtime_api(
    *,
    runtime_api_base: str | None = None,
    runtime_api: RuntimeAPI | None = None,
) -> RuntimeAPI:
    if runtime_api is not None:
        return runtime_api
    if runtime_api_base is None:
        return LocalRuntimeAPI()
    return HttpRuntimeAPI(runtime_api_base)


def require_ok(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise AgentRuntimeError("runtime response must be object")
    if response.get("ok") is True:
        return response
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        err0 = errors[0] if isinstance(errors[0], dict) else {}
        details = err0.get("details")
        if not isinstance(details, dict):
            details = {"message": str(err0)}
        raise AgentRuntimeError(
            message=str(details.get("message", "runtime request failed")),
            kind=str(err0.get("kind", "runtime")),
            path=str(err0.get("path", "$")),
            details=details,
        )
    raise AgentRuntimeError("runtime request failed")
