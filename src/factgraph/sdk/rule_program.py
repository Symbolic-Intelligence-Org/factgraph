"""Public value objects for read-only Horn-program evaluation.

A :class:`RuleProgram` is a selected set of application-rule clauses.  It is
evaluated against one existing FactGraph ledger; clauses are never accepted as
assertions and the ledger is never copied.  RuleRef support receipts carry the
multi-layer proof back to the original premise assertion ids.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from factgraph.application.explain import EvidenceGraph
from factgraph.application.protocol.explanation_render import (
    narrate_evidence,
    walk_evidence,
)
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    PredicatePremiseBlock,
)

from .errors import SDKValueError


@dataclass(frozen=True)
class RuleProgramClause:
    """One named Horn clause represented by a FactGraph body/head pair."""

    rule_id: str
    body: Any
    head: Any
    version: str = "1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id:
            raise SDKValueError("RuleProgramClause.rule_id must be a non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise SDKValueError("RuleProgramClause.version must be a non-empty string")


@dataclass(frozen=True)
class RuleProgramFact:
    """A provenance-bearing ground axiom supplied by the selected program.

    Program facts belong to the intensional evaluation input (for example an
    ontology-declared constant), not to the customer ledger.  They are visible
    in native support receipts under ``fact_id`` and never persisted.
    """

    fact_id: str
    predicate: str
    terms: tuple[Any, ...]
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.fact_id, str) or not self.fact_id:
            raise SDKValueError("RuleProgramFact.fact_id must be a non-empty string")
        if not isinstance(self.predicate, str) or not self.predicate:
            raise SDKValueError("RuleProgramFact.predicate must be a non-empty string")
        terms = tuple(self.terms)
        if not terms:
            raise SDKValueError("RuleProgramFact.terms must not be empty")
        if not isinstance(self.provenance, Mapping) or not self.provenance:
            raise SDKValueError("RuleProgramFact.provenance must be a non-empty mapping")
        object.__setattr__(self, "terms", terms)
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


@dataclass(frozen=True)
class RuleProgram:
    """An immutable, explicitly selected Horn-rule program."""

    clauses: tuple[RuleProgramClause, ...]
    facts: tuple[RuleProgramFact, ...] = ()

    def __post_init__(self) -> None:
        clauses = tuple(self.clauses)
        if not clauses:
            raise SDKValueError("RuleProgram.clauses must not be empty")
        if any(not isinstance(clause, RuleProgramClause) for clause in clauses):
            raise SDKValueError("RuleProgram.clauses must contain RuleProgramClause values")
        coordinates = [(clause.rule_id, clause.version) for clause in clauses]
        if len(coordinates) != len(set(coordinates)):
            raise SDKValueError("RuleProgram clause rule_id/version pairs must be unique")
        facts = tuple(self.facts)
        if any(not isinstance(fact, RuleProgramFact) for fact in facts):
            raise SDKValueError("RuleProgram.facts must contain RuleProgramFact values")
        fact_ids = [fact.fact_id for fact in facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise SDKValueError("RuleProgram fact_id values must be unique")
        object.__setattr__(self, "clauses", clauses)
        object.__setattr__(self, "facts", facts)


@dataclass(frozen=True)
class RuleProgramGoal:
    """A closed fact formula whose entailment is queried from a program."""

    predicate: str
    terms: tuple[Any, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.predicate, str) or not self.predicate:
            raise SDKValueError("RuleProgramGoal.predicate must be a non-empty string")
        terms = tuple(self.terms)
        if not terms:
            raise SDKValueError("RuleProgramGoal.terms must not be empty")
        for index, term in enumerate(terms):
            name = getattr(term, "name", None)
            token = getattr(term, "token", None)
            if (
                isinstance(name, str)
                and name.startswith("$")
                or isinstance(token, str)
                and token.startswith("$")
            ):
                raise SDKValueError(
                    f"RuleProgramGoal.terms[{index}] must be closed, not a variable"
                )
        object.__setattr__(self, "terms", terms)


@dataclass(frozen=True)
class EvaluationPremiseScope:
    """Per-evaluation override of the FactGraph premise-admissibility view.

    ``None`` inherits the corresponding configuration from the attached
    FactGraph.  An empty tuple explicitly disables that dimension for this one
    evaluation.  No runtime-global filter is mutated.
    """

    exclusions: tuple[MetaExclusion, ...] | None = None
    allowances: tuple[PredicatePremiseAllowance, ...] | None = None
    blocks: tuple[PredicatePremiseBlock, ...] | None = None

    def __post_init__(self) -> None:
        for field_name, expected in (
            ("exclusions", MetaExclusion),
            ("allowances", PredicatePremiseAllowance),
            ("blocks", PredicatePremiseBlock),
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            normalized = tuple(value)
            if any(not isinstance(item, expected) for item in normalized):
                raise SDKValueError(
                    f"EvaluationPremiseScope.{field_name} contains an invalid value"
                )
            object.__setattr__(self, field_name, normalized)


@dataclass(frozen=True)
class RuleProgramExplanation:
    """Canonical evidence plus recursive native support for one program check."""

    status: str
    failure_class: str | None
    root_support_digest: str | None
    steps: tuple[dict[str, Any], ...]
    checked_scope: dict[str, Any]
    evidence: EvidenceGraph

    @property
    def repr(self) -> tuple[str, ...]:
        """Return a deterministic structural walk of the EvidenceGraph.

        Returns:
            Stable presentation lines derived from structured evidence.
        """

        return walk_evidence(
            self.evidence,
            status=self.status,
            failure_class=self.failure_class,
        )

    def narrate(self) -> tuple[str, ...]:
        """Render this evidence through FactGraph's canonical narrator.

        Returns:
            Human-readable lines derived from structured evidence.
        """

        return narrate_evidence(
            self.evidence,
            status=self.status,
            failure_class=self.failure_class,
        )


@dataclass(frozen=True)
class RuleProgramResult:
    """Result of evaluating one closed goal against one selected rule program."""

    entailed: bool
    goal: RuleProgramGoal
    engine: str
    evaluated_at: datetime
    effective_rule_ids: tuple[str, ...]
    matched_rule_ids: tuple[str, ...]
    rule_set_digest: str
    view_snapshot_digest: str
    premise_scope_digest: str
    program_facts: tuple[RuleProgramFact, ...] = ()
    support_digest: str | None = None
    _evidence: EvidenceGraph | None = field(
        repr=False,
        compare=False,
        default=None,
    )
    _support_steps: tuple[dict[str, Any], ...] = field(
        repr=False,
        compare=False,
        default=(),
    )

    def explain(self) -> RuleProgramExplanation:
        """Return immutable evidence and support captured by this evaluation.

        Returns:
            A passed or failed Rule-program explanation.

        Raises:
            SDKValueError: If this result carries no canonical EvidenceGraph.

        Notes:
            Explain reads captured support only and does not rerun the program.
        """

        if self._evidence is None:
            raise SDKValueError("RuleProgramResult has no canonical EvidenceGraph")
        checked_scope = {
            "engine": self.engine,
            "effective_rule_ids": list(self.effective_rule_ids),
            "premise_scope_digest": self.premise_scope_digest,
            "rule_set_digest": self.rule_set_digest,
            "view_snapshot_digest": self.view_snapshot_digest,
        }
        if not self.entailed or self.support_digest is None:
            return RuleProgramExplanation(
                status="failed",
                failure_class="closed_goal_not_entailed",
                root_support_digest=None,
                steps=(),
                checked_scope=checked_scope,
                evidence=self._evidence,
            )

        return RuleProgramExplanation(
            status="passed",
            failure_class=None,
            root_support_digest=self.support_digest,
            steps=self._support_steps,
            checked_scope=checked_scope,
            evidence=self._evidence,
        )


__all__ = [
    "EvaluationPremiseScope",
    "RuleProgram",
    "RuleProgramClause",
    "RuleProgramExplanation",
    "RuleProgramFact",
    "RuleProgramGoal",
    "RuleProgramResult",
]
