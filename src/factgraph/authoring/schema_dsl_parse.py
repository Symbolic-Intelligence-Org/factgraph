from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from factgraph.core.schema.schema_ir import CANONICAL_TAGS
from factgraph.core.schema.schema_repr import (
    SchemaReprTemplateError,
    validate_member_repr_template,
    validate_meta_repr_template,
)


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


@dataclass(frozen=True)
class _AnnotationPlan:
    type_domain: str
    cardinality: str = "single"
    enum_values: tuple[Any, ...] | None = None


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
        _apply_entity_meta_fields(entity=entity, meta=meta, path=f"$.dsl.entities[{entity_index}].Meta")
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


def _apply_entity_meta_fields(*, entity: dict[str, Any], meta: dict[str, Any], path: str) -> None:
    allowed = {"version", "tags", "repr"}
    _reject_unknown_keys(meta, allowed, path=path)

    if "version" in meta:
        version = meta["version"]
        if not isinstance(version, str) or not version:
            raise _parse_error("Meta.version must be non-empty string", path=f"{path}.version")
        entity["version"] = version

    if "tags" in meta:
        tags = meta["tags"]
        if not isinstance(tags, list):
            raise _parse_error("Meta.tags must be list[str]", path=f"{path}.tags")
        normalized_tags: list[str] = []
        for index, tag in enumerate(tags):
            if not isinstance(tag, str) or not tag:
                raise _parse_error("Meta.tags items must be non-empty string", path=f"{path}.tags[{index}]")
            normalized_tags.append(tag)
        entity["tags"] = normalized_tags

    if "repr" in meta:
        identity_field_names = tuple(
            field.get("name")
            for field in entity.get("identity_fields", ())
            if isinstance(field, dict) and isinstance(field.get("name"), str)
        )
        try:
            validate_meta_repr_template(meta["repr"], identity_field_names=identity_field_names)
        except SchemaReprTemplateError as exc:
            raise _parse_error(str(exc), path=f"{path}.repr") from exc
        entity["repr"] = meta["repr"]


def _parse_entity_member_annassign(*, item: ast.AnnAssign, path: str, entity_name: str) -> dict[str, Any]:
    if item.simple != 1 or not isinstance(item.target, ast.Name):
        raise _parse_error("only simple annotated assignments are supported", path=path)
    if item.value is None or not isinstance(item.value, ast.Call):
        raise _parse_error("annotated assignment must call Identity(...) or Field(...)", path=path)
    field_name = item.target.id
    callee_name = _call_name(item.value.func)
    if callee_name not in {"Identity", "Field"}:
        raise _parse_error("annotated assignment must call Identity(...) or Field(...)", path=path)

    annotation_plan = _annotation_to_plan(item.annotation)
    kwargs = _parse_call_kwargs(item.value, path=f"{path}.{callee_name}")

    if callee_name == "Identity":
        return _build_identity_from_kwargs(field_name=field_name, annotation_plan=annotation_plan, kwargs=kwargs, path=path)
    return _build_field_from_kwargs(
        field_name=field_name,
        annotation_plan=annotation_plan,
        kwargs=kwargs,
        path=path,
        entity_name=entity_name,
    )


def _build_identity_from_kwargs(
    *,
    field_name: str,
    annotation_plan: _AnnotationPlan,
    kwargs: dict[str, Any],
    path: str,
) -> dict[str, Any]:
    if annotation_plan.cardinality != "single":
        raise _parse_error("Identity fields must use a single-value annotation", path=f"{path}.annotation")
    allowed = {"pattern", "repr"}
    _reject_unknown_keys(
        kwargs,
        allowed,
        path=f"{path}.Identity",
        message=(
            "Identity() only accepts pattern= and repr= in Form I; "
            "remove primary_key/default/default_factory and provide all identity values explicitly"
        ),
    )
    out = {
        "__kind__": "identity",
        "name": field_name,
        "type_domain": annotation_plan.type_domain,
    }
    _apply_common_member_kwargs(out=out, kwargs=kwargs, annotation_plan=annotation_plan, path=f"{path}.Identity")
    _validate_authoring_member_repr(kwargs, field_name=field_name, path=f"{path}.Identity")
    return out


def _build_field_from_kwargs(
    *,
    field_name: str,
    annotation_plan: _AnnotationPlan,
    kwargs: dict[str, Any],
    path: str,
    entity_name: str,
) -> dict[str, Any]:
    del entity_name
    allowed = {"pattern", "repr"}
    _reject_unknown_keys(
        kwargs,
        allowed,
        path=f"{path}.Field",
        message=(
            "Field() only accepts pattern= and repr= in Form I; "
            "replace cardinality= with scalar or collection type annotations"
        ),
    )

    out: dict[str, Any] = {
        "__kind__": "field",
        "py_name": field_name,
        "type_domain": annotation_plan.type_domain,
        "cardinality": annotation_plan.cardinality,
    }
    if annotation_plan.enum_values is not None:
        out["enum_values"] = list(annotation_plan.enum_values)

    _apply_common_member_kwargs(out=out, kwargs=kwargs, annotation_plan=annotation_plan, path=f"{path}.Field")
    _validate_authoring_member_repr(kwargs, field_name=field_name, path=f"{path}.Field")
    return out


def _apply_common_member_kwargs(
    *,
    out: dict[str, Any],
    kwargs: dict[str, Any],
    annotation_plan: _AnnotationPlan,
    path: str,
) -> None:
    if "pattern" in kwargs:
        value = kwargs["pattern"]
        if annotation_plan.type_domain != "string":
            raise _parse_error("pattern is only supported for string-typed Identity/Field members", path=f"{path}.pattern")
        if not isinstance(value, str) or not value:
            raise _parse_error("pattern must be non-empty string", path=f"{path}.pattern")
        try:
            import re

            re.compile(value)
        except re.error as exc:
            raise _parse_error(f"pattern must be valid regex: {exc}", path=f"{path}.pattern")
        out["pattern"] = value
    if "repr" in kwargs:
        out["repr"] = kwargs["repr"]


def _validate_authoring_member_repr(kwargs: dict[str, Any], *, field_name: str, path: str) -> None:
    if "repr" not in kwargs:
        return
    try:
        validate_member_repr_template(kwargs["repr"], field_name=field_name)
    except SchemaReprTemplateError as exc:
        raise _parse_error(str(exc), path=f"{path}.repr") from exc
    kwargs_repr = kwargs["repr"]
    if not isinstance(kwargs_repr, str) or not kwargs_repr:
        raise _parse_error("repr must be non-empty string", path=f"{path}.repr")


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


def _annotation_to_plan(node: ast.expr) -> _AnnotationPlan:
    if isinstance(node, ast.Name):
        return _AnnotationPlan(_python_name_to_type_domain(node.id))
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if node.value in CANONICAL_TAGS:
            return _AnnotationPlan(node.value)
        return _AnnotationPlan("entity_ref")
    if isinstance(node, ast.Attribute):
        dotted = _dotted_name(node)
        if dotted in {"uuid.UUID"}:
            return _AnnotationPlan("uuid")
        if dotted in {"datetime.datetime"}:
            return _AnnotationPlan("time")
        return _AnnotationPlan("entity_ref")
    if isinstance(node, ast.Subscript):
        name = _annotation_head_name(node.value)
        args = _annotation_subscript_args(node.slice)
        if name in {"list", "List", "set", "Set", "frozenset", "FrozenSet"}:
            if len(args) != 1:
                raise _parse_error(f"{name}[...] must specify exactly one element type", path="$.dsl.annotation")
            inner = _annotation_to_plan(args[0])
            if inner.cardinality != "single":
                raise _parse_error("multi-cardinality fields must use a scalar element annotation", path="$.dsl.annotation")
            return _AnnotationPlan(type_domain=inner.type_domain, cardinality="multi", enum_values=inner.enum_values)
        if name in {"tuple", "Tuple"}:
            if len(args) == 2 and isinstance(args[1], ast.Constant) and args[1].value is Ellipsis:
                inner = _annotation_to_plan(args[0])
                if inner.cardinality != "single":
                    raise _parse_error("multi-cardinality fields must use a scalar element annotation", path="$.dsl.annotation")
                return _AnnotationPlan(type_domain=inner.type_domain, cardinality="multi", enum_values=inner.enum_values)
            raise _parse_error("tuple fields must use tuple[T, ...] for multi-cardinality Form I fields", path="$.dsl.annotation")
        if name in {"Literal", "typing.Literal"}:
            return _literal_annotation_plan(tuple(_literal_value(arg) for arg in args))
        if name in {"dict", "Dict", "typing.Dict"}:
            raise _parse_error("dict annotations are not supported in Form I schema declarations", path="$.dsl.annotation")
        if name in {"Optional", "typing.Optional", "Union", "typing.Union"}:
            raise _parse_error("Optional/Union annotations are not supported in Form I schema declarations", path="$.dsl.annotation")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        raise _parse_error("Optional/Union annotations are not supported in Form I schema declarations", path="$.dsl.annotation")
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


def _annotation_head_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _dotted_name(node)
    return None


def _annotation_subscript_args(node: ast.expr) -> tuple[ast.expr, ...]:
    if isinstance(node, ast.Tuple):
        return tuple(node.elts)
    return (node,)


def _literal_annotation_plan(values: tuple[Any, ...]) -> _AnnotationPlan:
    if not values:
        raise _parse_error("Literal[...] enum fields must declare at least one value", path="$.dsl.annotation")
    domains = {_literal_value_type_domain(value) for value in values}
    if len(domains) != 1:
        raise _parse_error("Literal[...] enum values must all use the same canonical type", path="$.dsl.annotation")
    type_domain = next(iter(domains))
    if type_domain == "float64":
        raise _parse_error("Literal[...] float enum values are not supported", path="$.dsl.annotation")
    return _AnnotationPlan(type_domain=type_domain, enum_values=tuple(values))


def _literal_value(node: ast.expr) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError) as exc:
        raise _parse_error("Literal[...] values must be literal constants", path="$.dsl.annotation") from exc


def _literal_value_type_domain(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float64"
    if isinstance(value, bytes):
        return "bytes"
    raise _parse_error(
        f"Literal[...] enum value has unsupported type: {type(value).__name__}",
        path="$.dsl.annotation",
    )


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


def _reject_unknown_keys(
    kwargs: dict[str, Any],
    allowed: set[str],
    *,
    path: str,
    message: str | None = None,
) -> None:
    unknown = [key for key in kwargs.keys() if key not in allowed]
    if unknown:
        unknown_sorted = sorted(unknown)
        raise _parse_error(
            message or f"unsupported keyword(s): {', '.join(unknown_sorted)}",
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
