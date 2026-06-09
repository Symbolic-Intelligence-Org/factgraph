from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field as dc_field
from typing import Any, Literal, TypeAlias
from types import MappingProxyType

from factgraph.application.protocol.certainty import BOOLEAN_CERTAINTY, Certainty


TreeStatus = Literal["holds", "fails", "not_reached"]
RuleRole = Literal["head", "body"]
LayoutHint = Literal["tree", "timeline"]

LAYOUT_TREE: LayoutHint = "tree"
LAYOUT_TIMELINE: LayoutHint = "timeline"


@dataclass(frozen=True)
class BoundVar:
    name: str
    value: Any = None
    bound_by: str | None = None


@dataclass(frozen=True)
class Const:
    value: Any


@dataclass(frozen=True)
class Source:
    ref: str
    field: str | None = None
    value: Any = None
    meta: Mapping[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "meta", MappingProxyType(dict(self.meta)))


@dataclass(frozen=True)
class PortRef:
    rule_occurrence_alias: str
    port_name: str


@dataclass(frozen=True)
class Fact:
    predicate: str
    terms: tuple[BoundVar | Const, ...]


@dataclass(frozen=True)
class Compare:
    op: str
    left: BoundVar | Const
    right: BoundVar | Const


@dataclass(frozen=True)
class Builtin:
    kind: str
    operands: tuple[BoundVar | Const, ...]


@dataclass(frozen=True)
class Aggregate:
    kind: str
    body_terms: tuple[BoundVar | Const, ...] = ()
    head_terms: tuple[BoundVar | Const, ...] = ()


AtomForm: TypeAlias = Fact | Compare | Builtin | Aggregate


@dataclass(frozen=True)
class Holds:
    certainty: Certainty = BOOLEAN_CERTAINTY
    support: tuple[Source, ...] = ()


@dataclass(frozen=True)
class Fails:
    certainty: Certainty = BOOLEAN_CERTAINTY


@dataclass(frozen=True)
class NotReached:
    blocked_by: str | None = None


Verdict: TypeAlias = Holds | Fails | NotReached


@dataclass(frozen=True)
class EvidenceAtom:
    form: AtomForm
    verdict: Verdict
    atom_id: str
    repr_text: str | None = None
    negated: bool = False
    timestep: int | None = None


@dataclass(frozen=True)
class EvidenceJoin:
    left: PortRef
    right: PortRef
    status: TreeStatus
    join_id: str


@dataclass(frozen=True)
class EvidenceRule:
    occurrence_alias: str
    rule_id: str
    role: RuleRole
    status: TreeStatus
    ports: Mapping[str, Any] = dc_field(default_factory=dict)
    atoms: tuple[EvidenceAtom, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ports", MappingProxyType(dict(self.ports)))


@dataclass(frozen=True)
class EvidenceTree:
    tree_id: str
    status: TreeStatus
    rules: tuple[EvidenceRule, ...]
    joins: tuple[EvidenceJoin, ...] = ()
    certainty: Certainty | None = BOOLEAN_CERTAINTY
    metadata: Mapping[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class EvidenceTimeline:
    timeline_id: str
    status: TreeStatus
    events: tuple[Any, ...] = ()
    certainty: Certainty | None = None
    metadata: Mapping[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class EvidenceGraph:
    graph_id: str
    engine: str
    layout_hint: LayoutHint
    subject_binding: Mapping[str, Any]
    paths: tuple[EvidenceTree | EvidenceTimeline, ...]
    certainty: Certainty | None = BOOLEAN_CERTAINTY
    metadata: Mapping[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject_binding", MappingProxyType(dict(self.subject_binding)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class EvidenceProbeResult:
    paths: tuple[EvidenceTree, ...]
    certainty: Certainty | None = BOOLEAN_CERTAINTY


__all__ = [
    "Aggregate",
    "AtomForm",
    "BOOLEAN_CERTAINTY",
    "BoundVar",
    "Builtin",
    "Certainty",
    "Compare",
    "Const",
    "EvidenceAtom",
    "EvidenceGraph",
    "EvidenceJoin",
    "EvidenceProbeResult",
    "EvidenceRule",
    "EvidenceTimeline",
    "EvidenceTree",
    "Fact",
    "Fails",
    "Holds",
    "LAYOUT_TIMELINE",
    "LAYOUT_TREE",
    "LayoutHint",
    "NotReached",
    "PortRef",
    "RuleRole",
    "Source",
    "TreeStatus",
    "Verdict",
]
