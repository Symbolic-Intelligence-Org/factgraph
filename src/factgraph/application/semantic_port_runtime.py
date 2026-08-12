from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from factgraph.core.rules.where_ast import Atom, PredAtom, Var

from .protocol import ErrorDTO, Rule
from .protocol.semantic_port import (
    EntityIdentityEndpoint, FieldEndpoint, ResolvedRuleContract,
    SemanticEndpoint, SemanticRulePort,
)
from .schema_runtime import (
    SchemaIndex, SchemaResolutionError, entity_info, field_predicate, field_value_type,
)


class SemanticPortResolutionError(ValueError):
    """Typed failure while binding Rule ports to Ontology endpoints."""

    def __init__(
        self, message: str, *, code: str, path: tuple[str, ...],
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code, self.path, self.details = code, tuple(path), dict(details or {})

    def to_error_dto(self) -> ErrorDTO:
        return ErrorDTO(code=self.code, message=str(self), path=self.path, details=self.details)


@dataclass(frozen=True)
class ResolvedRuleBundle:
    """An ordinary Rule paired with its semantic contract."""

    rule: Rule
    contract: ResolvedRuleContract

    def __post_init__(self) -> None:
        assert_rule_contract_current(self.rule, self.contract)


def build_resolved_rule(
    *, id: str, when: tuple[Atom, ...], ports: Mapping[str, SemanticRulePort],
    schema_index: SchemaIndex, version: str | None = None, repr: str | None = None,
) -> ResolvedRuleBundle:
    """Build a legacy Rule and semantic contract from one complete port map."""

    declared = _normalize_ports(ports)
    rule = Rule(
        id=id, when=when, ports={name: port.var for name, port in declared.items()},
        version=version, repr=repr,
    )
    contract = resolve_rule_contract(rule, declared, schema_index=schema_index)
    return ResolvedRuleBundle(rule, contract)


def resolve_rule_contract(
    rule: Rule, semantic_ports: Mapping[str, SemanticRulePort], *, schema_index: SchemaIndex,
) -> ResolvedRuleContract:
    """Resolve complete bindings against a trusted in-process SchemaIndex."""

    if not isinstance(rule, Rule):
        raise _error("rule must be application Rule", "INVALID_RULE", ("rule",))
    if not isinstance(schema_index, SchemaIndex):
        raise _error("schema_index must be SchemaIndex", "INVALID_SCHEMA_INDEX", ("schema_index",))
    declared = _normalize_ports(semantic_ports)
    missing, extra = sorted(set(rule.ports) - set(declared)), sorted(set(declared) - set(rule.ports))
    if missing or extra:
        raise _error(
            "semantic ports must exactly cover Rule.ports", "PORT_COVERAGE_MISMATCH",
            ("semantic_ports",), {"missing": missing, "extra": extra},
        )

    endpoints: dict[Var, SemanticEndpoint] = {}
    for name, authored in declared.items():
        if authored.var in endpoints and endpoints[authored.var] != authored.endpoint:
            raise _error(
                f"Rule Var {authored.var.name!r} claims conflicting endpoints",
                "VAR_ENDPOINT_CONFLICT", ("semantic_ports", name, "endpoint"),
            )
        endpoints[authored.var] = authored.endpoint

    resolved: dict[str, SemanticRulePort] = {}
    for name in sorted(rule.ports):
        authored, rule_var = declared[name], rule.ports[name]
        if authored.var != rule_var:
            raise _error(
                f"semantic port {name!r} does not reference its Rule Var",
                "PORT_VAR_MISMATCH", ("semantic_ports", name, "var"),
            )
        _validate_endpoint(name, rule_var, authored.endpoint, rule, schema_index)
        resolved[name] = SemanticRulePort(rule_var, authored.endpoint)
    return ResolvedRuleContract(
        rule.id, rule.version, rule.content_digest, schema_index.schema_digest, resolved
    )


def assert_rule_contract_current(rule: Rule, contract: ResolvedRuleContract) -> None:
    """Fail when a trusted in-process Rule has drifted after resolution."""

    if not isinstance(rule, Rule) or not isinstance(contract, ResolvedRuleContract):
        raise _error("invalid rule or contract", "INVALID_RULE_CONTRACT", ("contract",))
    try:
        digest = rule.content_digest
    except Exception as exc:
        raise _error(
            "Rule content is no longer digestible", "RULE_CONTRACT_STALE",
            ("contract", "rule_content_digest"), {"cause_type": type(exc).__name__},
        ) from exc
    contract_ports = {name: port.var for name, port in contract.ports.items()}
    if (
        rule.id != contract.rule_id or rule.version != contract.rule_version
        or digest != contract.rule_content_digest or dict(rule.ports) != contract_ports
    ):
        raise _error("Rule no longer matches its contract", "RULE_CONTRACT_STALE", ("contract",))


def _normalize_ports(ports: Mapping[str, SemanticRulePort]) -> dict[str, SemanticRulePort]:
    if not isinstance(ports, Mapping) or not ports:
        raise _error("semantic ports must be a non-empty mapping", "INVALID_SEMANTIC_PORTS", ("semantic_ports",))
    normalized: dict[str, SemanticRulePort] = {}
    for name, port in ports.items():
        if not isinstance(name, str) or not name or not isinstance(port, SemanticRulePort):
            raise _error("invalid semantic port entry", "INVALID_SEMANTIC_PORTS", ("semantic_ports",))
        normalized[name] = port
    return normalized


def _validate_endpoint(
    name: str, var: Var, endpoint: SemanticEndpoint, rule: Rule, index: SchemaIndex,
) -> None:
    try:
        if isinstance(endpoint, EntityIdentityEndpoint):
            entity, port_type = entity_info(index, endpoint.entity_type), rule.port_types[name]
            if port_type.kind != "entity_ref" or port_type.entity_type != endpoint.entity_type:
                raise _error(
                    f"port {name!r} is not a {endpoint.entity_type} entity reference",
                    "PORT_EXECUTION_TYPE_MISMATCH", ("semantic_ports", name),
                )
            _require_witness(rule.when, entity.exists_predicate_id, 1, 0, var, name)
            return
        if isinstance(endpoint, FieldEndpoint):
            predicate = field_predicate(index, endpoint.entity_type, endpoint.field_name)
            value_type = field_value_type(index, endpoint.entity_type, endpoint.field_name)
            if value_type.value_kind == "entity_ref":
                raise _error(
                    f"entity-reference field {endpoint.entity_type}.{endpoint.field_name} is unsupported",
                    "UNSUPPORTED_ENTITY_REF_FIELD", ("semantic_ports", name, "endpoint"),
                )
            if rule.port_types[name].kind != "value":
                raise _error(
                    f"port {name!r} is not a scalar value", "PORT_EXECUTION_TYPE_MISMATCH",
                    ("semantic_ports", name),
                )
            _require_witness(rule.when, predicate.pred_id, 2, 1, var, name)
            return
    except SchemaResolutionError as exc:
        raise _error(
            str(exc), "SEMANTIC_ENDPOINT_NOT_FOUND", ("semantic_ports", name, "endpoint"),
            {"schema_error_code": exc.code},
        ) from exc
    raise _error(
        f"unsupported endpoint for port {name!r}", "UNSUPPORTED_ENDPOINT",
        ("semantic_ports", name, "endpoint"),
    )


def _require_witness(
    atoms: tuple[Atom, ...], pred_id: str, arity: int, position: int,
    var: Var, port_name: str,
) -> None:
    found = any(
        isinstance(atom, PredAtom) and atom.pred_id == pred_id
        and len(atom.terms) == arity and atom.terms[position] == var
        for atom in atoms
    )
    if not found:
        raise _error(
            f"port {port_name!r} has no positive {pred_id!r} witness",
            "SEMANTIC_VAR_POSITION_MISMATCH", ("semantic_ports", port_name, "var"),
        )


def _error(
    message: str, code: str, path: tuple[str, ...], details: dict[str, Any] | None = None,
) -> SemanticPortResolutionError:
    return SemanticPortResolutionError(message, code=code, path=path, details=details)


__all__ = [
    "ResolvedRuleBundle", "SemanticPortResolutionError", "assert_rule_contract_current",
    "build_resolved_rule", "resolve_rule_contract",
]
