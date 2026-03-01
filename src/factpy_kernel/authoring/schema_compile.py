from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from factpy_kernel.core.schema.schema_ir import CANONICAL_TAGS, ensure_schema_ir


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AuthoringSchemaCompileError(Exception):
    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


def compile_authoring_schema_v1(
    authoring_schema: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(authoring_schema, dict):
        raise _compile_error("authoring_schema must be object", path="$")
    entities_raw = authoring_schema.get("entities")
    if not isinstance(entities_raw, list) or not entities_raw:
        raise _compile_error("authoring_schema.entities must be non-empty list", path="$.entities")

    entities_out: list[dict[str, Any]] = []
    predicates_out: list[dict[str, Any]] = []
    projection_preds: list[str] = []
    projection_entities: list[str] = []

    for entity_index, entity_raw in enumerate(entities_raw):
        entity_out, entity_preds = _compile_entity(entity_raw, entity_index)
        entities_out.append(entity_out)
        projection_entities.append(entity_out["entity_type"])
        for pred in entity_preds:
            predicates_out.append(pred)
            projection_preds.append(pred["pred_id"])

    schema_ir = {
        "schema_ir_version": "v1",
        "entities": entities_out,
        "predicates": predicates_out,
        "projection": {
            "entities": projection_entities,
            "predicates": projection_preds,
        },
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": generated_at or _utc_now_iso_z(),
    }
    try:
        return ensure_schema_ir(schema_ir)
    except Exception as exc:
        raise AuthoringSchemaCompileError(str(exc)) from exc


def _compile_entity(entity_raw: Any, entity_index: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(entity_raw, dict):
        raise _compile_error(f"entities[{entity_index}] must be object", path=f"$.entities[{entity_index}]")

    entity_type = entity_raw.get("entity_type")
    if not isinstance(entity_type, str) or not entity_type:
        raise _compile_error(
            f"entities[{entity_index}].entity_type must be non-empty string",
            path=f"$.entities[{entity_index}].entity_type",
        )

    identity_fields_raw = entity_raw.get("identity_fields")
    if not isinstance(identity_fields_raw, list) or not identity_fields_raw:
        raise _compile_error(
            f"entities[{entity_index}].identity_fields must be non-empty list",
            path=f"$.entities[{entity_index}].identity_fields",
        )
    identity_fields = [_compile_identity_field(field, entity_index, idx) for idx, field in enumerate(identity_fields_raw)]

    fields_raw = entity_raw.get("fields")
    if not isinstance(fields_raw, list):
        raise _compile_error(
            f"entities[{entity_index}].fields must be list",
            path=f"$.entities[{entity_index}].fields",
        )

    entity_out: dict[str, Any] = {
        "entity_type": entity_type,
        "identity_fields": identity_fields,
    }

    owner_prefix = _owner_prefix(entity_type)
    predicates: list[dict[str, Any]] = []

    predicates.append(
        {
            "pred_id": f"{entity_type}:exists",
            "owner_type": entity_type,
            "arity": 1,
            "arg_specs": [{"name": owner_prefix, "type_domain": "entity_ref"}],
            "cardinality": "functional",
            "dims": [],
            "group_key_indexes": [0],
            "is_entity_exists": True,
        }
    )

    for field_index, field_raw in enumerate(fields_raw):
        predicates.append(
            _compile_field(
                field_raw=field_raw,
                entity_type=entity_type,
                owner_prefix=owner_prefix,
                entity_index=entity_index,
                field_index=field_index,
            )
        )

    return entity_out, predicates


def _compile_identity_field(field_raw: Any, entity_index: int, id_index: int) -> dict[str, Any]:
    if not isinstance(field_raw, dict):
        raise _compile_error(
            f"entities[{entity_index}].identity_fields[{id_index}] must be object",
            path=f"$.entities[{entity_index}].identity_fields[{id_index}]",
        )
    name = field_raw.get("name")
    type_domain = field_raw.get("type_domain")
    if not isinstance(name, str) or not name:
        raise _compile_error(
            f"entities[{entity_index}].identity_fields[{id_index}].name must be non-empty string",
            path=f"$.entities[{entity_index}].identity_fields[{id_index}].name",
        )
    if type_domain not in CANONICAL_TAGS:
        raise _compile_error(
            f"entities[{entity_index}].identity_fields[{id_index}].type_domain invalid: {type_domain}",
            path=f"$.entities[{entity_index}].identity_fields[{id_index}].type_domain",
        )
    out = {"name": name, "type_domain": type_domain}
    if "default_factory" in field_raw:
        out["default_factory"] = field_raw["default_factory"]
    return out


def _compile_field(
    *,
    field_raw: Any,
    entity_type: str,
    owner_prefix: str,
    entity_index: int,
    field_index: int,
) -> dict[str, Any]:
    if not isinstance(field_raw, dict):
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}] must be object",
            path=f"$.entities[{entity_index}].fields[{field_index}]",
        )

    py_name = field_raw.get("py_name")
    if not isinstance(py_name, str) or not py_name:
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}].py_name must be non-empty string",
            path=f"$.entities[{entity_index}].fields[{field_index}].py_name",
        )

    cardinality = field_raw.get("cardinality")
    if cardinality not in {"functional", "multi", "temporal"}:
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}].cardinality must be one of functional|multi|temporal",
            path=f"$.entities[{entity_index}].fields[{field_index}].cardinality",
        )

    dims_raw = field_raw.get("dims", [])
    if dims_raw is None:
        dims_raw = []
    if not isinstance(dims_raw, list):
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}].dims must be list",
            path=f"$.entities[{entity_index}].fields[{field_index}].dims",
        )
    dims: list[dict[str, Any]] = []
    dim_names: list[str] = []
    for dim_index, dim_raw in enumerate(dims_raw):
        if not isinstance(dim_raw, dict):
            raise _compile_error(
                f"entities[{entity_index}].fields[{field_index}].dims[{dim_index}] must be object",
                path=f"$.entities[{entity_index}].fields[{field_index}].dims[{dim_index}]",
            )
        dim_name = dim_raw.get("name")
        dim_type = dim_raw.get("type_domain")
        if not isinstance(dim_name, str) or not dim_name:
            raise _compile_error(
                f"entities[{entity_index}].fields[{field_index}].dims[{dim_index}].name must be non-empty string",
                path=f"$.entities[{entity_index}].fields[{field_index}].dims[{dim_index}].name",
            )
        if dim_name in dim_names:
            raise _compile_error(
                f"entities[{entity_index}].fields[{field_index}].dims contains duplicate name: {dim_name}",
                path=f"$.entities[{entity_index}].fields[{field_index}].dims",
            )
        if dim_type not in CANONICAL_TAGS:
            raise _compile_error(
                f"entities[{entity_index}].fields[{field_index}].dims[{dim_index}].type_domain invalid: {dim_type}",
                path=f"$.entities[{entity_index}].fields[{field_index}].dims[{dim_index}].type_domain",
            )
        dims.append({"name": dim_name, "type_domain": dim_type})
        dim_names.append(dim_name)

    value_type = field_raw.get("type_domain")
    if value_type not in CANONICAL_TAGS:
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}].type_domain invalid: {value_type}",
            path=f"$.entities[{entity_index}].fields[{field_index}].type_domain",
        )

    pred_id = _compile_pred_id(
        field_raw=field_raw,
        owner_prefix=owner_prefix,
        entity_index=entity_index,
        field_index=field_index,
    )

    fact_key_raw = field_raw.get("fact_key")
    if fact_key_raw is None:
        fact_key_names: list[str] = []
    else:
        if not isinstance(fact_key_raw, list):
            raise _compile_error(
                f"entities[{entity_index}].fields[{field_index}].fact_key must be list",
                path=f"$.entities[{entity_index}].fields[{field_index}].fact_key",
            )
        fact_key_names = []
        seen_fact_key: set[str] = set()
        for key_idx, item in enumerate(fact_key_raw):
            if not isinstance(item, str) or not item:
                raise _compile_error(
                    f"entities[{entity_index}].fields[{field_index}].fact_key[{key_idx}] must be non-empty string",
                    path=f"$.entities[{entity_index}].fields[{field_index}].fact_key[{key_idx}]",
                )
            if item in seen_fact_key:
                raise _compile_error(
                    f"entities[{entity_index}].fields[{field_index}].fact_key duplicate dim: {item}",
                    path=f"$.entities[{entity_index}].fields[{field_index}].fact_key[{key_idx}]",
                )
            if item not in dim_names:
                raise _compile_error(
                    f"entities[{entity_index}].fields[{field_index}].fact_key references unknown dim: {item}",
                    path=f"$.entities[{entity_index}].fields[{field_index}].fact_key[{key_idx}]",
                )
            seen_fact_key.add(item)
            fact_key_names.append(item)

    value_name = field_raw.get("value_name")
    if value_name is None:
        value_name = py_name if not dims else "value"
    if not isinstance(value_name, str) or not value_name:
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}].value_name must be non-empty string",
            path=f"$.entities[{entity_index}].fields[{field_index}].value_name",
        )

    arg_specs = [{"name": owner_prefix, "type_domain": "entity_ref"}]
    arg_specs.extend(dims)
    arg_specs.append({"name": value_name, "type_domain": value_type})

    group_key_indexes = [0]
    for dim_pos, dim_name in enumerate(dim_names, start=1):
        if dim_name in set(fact_key_names):
            group_key_indexes.append(dim_pos)

    if len(dims) == 0 and fact_key_names:
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}].fact_key cannot be set when dims is empty",
            path=f"$.entities[{entity_index}].fields[{field_index}].fact_key",
        )

    predicate: dict[str, Any] = {
        "pred_id": pred_id,
        "owner_type": entity_type,
        "arity": len(arg_specs),
        "arg_specs": arg_specs,
        "cardinality": cardinality,
        "dims": list(dim_names),
        "group_key_indexes": group_key_indexes,
    }

    aliases = field_raw.get("aliases")
    if aliases is not None:
        if not isinstance(aliases, list) or any(not isinstance(x, str) or not x for x in aliases):
            raise _compile_error(
                f"entities[{entity_index}].fields[{field_index}].aliases must be list[str]",
                path=f"$.entities[{entity_index}].fields[{field_index}].aliases",
            )
        predicate["aliases"] = list(aliases)
    else:
        predicate["aliases"] = []

    for key in ("display_name", "description"):
        if key in field_raw:
            value = field_raw.get(key)
            if value is not None and not isinstance(value, str):
                raise _compile_error(
                    f"entities[{entity_index}].fields[{field_index}].{key} must be string",
                    path=f"$.entities[{entity_index}].fields[{field_index}].{key}",
                )
            if isinstance(value, str):
                predicate[key] = value

    predicate["py_field_name"] = py_name
    if fact_key_names:
        predicate["fact_key"] = fact_key_names
    return predicate


def _compile_pred_id(
    *,
    field_raw: dict[str, Any],
    owner_prefix: str,
    entity_index: int,
    field_index: int,
) -> str:
    pred_id = field_raw.get("pred_id")
    if pred_id is not None:
        if not isinstance(pred_id, str) or not pred_id:
            raise _compile_error(
                f"entities[{entity_index}].fields[{field_index}].pred_id must be non-empty string",
                path=f"$.entities[{entity_index}].fields[{field_index}].pred_id",
            )
        return pred_id

    local = field_raw.get("pred_name", field_raw.get("name", field_raw.get("py_name")))
    if not isinstance(local, str) or not local:
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}] must provide pred_id/pred_name/name/py_name",
            path=f"$.entities[{entity_index}].fields[{field_index}]",
        )
    if not _IDENT_RE.fullmatch(local):
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}] local predicate name must match {_IDENT_RE.pattern}: {local}",
            path=f"$.entities[{entity_index}].fields[{field_index}].name",
        )
    return f"{owner_prefix}:{local}"


def _owner_prefix(entity_type: str) -> str:
    if not entity_type:
        return entity_type
    out: list[str] = []
    for idx, ch in enumerate(entity_type):
        if ch.isupper() and idx > 0 and (
            (idx + 1 < len(entity_type) and entity_type[idx + 1].islower())
            or entity_type[idx - 1].islower()
        ):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _compile_error(message: str, *, path: str) -> AuthoringSchemaCompileError:
    return AuthoringSchemaCompileError(message, path=path)
