from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factgraph.core.protocol.digests import sha256_token


CANONICAL_TAGS = {
    "entity_ref",
    "string",
    "int",
    "float64",
    "bool",
    "bytes",
    "time",
    "uuid",
}

REQUIRED_TOP_LEVEL_KEYS = (
    "schema_ir_version",
    "entities",
    "predicates",
    "projection",
    "protocol_version",
    "generated_at",
)

REQUIRED_PROTOCOL_KEYS = ("idref_v1", "tup_v1", "export_v1")
SCHEMA_IDENTITY_EXCLUDED_TOP_LEVEL_KEYS = frozenset({"generated_at"})


class SchemaIRValidationError(Exception):
    pass


def load_schema_ir(path: str | Path) -> dict:
    schema_path = Path(path)
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SchemaIRValidationError(f"schema file not found: {schema_path}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaIRValidationError(f"invalid schema json: {exc}") from exc
    if not isinstance(data, dict):
        raise SchemaIRValidationError("schema_ir root must be JSON object")
    return ensure_schema_ir(data)


def ensure_schema_ir(schema_ir: dict) -> dict:
    if not isinstance(schema_ir, dict):
        raise SchemaIRValidationError("schema_ir must be dict")

    _validate_top_level(schema_ir)
    _validate_protocol_version(schema_ir["protocol_version"])
    _validate_entities(schema_ir["entities"])
    _validate_predicates(schema_ir["predicates"])
    _validate_projection(schema_ir["projection"])
    return schema_ir


def canonicalize_schema_ir_jcs(schema_ir: dict) -> bytes:
    validated = ensure_schema_ir(schema_ir)
    _reject_floats(validated, "$")
    try:
        return json.dumps(
            validated,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SchemaIRValidationError(f"failed to canonicalize schema_ir: {exc}") from exc


def canonicalize_schema_ir_identity_jcs(schema_ir: dict) -> bytes:
    validated = ensure_schema_ir(schema_ir)
    identity = {
        key: value
        for key, value in validated.items()
        if key not in SCHEMA_IDENTITY_EXCLUDED_TOP_LEVEL_KEYS
    }
    _reject_floats(identity, "$")
    try:
        return json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SchemaIRValidationError(f"failed to canonicalize schema identity: {exc}") from exc


def schema_digest(schema_ir: dict) -> str:
    canonical = canonicalize_schema_ir_identity_jcs(schema_ir)
    return sha256_token(canonical)


def _validate_top_level(schema_ir: dict) -> None:
    keys = set(schema_ir.keys())
    required = set(REQUIRED_TOP_LEVEL_KEYS)
    missing = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in keys]
    if missing:
        raise SchemaIRValidationError(f"missing top-level keys: {missing}")
    extra = sorted(keys - required)
    if extra:
        raise SchemaIRValidationError(
            f"unexpected top-level keys: {extra}; top-level structure is canonical"
        )
    if not isinstance(schema_ir["schema_ir_version"], str) or not schema_ir["schema_ir_version"]:
        raise SchemaIRValidationError("schema_ir_version must be non-empty string")
    if not isinstance(schema_ir["generated_at"], str) or not schema_ir["generated_at"]:
        raise SchemaIRValidationError("generated_at must be non-empty string")


def _validate_protocol_version(protocol_version: Any) -> None:
    if not isinstance(protocol_version, dict):
        raise SchemaIRValidationError("protocol_version must be object")
    for key in REQUIRED_PROTOCOL_KEYS:
        if key not in protocol_version:
            raise SchemaIRValidationError(
                f"protocol_version missing required key: {key}"
            )
        if not isinstance(protocol_version[key], str) or not protocol_version[key]:
            raise SchemaIRValidationError(
                f"protocol_version[{key}] must be non-empty string"
            )


def _validate_entities(entities: Any) -> None:
    if not isinstance(entities, list):
        raise SchemaIRValidationError("entities must be list")
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            raise SchemaIRValidationError(f"entities[{index}] must be object")
        entity_type = entity.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type:
            raise SchemaIRValidationError(
                f"entities[{index}].entity_type must be non-empty string"
            )
        identity_fields = entity.get("identity_fields")
        if not isinstance(identity_fields, list):
            raise SchemaIRValidationError(
                f"entities[{index}].identity_fields must be list"
            )
        for id_index, field in enumerate(identity_fields):
            if not isinstance(field, dict):
                raise SchemaIRValidationError(
                    f"entities[{index}].identity_fields[{id_index}] must be object"
                )
            if not isinstance(field.get("name"), str) or not field.get("name"):
                raise SchemaIRValidationError(
                    f"entities[{index}].identity_fields[{id_index}].name must be non-empty string"
                )
            domain = field.get("type_domain")
            if domain not in CANONICAL_TAGS:
                raise SchemaIRValidationError(
                    f"entities[{index}].identity_fields[{id_index}].type_domain is invalid: {domain}"
                )


def _validate_predicates(predicates: Any) -> None:
    if not isinstance(predicates, list):
        raise SchemaIRValidationError("predicates must be list")
    for index, predicate in enumerate(predicates):
        if not isinstance(predicate, dict):
            raise SchemaIRValidationError(f"predicates[{index}] must be object")
        pred_id = predicate.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            raise SchemaIRValidationError(
                f"predicates[{index}].pred_id must be non-empty string"
            )
        arg_specs = predicate.get("arg_specs")
        if not isinstance(arg_specs, list) or len(arg_specs) == 0:
            raise SchemaIRValidationError(
                f"predicates[{index}].arg_specs must be non-empty list"
            )
        for arg_index, arg_spec in enumerate(arg_specs):
            if not isinstance(arg_spec, dict):
                raise SchemaIRValidationError(
                    f"predicates[{index}].arg_specs[{arg_index}] must be object"
                )
            if not isinstance(arg_spec.get("name"), str) or not arg_spec.get("name"):
                raise SchemaIRValidationError(
                    f"predicates[{index}].arg_specs[{arg_index}].name must be non-empty string"
                )
            domain = arg_spec.get("type_domain")
            if domain not in CANONICAL_TAGS:
                raise SchemaIRValidationError(
                    f"predicates[{index}].arg_specs[{arg_index}].type_domain is invalid: {domain}"
                )

        group_key_indexes = predicate.get("group_key_indexes")
        if not isinstance(group_key_indexes, list):
            raise SchemaIRValidationError(
                f"predicates[{index}].group_key_indexes must be list"
            )
        _validate_group_key_indexes(
            group_key_indexes, len(arg_specs), f"predicates[{index}]"
        )


def _validate_group_key_indexes(
    group_key_indexes: list[Any], arg_count: int, ctx: str
) -> None:
    last = -1
    for i, raw_idx in enumerate(group_key_indexes):
        if isinstance(raw_idx, bool) or not isinstance(raw_idx, int):
            raise SchemaIRValidationError(f"{ctx}.group_key_indexes[{i}] must be int")
        if raw_idx < 0:
            raise SchemaIRValidationError(
                f"{ctx}.group_key_indexes[{i}] must be 0-based"
            )
        if raw_idx >= arg_count:
            raise SchemaIRValidationError(
                f"{ctx}.group_key_indexes[{i}] out of range for arg_specs size {arg_count}"
            )
        if raw_idx <= last:
            raise SchemaIRValidationError(
                f"{ctx}.group_key_indexes must be strictly ascending"
            )
        last = raw_idx


def _validate_projection(projection: Any) -> None:
    if not isinstance(projection, dict):
        raise SchemaIRValidationError("projection must be object")
    for key in ("entities", "predicates"):
        if key not in projection:
            raise SchemaIRValidationError(f"projection missing key: {key}")
        if not isinstance(projection[key], list):
            raise SchemaIRValidationError(f"projection.{key} must be list")


def _reject_floats(value: Any, path: str) -> None:
    if isinstance(value, float):
        raise SchemaIRValidationError(f"float is not allowed in schema_ir at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise SchemaIRValidationError(
                    f"schema_ir object key must be string at {path}"
                )
            _reject_floats(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_floats(child, f"{path}[{index}]")
