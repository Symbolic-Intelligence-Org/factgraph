from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from factgraph.core.schema.schema_ir import CANONICAL_TAGS, ensure_schema_ir


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
    relationships_raw = authoring_schema.get("relationships", [])
    if relationships_raw is None:
        relationships_raw = []
    if not isinstance(relationships_raw, list):
        raise _compile_error("authoring_schema.relationships must be list when provided", path="$.relationships")

    for entity_index, entity_raw in enumerate(entities_raw):
        entity_out, entity_preds = _compile_entity(entity_raw, entity_index)
        entities_out.append(entity_out)
        projection_entities.append(entity_out["entity_type"])
        for pred in entity_preds:
            predicates_out.append(pred)
            projection_preds.append(pred["pred_id"])

    for rel_index, rel_raw in enumerate(relationships_raw):
        rel_preds = _compile_relationship(rel_raw, rel_index)
        for pred in rel_preds:
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
    version = _compile_optional_version(
        entity_raw.get("version"),
        path=f"$.entities[{entity_index}].version",
        label=f"entities[{entity_index}].version",
    )
    if version is not None:
        entity_out["version"] = version
    tags = _compile_optional_tags(
        entity_raw.get("tags"),
        path=f"$.entities[{entity_index}].tags",
        label=f"entities[{entity_index}].tags",
    )
    if tags is not None:
        entity_out["tags"] = tags

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


def _compile_relationship(rel_raw: Any, rel_index: int) -> list[dict[str, Any]]:
    if not isinstance(rel_raw, dict):
        raise _compile_error(
            f"relationships[{rel_index}] must be object",
            path=f"$.relationships[{rel_index}]",
        )

    relationship_type = rel_raw.get("relationship_type")
    if not isinstance(relationship_type, str) or not relationship_type:
        raise _compile_error(
            f"relationships[{rel_index}].relationship_type must be non-empty string",
            path=f"$.relationships[{rel_index}].relationship_type",
        )

    from_entity_type = rel_raw.get("from_entity_type")
    if not isinstance(from_entity_type, str) or not from_entity_type:
        raise _compile_error(
            f"relationships[{rel_index}].from_entity_type must be non-empty string",
            path=f"$.relationships[{rel_index}].from_entity_type",
        )

    to_entity_type = rel_raw.get("to_entity_type")
    if not isinstance(to_entity_type, str) or not to_entity_type:
        raise _compile_error(
            f"relationships[{rel_index}].to_entity_type must be non-empty string",
            path=f"$.relationships[{rel_index}].to_entity_type",
        )

    fields_raw = rel_raw.get("fields")
    if not isinstance(fields_raw, list):
        raise _compile_error(
            f"relationships[{rel_index}].fields must be list",
            path=f"$.relationships[{rel_index}].fields",
        )

    relationship_prefix = _owner_prefix(relationship_type)
    predicates: list[dict[str, Any]] = []
    for field_index, field_raw in enumerate(fields_raw):
        predicates.append(
            _compile_relationship_field(
                field_raw=field_raw,
                relationship_type=relationship_type,
                relationship_prefix=relationship_prefix,
                from_entity_type=from_entity_type,
                to_entity_type=to_entity_type,
                rel_index=rel_index,
                field_index=field_index,
            )
        )
    return predicates


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
    _copy_pattern_enum(
        source=identity_field,
        predicate=predicate,
        type_domain=type_domain,
        path="$.entities[].identity_fields[]",
    )
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
    _copy_pattern_enum(
        source=field_raw,
        predicate=out,
        type_domain=type_domain,
        path=f"$.entities[{entity_index}].identity_fields[{id_index}]",
    )
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
    _copy_pattern_enum(
        source=field_raw,
        predicate=predicate,
        type_domain=value_type,
        path=f"$.entities[{entity_index}].fields[{field_index}]",
    )
    return predicate


def _compile_relationship_field(
    *,
    field_raw: Any,
    relationship_type: str,
    relationship_prefix: str,
    from_entity_type: str,
    to_entity_type: str,
    rel_index: int,
    field_index: int,
) -> dict[str, Any]:
    if not isinstance(field_raw, dict):
        raise _compile_error(
            f"relationships[{rel_index}].fields[{field_index}] must be object",
            path=f"$.relationships[{rel_index}].fields[{field_index}]",
        )

    py_name = field_raw.get("py_name")
    if not isinstance(py_name, str) or not py_name:
        raise _compile_error(
            f"relationships[{rel_index}].fields[{field_index}].py_name must be non-empty string",
            path=f"$.relationships[{rel_index}].fields[{field_index}].py_name",
        )

    cardinality = field_raw.get("cardinality")
    if cardinality not in {"single", "multi"}:
        raise _compile_error(
            f"relationships[{rel_index}].fields[{field_index}].cardinality must be one of single|multi",
            path=f"$.relationships[{rel_index}].fields[{field_index}].cardinality",
        )

    value_type = field_raw.get("type_domain")
    if value_type not in CANONICAL_TAGS:
        raise _compile_error(
            f"relationships[{rel_index}].fields[{field_index}].type_domain invalid: {value_type}",
            path=f"$.relationships[{rel_index}].fields[{field_index}].type_domain",
        )

    pred_id = _compile_relationship_pred_id(
        field_raw=field_raw,
        relationship_prefix=relationship_prefix,
        rel_index=rel_index,
        field_index=field_index,
    )

    arg_specs = [
        {"name": "from_ref", "type_domain": "entity_ref"},
        {"name": "to_ref", "type_domain": "entity_ref"},
        {"name": py_name, "type_domain": value_type},
    ]

    predicate: dict[str, Any] = {
        "pred_id": pred_id,
        "arity": len(arg_specs),
        "arg_specs": arg_specs,
        "cardinality": cardinality,
        "group_key_indexes": [0, 1],
        "owner_type": relationship_type,
        "relationship_type": relationship_type,
        "from_entity_type": from_entity_type,
        "to_entity_type": to_entity_type,
        "py_field_name": py_name,
    }
    _copy_pattern_enum(
        source=field_raw,
        predicate=predicate,
        type_domain=value_type,
        path=f"$.relationships[{rel_index}].fields[{field_index}]",
    )
    return predicate


def _copy_pattern_enum(
    *,
    source: dict[str, Any],
    predicate: dict[str, Any],
    type_domain: Any,
    path: str,
) -> None:
    pattern = source.get("pattern")
    if pattern is not None:
        if type_domain != "string":
            raise _compile_error(f"{path}.pattern is only supported for string fields", path=f"{path}.pattern")
        if not isinstance(pattern, str) or not pattern:
            raise _compile_error(f"{path}.pattern must be non-empty string", path=f"{path}.pattern")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise _compile_error(f"{path}.pattern must be valid regex: {exc}", path=f"{path}.pattern")
        predicate["pattern"] = pattern

    enum_values = source.get("enum_values")
    if enum_values is not None:
        if not isinstance(enum_values, list) or not enum_values:
            raise _compile_error(f"{path}.enum_values must be non-empty list", path=f"{path}.enum_values")
        domains = {_literal_value_type_domain(value) for value in enum_values}
        if len(domains) != 1:
            raise _compile_error(f"{path}.enum_values must be homogeneous", path=f"{path}.enum_values")
        enum_type_domain = next(iter(domains))
        if enum_type_domain == "float64":
            raise _compile_error(f"{path}.enum_values does not support float Literal values", path=f"{path}.enum_values")
        if enum_type_domain != type_domain:
            raise _compile_error(
                f"{path}.enum_values type {enum_type_domain} does not match field type_domain {type_domain}",
                path=f"{path}.enum_values",
            )
        predicate["enum_values"] = list(enum_values)


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
    raise _compile_error(
        f"enum_values contains unsupported literal type: {type(value).__name__}",
        path="$.entities[].fields[].enum_values",
    )


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


def _compile_relationship_pred_id(
    *,
    field_raw: dict[str, Any],
    relationship_prefix: str,
    rel_index: int,
    field_index: int,
) -> str:
    local = field_raw.get("py_name")
    if not isinstance(local, str) or not local:
        raise _compile_error(
            f"relationships[{rel_index}].fields[{field_index}] must provide py_name",
            path=f"$.relationships[{rel_index}].fields[{field_index}]",
        )
    if not _IDENT_RE.fullmatch(local):
        raise _compile_error(
            f"relationships[{rel_index}].fields[{field_index}] local predicate name must match {_IDENT_RE.pattern}: {local}",
            path=f"$.relationships[{rel_index}].fields[{field_index}].py_name",
        )
    return f"{relationship_prefix}:{local}"


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


def _compile_optional_version(value: Any, *, path: str, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _compile_error(f"{label} must be non-empty string", path=path)
    return value


def _compile_optional_tags(value: Any, *, path: str, label: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise _compile_error(f"{label} must be list[str]", path=path)
    out: list[str] = []
    for index, tag in enumerate(value):
        if not isinstance(tag, str) or not tag:
            raise _compile_error(f"{label}[{index}] must be non-empty string", path=f"{path}[{index}]")
        out.append(tag)
    return out
