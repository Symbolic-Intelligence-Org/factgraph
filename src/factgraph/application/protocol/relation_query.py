from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from .common import JSONValue, ProtocolShapeError
from .schema_runtime import EntityRef

RelationQueryValue: TypeAlias = EntityRef | JSONValue | bytes
RelationQueryNodeKind: TypeAlias = Literal[
    "stored_field",
    "stored_relation",
    "rule",
    "provider",
    "scenario",
]


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProtocolShapeError(f"{field_name} must be a non-empty string")
    return value


def _tuple_of(value: object, *, field_name: str, item_type: type) -> tuple[Any, ...]:
    if not isinstance(value, tuple) or not all(isinstance(item, item_type) for item in value):
        raise ProtocolShapeError(f"{field_name} must be a tuple of {item_type.__name__}")
    return value


@dataclass(frozen=True)
class PublishedEntityFieldV1:
    key: str
    predicate_id: str
    entity_type: str
    value_type: str
    cardinality: Literal["single", "multi"]
    node_kind: RelationQueryNodeKind = "stored_field"

    def __post_init__(self) -> None:
        for name in ("key", "predicate_id", "entity_type", "value_type"):
            _text(getattr(self, name), field_name=name)
        if self.cardinality not in {"single", "multi"}:
            raise ProtocolShapeError("cardinality must be single|multi")
        if self.node_kind not in {
            "stored_field",
            "stored_relation",
            "rule",
            "provider",
            "scenario",
        }:
            raise ProtocolShapeError("node_kind is invalid")


@dataclass(frozen=True)
class PublishedStoredRelationV1:
    key: str
    predicate_id: str
    from_entity_type: str
    to_entity_type: str
    value_type: str
    cardinality: Literal["single", "multi"]
    node_kind: RelationQueryNodeKind = "stored_relation"

    def __post_init__(self) -> None:
        for name in (
            "key",
            "predicate_id",
            "from_entity_type",
            "to_entity_type",
            "value_type",
        ):
            _text(getattr(self, name), field_name=name)
        if self.cardinality not in {"single", "multi"}:
            raise ProtocolShapeError("cardinality must be single|multi")
        if self.node_kind not in {
            "stored_field",
            "stored_relation",
            "rule",
            "provider",
            "scenario",
        }:
            raise ProtocolShapeError("node_kind is invalid")


@dataclass(frozen=True)
class RelationPathStepV1:
    relation_key: str
    direction: Literal["forward", "reverse"] = "forward"

    def __post_init__(self) -> None:
        _text(self.relation_key, field_name="relation_key")
        if self.direction not in {"forward", "reverse"}:
            raise ProtocolShapeError("direction must be forward|reverse")


@dataclass(frozen=True)
class PublishedRelationPathV1:
    key: str
    root_entity_type: str
    steps: tuple[RelationPathStepV1, ...]

    def __post_init__(self) -> None:
        _text(self.key, field_name="key")
        _text(self.root_entity_type, field_name="root_entity_type")
        _tuple_of(self.steps, field_name="steps", item_type=RelationPathStepV1)
        if len(self.steps) > 32:
            raise ProtocolShapeError("a published relation path may contain at most 32 steps")


@dataclass(frozen=True)
class PublishedRelationGraphV1:
    publication_id: str
    fields: tuple[PublishedEntityFieldV1, ...]
    relations: tuple[PublishedStoredRelationV1, ...]
    paths: tuple[PublishedRelationPathV1, ...]

    def __post_init__(self) -> None:
        _text(self.publication_id, field_name="publication_id")
        _tuple_of(self.fields, field_name="fields", item_type=PublishedEntityFieldV1)
        _tuple_of(
            self.relations,
            field_name="relations",
            item_type=PublishedStoredRelationV1,
        )
        _tuple_of(self.paths, field_name="paths", item_type=PublishedRelationPathV1)
        for name, values in (
            ("field", tuple(item.key for item in self.fields)),
            ("relation", tuple(item.key for item in self.relations)),
            ("path", tuple(item.key for item in self.paths)),
        ):
            if len(set(values)) != len(values):
                raise ProtocolShapeError(f"published graph has duplicate {name} keys")


@dataclass(frozen=True)
class RelationQuerySourceV1:
    kind: Literal["entity", "field", "relation_value"]
    path_key: str
    position: int
    member_key: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"entity", "field", "relation_value"}:
            raise ProtocolShapeError("source kind must be entity|field|relation_value")
        _text(self.path_key, field_name="path_key")
        if not isinstance(self.position, int) or isinstance(self.position, bool) or self.position < 0:
            raise ProtocolShapeError("source position must be a non-negative integer")
        if self.kind == "entity":
            if self.member_key is not None:
                raise ProtocolShapeError("entity source must not carry member_key")
        else:
            _text(self.member_key, field_name="member_key")


@dataclass(frozen=True)
class RelationQueryBindingV1:
    source: RelationQuerySourceV1
    value: RelationQueryValue
    operator: Literal["eq", "ne", "gt", "ge", "lt", "le"] = "eq"

    def __post_init__(self) -> None:
        if not isinstance(self.source, RelationQuerySourceV1):
            raise ProtocolShapeError("binding source must be RelationQuerySourceV1")
        if not isinstance(self.value, (EntityRef, str, int, float, bool, bytes)) and self.value is not None:
            raise ProtocolShapeError("binding value has an unsupported typed value")
        if self.operator not in {"eq", "ne", "gt", "ge", "lt", "le"}:
            raise ProtocolShapeError("binding operator must be eq|ne|gt|ge|lt|le")


@dataclass(frozen=True)
class RelationQuerySelectionV1:
    alias: str
    source: RelationQuerySourceV1

    def __post_init__(self) -> None:
        _text(self.alias, field_name="alias")
        if not isinstance(self.source, RelationQuerySourceV1):
            raise ProtocolShapeError("selection source must be RelationQuerySourceV1")


@dataclass(frozen=True)
class PublishedRelationQueryV1:
    graph: PublishedRelationGraphV1
    bindings: tuple[RelationQueryBindingV1, ...]
    selections: tuple[RelationQuerySelectionV1, ...]
    row_limit: int

    def __post_init__(self) -> None:
        if not isinstance(self.graph, PublishedRelationGraphV1):
            raise ProtocolShapeError("graph must be PublishedRelationGraphV1")
        _tuple_of(self.bindings, field_name="bindings", item_type=RelationQueryBindingV1)
        _tuple_of(self.selections, field_name="selections", item_type=RelationQuerySelectionV1)
        if not self.selections:
            raise ProtocolShapeError("selections must not be empty")
        if not isinstance(self.row_limit, int) or isinstance(self.row_limit, bool):
            raise ProtocolShapeError("row_limit must be an integer")
        if self.row_limit < 1 or self.row_limit > 100_000:
            raise ProtocolShapeError("row_limit must be within 1..100000")
        aliases = tuple(item.alias for item in self.selections)
        if len(set(aliases)) != len(aliases):
            raise ProtocolShapeError("selection aliases must be unique")
        binding_sources = tuple(item.source for item in self.bindings)
        if len(set(binding_sources)) != len(binding_sources):
            raise ProtocolShapeError("binding sources must be unique")


__all__ = [
    "PublishedEntityFieldV1",
    "PublishedRelationGraphV1",
    "PublishedRelationPathV1",
    "PublishedRelationQueryV1",
    "PublishedStoredRelationV1",
    "RelationPathStepV1",
    "RelationQueryBindingV1",
    "RelationQueryNodeKind",
    "RelationQuerySelectionV1",
    "RelationQuerySourceV1",
    "RelationQueryValue",
]
