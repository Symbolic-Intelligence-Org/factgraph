from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factpy_kernel.authoring.rule_compile import AuthoringRuleCompileError, compile_authoring_rule_v1
from factpy_kernel.core.rules.backend_profile import (
    BackendProfile,
    PROFILE_DEFAULT,
    PROFILE_SOUFFLE_STRICT,
)
from factpy_kernel.core.rules.rule_ast import RuleASTError, parse_query_rule_ir_to_ast
from factpy_kernel.core.rules.rule_ast_validate import RuleASTValidationError, validate_query_rule_ast

_SUPPORTED_API_VERSION = "v1"
_SUPPORTED_MODES = {"souffle"}
_KNOWN_PROFILES: dict[str, BackendProfile] = {
    "default": PROFILE_DEFAULT,
    "souffle_strict": PROFILE_SOUFFLE_STRICT,
}
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
class _FacadeError(Exception):
    message: str
    kind: str
    path: str
    details: dict[str, Any]

    def __str__(self) -> str:
        return self.message


def validate_rule(dto: dict) -> dict:
    try:
        payload, meta, effective_profile, _strict_for_compile = _prepare_request(dto)
        ast = parse_query_rule_ir_to_ast(payload)
        validate_query_rule_ast(ast, mode=meta["mode"], profile=effective_profile)
        return _ok(meta)
    except Exception as exc:
        err = _exception_to_error(exc)
        meta = _error_meta_from_dto(dto, fallback_profile=err["details"].get("profile_effective"))
        return _err([err], meta)


def compile_rule_preview(dto: dict) -> dict:
    try:
        payload, meta, effective_profile, strict_for_compile = _prepare_request(dto)
        ast = parse_query_rule_ir_to_ast(payload)
        validate_query_rule_ast(ast, mode=meta["mode"], profile=effective_profile)

        authoring_rule: dict[str, Any] = {
            "rule_id": payload["rule_id"],
            "version": payload["version"],
            "select_vars": list(payload["select_vars"]),
            "where": payload["where"],
        }
        if "expose" in payload:
            authoring_rule["expose"] = payload["expose"]
        if "meta" in payload:
            authoring_rule["meta"] = payload["meta"]

        compiled_payload = compile_authoring_rule_v1(
            authoring_rule,
            profile=effective_profile,
            strict=strict_for_compile,
        )
        return _ok(meta, preview={"compiled_payload": _to_jsonable(compiled_payload)})
    except Exception as exc:
        err = _exception_to_error(exc)
        meta = _error_meta_from_dto(dto, fallback_profile=err["details"].get("profile_effective"))
        return _err([err], meta)


def list_profiles() -> dict:
    return {
        "ok": True,
        "errors": [],
        "profiles": [
            {
                "name": "default",
                "description": "No additional restrictions; matches current behavior.",
                "capabilities": {},
            },
            {
                "name": "souffle_strict",
                "description": (
                    "Soufflé strict validation: requires resolved ruleref and forbids not-body OR."
                ),
                "capabilities": dict(PROFILE_SOUFFLE_STRICT.capabilities),
            },
        ],
    }


def _prepare_request(dto: dict) -> tuple[dict[str, Any], dict[str, Any], BackendProfile | None, bool]:
    if not isinstance(dto, dict):
        raise _facade_error("dto must be object", kind="shape", path="$")

    api_version = dto.get("api_version", _SUPPORTED_API_VERSION)
    if api_version != _SUPPORTED_API_VERSION:
        raise _facade_error(
            f"unsupported api_version: {api_version}",
            kind="shape",
            path="$.api_version",
            details={"api_version": api_version},
        )

    mode = dto.get("mode", "souffle")
    if not isinstance(mode, str):
        raise _facade_error("mode must be string", kind="shape", path="$.mode")
    if mode not in _SUPPORTED_MODES:
        raise _facade_error(
            f"unsupported mode in facade v1: {mode}",
            kind="shape",
            path="$.mode",
            details={"mode": mode},
        )

    strict = dto.get("strict", False)
    if not isinstance(strict, bool):
        raise _facade_error("strict must be bool", kind="shape", path="$.strict")

    effective_profile, profile_effective_name = _resolve_profile(dto.get("profile"), strict)

    rule = dto.get("rule")
    if not isinstance(rule, dict):
        raise _facade_error("rule must be object", kind="shape", path="$.rule")

    payload = dict(rule)
    if payload.get("version") is None:
        payload["version"] = "v1"
    if "where" in payload:
        payload["where"] = _json_where_to_ir(payload["where"])

    meta = {
        "profile_effective": profile_effective_name,
        "mode": mode,
    }
    return payload, meta, effective_profile, strict


def _json_where_to_ir(where_json: Any) -> Any:
    if isinstance(where_json, list):
        if where_json and isinstance(where_json[0], str) and where_json[0] in _ATOM_TAGS:
            return tuple(_json_where_to_ir(item) for item in where_json)
        return [_json_where_to_ir(item) for item in where_json]
    if isinstance(where_json, dict):
        return {key: _json_where_to_ir(value) for key, value in where_json.items()}
    return where_json


def _resolve_profile(profile_obj: Any, strict: bool) -> tuple[BackendProfile | None, str]:
    if profile_obj is not None:
        if not isinstance(profile_obj, dict):
            raise _facade_error("profile must be object or null", kind="shape", path="$.profile")
        name = profile_obj.get("name")
        if not isinstance(name, str) or not name:
            raise _facade_error("profile.name must be non-empty string", kind="shape", path="$.profile.name")
        profile = _KNOWN_PROFILES.get(name)
        if profile is None:
            raise _facade_error(
                f"unknown profile name: {name}",
                kind="profile_unknown",
                path="$.profile.name",
                details={"profile_name": name},
            )
        return profile, name
    if strict:
        return PROFILE_SOUFFLE_STRICT, PROFILE_SOUFFLE_STRICT.name
    return None, PROFILE_DEFAULT.name


def _exception_to_error(exc: Exception) -> dict:
    kind = getattr(exc, "kind", None)
    path = getattr(exc, "path", None)
    details = getattr(exc, "details", None)

    if isinstance(exc, (RuleASTError, RuleASTValidationError)) and not kind:
        kind = "rule_ast_validate"
    elif isinstance(exc, AuthoringRuleCompileError) and not kind:
        kind = "authoring_rule_compile"

    if not isinstance(kind, str) or not kind:
        kind = "runtime"
    if not isinstance(path, str) or not path:
        path = "$"
    if not isinstance(details, dict):
        details = {"message": str(exc)}
    else:
        details = dict(details)
        details.setdefault("message", str(exc))

    return {
        "kind": kind,
        "path": path,
        "details": details,
    }


def _ok(meta: dict[str, Any], **payload: Any) -> dict:
    out = {
        "ok": True,
        "errors": [],
        "meta": meta,
    }
    out.update(payload)
    return out


def _err(errors: list[dict], meta: dict[str, Any]) -> dict:
    return {
        "ok": False,
        "errors": errors,
        "meta": meta,
    }


def _error_meta_from_dto(dto: Any, *, fallback_profile: Any = None) -> dict[str, Any]:
    mode = "souffle"
    profile_effective = "unknown"
    if isinstance(dto, dict):
        if isinstance(dto.get("mode"), str):
            mode = dto["mode"]
        if isinstance(fallback_profile, str) and fallback_profile:
            profile_effective = fallback_profile
        else:
            profile = dto.get("profile")
            if isinstance(profile, dict) and isinstance(profile.get("name"), str):
                profile_effective = str(profile["name"])
            elif dto.get("strict") is True:
                profile_effective = PROFILE_SOUFFLE_STRICT.name
            else:
                profile_effective = PROFILE_DEFAULT.name
    return {"profile_effective": profile_effective, "mode": mode}


def _facade_error(
    message: str,
    *,
    kind: str,
    path: str,
    details: dict[str, Any] | None = None,
) -> _FacadeError:
    payload = {"message": message}
    if details:
        payload.update(details)
    return _FacadeError(message=message, kind=kind, path=path, details=payload)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value
