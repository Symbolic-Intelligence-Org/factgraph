from __future__ import annotations

import ast
from typing import Any


class AuthoringRuleDSLParseError(Exception):
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


def parse_authoring_rule_dsl_v1(source: str) -> dict[str, Any]:
    if not isinstance(source, str):
        raise AuthoringRuleDSLParseError("source must be string", path="$", kind="input_type")
    try:
        module = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        path = "$" if exc.lineno is None else f"$.dsl:line:{exc.lineno}"
        raise AuthoringRuleDSLParseError(str(exc), path=path, kind="syntax") from exc

    body_nodes = _unwrap_vars_with_block(module.body)

    found: dict[str, Any] | None = None
    for idx, node in enumerate(body_nodes):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass)):
            continue
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            payload = _parse_rule_expr(node.value, path=f"$.dsl.body[{idx}]")
            if found is not None:
                raise _err("multiple Rule(...) declarations found", path=f"$.dsl.body[{idx}]")
            found = payload
            continue
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise _err("only simple assignment to a name is supported", path=f"$.dsl.body[{idx}]")
            payload = _parse_rule_expr(node.value, path=f"$.dsl.body[{idx}]")
            if "rule_id" not in payload and "name" not in payload:
                payload["name"] = node.targets[0].id
            if found is not None:
                raise _err("multiple Rule(...) declarations found", path=f"$.dsl.body[{idx}]")
            found = payload
            continue
        raise _err(f"unsupported top-level statement: {type(node).__name__}", path=f"$.dsl.body[{idx}]")

    if found is None:
        raise _err("no Rule(...) declaration found", path="$.dsl.body")
    return found


def _parse_rule_expr(node: ast.AST, *, path: str) -> dict[str, Any]:
    if not isinstance(node, ast.Call):
        raise _err("expected Rule(...) call", path=path)
    if not (isinstance(node.func, ast.Name) and node.func.id == "Rule"):
        raise _err("expected Rule(...) call", path=path)
    if node.args:
        raise _err("Rule(...) positional arguments are not supported", path=f"{path}.args")
    out: dict[str, Any] = {}
    for kw_idx, kw in enumerate(node.keywords):
        if kw.arg is None:
            raise _err("Rule(...) **kwargs are not supported", path=f"{path}.keywords[{kw_idx}]")
        if kw.arg in out:
            raise _err(f"duplicate keyword: {kw.arg}", path=f"{path}.{kw.arg}")
        if kw.arg in {"where", "body"}:
            out[kw.arg] = _where_literal(kw.value, path=f"{path}.{kw.arg}", record_var_types={})
        else:
            out[kw.arg] = _literal(kw.value, path=f"{path}.{kw.arg}")
    return out


def _literal(node: ast.AST, *, path: str) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (str, int, bool, float, type(None))):
            return node.value
        raise _err("unsupported literal type", path=path)
    if isinstance(node, ast.List):
        return [_literal(x, path=f"{path}[]") for x in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal(x, path=f"{path}[]") for x in node.elts)
    if isinstance(node, ast.Dict):
        out: dict[str, Any] = {}
        for key_node, value_node in zip(node.keys, node.values):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                raise _err("dict keys must be string literals", path=path)
            out[key_node.value] = _literal(value_node, path=f"{path}.{key_node.value}")
        return out
    if isinstance(node, ast.Call):
        return _dsl_call(node, path=path)
    raise _err("unsupported expression in Rule(...) DSL", path=path)


def _where_literal(node: ast.AST, *, path: str, record_var_types: dict[str, str]) -> Any:
    if isinstance(node, ast.List):
        out: list[Any] = []
        local_types = dict(record_var_types)
        for idx, elt in enumerate(node.elts):
            atom = _where_atom(elt, path=f"{path}[]", record_var_types=local_types)
            out.append(atom)
        return out
    if isinstance(node, ast.Tuple):
        return tuple(_where_literal(x, path=f"{path}[]", record_var_types=record_var_types) for x in node.elts)
    if isinstance(node, ast.Call):
        return _where_dsl_call(node, path=path, record_var_types=record_var_types)
    if isinstance(node, ast.Compare):
        return _where_compare(node, path=path, record_var_types=record_var_types)
    return _literal(node, path=path)


def _where_atom(node: ast.AST, *, path: str, record_var_types: dict[str, str]) -> Any:
    if isinstance(node, ast.Call):
        return _where_dsl_call(node, path=path, record_var_types=record_var_types)
    if isinstance(node, ast.Compare):
        return _where_compare(node, path=path, record_var_types=record_var_types)
    return _where_literal(node, path=path, record_var_types=record_var_types)


def _where_dsl_call(node: ast.Call, *, path: str, record_var_types: dict[str, str]) -> Any:
    name = _call_name(node.func)
    if name is None:
        raise _helper_err("unsupported DSL helper call", path=path, detail_code="helper_callable", helper=None)
    if node.keywords:
        raise _helper_err(
            "DSL helper calls do not support keyword arguments",
            path=f"{path}.keywords",
            detail_code="helper_kwargs_not_supported",
            helper=name,
        )

    helper_names = {"Pred", "Eq", "Gt", "Ge", "Lt", "Le", "In", "Not", "Or"}
    if name not in helper_names:
        if not (
            len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and not node.keywords
        ):
            raise _helper_err(f"unsupported DSL helper: {name}", path=path, detail_code="unsupported_helper", helper=name)
        return _where_record_exists_call(node, path=path, record_var_types=record_var_types)

    if name == "Pred":
        if len(node.args) < 2:
            raise _helper_err(
                "Pred(...) requires pred_id and at least one term",
                path=path,
                detail_code="helper_arity",
                helper=name,
            )
        pred_id = _literal(node.args[0], path=f"{path}.args[0]")
        if not isinstance(pred_id, str) or not pred_id:
            raise _helper_err(
                "Pred(...) first argument must be non-empty string",
                path=f"{path}.args[0]",
                detail_code="helper_arg_type",
                helper=name,
                arg_index=0,
            )
        terms = [_where_term(arg, path=f"{path}.args[{idx}]") for idx, arg in enumerate(node.args[1:], start=1)]
        return ("pred", pred_id, terms)

    simple_binops = {
        "Eq": "eq",
        "Gt": "gt",
        "Ge": "ge",
        "Lt": "lt",
        "Le": "le",
    }
    if name in simple_binops:
        if len(node.args) != 2:
            raise _helper_err(
                f"{name}(...) requires exactly 2 arguments",
                path=path,
                detail_code="helper_arity",
                helper=name,
            )
        left = _where_term(node.args[0], path=f"{path}.args[0]")
        right = _where_term(node.args[1], path=f"{path}.args[1]")
        return (simple_binops[name], left, right)

    if name == "In":
        if len(node.args) != 2:
            raise _helper_err("In(...) requires exactly 2 arguments", path=path, detail_code="helper_arity", helper=name)
        lhs = _where_term(node.args[0], path=f"{path}.args[0]")
        rhs = _where_literal(node.args[1], path=f"{path}.args[1]", record_var_types=record_var_types)
        if not isinstance(rhs, list):
            raise _helper_err(
                "In(...) second argument must be list",
                path=f"{path}.args[1]",
                detail_code="helper_arg_type",
                helper=name,
                arg_index=1,
            )
        return ("in", lhs, rhs)

    if name == "Not":
        if len(node.args) != 1:
            raise _helper_err("Not(...) requires exactly 1 argument", path=path, detail_code="helper_arity", helper=name)
        body = _where_literal(node.args[0], path=f"{path}.args[0]", record_var_types=dict(record_var_types))
        if not isinstance(body, list):
            raise _helper_err(
                "Not(...) body must be list",
                path=f"{path}.args[0]",
                detail_code="helper_arg_type",
                helper=name,
                arg_index=0,
            )
        return ("not", body)

    if name == "Or":
        if len(node.args) < 2:
            raise _helper_err("Or(...) requires at least 2 branch bodies", path=path, detail_code="helper_arity", helper=name)
        bodies: list[Any] = []
        for idx, arg in enumerate(node.args):
            body = _where_literal(arg, path=f"{path}.args[{idx}]", record_var_types=dict(record_var_types))
            if not isinstance(body, list):
                raise _helper_err(
                    "Or(...) branches must be list bodies",
                    path=f"{path}.args[{idx}]",
                    detail_code="helper_arg_type",
                    helper=name,
                    arg_index=idx,
                )
            bodies.append(body)
        return bodies

    raise _helper_err(f"unsupported DSL helper: {name}", path=path, detail_code="unsupported_helper", helper=name)


def _where_term(node: ast.AST, *, path: str) -> Any:
    if isinstance(node, ast.Name):
        return f"${node.id}"
    return _literal(node, path=path)


def _where_record_exists_call(node: ast.Call, *, path: str, record_var_types: dict[str, str]) -> tuple[str, str, list[Any]]:
    if not isinstance(node.func, ast.Name):
        raise _helper_err("unsupported DSL helper call", path=path, detail_code="helper_callable", helper=None)
    record_type = node.func.id
    if node.keywords:
        raise _err("record constructor where syntax does not support keyword arguments", path=f"{path}.keywords")
    if len(node.args) != 1 or not isinstance(node.args[0], ast.Name):
        raise _err("record constructor where syntax requires exactly one variable argument", path=f"{path}.args")
    rec_var = node.args[0].id
    record_var_types[rec_var] = record_type
    return ("pred", f"{record_type}:exists", [f"${rec_var}"])


def _where_compare(node: ast.Compare, *, path: str, record_var_types: dict[str, str]) -> Any:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        raise _err("where comparison syntax supports exactly one comparator", path=path)
    if not isinstance(node.ops[0], ast.Eq):
        raise _err("where path comparison syntax currently supports only ==", path=path)
    left_attr = _record_attr_ref(node.left)
    right_attr = _record_attr_ref(node.comparators[0])
    if left_attr is None and right_attr is None:
        left = _where_term(node.left, path=f"{path}.left")
        right = _where_term(node.comparators[0], path=f"{path}.right")
        return ("eq", left, right)
    if left_attr is not None and right_attr is not None:
        raise _err("comparison between two record attributes is not supported in v1 where sugar", path=path)
    attr_side = left_attr if left_attr is not None else right_attr
    assert attr_side is not None
    var_name, field_name = attr_side
    record_type = record_var_types.get(var_name)
    if record_type is None:
        raise _err("record variable used in path comparison before constructor binding", path=path)
    other_node = node.comparators[0] if left_attr is not None else node.left
    other = _where_term(other_node, path=f"{path}.right" if left_attr is not None else f"{path}.left")
    return ("pred", f"{record_type.lower()}:{field_name}", [f"${var_name}", other])


def _record_attr_ref(node: ast.AST) -> tuple[str, str] | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id, node.attr
    return None


def _unwrap_vars_with_block(body: list[ast.stmt]) -> list[ast.stmt]:
    if len(body) != 1 or not isinstance(body[0], ast.With):
        return body
    with_node = body[0]
    if len(with_node.items) != 1:
        return body
    item = with_node.items[0]
    if not (
        isinstance(item.context_expr, ast.Call)
        and isinstance(item.context_expr.func, ast.Name)
        and item.context_expr.func.id == "vars"
        and not item.context_expr.args
        and not item.context_expr.keywords
    ):
        return body
    optional = item.optional_vars
    if optional is not None and not (
        isinstance(optional, ast.Tuple)
        and all(isinstance(elt, ast.Name) for elt in optional.elts)
    ):
        raise _err("with vars() as (...) requires tuple of names", path="$.dsl.body[0].with")
    return with_node.body


def _dsl_call(node: ast.Call, *, path: str) -> Any:
    name = _call_name(node.func)
    if name is None:
        raise _helper_err("unsupported DSL helper call", path=path, detail_code="helper_callable", helper=None)
    if node.keywords:
        raise _helper_err(
            "DSL helper calls do not support keyword arguments",
            path=f"{path}.keywords",
            detail_code="helper_kwargs_not_supported",
            helper=name,
        )

    if name == "Pred":
        if len(node.args) < 2:
            raise _helper_err(
                "Pred(...) requires pred_id and at least one term",
                path=path,
                detail_code="helper_arity",
                helper=name,
            )
        pred_id = _literal(node.args[0], path=f"{path}.args[0]")
        if not isinstance(pred_id, str) or not pred_id:
            raise _helper_err(
                "Pred(...) first argument must be non-empty string",
                path=f"{path}.args[0]",
                detail_code="helper_arg_type",
                helper=name,
                arg_index=0,
            )
        terms = [_literal(arg, path=f"{path}.args[{idx}]") for idx, arg in enumerate(node.args[1:], start=1)]
        return ("pred", pred_id, terms)

    simple_binops = {
        "Eq": "eq",
        "Gt": "gt",
        "Ge": "ge",
        "Lt": "lt",
        "Le": "le",
    }
    if name in simple_binops:
        if len(node.args) != 2:
            raise _helper_err(
                f"{name}(...) requires exactly 2 arguments",
                path=path,
                detail_code="helper_arity",
                helper=name,
            )
        left = _literal(node.args[0], path=f"{path}.args[0]")
        right = _literal(node.args[1], path=f"{path}.args[1]")
        return (simple_binops[name], left, right)

    if name == "In":
        if len(node.args) != 2:
            raise _helper_err("In(...) requires exactly 2 arguments", path=path, detail_code="helper_arity", helper=name)
        lhs = _literal(node.args[0], path=f"{path}.args[0]")
        rhs = _literal(node.args[1], path=f"{path}.args[1]")
        if not isinstance(rhs, list):
            raise _helper_err(
                "In(...) second argument must be list",
                path=f"{path}.args[1]",
                detail_code="helper_arg_type",
                helper=name,
                arg_index=1,
            )
        return ("in", lhs, rhs)

    if name == "Not":
        if len(node.args) != 1:
            raise _helper_err("Not(...) requires exactly 1 argument", path=path, detail_code="helper_arity", helper=name)
        body = _literal(node.args[0], path=f"{path}.args[0]")
        if not isinstance(body, list):
            raise _helper_err(
                "Not(...) body must be list",
                path=f"{path}.args[0]",
                detail_code="helper_arg_type",
                helper=name,
                arg_index=0,
            )
        return ("not", body)

    if name == "Or":
        if len(node.args) < 2:
            raise _helper_err("Or(...) requires at least 2 branch bodies", path=path, detail_code="helper_arity", helper=name)
        bodies: list[Any] = []
        for idx, arg in enumerate(node.args):
            body = _literal(arg, path=f"{path}.args[{idx}]")
            if not isinstance(body, list):
                raise _helper_err(
                    "Or(...) branches must be list bodies",
                    path=f"{path}.args[{idx}]",
                    detail_code="helper_arg_type",
                    helper=name,
                    arg_index=idx,
                )
            bodies.append(body)
        return bodies

    raise _helper_err(f"unsupported DSL helper: {name}", path=path, detail_code="unsupported_helper", helper=name)


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    return None


def _helper_err(
    message: str,
    *,
    path: str,
    detail_code: str,
    helper: str | None,
    arg_index: int | None = None,
) -> AuthoringRuleDSLParseError:
    details: dict[str, Any] = {"dsl_error_detail_code": detail_code}
    if helper is not None:
        details["helper"] = helper
    if arg_index is not None:
        details["arg_index"] = arg_index
    return AuthoringRuleDSLParseError(message, path=path, kind="structure", details=details)


def _err(message: str, *, path: str) -> AuthoringRuleDSLParseError:
    return AuthoringRuleDSLParseError(message, path=path, kind="structure")
