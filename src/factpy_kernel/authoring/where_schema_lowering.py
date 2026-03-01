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
    if isinstance(entities, list):
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            entity_type = entity.get("entity_type")
            if not isinstance(entity_type, str) or not entity_type:
                continue
            entity_types.add(entity_type)
            record_types.add(entity_type)

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
            if pred.get("is_record_exists") is True:
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
    for idx, atom in enumerate(body):
        out.append(_rewrite_atom(atom, meta=meta, record_var_types=record_var_types, path=f"{path}[{idx}]"))
    return out


def _rewrite_atom(
    atom: Any,
    *,
    meta: dict[str, Any],
    record_var_types: dict[str, str],
    path: str,
) -> Any:
    if isinstance(atom, tuple) and len(atom) >= 1 and atom[0] == "not":
        if len(atom) != 2 or not isinstance(atom[1], list):
            return atom
        nested = _rewrite_body(atom[1], meta=meta, path=f"{path}[1]")
        return ("not", nested)

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

    # Already canonical predicates may still carry useful record-var bindings.
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
                f"record exists predicate not found in schema for {record_type}",
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
                    f"record role predicate not found in schema for {record_type}.{field_name}",
                    path=path,
                )
    return atom


def _looks_like_or_of_bodies(where: list[Any]) -> bool:
    return bool(where) and all(isinstance(item, list) for item in where)


def _is_var(term: Any) -> bool:
    return isinstance(term, str) and term.startswith("$") and len(term) > 1


def _var_name(term: str) -> str:
    return term[1:]
