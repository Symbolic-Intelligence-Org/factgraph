from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, cast

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import PredAtom, Var

from .protocol.semantic_port import FieldEndpoint
from .schema_runtime import (
    SchemaIndex,
    build_schema_index,
    field_predicate,
    field_value_type,
    is_scenario_relation_predicate_v1,
)
from .semantic_port_runtime import ResolvedRuleBundle, assert_rule_contract_current

_VALUE_DOMAINS = frozenset(
    {"string", "int", "float64", "bool", "bytes", "time", "uuid", "entity_ref"}
)


class ProductCompilationContextErrorV1(ValueError):
    """A trusted product compiler requested an unsupported schema projection."""


@dataclass(frozen=True, slots=True)
class ProductFieldDescriptorV1:
    entity_type: str
    field_name: str
    predicate_id: str
    value_kind: Literal["scalar", "entity_ref"]
    value_type: str
    cardinality: Literal["single", "multi"]


@dataclass(frozen=True, slots=True)
class ProductRelationArgumentV1:
    position: int
    name: str
    type_domain: str
    anchor_ports: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductRelationPremiseV1:
    premise_key: str
    predicate_id: str
    owner_type: str
    field_name: str | None
    cardinality: Literal["single", "multi"]
    arguments: tuple[ProductRelationArgumentV1, ...]


class ProductCompilationContextV1:
    """Immutable schema-bound projection for trusted product compilers.

    The context deliberately hides ``SchemaIndex``.  Consumers can ask only
    for the field and positive relation-premise descriptions needed to compile
    a sealed product contract.
    """

    __slots__ = ("_index", "schema_digest")

    def __init__(self, index: SchemaIndex) -> None:
        if not isinstance(index, SchemaIndex):
            raise ProductCompilationContextErrorV1("schema index is invalid")
        self._index = index
        self.schema_digest = index.schema_digest

    def describe_field(self, endpoint: object) -> ProductFieldDescriptorV1:
        if not isinstance(endpoint, FieldEndpoint):
            raise ProductCompilationContextErrorV1("endpoint is not a field")
        predicate = field_predicate(
            self._index, endpoint.entity_type, endpoint.field_name
        )
        value_type = field_value_type(
            self._index, endpoint.entity_type, endpoint.field_name
        )
        public_type = (
            "entity_ref"
            if value_type.value_kind == "entity_ref"
            else value_type.scalar_domain
        )
        if public_type not in _VALUE_DOMAINS:
            raise ProductCompilationContextErrorV1("field value type is unsupported")
        return ProductFieldDescriptorV1(
            endpoint.entity_type,
            endpoint.field_name,
            predicate.pred_id,
            value_type.value_kind,
            public_type,
            value_type.cardinality,
        )

    def relation_premises(
        self, bundle: ResolvedRuleBundle
    ) -> tuple[ProductRelationPremiseV1, ...]:
        if not isinstance(bundle, ResolvedRuleBundle):
            raise ProductCompilationContextErrorV1("resolved Rule is invalid")
        assert_rule_contract_current(bundle.rule, bundle.contract)
        if bundle.contract.schema_digest != self.schema_digest:
            raise ProductCompilationContextErrorV1("resolved Rule schema is stale")

        anchors: dict[Var, set[str]] = {}
        for port_name, port in bundle.contract.ports.items():
            anchors.setdefault(port.var, set()).add(port_name)
            if not isinstance(port.endpoint, FieldEndpoint):
                continue
            predicate = field_predicate(
                self._index,
                port.endpoint.entity_type,
                port.endpoint.field_name,
            )
            for atom in bundle.rule.when:
                if (
                    isinstance(atom, PredAtom)
                    and atom.pred_id == predicate.pred_id
                    and len(atom.terms) == 2
                    and atom.terms[1] == port.var
                    and isinstance(atom.terms[0], Var)
                ):
                    anchors.setdefault(atom.terms[0], set()).add(port_name)

        records = {
            item["pred_id"]: item
            for item in self._index.schema_ir.get("predicates", ())
            if isinstance(item, dict) and isinstance(item.get("pred_id"), str)
        }
        premises: list[ProductRelationPremiseV1] = []
        for atom_index, atom in enumerate(bundle.rule.when):
            if not isinstance(atom, PredAtom):
                continue
            record = records.get(atom.pred_id)
            info = self._index.predicates_by_id.get(atom.pred_id)
            if (
                record is None
                or info is None
                or not is_scenario_relation_predicate_v1(self._index, atom.pred_id)
            ):
                continue
            arg_specs = record.get("arg_specs")
            if (
                not isinstance(arg_specs, list)
                or len(arg_specs) != len(atom.terms)
                or not all(isinstance(term, Var) for term in atom.terms)
            ):
                continue
            arguments: list[ProductRelationArgumentV1] = []
            for position, (term, spec) in enumerate(zip(atom.terms, arg_specs, strict=True)):
                assert isinstance(term, Var)
                if not isinstance(spec, dict):
                    break
                name, domain = spec.get("name"), spec.get("type_domain")
                if not isinstance(name, str) or not name or domain not in _VALUE_DOMAINS:
                    break
                arguments.append(
                    ProductRelationArgumentV1(
                        position,
                        name,
                        domain,
                        tuple(sorted(anchors.get(term, ()))),
                    )
                )
            else:
                identity = {
                    "schema_digest": self.schema_digest,
                    "rule_contract_digest": bundle.contract.semantic_contract_digest,
                    "atom_index": atom_index,
                    "predicate_id": atom.pred_id,
                    "arguments": [
                        {
                            "position": item.position,
                            "name": item.name,
                            "type_domain": item.type_domain,
                            "anchor_ports": item.anchor_ports,
                        }
                        for item in arguments
                    ],
                }
                key = sha256_hex(
                    json.dumps(
                        identity,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                )
                premises.append(
                    ProductRelationPremiseV1(
                        "relation-premise-" + key[:16],
                        atom.pred_id,
                        info.owner_type,
                        info.py_field_name,
                        cast(Literal["single", "multi"], info.cardinality),
                        tuple(arguments),
                    )
                )
        return tuple(sorted(premises, key=lambda item: (item.predicate_id, item.premise_key)))


def build_product_compilation_context_v1(
    schema_ir: dict[str, Any],
) -> ProductCompilationContextV1:
    return ProductCompilationContextV1(build_schema_index(schema_ir))


__all__ = [
    "ProductCompilationContextErrorV1",
    "ProductCompilationContextV1",
    "ProductFieldDescriptorV1",
    "ProductRelationArgumentV1",
    "ProductRelationPremiseV1",
    "build_product_compilation_context_v1",
]
