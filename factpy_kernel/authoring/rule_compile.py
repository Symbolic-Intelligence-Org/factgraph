from __future__ import annotations

import re
from typing import Any

from factpy_kernel.authoring.where_schema_lowering import (
    WhereSchemaLoweringError,
    lower_blueprint_where_sugar_with_schema_v1,
)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AuthoringRuleCompileError(Exception):
    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


def compile_authoring_rule_v1(
    authoring_rule: dict[str, Any],
    *,
    schema_ir: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(authoring_rule, dict):
        raise _compile_error("authoring_rule must be object", path="$")

    rule_id = authoring_rule.get("rule_id", authoring_rule.get("name"))
    if not isinstance(rule_id, str) or not rule_id:
        raise _compile_error("rule_id (or name) must be non-empty string", path="$.rule_id")

    version = authoring_rule.get("version", "v1")
    if not isinstance(version, str) or not version:
        raise _compile_error("version must be non-empty string", path="$.version")

    select_vars = _compile_select_vars(authoring_rule)
    where = _compile_where(authoring_rule, schema_ir=schema_ir)
    expose = _compile_expose(authoring_rule)

    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "version": version,
        "select_vars": select_vars,
        "where": where,
    }
    if expose:
        payload["expose"] = True
    return payload


def _compile_select_vars(authoring_rule: dict[str, Any]) -> list[str]:
    has_select_vars = "select_vars" in authoring_rule
    has_select = "select" in authoring_rule
    if not has_select_vars and not has_select:
        raise _compile_error("select_vars (or select) is required", path="$.select_vars")
    if has_select_vars and has_select and authoring_rule["select_vars"] != authoring_rule["select"]:
        raise _compile_error("select_vars and select conflict", path="$.select")

    raw = authoring_rule["select_vars"] if has_select_vars else authoring_rule["select"]
    path = "$.select_vars" if has_select_vars else "$.select"
    if not isinstance(raw, list) or not raw:
        raise _compile_error("select_vars must be non-empty list", path=path)

    out: list[str] = []
    for idx, item in enumerate(raw):
        item_path = f"{path}[{idx}]"
        if not isinstance(item, str) or not item:
            raise _compile_error("select var must be non-empty string", path=item_path)
        if item.startswith("$"):
            normalized = item
        else:
            if not _IDENT_RE.fullmatch(item):
                raise _compile_error("select alias must be identifier when '$' is omitted", path=item_path)
            normalized = f"${item}"
        if not _IDENT_RE.fullmatch(normalized[1:]):
            raise _compile_error("select var must be '$' + identifier", path=item_path)
        out.append(normalized)
    return out


def _compile_where(authoring_rule: dict[str, Any], *, schema_ir: dict[str, Any] | None = None) -> list[Any]:
    has_where = "where" in authoring_rule
    has_body = "body" in authoring_rule
    if not has_where and not has_body:
        raise _compile_error("where (or body) is required", path="$.where")
    if has_where and has_body and authoring_rule["where"] != authoring_rule["body"]:
        raise _compile_error("where and body conflict", path="$.body")
    raw = authoring_rule["where"] if has_where else authoring_rule["body"]
    path = "$.where" if has_where else "$.body"
    if not isinstance(raw, list) or not raw:
        raise _compile_error("where must be non-empty list", path=path)
    try:
        return lower_blueprint_where_sugar_with_schema_v1(raw, schema_ir=schema_ir, path=path)
    except WhereSchemaLoweringError as exc:
        raise _compile_error(str(exc), path=getattr(exc, "path", path) or path)


def _compile_expose(authoring_rule: dict[str, Any]) -> bool:
    has_expose = "expose" in authoring_rule
    has_public = "public" in authoring_rule
    if has_expose and has_public and bool(authoring_rule["expose"]) != bool(authoring_rule["public"]):
        raise _compile_error("expose and public conflict", path="$.public")
    raw = authoring_rule.get("expose", authoring_rule.get("public", False))
    if isinstance(raw, bool):
        return raw
    raise _compile_error("expose/public must be bool", path="$.expose" if has_expose else "$.public")


def _compile_error(message: str, *, path: str) -> AuthoringRuleCompileError:
    return AuthoringRuleCompileError(message, path=path)
