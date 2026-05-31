from __future__ import annotations

import math
import os
import re
from typing import Any

from factgraph.core.rules.backend_profile import BackendProfile, PROFILE_SOUFFLE_STRICT
from factgraph.core.rules.rule_ast import RuleASTError, parse_query_rule_ir_to_ast
from factgraph.core.rules.rule_ast_validate import (
    RuleASTValidationError,
    validate_query_rule_ast,
)
from factgraph.authoring.where_schema_lowering import (
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
    profile: BackendProfile | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    if not isinstance(authoring_rule, dict):
        raise _compile_error("authoring_rule must be object", path="$")

    rule_id = authoring_rule.get("rule_id", authoring_rule.get("name"))
    if not isinstance(rule_id, str) or not rule_id:
        raise _compile_error("rule_id (or name) must be non-empty string", path="$.rule_id")

    version = authoring_rule.get("version", "v1")
    if not isinstance(version, str) or not version:
        raise _compile_error("version must be non-empty string", path="$.version")
    description = _compile_optional_description(authoring_rule.get("description"), path="$.description")
    tags = _compile_optional_tags(authoring_rule.get("tags"), path="$.tags")

    select_vars = _compile_select_vars(authoring_rule)
    where = _compile_where(authoring_rule, schema_ir=schema_ir)
    expose = _compile_expose(authoring_rule)
    condition_weights = _compile_condition_weights(
        authoring_rule.get("condition_weights"),
        where=where,
        path="$.condition_weights",
    )

    ast_payload: dict[str, Any] = {
        "rule_id": rule_id,
        "version": version,
        "select_vars": select_vars,
        "where": where,
    }
    if expose:
        ast_payload["expose"] = True
    if _rule_ast_gate_enabled():
        effective_profile = profile if profile is not None else (PROFILE_SOUFFLE_STRICT if strict else None)
        try:
            ast = parse_query_rule_ir_to_ast(ast_payload)
            validate_query_rule_ast(ast, mode="souffle", profile=effective_profile)
        except (RuleASTError, RuleASTValidationError) as exc:
            raise _adapt_rule_ast_error(exc) from exc
    payload = dict(ast_payload)
    if description is not None:
        payload["description"] = description
    if tags is not None:
        payload["tags"] = tags
    if condition_weights is not None:
        payload["condition_weights"] = condition_weights
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


def _compile_optional_description(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _compile_error("description must be non-empty string", path=path)
    return value


def _compile_optional_tags(value: Any, *, path: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise _compile_error("tags must be list[str]", path=path)
    out: list[str] = []
    for index, tag in enumerate(value):
        if not isinstance(tag, str) or not tag:
            raise _compile_error("tags items must be non-empty string", path=f"{path}[{index}]")
        out.append(tag)
    return out


def _compile_condition_weights(
    value: Any,
    *,
    where: list[Any],
    path: str,
) -> dict[str, float] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise _compile_error("condition_weights must be object[str, number]", path=path)

    valid_keys = _collect_condition_keys(where)
    out: dict[str, float] = {}
    for key, raw_weight in value.items():
        if not isinstance(key, str) or not key:
            raise _compile_error("condition_weights keys must be non-empty string", path=path)
        item_path = f'{path}["{key}"]'
        if key not in valid_keys:
            raise _compile_error(
                "condition_weights key must match existing where atom position",
                path=item_path,
            )
        if isinstance(raw_weight, bool) or not isinstance(raw_weight, (int, float)):
            raise _compile_error("condition weight must be numeric", path=item_path)
        weight = float(raw_weight)
        if not math.isfinite(weight) or weight <= 0:
            raise _compile_error("condition weight must be positive finite number", path=item_path)
        out[key] = weight
    if not out:
        return None
    return {key: out[key] for key in sorted(out)}


def _collect_condition_keys(where: list[Any]) -> set[str]:
    branches = _where_branches(where)
    out: set[str] = set()
    for case_index, branch in enumerate(branches):
        for condition_index, _atom in enumerate(branch):
            out.add(f"c{case_index}.c{condition_index}")
    return out


def _where_branches(where: list[Any]) -> list[list[Any]]:
    if where and all(_is_where_atom(item) for item in where):
        return [list(where)]
    branches: list[list[Any]] = []
    for branch in where:
        if not isinstance(branch, list) or not branch or not all(_is_where_atom(atom) for atom in branch):
            raise _compile_error("where must be list of atoms or OR branches", path="$.where")
        branches.append(list(branch))
    return branches


def _is_where_atom(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and bool(value) and isinstance(value[0], str)


def _rule_ast_gate_enabled() -> bool:
    raw = os.environ.get("FACTPY_RULE_AST_VALIDATE", "1")
    return raw not in {"0", "false", "False", "off", "OFF"}


def _adapt_rule_ast_error(exc: Exception) -> AuthoringRuleCompileError:
    origin_path = getattr(exc, "path", None) or "$.query_rule"
    err = AuthoringRuleCompileError(str(exc), path=origin_path)
    setattr(err, "kind", "rule_ast_validate")
    setattr(
        err,
        "details",
        {
            "ast_error_code": type(exc).__name__,
            "message": str(exc),
            "origin_source": "authoring.rule_compile",
            "origin_path": getattr(exc, "path", None),
        },
    )
    return err
