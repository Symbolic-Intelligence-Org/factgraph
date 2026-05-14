from __future__ import annotations

from typing import Any

from factgraph.core.protocol.idref_v1 import encode_idref_v1

from ..errors import AgentContractError


def encode_entity_ref(
    schema_ir: dict[str, Any],
    *,
    entity_type: str,
    identity: dict[str, object],
) -> str:
    entities = schema_ir.get("entities", [])
    if not isinstance(entities, list):
        raise AgentContractError("schema_ir.entities must be list")
    entity_row = next(
        (
            row
            for row in entities
            if isinstance(row, dict) and row.get("entity_type") == entity_type
        ),
        None,
    )
    if entity_row is None:
        raise AgentContractError(f"entity_type not found in schema: {entity_type}")
    identity_fields = entity_row.get("identity_fields", [])
    if not isinstance(identity_fields, list):
        raise AgentContractError("entity.identity_fields must be list")
    tuples: list[tuple[str, str, object]] = []
    for field in identity_fields:
        if not isinstance(field, dict):
            raise AgentContractError("identity field entries must be objects")
        name = _require_non_empty_str(field.get("name"), "identity_field.name")
        type_domain = _require_non_empty_str(field.get("type_domain"), "identity_field.type_domain")
        if name not in identity:
            raise AgentContractError(f"identity missing field: {name}")
        tuples.append((name, type_domain, identity[name]))
    return encode_idref_v1(entity_type, tuples)


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value
