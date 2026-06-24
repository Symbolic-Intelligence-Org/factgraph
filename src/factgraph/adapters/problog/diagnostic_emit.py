"""Shared diagnostic result records for engine reach-chain explain."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class DiagnosticProbLogError(Exception):
    pass


@dataclass(frozen=True)
class DiagnosticAtomProbability:
    branch_id: str
    atom_index: int
    verdict: str
    probability: float
    blocked_by: str | None = None


@dataclass(frozen=True)
class DiagnosticWitnessProbability:
    branch_id: str
    atom_index: int
    terms: tuple[Any, ...]
    probability: float


@dataclass(frozen=True)
class DiagnosticProbLogResult:
    atom_probabilities: tuple[DiagnosticAtomProbability, ...] = ()
    witnesses: tuple[DiagnosticWitnessProbability, ...] = ()
    branch_probabilities: Mapping[str, float] = field(default_factory=dict)
    occurrence_probabilities: Mapping[tuple[str, str], float] = field(default_factory=dict)
    head_probabilities: Mapping[str, float] = field(default_factory=dict)


__all__ = [
    "DiagnosticAtomProbability",
    "DiagnosticProbLogError",
    "DiagnosticProbLogResult",
    "DiagnosticWitnessProbability",
]
