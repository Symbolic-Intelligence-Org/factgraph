from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypeAlias

from factgraph.core.rules.where_ast import Const, Var


class DiagnosticProjectionError(Exception):
    pass


@dataclass(frozen=True)
class Wildcard:
    name: str = "_"


CompanionTerm: TypeAlias = Const | Var | Wildcard


@dataclass(frozen=True)
class CompanionLiteral:
    pred_id: str
    terms: tuple[CompanionTerm, ...]
    negated: bool = False


@dataclass(frozen=True)
class CompanionCompare:
    op: str
    lhs: CompanionTerm
    rhs: CompanionTerm
    negated: bool = False


CompanionAtom: TypeAlias = CompanionLiteral | CompanionCompare


@dataclass(frozen=True)
class CompanionWitness:
    terms: tuple[CompanionTerm, ...]


@dataclass(frozen=True)
class CompanionNotReached:
    var: str


@dataclass(frozen=True)
class CompanionAtomRules:
    branch_id: str
    atom_index: int
    holds_body: tuple[CompanionAtom, ...]
    fails_body: tuple[CompanionAtom, ...]
    not_reached: tuple[CompanionNotReached, ...]
    witness: CompanionWitness | None = None


@dataclass(frozen=True)
class BranchCompanion:
    branch_id: str
    atoms: tuple[CompanionAtomRules, ...]
    branch_body: tuple[CompanionAtom, ...]
    occ_bodies: Mapping[str, tuple[CompanionAtom, ...]]
    bound_defs: Mapping[str, tuple[CompanionAtom, ...]]
    head_body: tuple[CompanionAtom, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "occ_bodies", MappingProxyType(dict(self.occ_bodies)))
        object.__setattr__(self, "bound_defs", MappingProxyType(dict(self.bound_defs)))


@dataclass(frozen=True)
class CompanionProgram:
    anchor: Mapping[str, Const]
    branches: tuple[BranchCompanion, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchor", MappingProxyType(dict(self.anchor)))


__all__ = [
    "BranchCompanion",
    "CompanionAtom",
    "CompanionAtomRules",
    "CompanionCompare",
    "CompanionLiteral",
    "CompanionNotReached",
    "CompanionProgram",
    "CompanionTerm",
    "CompanionWitness",
    "DiagnosticProjectionError",
    "Wildcard",
]
