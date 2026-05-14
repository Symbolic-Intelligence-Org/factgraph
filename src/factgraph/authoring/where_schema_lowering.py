from __future__ import annotations

from typing import Any


class WhereSchemaLoweringError(Exception):
    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


def lower_blueprint_where_sugar_with_schema_v1(
    where: list[Any],
    *,
    schema_ir: dict[str, Any] | None,
    path: str = "$.where",
) -> list[Any]:
    if schema_ir is None:
        if _contains_attr_eq(where):
            raise WhereSchemaLoweringError(
                "attribute-to-attribute comparison requires schema-aware compile context",
                path=path,
            )
        return where
    meta = _build_record_meta(schema_ir)
    if not meta["entity_types"] and not meta["predicate_ids"]:
        return where
    return _rewrite_where(where, meta=meta, path=path)


def _build_record_meta(schema_ir: dict[str, Any]) -> dict[str, Any]:
    entities = schema_ir.get("entities", [])
    predicates = schema_ir.get("predicates", [])
    entity_types: set[str] = set()
    record_types: set[str] = set()
    primary_keys_by_type: dict[str, list[str]] = {}
    if isinstance(entities, list):
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            entity_type = entity.get("entity_type")
            if not isinstance(entity_type, str) or not entity_type:
                continue
            entity_types.add(entity_type)
            record_types.add(entity_type)
            primary_keys: list[str] = []
            identity_fields = entity.get("identity_fields")
            if isinstance(identity_fields, list):
                for field in identity_fields:
                    if not isinstance(field, dict):
                        continue
                    if field.get("primary_key") is not True:
                        continue
                    name = field.get("name")
                    if isinstance(name, str) and name:
                        primary_keys.append(name)
            primary_keys_by_type[entity_type] = sorted(set(primary_keys))

    exists_pred_by_type: dict[str, str] = {}
    role_pred_by_type_field: dict[str, dict[str, str]] = {}
    type_by_exists_pred: dict[str, str] = {}
    type_by_role_pred: dict[str, tuple[str, str]] = {}

    if isinstance(predicates, list):
        for pred in predicates:
            if not isinstance(pred, dict):
                continue
            pred_id = pred.get("pred_id")
            owner_type = pred.get("owner_type")
            if not isinstance(pred_id, str) or not pred_id:
                continue
            if not isinstance(owner_type, str) or not owner_type:
                continue
            if pred.get("is_entity_exists") is True:
                record_types.add(owner_type)
                exists_pred_by_type[owner_type] = pred_id
                type_by_exists_pred[pred_id] = owner_type
                continue
            if owner_type not in record_types:
                continue
            py_field_name = pred.get("py_field_name")
            if not isinstance(py_field_name, str) or not py_field_name:
                continue
            role_pred_by_type_field.setdefault(owner_type, {})[py_field_name] = pred_id
            type_by_role_pred[pred_id] = (owner_type, py_field_name)

    return {
        "entity_types": entity_types,
        "record_types": record_types,
        "primary_keys_by_type": primary_keys_by_type,
        "exists_pred_by_type": exists_pred_by_type,
        "role_pred_by_type_field": role_pred_by_type_field,
        "type_by_exists_pred": type_by_exists_pred,
        "type_by_role_pred": type_by_role_pred,
        "predicate_ids": {
            *type_by_exists_pred.keys(),
            *type_by_role_pred.keys(),
            *(
                pred.get("pred_id")
                for pred in predicates
                if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str)
            ),
        },
    }


def _rewrite_where(where: list[Any], *, meta: dict[str, Any], path: str) -> list[Any]:
    if _looks_like_or_of_bodies(where):
        out: list[Any] = []
        for idx, body in enumerate(where):
            out.append(_rewrite_body(body, meta=meta, path=f"{path}[{idx}]"))
        return out
    return _rewrite_body(where, meta=meta, path=path)


def _rewrite_body(body: list[Any], *, meta: dict[str, Any], path: str) -> list[Any]:
    if not isinstance(body, list):
        return body
    out: list[Any] = []
    record_var_types: dict[str, str] = {}
    rewrite_ctx: dict[str, Any] = {
        "used_vars": _collect_body_vars(body),
        "pk_tmp_seq": 0,
    }
    for idx, atom in enumerate(body):
        rewritten = _rewrite_atom(
            atom,
            meta=meta,
            record_var_types=record_var_types,
            rewrite_ctx=rewrite_ctx,
            path=f"{path}[{idx}]",
        )
        if isinstance(rewritten, list):
            out.extend(rewritten)
        else:
            out.append(rewritten)
    return out


def _rewrite_atom(
    atom: Any,
    *,
    meta: dict[str, Any],
    record_var_types: dict[str, str],
    rewrite_ctx: dict[str, Any],
    path: str,
) -> Any | list[Any]:
    if isinstance(atom, tuple) and len(atom) >= 1 and atom[0] == "not":
        if len(atom) != 2 or not isinstance(atom[1], list):
            return atom
        nested = _rewrite_body(atom[1], meta=meta, path=f"{path}[1]")
        return ("not", nested)

    if isinstance(atom, tuple) and len(atom) == 3 and atom[0] == "attr_eq":
        return _rewrite_attr_eq_atom(
            atom,
            meta=meta,
            record_var_types=record_var_types,
            rewrite_ctx=rewrite_ctx,
            path=path,
        )

    if not (isinstance(atom, tuple) and len(atom) == 3 and atom[0] == "pred"):
        return atom
    pred_id, terms = atom[1], atom[2]
    if not isinstance(pred_id, str) or not isinstance(terms, list):
        return atom

    canonical_pred_ids: set[str] = meta["predicate_ids"]
    type_by_exists_pred: dict[str, str] = meta["type_by_exists_pred"]
    type_by_role_pred: dict[str, tuple[str, str]] = meta["type_by_role_pred"]
    exists_pred_by_type: dict[str, str] = meta["exists_pred_by_type"]
    role_pred_by_type_field: dict[str, dict[str, str]] = meta["role_pred_by_type_field"]

    # Already canonical predicates may still carry useful entity-var bindings.
    if pred_id in type_by_exists_pred and terms and _is_var(terms[0]):
        record_var_types[_var_name(terms[0])] = type_by_exists_pred[pred_id]
        return atom
    if pred_id in type_by_role_pred and terms and _is_var(terms[0]):
        owner_type, _ = type_by_role_pred[pred_id]
        record_var_types.setdefault(_var_name(terms[0]), owner_type)
        return atom

    # Blueprint sugar constructor form from parser: ("pred", "LivesIn:exists", ["$li"])
    if pred_id.endswith(":exists") and terms and _is_var(terms[0]):
        record_type = pred_id[:-len(":exists")]
        canonical_exists = exists_pred_by_type.get(record_type)
        if canonical_exists is not None:
            record_var_types[_var_name(terms[0])] = record_type
            return ("pred", canonical_exists, terms)
        if pred_id in canonical_pred_ids:
            return atom
        if pred_id not in canonical_pred_ids and record_type in meta["record_types"]:
            raise WhereSchemaLoweringError(
                f"entity exists predicate not found in schema for {record_type}",
                path=path,
            )
        return atom

    # Blueprint sugar path form from parser: ("pred", "livesin:person", ["$li", "$p"])
    if ":" in pred_id and terms and _is_var(terms[0]):
        rec_var = _var_name(terms[0])
        record_type = record_var_types.get(rec_var)
        if record_type is not None:
            _, field_name = pred_id.split(":", 1)
            canonical_role = role_pred_by_type_field.get(record_type, {}).get(field_name)
            if canonical_role is not None:
                return ("pred", canonical_role, terms)
            if pred_id not in canonical_pred_ids:
                raise WhereSchemaLoweringError(
                    f"entity field predicate not found in schema for {record_type}.{field_name}",
                    path=path,
                )
    return atom


def _rewrite_attr_eq_atom(
    atom: tuple[Any, Any, Any],
    *,
    meta: dict[str, Any],
    record_var_types: dict[str, str],
    rewrite_ctx: dict[str, Any],
    path: str,
) -> list[Any]:
    left_var_token, left_field, left_var_name = _parse_attr_eq_side(atom[1], path=f"{path}[1]")
    right_var_token, right_field, right_var_name = _parse_attr_eq_side(atom[2], path=f"{path}[2]")

    left_type = record_var_types.get(left_var_name)
    right_type = record_var_types.get(right_var_name)
    if left_type is None:
        raise WhereSchemaLoweringError(
            "entity variable used in attribute comparison before constructor binding",
            path=path,
        )
    if right_type is None:
        raise WhereSchemaLoweringError(
            "entity variable used in attribute comparison before constructor binding",
            path=path,
        )
    if left_type != right_type:
        raise WhereSchemaLoweringError(
            f"cross-coordinate comparison requires same entity type on both sides: {left_type} != {right_type}",
            path=path,
        )

    entity_type = left_type
    primary_keys_by_type: dict[str, list[str]] = meta["primary_keys_by_type"]
    primary_fields = primary_keys_by_type.get(entity_type, [])
    if not primary_fields:
        raise WhereSchemaLoweringError(
            f"{entity_type} does not declare any primary_key identity field; cross-coordinate comparison is undefined",
            path=path,
        )

    primary_set = set(primary_fields)

    def _raise_non_primary(field_name: str) -> None:
        if len(primary_fields) == 1:
            expected_msg = f"Cross-coordinate comparison requires primary_key field '{primary_fields[0]}'."
        else:
            expected_msg = "Cross-coordinate comparison requires one of primary_key fields: " + ", ".join(
                f"'{name}'" for name in primary_fields
            )
        raise WhereSchemaLoweringError(
            f"'{field_name}' is not a primary_key field of {entity_type}. {expected_msg}",
            path=path,
        )
    if left_field not in primary_set:
        _raise_non_primary(left_field)
    if right_field not in primary_set:
        _raise_non_primary(right_field)
    if left_field != right_field:
        raise WhereSchemaLoweringError(
            f"cross-coordinate comparison must use the same primary_key field on both sides: {left_field} != {right_field}",
            path=path,
        )

    role_pred_by_type_field: dict[str, dict[str, str]] = meta["role_pred_by_type_field"]
    canonical_pred = role_pred_by_type_field.get(entity_type, {}).get(left_field)
    if canonical_pred is None:
        raise WhereSchemaLoweringError(
            f"primary_key field predicate not found in schema for {entity_type}.{left_field}",
            path=path,
        )

    temp_name = _allocate_system_pk_var(rewrite_ctx)
    temp_token = f"${temp_name}"
    return [
        ("pred", canonical_pred, [left_var_token, temp_token]),
        ("pred", canonical_pred, [right_var_token, temp_token]),
    ]


def _parse_attr_eq_side(side: Any, *, path: str) -> tuple[str, str, str]:
    if not isinstance(side, (list, tuple)) or len(side) != 2:
        raise WhereSchemaLoweringError("attr_eq side must be (var, field_name)", path=path)
    var_token, field_name = side[0], side[1]
    if not _is_var(var_token):
        raise WhereSchemaLoweringError("attr_eq side var must be '$' variable", path=f"{path}[0]")
    if not isinstance(field_name, str) or not field_name:
        raise WhereSchemaLoweringError("attr_eq side field_name must be non-empty string", path=f"{path}[1]")
    return var_token, field_name, _var_name(var_token)


def _allocate_system_pk_var(rewrite_ctx: dict[str, Any]) -> str:
    used_vars = rewrite_ctx.get("used_vars")
    if not isinstance(used_vars, set):
        used_vars = set()
        rewrite_ctx["used_vars"] = used_vars
    seq = rewrite_ctx.get("pk_tmp_seq", 0)
    while True:
        candidate = f"__pk_{seq}"
        seq += 1
        if candidate not in used_vars:
            used_vars.add(candidate)
            rewrite_ctx["pk_tmp_seq"] = seq
            return candidate


def _contains_attr_eq(node: Any) -> bool:
    if isinstance(node, tuple) and len(node) >= 1 and node[0] == "attr_eq":
        return True
    if isinstance(node, list):
        return any(_contains_attr_eq(item) for item in node)
    if isinstance(node, tuple):
        return any(_contains_attr_eq(item) for item in node[1:])
    return False


def _collect_body_vars(node: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(node, str) and _is_var(node):
        out.add(_var_name(node))
        return out
    if isinstance(node, list):
        for item in node:
            out.update(_collect_body_vars(item))
        return out
    if isinstance(node, tuple):
        for item in node:
            out.update(_collect_body_vars(item))
        return out
    return out


def _looks_like_or_of_bodies(where: list[Any]) -> bool:
    return bool(where) and all(isinstance(item, list) for item in where)


def _is_var(term: Any) -> bool:
    return isinstance(term, str) and term.startswith("$") and len(term) > 1


def _var_name(term: str) -> str:
    return term[1:]
