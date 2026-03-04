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
    identity_names = {field["name"] for field in identity_fields}
    for idx, field_raw in enumerate(fields_raw):
        if not isinstance(field_raw, dict):
            continue
        py_name = field_raw.get("py_name")
        if isinstance(py_name, str) and py_name in identity_names:
            raise _compile_error(
                f"entities[{entity_index}].fields[{idx}].py_name conflicts with identity field: {py_name}",
                path=f"$.entities[{entity_index}].fields[{idx}].py_name",
            )

    entity_out: dict[str, Any] = {
        "entity_type": entity_type,
        "identity_fields": identity_fields,
    }
    description = entity_raw.get("description")
    if description is not None:
        if not isinstance(description, str) or not description:
            raise _compile_error(
                f"entities[{entity_index}].description must be non-empty string",
                path=f"$.entities[{entity_index}].description",
            )
        entity_out["description"] = description

    owner_prefix = _owner_prefix(entity_type)
    predicates: list[dict[str, Any]] = []

    predicates.append(
        {
            "pred_id": f"{entity_type}:exists",
            "owner_type": entity_type,
            "arity": 1,
            "arg_specs": [{"name": owner_prefix, "type_domain": "entity_ref"}],
            "cardinality": "single",
            "group_key_indexes": [0],
            "is_entity_exists": True,
        }
    )

    for identity in identity_fields:
        predicates.append(
            _compile_identity_predicate(
                identity_field=identity,
                entity_type=entity_type,
                owner_prefix=owner_prefix,
            )
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


def _compile_identity_predicate(
    *,
    identity_field: dict[str, Any],
    entity_type: str,
    owner_prefix: str,
) -> dict[str, Any]:
    field_name = identity_field.get("name")
    type_domain = identity_field.get("type_domain")
    if not isinstance(field_name, str) or not field_name:
        raise _compile_error(
            f"identity field name must be non-empty string for {entity_type}",
            path="$.entities[].identity_fields[].name",
        )
    if type_domain not in CANONICAL_TAGS:
        raise _compile_error(
            f"identity field type_domain invalid for {entity_type}.{field_name}: {type_domain}",
            path="$.entities[].identity_fields[].type_domain",
        )
    predicate: dict[str, Any] = {
        "pred_id": f"{owner_prefix}:{field_name}",
        "owner_type": entity_type,
        "arity": 2,
        "arg_specs": [
            {"name": owner_prefix, "type_domain": "entity_ref"},
            {"name": field_name, "type_domain": type_domain},
        ],
        "cardinality": "single",
        "group_key_indexes": [0],
        "py_field_name": field_name,
        "is_identity_field": True,
    }
    if identity_field.get("primary_key") is True:
        predicate["primary_key"] = True
    return predicate


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
    if "default" in field_raw:
        out["default"] = field_raw["default"]
    if "default_factory" in field_raw:
        out["default_factory"] = field_raw["default_factory"]
    if field_raw.get("primary_key") is True:
        out["primary_key"] = True
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
    if cardinality not in {"single", "multi"}:
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}].cardinality must be one of single|multi",
            path=f"$.entities[{entity_index}].fields[{field_index}].cardinality",
        )

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

    value_name = py_name
    if not isinstance(value_name, str) or not value_name:
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}].value_name must be non-empty string",
            path=f"$.entities[{entity_index}].fields[{field_index}].value_name",
        )

    arg_specs = [
        {"name": owner_prefix, "type_domain": "entity_ref"},
        {"name": value_name, "type_domain": value_type},
    ]

    predicate: dict[str, Any] = {
        "pred_id": pred_id,
        "owner_type": entity_type,
        "arity": len(arg_specs),
        "arg_specs": arg_specs,
        "cardinality": cardinality,
        "group_key_indexes": [0],
    }

    predicate["py_field_name"] = py_name
    description = field_raw.get("description")
    if description is not None:
        if not isinstance(description, str) or not description:
            raise _compile_error(
                f"entities[{entity_index}].fields[{field_index}].description must be non-empty string",
                path=f"$.entities[{entity_index}].fields[{field_index}].description",
            )
        predicate["description"] = description
    return predicate


def _compile_pred_id(
    *,
    field_raw: dict[str, Any],
    owner_prefix: str,
    entity_index: int,
    field_index: int,
) -> str:
    local = field_raw.get("py_name")
    if not isinstance(local, str) or not local:
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}] must provide py_name",
            path=f"$.entities[{entity_index}].fields[{field_index}]",
        )
    if not _IDENT_RE.fullmatch(local):
        raise _compile_error(
            f"entities[{entity_index}].fields[{field_index}] local predicate name must match {_IDENT_RE.pattern}: {local}",
            path=f"$.entities[{entity_index}].fields[{field_index}].py_name",
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
