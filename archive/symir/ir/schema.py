"""Fact schema definitions and validation."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

from symir.errors import SchemaError
from symir.ir.types import IRPredicateRef

class DefBase:
    """Base class for fact definitions."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class FactNodeDef(DefBase):
    """Definition of a unary predicate backed by a CSV file."""

    name: str
    file: str
    column: str
    prob_column: Optional[str] = None


@dataclass(frozen=True)
class FactRelationDef(DefBase):
    """Definition of a binary predicate backed by a CSV file."""

    name: str
    file: str
    columns: tuple[str, str]
    prob_column: Optional[str] = None


class FactSchema:
    """Schema for fact predicates and CSV mappings."""

    def __init__(self, nodes: dict[str, FactNodeDef], relations: dict[str, FactRelationDef]):
        self._nodes = nodes
        self._relations = relations
        self._validate()

    @property
    def nodes(self) -> dict[str, FactNodeDef]:
        return self._nodes

    @property
    def relations(self) -> dict[str, FactRelationDef]:
        return self._relations

    def _validate(self) -> None:
        if not isinstance(self._nodes, dict) or not isinstance(self._relations, dict):
            raise SchemaError("nodes and relations must be dicts.")
        for name, node in self._nodes.items():
            if not isinstance(node, FactNodeDef):
                raise SchemaError(f"Node definition for {name} must be FactNodeDef.")
            if node.name != name:
                raise SchemaError(f"Node name mismatch: {node.name} vs {name}.")
            if not node.file or not node.column:
                raise SchemaError(f"Node {name} must define file and column.")
        for name, rel in self._relations.items():
            if not isinstance(rel, FactRelationDef):
                raise SchemaError(f"Relation definition for {name} must be FactRelationDef.")
            if rel.name != name:
                raise SchemaError(f"Relation name mismatch: {rel.name} vs {name}.")
            if not rel.file or len(rel.columns) != 2:
                raise SchemaError(f"Relation {name} must define file and 2 columns.")
        overlap = set(self._nodes).intersection(self._relations)
        if overlap:
            raise SchemaError(f"Predicate names overlap between nodes and relations: {sorted(overlap)}")

    def predicate_ref(self, name: str) -> IRPredicateRef:
        if name in self._nodes:
            return IRPredicateRef(name=name, arity=1, layer="fact")
        if name in self._relations:
            return IRPredicateRef(name=name, arity=2, layer="fact")
        raise SchemaError(f"Unknown fact predicate: {name}")

    def all_predicates(self) -> list[IRPredicateRef]:
        preds = [IRPredicateRef(name=n, arity=1, layer="fact") for n in self._nodes]
        preds.extend(IRPredicateRef(name=r, arity=2, layer="fact") for r in self._relations)
        return preds

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {
                name: node.to_dict()
                for name, node in self._nodes.items()
            },
            "relations": {
                name: rel.to_dict()
                for name, rel in self._relations.items()
            },
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "FactSchema":
        if not isinstance(data, dict):
            raise SchemaError("Fact schema must be a dict.")
        nodes_data = data.get("nodes", {})
        rels_data = data.get("relations", {})
        if not isinstance(nodes_data, dict) or not isinstance(rels_data, dict):
            raise SchemaError("nodes and relations must be dicts.")
        nodes: dict[str, FactNodeDef] = {}
        for name, cfg in nodes_data.items():
            if not isinstance(cfg, dict):
                raise SchemaError(f"Node config for {name} must be dict.")
            nodes[name] = FactNodeDef(
                name=name,
                file=str(cfg.get("file", "")),
                column=str(cfg.get("column", "")),
                prob_column=cfg.get("prob_column"),
            )
        relations: dict[str, FactRelationDef] = {}
        for name, cfg in rels_data.items():
            if not isinstance(cfg, dict):
                raise SchemaError(f"Relation config for {name} must be dict.")
            columns = cfg.get("columns", [])
            if not isinstance(columns, list) or len(columns) != 2:
                raise SchemaError(f"Relation {name} must have exactly 2 columns.")
            relations[name] = FactRelationDef(
                name=name,
                file=str(cfg.get("file", "")),
                columns=(str(columns[0]), str(columns[1])),
                prob_column=cfg.get("prob_column"),
            )
        return FactSchema(nodes=nodes, relations=relations)
