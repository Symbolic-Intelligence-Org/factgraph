from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from types import MappingProxyType
from typing import TypeAlias

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import Var

from .schema_runtime import FieldPath

_CONTRACT_FORMAT = "resolved_rule_contract_lite_v1"


class SemanticPortShapeError(ValueError):
    """A semantic-port protocol value is malformed."""


@dataclass(frozen=True)
class EntityIdentityEndpoint:
    """An entity's complete identity bundle."""

    entity_type: str

    def __post_init__(self) -> None:
        _require_text(self.entity_type, "entity_type")


@dataclass(frozen=True)
class FieldEndpoint:
    """One concrete entity field."""

    path: FieldPath

    def __post_init__(self) -> None:
        if not isinstance(self.path, FieldPath):
            raise SemanticPortShapeError("path must be FieldPath")

    @property
    def entity_type(self) -> str:
        return self.path.entity_type

    @property
    def field_name(self) -> str:
        return self.path.field_name


SemanticEndpoint: TypeAlias = EntityIdentityEndpoint | FieldEndpoint


def entity_identity(entity_type: str) -> EntityIdentityEndpoint:
    return EntityIdentityEndpoint(entity_type)


def field_endpoint(entity_type: str, field_name: str) -> FieldEndpoint:
    return FieldEndpoint(FieldPath(entity_type, field_name))


@dataclass(frozen=True)
class SemanticRulePort:
    """Exact internal Rule Var plus its Ontology endpoint."""

    var: Var
    endpoint: SemanticEndpoint

    def __post_init__(self) -> None:
        if not isinstance(self.var, Var):
            raise SemanticPortShapeError("var must be core.rules.where_ast.Var")
        if not isinstance(self.endpoint, (EntityIdentityEndpoint, FieldEndpoint)):
            raise SemanticPortShapeError("endpoint must be a supported semantic endpoint")


@dataclass(frozen=True)
class ResolvedRuleContract:
    """Frozen in-process binding for one exact Rule and trusted SchemaIndex."""

    rule_id: str
    rule_version: str | None
    rule_content_digest: str
    schema_digest: str
    ports: Mapping[str, SemanticRulePort]
    semantic_contract_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text(self.rule_id, "rule_id")
        if self.rule_version is not None:
            _require_text(self.rule_version, "rule_version")
        if not _is_hex_digest(self.rule_content_digest):
            raise SemanticPortShapeError("rule_content_digest must be lowercase sha256 hex")
        if not (
            isinstance(self.schema_digest, str)
            and self.schema_digest.startswith("sha256:")
            and _is_hex_digest(self.schema_digest[7:])
        ):
            raise SemanticPortShapeError("schema_digest must be a sha256: token")
        if not isinstance(self.ports, Mapping) or not self.ports:
            raise SemanticPortShapeError("ports must be a non-empty mapping")

        frozen: dict[str, SemanticRulePort] = {}
        endpoints: dict[Var, SemanticEndpoint] = {}
        for name, port in sorted(self.ports.items()):
            _require_text(name, "ports.<key>")
            if not isinstance(port, SemanticRulePort):
                raise SemanticPortShapeError(f"ports[{name!r}] must be SemanticRulePort")
            if port.var in endpoints and endpoints[port.var] != port.endpoint:
                raise SemanticPortShapeError(
                    f"Var {port.var.name!r} cannot claim conflicting endpoints"
                )
            endpoints[port.var] = port.endpoint
            frozen[name] = port
        object.__setattr__(self, "ports", MappingProxyType(frozen))
        object.__setattr__(self, "semantic_contract_digest", _contract_digest(self, frozen))


def _require_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise SemanticPortShapeError(f"{name} must be non-empty string")


def _is_hex_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _contract_digest(
    contract: ResolvedRuleContract, ports: Mapping[str, SemanticRulePort]
) -> str:
    payload = {
        "format": _CONTRACT_FORMAT,
        "rule": {
            "id": contract.rule_id,
            "version": contract.rule_version,
            "content_digest": contract.rule_content_digest,
        },
        "schema_digest": contract.schema_digest,
        "ports": [
            {
                "name": name,
                "var": _var_payload(port.var),
                "endpoint": _endpoint_payload(port.endpoint),
            }
            for name, port in sorted(ports.items())
        ],
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return sha256_hex(encoded)


def _var_payload(var: Var) -> dict[str, object]:
    origin = var.origin
    return {
        "name": var.name,
        "origin": None if origin is None else {"source": origin.source, "path": origin.path},
    }


def _endpoint_payload(endpoint: SemanticEndpoint) -> dict[str, str]:
    if isinstance(endpoint, EntityIdentityEndpoint):
        return {"kind": "entity_identity", "entity_type": endpoint.entity_type}
    return {
        "kind": "field",
        "entity_type": endpoint.entity_type,
        "field_name": endpoint.field_name,
    }


__all__ = [
    "EntityIdentityEndpoint", "FieldEndpoint", "ResolvedRuleContract",
    "SemanticEndpoint", "SemanticPortShapeError", "SemanticRulePort",
    "entity_identity", "field_endpoint",
]
