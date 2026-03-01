from __future__ import annotations

import ast
from typing import Any

from factpy_kernel.core.schema.schema_ir import CANONICAL_TAGS


_BUILTIN_TAG_MAP = {
    "str": "string",
    "int": "int",
    "bool": "bool",
    "bytes": "bytes",
    "float": "float64",
}


class AuthoringSchemaDSLParseError(Exception):
    def __init__(
        self,
        message: str,
        *,
        path: str | None = None,
        kind: str = "structure",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.kind = kind
        self.details = details


def parse_authoring_schema_dsl_v1(source: str) -> dict[str, Any]:
    if not isinstance(source, str):
        raise AuthoringSchemaDSLParseError("source must be string", path="$", kind="input_type")
    try:
        module = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        path = "$"
        if exc.lineno is not None:
            path = f"$.dsl:line:{exc.lineno}"
        raise AuthoringSchemaDSLParseError(str(exc), path=path, kind="syntax") from exc

    entities: list[dict[str, Any]] = []
    for node_index, node in enumerate(module.body):
        if isinstance(node, ast.ClassDef) and _is_entity_class(node):
            entities.append(_parse_entity_class(node=node, entity_index=len(entities)))
        elif isinstance(node, (ast.Import, ast.ImportFrom, ast.Expr, ast.Assign, ast.AnnAssign, ast.Pass)):
            continue
        else:
            raise _parse_error(
                f"unsupported top-level statement: {type(node).__name__}",
                path=f"$.dsl.body[{node_index}]",
                detail_code="unsupported_top_level_statement",
                details={"statement_type": type(node).__name__},
            )

    if not entities:
        raise AuthoringSchemaDSLParseError("no Entity classes found", path="$.dsl.body", kind="structure")
    return {"entities": entities}


def _is_entity_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Entity":
            return True
    return False


def _parse_entity_class(*, node: ast.ClassDef, entity_index: int) -> dict[str, Any]:
    entity: dict[str, Any] = {
        "entity_type": node.name,
        "identity_fields": [],
        "fields": [],
    }
    meta: dict[str, Any] = {}

    for body_index, item in enumerate(node.body):
        body_path = f"$.dsl.entities[{entity_index}].body[{body_index}]"
        if isinstance(item, ast.AnnAssign):
            parsed = _parse_entity_member_annassign(item=item, path=body_path, entity_name=node.name)
            kind = parsed.pop("__kind__")
            if kind == "identity":
                entity["identity_fields"].append(parsed)
            else:
                entity["fields"].append(parsed)
            continue
        if isinstance(item, ast.ClassDef) and item.name == "Meta":
            meta = _parse_meta_class(item=item, path=f"$.dsl.entities[{entity_index}].Meta")
            continue
        if isinstance(item, (ast.Expr, ast.Pass)):
            continue
        raise _parse_error(
            f"unsupported entity class member: {type(item).__name__}",
            path=body_path,
        )

    if not entity["identity_fields"]:
        raise _parse_error(
            f"Entity '{node.name}' must declare at least one Identity field",
            path=f"$.dsl.entities[{entity_index}].identity_fields",
        )
    if meta:
        entity["meta"] = meta
    return entity


def _parse_meta_class(*, item: ast.ClassDef, path: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for idx, stmt in enumerate(item.body):
        stmt_path = f"{path}.body[{idx}]"
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            key = stmt.targets[0].id
            meta[key] = _literal_eval_supported(stmt.value, path=f"{path}.{key}")
            continue
        if isinstance(stmt, (ast.Expr, ast.Pass)):
            continue
        raise _parse_error("Meta only supports simple assignments", path=stmt_path)
    return meta


def _parse_entity_member_annassign(*, item: ast.AnnAssign, path: str, entity_name: str) -> dict[str, Any]:
    if item.simple != 1 or not isinstance(item.target, ast.Name):
        raise _parse_error("only simple annotated assignments are supported", path=path)
    if item.value is None or not isinstance(item.value, ast.Call):
        raise _parse_error("annotated assignment must call Identity(...) or Field(...)", path=path)
    field_name = item.target.id
    callee_name = _call_name(item.value.func)
    if callee_name not in {"Identity", "Field"}:
        raise _parse_error("annotated assignment must call Identity(...) or Field(...)", path=path)

    type_domain = _annotation_to_type_domain(item.annotation)
    kwargs = _parse_call_kwargs(item.value, path=f"{path}.{callee_name}")

    if callee_name == "Identity":
        return _build_identity_from_kwargs(field_name=field_name, type_domain=type_domain, kwargs=kwargs, path=path)
    return _build_field_from_kwargs(
        field_name=field_name,
        type_domain=type_domain,
        kwargs=kwargs,
        path=path,
        entity_name=entity_name,
    )


def _build_identity_from_kwargs(
    *,
    field_name: str,
    type_domain: str,
    kwargs: dict[str, Any],
    path: str,
) -> dict[str, Any]:
    allowed = {"default_factory"}
    _reject_unknown_keys(kwargs, allowed, path=f"{path}.Identity")
    out = {
        "__kind__": "identity",
        "name": field_name,
        "type_domain": type_domain,
    }
    if "default_factory" in kwargs:
        value = kwargs["default_factory"]
        if not isinstance(value, str) or not value:
            raise _parse_error("Identity.default_factory must be non-empty string", path=f"{path}.Identity.default_factory")
        out["default_factory"] = value
    return out


def _build_field_from_kwargs(
    *,
    field_name: str,
    type_domain: str,
    kwargs: dict[str, Any],
    path: str,
    entity_name: str,
) -> dict[str, Any]:
    allowed = {
        "cardinality",
        "name",
        "pred_id",
        "aliases",
        "display_name",
        "description",
        "value_name",
        "fact_key",
        "dims",
        "type_domain",
    }
    _reject_unknown_keys(kwargs, allowed, path=f"{path}.Field")

    cardinality = kwargs.get("cardinality")
    if cardinality not in {"functional", "multi", "temporal"}:
        raise _parse_error(
            "Field.cardinality must be one of functional|multi|temporal",
            path=f"{path}.Field.cardinality",
        )

    if "type_domain" in kwargs:
        override = kwargs["type_domain"]
        if not isinstance(override, str) or override not in CANONICAL_TAGS:
            raise _parse_error("Field.type_domain must be canonical tag string", path=f"{path}.Field.type_domain")
        type_domain = override

    out: dict[str, Any] = {
        "__kind__": "field",
        "py_name": field_name,
        "type_domain": type_domain,
        "cardinality": cardinality,
    }

    if "name" in kwargs:
        name_val = kwargs["name"]
        if not isinstance(name_val, str) or not name_val:
            raise _parse_error("Field.name must be non-empty string", path=f"{path}.Field.name")
        out["name"] = name_val
    if "pred_id" in kwargs:
        pred_id = kwargs["pred_id"]
        if not isinstance(pred_id, str) or not pred_id:
            raise _parse_error("Field.pred_id must be non-empty string", path=f"{path}.Field.pred_id")
        out["pred_id"] = pred_id
    for key in ("display_name", "description", "value_name"):
        if key in kwargs:
            value = kwargs[key]
            if not isinstance(value, str) or not value:
                raise _parse_error(f"Field.{key} must be non-empty string", path=f"{path}.Field.{key}")
            out[key] = value
    if "aliases" in kwargs:
        aliases = kwargs["aliases"]
        if not isinstance(aliases, list) or any(not isinstance(x, str) or not x for x in aliases):
            raise _parse_error("Field.aliases must be list[str]", path=f"{path}.Field.aliases")
        out["aliases"] = aliases
    if "fact_key" in kwargs:
        fact_key = kwargs["fact_key"]
        if not isinstance(fact_key, list) or any(not isinstance(x, str) or not x for x in fact_key):
            raise _parse_error("Field.fact_key must be list[str]", path=f"{path}.Field.fact_key")
        out["fact_key"] = fact_key
    if "dims" in kwargs:
        out["dims"] = _normalize_dims(kwargs["dims"], path=f"{path}.Field.dims")

    _default_relation_field_name(entity_name=entity_name, field_name=field_name, out=out)
    return out


def _default_relation_field_name(*, entity_name: str, field_name: str, out: dict[str, Any]) -> None:
    if out.get("pred_id") or out.get("name"):
        return
    if out["type_domain"] == "entity_ref":
        owner = entity_name[:1].lower() + entity_name[1:]
        out["pred_id"] = f"{owner}:{field_name}"


def _normalize_dims(value: Any, *, path: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise _parse_error("Field.dims must be list", path=path)
    dims: list[dict[str, str]] = []
    for idx, item in enumerate(value):
        item_path = f"{path}[{idx}]"
        if isinstance(item, dict):
            name = item.get("name")
            type_domain = item.get("type_domain")
        elif isinstance(item, tuple) and len(item) == 2:
            name, type_domain = item
        elif isinstance(item, list) and len(item) == 2:
            name, type_domain = item
        else:
            raise _parse_error("Field.dims entries must be {'name','type_domain'} or [name, type]", path=item_path)

        if not isinstance(name, str) or not name:
            raise _parse_error("Field.dims name must be non-empty string", path=f"{item_path}.name")
        if isinstance(type_domain, str) and type_domain in CANONICAL_TAGS:
            td = type_domain
        elif isinstance(type_domain, str):
            td = _python_name_to_type_domain(type_domain)
        else:
            raise _parse_error("Field.dims type must be string/canonical tag", path=f"{item_path}.type_domain")
        dims.append({"name": name, "type_domain": td})
    return dims


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    return None


def _parse_call_kwargs(call: ast.Call, *, path: str) -> dict[str, Any]:
    if call.args:
        raise _parse_error(
            "positional arguments are not supported",
            path=f"{path}.args",
            detail_code="call_positional_args_not_supported",
            details={"call_name": path.rsplit(".", 1)[-1]},
        )
    kwargs: dict[str, Any] = {}
    for idx, kw in enumerate(call.keywords):
        if kw.arg is None:
            raise _parse_error(
                "**kwargs are not supported",
                path=f"{path}.keywords[{idx}]",
                detail_code="call_kwargs_unpack_not_supported",
                details={"call_name": path.rsplit(".", 1)[-1]},
            )
        if kw.arg in kwargs:
            raise _parse_error(
                f"duplicate keyword: {kw.arg}",
                path=f"{path}.keywords[{idx}]",
                detail_code="duplicate_keyword",
                details={"call_name": path.rsplit(".", 1)[-1], "keyword": kw.arg},
            )
        kwargs[kw.arg] = _literal_eval_supported(kw.value, path=f"{path}.{kw.arg}")
    return kwargs


def _annotation_to_type_domain(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return _python_name_to_type_domain(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if node.value in CANONICAL_TAGS:
            return node.value
        return "entity_ref"
    if isinstance(node, ast.Attribute):
        dotted = _dotted_name(node)
        if dotted in {"uuid.UUID"}:
            return "uuid"
        if dotted in {"datetime.datetime"}:
            return "time"
        return "entity_ref"
    raise _parse_error("unsupported type annotation", path="$.dsl.annotation")


def _python_name_to_type_domain(name: str) -> str:
    if name in _BUILTIN_TAG_MAP:
        return _BUILTIN_TAG_MAP[name]
    if name in CANONICAL_TAGS:
        return name
    return "entity_ref"


def _dotted_name(node: ast.Attribute) -> str | None:
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _literal_eval_supported(node: ast.AST, *, path: str) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (str, int, bool, type(None), float)):
            return node.value
        raise _parse_error("unsupported literal type", path=path)
    if isinstance(node, ast.List):
        return [_literal_eval_supported(item, path=f"{path}[]") for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal_eval_supported(item, path=f"{path}[]") for item in node.elts)
    if isinstance(node, ast.Dict):
        out: dict[str, Any] = {}
        for key_node, value_node in zip(node.keys, node.values):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                raise _parse_error("dict keys must be string literals", path=path)
            out[key_node.value] = _literal_eval_supported(value_node, path=f"{path}.{key_node.value}")
        return out
    if isinstance(node, ast.Name):
        if node.id in _BUILTIN_TAG_MAP:
            return node.id
        if node.id in {"None", "True", "False"}:
            return {"None": None, "True": True, "False": False}[node.id]
    raise _parse_error("unsupported expression in DSL call arguments", path=path)


def _reject_unknown_keys(kwargs: dict[str, Any], allowed: set[str], *, path: str) -> None:
    unknown = [key for key in kwargs.keys() if key not in allowed]
    if unknown:
        unknown_sorted = sorted(unknown)
        raise _parse_error(
            f"unsupported keyword(s): {', '.join(unknown_sorted)}",
            path=path,
            detail_code="unsupported_keywords",
            details={
                "call_name": path.rsplit(".", 1)[-1],
                "unsupported_keywords": ",".join(unknown_sorted),
                "unsupported_keyword_count": len(unknown_sorted),
            },
        )


def _parse_error(
    message: str,
    *,
    path: str,
    detail_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuthoringSchemaDSLParseError:
    normalized_details: dict[str, Any] | None = None
    if detail_code is not None:
        normalized_details = {"dsl_error_detail_code": detail_code}
        if isinstance(details, dict):
            normalized_details.update(details)
    return AuthoringSchemaDSLParseError(message, path=path, kind="structure", details=normalized_details)
