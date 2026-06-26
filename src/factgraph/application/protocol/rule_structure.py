from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, TypeAlias

from .rule_expr import RuleExprError, RuleJoinConstraint
from .rule_expr_inspect import _render_ast_compact, _render_join, _render_repr_template


@dataclass(frozen=True)
class FreeVar:
    name: str
    port_name: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.name, field_name="FreeVar.name")
        _require_optional_str(self.port_name, field_name="FreeVar.port_name")


@dataclass(frozen=True)
class Const:
    value: Any


StructureTerm: TypeAlias = FreeVar | Const


@dataclass(frozen=True)
class Fact:
    predicate: str
    terms: tuple[StructureTerm, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.predicate, field_name="Fact.predicate")
        _require_tuple(self.terms, field_name="Fact.terms", item_type=(FreeVar, Const))


@dataclass(frozen=True)
class Compare:
    op: str
    left: StructureTerm
    right: StructureTerm

    def __post_init__(self) -> None:
        _require_non_empty_str(self.op, field_name="Compare.op")
        _require_instance(self.left, field_name="Compare.left", item_type=(FreeVar, Const))
        _require_instance(self.right, field_name="Compare.right", item_type=(FreeVar, Const))


@dataclass(frozen=True)
class Builtin:
    kind: str
    operands: tuple[StructureTerm, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.kind, field_name="Builtin.kind")
        _require_tuple(self.operands, field_name="Builtin.operands", item_type=(FreeVar, Const))


@dataclass(frozen=True)
class Aggregate:
    kind: str
    body_terms: tuple[StructureTerm, ...] = ()
    head_terms: tuple[StructureTerm, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.kind, field_name="Aggregate.kind")
        _require_tuple(self.body_terms, field_name="Aggregate.body_terms", item_type=(FreeVar, Const))
        _require_tuple(self.head_terms, field_name="Aggregate.head_terms", item_type=(FreeVar, Const))


StructureAtomForm: TypeAlias = Fact | Compare | Builtin | Aggregate


@dataclass(frozen=True)
class StructurePort:
    name: str
    kind: Literal["entity_ref", "value"]
    entity_type: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.name, field_name="StructurePort.name")
        if self.kind not in {"entity_ref", "value"}:
            raise RuleExprError("StructurePort.kind must be 'entity_ref' or 'value'")
        _require_optional_str(self.entity_type, field_name="StructurePort.entity_type")
        if self.kind == "entity_ref" and not self.entity_type:
            raise RuleExprError("StructurePort.entity_type is required for entity_ref ports")


@dataclass(frozen=True)
class StructurePortRef:
    occurrence_alias: str
    port_name: str
    rule_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.occurrence_alias, field_name="StructurePortRef.occurrence_alias")
        _require_non_empty_str(self.port_name, field_name="StructurePortRef.port_name")
        _require_optional_str(self.rule_id, field_name="StructurePortRef.rule_id")


@dataclass(frozen=True)
class StructureAtom:
    atom_id: str
    kind: str
    form: StructureAtomForm | None = None
    subject: str | None = None
    entity_type: str | None = None
    field: str | None = None
    op: str | None = None
    value: object = None
    negated: bool = False
    summary: str = ""

    def __post_init__(self) -> None:
        _require_non_empty_str(self.atom_id, field_name="StructureAtom.atom_id")
        _require_non_empty_str(self.kind, field_name="StructureAtom.kind")
        if self.form is not None and not isinstance(self.form, (Fact, Compare, Builtin, Aggregate)):
            raise RuleExprError("StructureAtom.form must be Fact, Compare, Builtin, Aggregate, or None")
        _require_optional_str(self.subject, field_name="StructureAtom.subject")
        _require_optional_str(self.entity_type, field_name="StructureAtom.entity_type")
        _require_optional_str(self.field, field_name="StructureAtom.field")
        _require_optional_str(self.op, field_name="StructureAtom.op")
        if not isinstance(self.negated, bool):
            raise RuleExprError("StructureAtom.negated must be bool")
        if not isinstance(self.summary, str):
            raise RuleExprError("StructureAtom.summary must be string")


@dataclass(frozen=True)
class StructureJoin:
    left: StructurePortRef
    right: StructurePortRef
    join_id: str
    op: Literal["eq"] = "eq"

    def __post_init__(self) -> None:
        _require_instance(self.left, field_name="StructureJoin.left", item_type=StructurePortRef)
        _require_instance(self.right, field_name="StructureJoin.right", item_type=StructurePortRef)
        _require_non_empty_str(self.join_id, field_name="StructureJoin.join_id")
        if self.op != "eq":
            raise RuleExprError("StructureJoin.op must be 'eq'")


@dataclass(frozen=True)
class StructureHeadLink:
    head_port_name: str
    source_occurrence_alias: str
    source_port_name: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.head_port_name, field_name="StructureHeadLink.head_port_name")
        _require_non_empty_str(
            self.source_occurrence_alias,
            field_name="StructureHeadLink.source_occurrence_alias",
        )
        _require_non_empty_str(self.source_port_name, field_name="StructureHeadLink.source_port_name")


@dataclass(frozen=True)
class StructureOccurrence:
    occurrence_alias: str
    rule_id: str
    role: Literal["head", "body"]
    repr_text: str | None = None
    port_names: tuple[str, ...] = ()
    ports: Mapping[str, StructurePort] = field(default_factory=dict)
    atoms: tuple[StructureAtom, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.occurrence_alias, field_name="StructureOccurrence.occurrence_alias")
        _require_non_empty_str(self.rule_id, field_name="StructureOccurrence.rule_id")
        if self.role not in {"head", "body"}:
            raise RuleExprError("StructureOccurrence.role must be 'head' or 'body'")
        _require_optional_str(self.repr_text, field_name="StructureOccurrence.repr_text")
        _require_tuple(self.port_names, field_name="StructureOccurrence.port_names", item_type=str)
        _require_tuple(self.atoms, field_name="StructureOccurrence.atoms", item_type=StructureAtom)
        if not isinstance(self.ports, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, StructurePort)
            for key, value in self.ports.items()
        ):
            raise RuleExprError("StructureOccurrence.ports must be Mapping[str, StructurePort]")
        object.__setattr__(self, "ports", MappingProxyType(dict(self.ports)))

    @property
    def alias(self) -> str:
        return self.occurrence_alias

    @property
    def template_id(self) -> str:
        return self.rule_id

    @property
    def repr_template(self) -> str | None:
        return self.repr_text


@dataclass(frozen=True)
class StructureBranch:
    branch_id: str
    path: tuple[int, ...]
    occurrences: tuple[StructureOccurrence, ...]
    joins: tuple[StructureJoin, ...] = ()
    head_links: tuple[StructureHeadLink, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.branch_id, field_name="StructureBranch.branch_id")
        _require_tuple(self.path, field_name="StructureBranch.path", item_type=int)
        _require_tuple(self.occurrences, field_name="StructureBranch.occurrences", item_type=StructureOccurrence)
        _require_tuple(self.joins, field_name="StructureBranch.joins", item_type=StructureJoin)
        _require_tuple(self.head_links, field_name="StructureBranch.head_links", item_type=StructureHeadLink)


@dataclass(frozen=True)
class HeadClosure:
    is_closed: bool
    unbound_ports: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.is_closed, bool):
            raise RuleExprError("HeadClosure.is_closed must be bool")
        _require_tuple(self.unbound_ports, field_name="HeadClosure.unbound_ports", item_type=str)


@dataclass(frozen=True)
class RuleStructure:
    structure_id: str
    source_kind: Literal["rule", "rule_expr"]
    head_rule_id: str
    head_binding_kind: Literal["external", "inline", "projection"]
    ast: tuple[object, ...]
    branches: tuple[StructureBranch, ...]
    ports: tuple[StructurePort, ...] = ()
    unjoined_same_name_ports: tuple[Mapping[str, object], ...] = ()
    head_closure: HeadClosure | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    _floor_occurrences: tuple[StructureOccurrence, ...] = field(default=(), repr=False)
    _floor_joins: tuple[RuleJoinConstraint, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.structure_id, field_name="RuleStructure.structure_id")
        if self.source_kind not in {"rule", "rule_expr"}:
            raise RuleExprError("RuleStructure.source_kind must be 'rule' or 'rule_expr'")
        _require_non_empty_str(self.head_rule_id, field_name="RuleStructure.head_rule_id")
        if self.head_binding_kind not in {"external", "inline", "projection"}:
            raise RuleExprError("RuleStructure.head_binding_kind must be external, inline, or projection")
        if not isinstance(self.ast, tuple):
            raise RuleExprError("RuleStructure.ast must be tuple")
        _require_tuple(self.branches, field_name="RuleStructure.branches", item_type=StructureBranch)
        _require_tuple(self.ports, field_name="RuleStructure.ports", item_type=StructurePort)
        if not isinstance(self.unjoined_same_name_ports, tuple):
            raise RuleExprError("RuleStructure.unjoined_same_name_ports must be tuple")
        if self.head_closure is not None and not isinstance(self.head_closure, HeadClosure):
            raise RuleExprError("RuleStructure.head_closure must be HeadClosure or None")
        if not isinstance(self.metadata, Mapping):
            raise RuleExprError("RuleStructure.metadata must be Mapping")
        _require_tuple(
            self._floor_occurrences,
            field_name="RuleStructure.floor_occurrences",
            item_type=StructureOccurrence,
        )
        _require_tuple(self._floor_joins, field_name="RuleStructure.floor_joins", item_type=RuleJoinConstraint)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def occurrences(self) -> tuple[StructureOccurrence, ...]:
        if self._floor_occurrences:
            return self._floor_occurrences
        seen: set[str] = set()
        out: list[StructureOccurrence] = []
        for branch in self.branches:
            for occurrence in branch.occurrences:
                if occurrence.occurrence_alias in seen:
                    continue
                seen.add(occurrence.occurrence_alias)
                out.append(occurrence)
        return tuple(out)

    @property
    def joins(self) -> tuple[RuleJoinConstraint, ...]:
        return self._floor_joins

    @property
    def templates(self) -> tuple[str, ...]:
        seen: set[str] = set()
        out: list[str] = []
        for occurrence in self.occurrences:
            if occurrence.rule_id not in seen:
                seen.add(occurrence.rule_id)
                out.append(occurrence.rule_id)
        return tuple(out)

    @property
    def port_visibility(self) -> Mapping[str, tuple[str, ...]]:
        return MappingProxyType({occurrence.occurrence_alias: occurrence.port_names for occurrence in self.occurrences})

    @property
    def is_closed(self) -> bool:
        return False if self.head_closure is None else self.head_closure.is_closed

    @property
    def unbound_ports(self) -> tuple[str, ...]:
        return () if self.head_closure is None else self.head_closure.unbound_ports

    def render(self, bindings: Mapping[str, object] | None = None) -> str:
        values = {} if bindings is None else bindings
        if not isinstance(values, Mapping):
            raise RuleExprError("RuleStructure.render bindings must be Mapping[str, object] or None")
        occurrence_lines = []
        for occurrence in self.occurrences:
            rendered_repr = _render_repr_template(occurrence.repr_text, occurrence.occurrence_alias, values)
            label = f"{occurrence.occurrence_alias}:{occurrence.rule_id}"
            occurrence_lines.append(label if not rendered_repr else f"{label} {rendered_repr}")
        pieces = ["RuleExprInspect", _render_ast_compact(self.ast), "; ".join(occurrence_lines)]
        if self.joins:
            pieces.append("joins " + ", ".join(_render_join(join) for join in self.joins))
        return " | ".join(piece for piece in pieces if piece)

    def render_compact(self) -> str:
        return _render_ast_compact(self.ast)


def _require_non_empty_str(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuleExprError(f"{field_name} must be non-empty string")
    return value


def _require_optional_str(value: object, *, field_name: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise RuleExprError(f"{field_name} must be string or None")
    return value


def _require_instance(value: object, *, field_name: str, item_type: type | tuple[type, ...]) -> None:
    if not isinstance(value, item_type):
        name = getattr(item_type, "__name__", repr(item_type))
        raise RuleExprError(f"{field_name} must be {name}")


def _require_tuple(value: object, *, field_name: str, item_type: type | tuple[type, ...]) -> None:
    if not isinstance(value, tuple) or any(not isinstance(item, item_type) for item in value):
        raise RuleExprError(f"{field_name} must be tuple[{item_type}, ...]")


__all__ = [
    "Aggregate",
    "Builtin",
    "Compare",
    "Const",
    "Fact",
    "FreeVar",
    "HeadClosure",
    "RuleStructure",
    "StructureAtom",
    "StructureAtomForm",
    "StructureBranch",
    "StructureHeadLink",
    "StructureJoin",
    "StructureOccurrence",
    "StructurePort",
    "StructurePortRef",
    "StructureTerm",
]
