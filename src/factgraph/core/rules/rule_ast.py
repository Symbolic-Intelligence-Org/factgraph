from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factgraph.core.rules.where_ast import (
    Const,
    Origin,
    Term,
    Var,
    WhereASTError,
    WhereExpr,
    lower_ast_to_where_ir,
    parse_where_ir_to_ast,
)


class RuleASTError(Exception):
    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


@dataclass(frozen=True)
class HeadAtom:
    pred_id: str
    terms: list[Term]
    origin: Origin | None = None


@dataclass(frozen=True)
class RuleRef:
    rule_id: str
    version: str | None
    origin: Origin | None = None


@dataclass(frozen=True)
class RuleAst:
    rule_id: str
    version: str
    head: HeadAtom
    where: WhereExpr
    origin: Origin | None = None
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProgramAst:
    rules: list[RuleAst]
    origin: Origin | None = None
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class QueryRuleAst:
    rule_id: str
    version: str
    select_vars: list[str]
    where: WhereExpr
    expose: bool | None = None
    origin: Origin | None = None
    meta: dict[str, Any] | None = None


def parse_rule_ir_to_ast(rule_ir: Any) -> RuleAst:
    if not isinstance(rule_ir, dict):
        raise RuleASTError("rule_ir must be dict", path="$.rule")
    extra_keys = sorted(set(rule_ir.keys()) - {"rule_id", "version", "head", "where", "meta"})
    if extra_keys:
        raise RuleASTError(
            "unsupported rule_ir fields: " + ", ".join(extra_keys),
            path="$.rule",
        )
    if "rule_id" not in rule_ir:
        raise RuleASTError("rule_ir.rule_id is required", path="$.rule.rule_id")
    if "version" not in rule_ir:
        raise RuleASTError("rule_ir.version is required", path="$.rule.version")
    if "head" not in rule_ir:
        raise RuleASTError("rule_ir.head is required", path="$.rule.head")
    if "where" not in rule_ir:
        raise RuleASTError("rule_ir.where is required", path="$.rule.where")

    head = _parse_head_atom(rule_ir["head"], path="$.rule.head")
    try:
        where = parse_where_ir_to_ast(rule_ir["where"])
    except WhereASTError as exc:
        raise RuleASTError(str(exc), path=_remap_where_path(exc.path)) from exc

    meta = rule_ir.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise RuleASTError("rule_ir.meta must be dict or None", path="$.rule.meta")

    return RuleAst(
        rule_id=rule_ir["rule_id"],
        version=rule_ir["version"],
        head=head,
        where=where,
        origin=Origin(source="raw_ir", path="$.rule"),
        meta=meta,
    )


def lower_rule_ast_to_ir(rule_ast: RuleAst) -> dict[str, Any]:
    if not isinstance(rule_ast, RuleAst):
        raise RuleASTError("rule_ast must be RuleAst")
    out: dict[str, Any] = {
        "rule_id": rule_ast.rule_id,
        "version": rule_ast.version,
        "head": _lower_head_atom(rule_ast.head),
        "where": lower_ast_to_where_ir(rule_ast.where),
    }
    if rule_ast.meta is not None:
        out["meta"] = rule_ast.meta
    return out


def parse_query_rule_ir_to_ast(rule_ir: Any) -> QueryRuleAst:
    if not isinstance(rule_ir, dict):
        raise RuleASTError("query rule_ir must be dict", path="$.query_rule")
    extra_keys = sorted(set(rule_ir.keys()) - {"rule_id", "version", "select_vars", "where", "expose", "meta"})
    if extra_keys:
        raise RuleASTError(
            "unsupported query rule_ir fields: " + ", ".join(extra_keys),
            path="$.query_rule",
        )
    if "rule_id" not in rule_ir:
        raise RuleASTError("query rule_ir.rule_id is required", path="$.query_rule.rule_id")
    if "version" not in rule_ir:
        raise RuleASTError("query rule_ir.version is required", path="$.query_rule.version")
    if "select_vars" not in rule_ir:
        raise RuleASTError("query rule_ir.select_vars is required", path="$.query_rule.select_vars")
    if "where" not in rule_ir:
        raise RuleASTError("query rule_ir.where is required", path="$.query_rule.where")

    select_vars = rule_ir["select_vars"]
    if not isinstance(select_vars, list):
        raise RuleASTError("query rule_ir.select_vars must be list", path="$.query_rule.select_vars")
    for idx, value in enumerate(select_vars):
        if not isinstance(value, str):
            raise RuleASTError(
                "query rule_ir.select_vars items must be string",
                path=f"$.query_rule.select_vars[{idx}]",
            )

    expose = rule_ir.get("expose")
    if expose is not None and not isinstance(expose, bool):
        raise RuleASTError("query rule_ir.expose must be bool or None", path="$.query_rule.expose")

    try:
        where = parse_where_ir_to_ast(rule_ir["where"])
    except WhereASTError as exc:
        raise RuleASTError(str(exc), path=_remap_where_path(exc.path, root="$.query_rule.where")) from exc

    meta = rule_ir.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise RuleASTError("query rule_ir.meta must be dict or None", path="$.query_rule.meta")

    return QueryRuleAst(
        rule_id=rule_ir["rule_id"],
        version=rule_ir["version"],
        select_vars=list(select_vars),
        where=where,
        expose=expose,
        origin=Origin(source="raw_ir", path="$.query_rule"),
        meta=meta,
    )


def lower_query_rule_ast_to_ir(rule_ast: QueryRuleAst) -> dict[str, Any]:
    if not isinstance(rule_ast, QueryRuleAst):
        raise RuleASTError("query rule_ast must be QueryRuleAst")
    out: dict[str, Any] = {
        "rule_id": rule_ast.rule_id,
        "version": rule_ast.version,
        "select_vars": list(rule_ast.select_vars),
        "where": lower_ast_to_where_ir(rule_ast.where),
    }
    if rule_ast.expose is not None:
        out["expose"] = rule_ast.expose
    if rule_ast.meta is not None:
        out["meta"] = rule_ast.meta
    return out


def parse_program_ir_to_ast(program_ir: Any) -> ProgramAst:
    if not isinstance(program_ir, dict):
        raise RuleASTError("program_ir must be dict", path="$.program")
    extra_keys = sorted(set(program_ir.keys()) - {"rules", "meta"})
    if extra_keys:
        raise RuleASTError(
            "unsupported program_ir fields: " + ", ".join(extra_keys),
            path="$.program",
        )
    if "rules" not in program_ir:
        raise RuleASTError("program_ir.rules is required", path="$.program.rules")

    rules_raw = program_ir["rules"]
    if not isinstance(rules_raw, list):
        raise RuleASTError("program_ir.rules must be list", path="$.program.rules")

    rules: list[RuleAst] = []
    for idx, rule_ir in enumerate(rules_raw):
        try:
            rules.append(parse_rule_ir_to_ast(rule_ir))
        except RuleASTError as exc:
            path = exc.path
            if path and path.startswith("$.rule"):
                path = path.replace("$.rule", f"$.program.rules[{idx}]", 1)
            raise RuleASTError(str(exc), path=path or f"$.program.rules[{idx}]") from exc

    meta = program_ir.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise RuleASTError("program_ir.meta must be dict or None", path="$.program.meta")

    return ProgramAst(
        rules=rules,
        origin=Origin(source="raw_ir", path="$.program"),
        meta=meta,
    )


def lower_program_ast_to_ir(program_ast: ProgramAst) -> dict[str, Any]:
    if not isinstance(program_ast, ProgramAst):
        raise RuleASTError("program_ast must be ProgramAst")
    out: dict[str, Any] = {
        "rules": [lower_rule_ast_to_ir(rule) for rule in program_ast.rules],
    }
    if program_ast.meta is not None:
        out["meta"] = program_ast.meta
    return out


def _parse_head_atom(raw: Any, *, path: str) -> HeadAtom:
    if not (isinstance(raw, tuple) and raw and isinstance(raw[0], str)):
        raise RuleASTError("head must be tuple(tag, ...)", path=path)
    if raw[0] != "pred":
        raise RuleASTError("head must be ('pred', pred_id, [terms...])", path=path)
    if len(raw) != 3:
        raise RuleASTError("head must be ('pred', pred_id, [terms...])", path=path)
    _, pred_id, terms = raw
    if not isinstance(terms, list):
        raise RuleASTError("head terms must be list", path=f"{path}[2]")
    return HeadAtom(
        pred_id=pred_id,
        terms=[_parse_term(term, path=f"{path}[2][{idx}]") for idx, term in enumerate(terms)],
        origin=Origin(source="raw_ir", path=path),
    )


def _lower_head_atom(head: HeadAtom) -> tuple[Any, ...]:
    if not isinstance(head, HeadAtom):
        raise RuleASTError("head must be HeadAtom")
    return ("pred", head.pred_id, [_lower_term(term) for term in head.terms])


def _parse_term(raw: Any, *, path: str) -> Term:
    if isinstance(raw, str) and raw.startswith("$") and len(raw) > 1:
        return Var(name=raw, origin=Origin(source="raw_ir", path=path))
    return Const(value=raw, origin=Origin(source="raw_ir", path=path))


def _lower_term(term: Term) -> Any:
    if isinstance(term, Var):
        return term.name
    if isinstance(term, Const):
        return term.value
    raise RuleASTError(f"unsupported term node: {type(term).__name__}")


def _remap_where_path(path: str | None, *, root: str = "$.rule.where") -> str:
    if not path:
        return root
    if path.startswith("$.where"):
        return path.replace("$.where", root, 1)
    return path
