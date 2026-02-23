"""Filter AST for selecting predicate schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Iterable

from symir.ir.fact_schema import PredicateSchema
from symir.errors import SchemaError


class FilterAST:
    """Base class for filter AST nodes."""

    def matches(self, predicate: PredicateSchema) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def to_dict(self) -> dict[str, object]:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass(frozen=True)
class PredMatch(FilterAST):
    """Match predicates by name/arity/signature fields."""

    name: Optional[str] = None
    arity: Optional[int] = None
    datatype: Optional[str] = None
    role: Optional[str] = None
    namespace: Optional[str] = None

    def matches(self, predicate: PredicateSchema) -> bool:
        if self.name is not None and predicate.name != self.name:
            return False
        if self.arity is not None and predicate.arity != self.arity:
            return False
        if self.datatype is not None:
            if any(arg.datatype != self.datatype for arg in predicate.signature):
                return False
        if self.role is not None:
            if any(arg.role != self.role for arg in predicate.signature):
                return False
        if self.namespace is not None:
            if any(arg.namespace != self.namespace for arg in predicate.signature):
                return False
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "match": {
                "name": self.name,
                "arity": self.arity,
                "datatype": self.datatype,
                "role": self.role,
                "namespace": self.namespace,
            }
        }


@dataclass(frozen=True)
class And(FilterAST):
    items: list[FilterAST]

    def matches(self, predicate: PredicateSchema) -> bool:
        return all(item.matches(predicate) for item in self.items)

    def to_dict(self) -> dict[str, object]:
        return {"and": [item.to_dict() for item in self.items]}


@dataclass(frozen=True)
class Or(FilterAST):
    items: list[FilterAST]

    def matches(self, predicate: PredicateSchema) -> bool:
        return any(item.matches(predicate) for item in self.items)

    def to_dict(self) -> dict[str, object]:
        return {"or": [item.to_dict() for item in self.items]}


@dataclass(frozen=True)
class Not(FilterAST):
    item: FilterAST

    def matches(self, predicate: PredicateSchema) -> bool:
        return not self.item.matches(predicate)

    def to_dict(self) -> dict[str, object]:
        return {"not": self.item.to_dict()}


def filter_from_dict(data: dict[str, object]) -> FilterAST:
    """Parse a filter AST from a dict.

    Dict sugar: if the dict does not include 'and/or/not/match', treat it as a PredMatch.
    """

    if not isinstance(data, dict):
        raise SchemaError("Filter must be a dict.")
    if "and" in data:
        items = data["and"]
        if not isinstance(items, list):
            raise SchemaError("and must be a list.")
        return And([filter_from_dict(item) for item in items])
    if "or" in data:
        items = data["or"]
        if not isinstance(items, list):
            raise SchemaError("or must be a list.")
        return Or([filter_from_dict(item) for item in items])
    if "not" in data:
        return Not(filter_from_dict(data["not"]))
    if "match" in data:
        match = data["match"]
        if not isinstance(match, dict):
            raise SchemaError("match must be a dict.")
        return PredMatch(
            name=match.get("name"),
            arity=match.get("arity"),
            datatype=match.get("datatype"),
            role=match.get("role"),
            namespace=match.get("namespace"),
        )
    return PredMatch(
        name=data.get("name"),
        arity=data.get("arity"),
        datatype=data.get("datatype"),
        role=data.get("role"),
        namespace=data.get("namespace"),
    )


def apply_filter(predicates: Iterable[PredicateSchema], filt: FilterAST) -> list[PredicateSchema]:
    return [pred for pred in predicates if filt.matches(pred)]
