from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..errors import AgentContractError, AgentRuntimeError
from ..session import AgentSession
from ._runtime_api import RuntimeAPI, require_ok
from .evaluate import EvaluateResult
from .routing import EngineRoutingHint


@dataclass(frozen=True)
class RuleSpec:
    """Structured rule spec for agent-side authoring."""

    rule_id: str
    select_vars: list[str]
    where: list[Any]
    version: str = "v1"
    expose: bool = True
    description: str | None = None
    tags: list[str] | None = None
    condition_weights: dict[str, Any] | None = None
    routing_hint: EngineRoutingHint | None = None

    def to_rule_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "rule_id": self.rule_id,
            "version": self.version,
            "select_vars": list(self.select_vars),
            "where": list(self.where),
            "expose": self.expose,
        }
        if self.description is not None:
            out["description"] = self.description
        if self.tags is not None:
            out["tags"] = list(self.tags)
        if self.condition_weights is not None:
            out["condition_weights"] = dict(self.condition_weights)
        return out


@dataclass(frozen=True)
class ValidateResult:
    valid: bool
    profile_effective: str
    mode: str
    errors: list[dict[str, Any]]


@dataclass(frozen=True)
class CompilePreviewResult:
    valid: bool
    compiled_payload: dict[str, Any] | None
    profile_effective: str
    mode: str
    errors: list[dict[str, Any]]


@dataclass(frozen=True)
class RegisterResult:
    rule_id: str
    version: str
    status: str
    total_ephemeral: int


@dataclass(frozen=True)
class RegisterError:
    rule_id: str
    error_kind: str
    error_message: str


@dataclass(frozen=True)
class EvaluateOutcome:
    status: Literal["not_requested", "ok", "error", "skipped"]
    result: EvaluateResult | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class EphemeralRuleSummary:
    rule_id: str
    version: str


class RuleTools:
    """Native-first rule authoring helpers over runtime/rules service surfaces."""

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

    def validate(self, spec: RuleSpec) -> ValidateResult:
        if not isinstance(spec, RuleSpec):
            raise AgentContractError("spec must be RuleSpec")
        response = self._runtime.validate_rule({"rule": spec.to_rule_dict()})
        meta = _response_meta(response)
        return ValidateResult(
            valid=response.get("ok") is True,
            profile_effective=_require_non_empty_str(
                meta.get("profile_effective", "unknown"),
                "meta.profile_effective",
            ),
            mode=_require_non_empty_str(meta.get("mode", "souffle"), "meta.mode"),
            errors=_response_errors(response),
        )

    def compile_preview(self, spec: RuleSpec) -> CompilePreviewResult:
        if not isinstance(spec, RuleSpec):
            raise AgentContractError("spec must be RuleSpec")
        response = self._runtime.compile_rule_preview({"rule": spec.to_rule_dict()})
        meta = _response_meta(response)
        compiled_payload: dict[str, Any] | None = None
        if response.get("ok") is True:
            preview = _require_dict(response.get("preview"), "preview")
            raw_payload = preview.get("compiled_payload")
            if raw_payload is not None:
                compiled_payload = _require_dict(raw_payload, "preview.compiled_payload")
        return CompilePreviewResult(
            valid=response.get("ok") is True,
            compiled_payload=compiled_payload,
            profile_effective=_require_non_empty_str(
                meta.get("profile_effective", "unknown"),
                "meta.profile_effective",
            ),
            mode=_require_non_empty_str(meta.get("mode", "souffle"), "meta.mode"),
            errors=_response_errors(response),
        )

    def register_ephemeral(self, spec: RuleSpec) -> RegisterResult | RegisterError:
        if not isinstance(spec, RuleSpec):
            raise AgentContractError("spec must be RuleSpec")
        validation = self.validate(spec)
        if not validation.valid:
            return _register_error_from_errors(spec.rule_id, validation.errors, "rule validation failed")
        response = self._runtime.register_ephemeral_rule(
            self._runtime_session_id,
            {"rule": spec.to_rule_dict()},
        )
        if response.get("ok") is True:
            result = _require_dict(response.get("result"), "result")
            return RegisterResult(
                rule_id=_require_non_empty_str(result.get("rule_id"), "result.rule_id"),
                version=_require_non_empty_str(result.get("version"), "result.version"),
                status=_require_non_empty_str(result.get("status"), "result.status"),
                total_ephemeral=_require_int(result.get("total_ephemeral"), "result.total_ephemeral"),
            )
        return _register_error_from_errors(
            spec.rule_id,
            _response_errors(response),
            "ephemeral register failed",
        )

    def list_ephemeral(self) -> list[EphemeralRuleSummary]:
        response = require_ok(self._runtime.list_ephemeral_rules(self._runtime_session_id))
        result = _require_dict(response.get("result"), "result")
        raw_rules = result.get("ephemeral_rules")
        if not isinstance(raw_rules, list):
            raise AgentContractError("result.ephemeral_rules must be list")
        out: list[EphemeralRuleSummary] = []
        for item in raw_rules:
            entry = _require_dict(item, "result.ephemeral_rules[]")
            out.append(
                EphemeralRuleSummary(
                    rule_id=_require_non_empty_str(entry.get("rule_id"), "rule_id"),
                    version=_require_non_empty_str(entry.get("version"), "version"),
                )
            )
        return out

    def clear_ephemeral(self) -> int:
        response = require_ok(self._runtime.clear_ephemeral_rules(self._runtime_session_id))
        result = _require_dict(response.get("result"), "result")
        return _require_int(result.get("cleared"), "result.cleared")


def _response_meta(response: dict[str, Any]) -> dict[str, Any]:
    raw = response.get("meta")
    if raw is None:
        return {}
    return _require_dict(raw, "meta")


def _response_errors(response: dict[str, Any]) -> list[dict[str, Any]]:
    raw = response.get("errors", [])
    if not isinstance(raw, list):
        raise AgentContractError("errors must be list")
    return [_require_dict(item, "errors[]") for item in raw]


def _register_error_from_errors(
    rule_id: str,
    errors: list[dict[str, Any]],
    default_message: str,
) -> RegisterError:
    if errors:
        err0 = errors[0]
        details = err0.get("details")
        message = default_message
        if isinstance(details, dict) and isinstance(details.get("message"), str):
            message = details["message"]
        elif isinstance(err0.get("message"), str) and err0["message"]:
            message = err0["message"]
        return RegisterError(
            rule_id=rule_id,
            error_kind=str(err0.get("kind", "runtime")),
            error_message=message,
        )
    return RegisterError(
        rule_id=rule_id,
        error_kind="runtime",
        error_message=default_message,
    )


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentContractError(f"{name} must be object")
    return dict(value)


def _require_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AgentContractError(f"{name} must be int")
    return value


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value
