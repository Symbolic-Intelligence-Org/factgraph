"""ProbLog adapter-local rule and derivation extensions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

from factgraph.core.semantics import SemanticsProfile
from factgraph.core.store.types import EngineExtBase

_CANONICAL_DECIMAL_RE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_MAX_WEIGHTED_CHOICE_PROBABILITY_CHARS = 32
_MAX_WEIGHTED_CHOICE_PROBABILITY_SCALE = 18


class ProbLogWeightedChoiceError(ValueError):
    """Fail-closed rejection for the V2 annotated-disjunction seam."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _choice_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProbLogWeightedChoiceError(
            f"{field_name} must be a non-empty string",
            code="PROBLOG_WEIGHTED_CHOICE_INVALID_SHAPE",
        )
    return value


def _canonical_choice_probability(value: object, *, field_name: str) -> str:
    """Validate the product topology's exact decimal wire representation."""

    if (
        type(value) is not str
        or len(value) > _MAX_WEIGHTED_CHOICE_PROBABILITY_CHARS
        or not _CANONICAL_DECIMAL_RE.fullmatch(value)
    ):
        raise ProbLogWeightedChoiceError(
            f"{field_name} must be a canonical non-exponent decimal string",
            code="PROBLOG_WEIGHTED_CHOICE_INVALID_PROBABILITY",
        )
    if "." in value and value.endswith("0"):
        raise ProbLogWeightedChoiceError(
            f"{field_name} must not have trailing decimal zeroes",
            code="PROBLOG_WEIGHTED_CHOICE_NONCANONICAL_PROBABILITY",
        )
    if len(value.partition(".")[2]) > _MAX_WEIGHTED_CHOICE_PROBABILITY_SCALE:
        raise ProbLogWeightedChoiceError(
            f"{field_name} exceeds the bounded decimal scale",
            code="PROBLOG_WEIGHTED_CHOICE_INVALID_PROBABILITY",
        )
    try:
        decimal = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - regex already excludes this.
        raise ProbLogWeightedChoiceError(
            f"{field_name} is not a decimal",
            code="PROBLOG_WEIGHTED_CHOICE_INVALID_PROBABILITY",
        ) from exc
    if not (Decimal(0) < decimal <= Decimal(1)):
        raise ProbLogWeightedChoiceError(
            f"{field_name} must be in (0, 1]",
            code="PROBLOG_WEIGHTED_CHOICE_INVALID_PROBABILITY",
        )
    return value


@dataclass(frozen=True, order=True)
class ProbLogWeightedChoiceArm:
    """One arm in one exact ProbLog annotated disjunction."""

    arm_id: str
    probability: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "arm_id", _choice_text(self.arm_id, field_name="arm_id"))
        object.__setattr__(
            self,
            "probability",
            _canonical_choice_probability(self.probability, field_name="probability"),
        )


@dataclass(frozen=True, order=True)
class ProbLogWeightedChoiceBranch:
    """One compiled DNF branch selected by exactly one choice arm."""

    branch_index: int
    arm_id: str
    key_variables: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.branch_index, int)
            or isinstance(self.branch_index, bool)
            or self.branch_index < 0
        ):
            raise ProbLogWeightedChoiceError(
                "branch_index must be a non-negative integer",
                code="PROBLOG_WEIGHTED_CHOICE_INVALID_BRANCH",
            )
        object.__setattr__(self, "arm_id", _choice_text(self.arm_id, field_name="arm_id"))
        if (
            not isinstance(self.key_variables, tuple)
            or not self.key_variables
            or not all(
                isinstance(name, str) and name.startswith("$") and len(name) > 1
                for name in self.key_variables
            )
        ):
            raise ProbLogWeightedChoiceError(
                "key_variables must be a non-empty tuple of compiled '$' variable names",
                code="PROBLOG_WEIGHTED_CHOICE_INVALID_SELECTION_KEY",
            )


@dataclass(frozen=True)
class ProbLogWeightedChoiceExt:
    """One V2-only exclusive choice lowered as a ProbLog annotated disjunction.

    ``branches`` uses *compiled* DNF branch indexes, not authored arm order.
    Each branch is mapped to exactly one arm.  A copied Policy occurrence may
    have different local variable names in different DNF branches, so the
    extension carries an explicit canonical ``domain_body`` and corresponding
    ``domain_key_variables``.  The exporter emits one annotated disjunction;
    it never turns these arm probabilities into independent ``rule_body_N``
    weights.
    """

    choice_id: str
    choice_node_id: str
    topology_digest: str
    arms: tuple[ProbLogWeightedChoiceArm, ...]
    branches: tuple[ProbLogWeightedChoiceBranch, ...]
    domain_key_variables: tuple[str, ...]
    domain_body: tuple[Any, ...]

    def __post_init__(self) -> None:
        for name in ("choice_id", "choice_node_id", "topology_digest"):
            object.__setattr__(self, name, _choice_text(getattr(self, name), field_name=name))
        if not isinstance(self.arms, tuple) or len(self.arms) < 2 or not all(
            isinstance(arm, ProbLogWeightedChoiceArm) for arm in self.arms
        ):
            raise ProbLogWeightedChoiceError(
                "arms must be a tuple of at least two ProbLogWeightedChoiceArm values",
                code="PROBLOG_WEIGHTED_CHOICE_INVALID_ARMS",
            )
        ordered_arms = tuple(sorted(self.arms, key=lambda arm: arm.arm_id))
        if ordered_arms != self.arms or len({arm.arm_id for arm in ordered_arms}) != len(ordered_arms):
            raise ProbLogWeightedChoiceError(
                "arms must be uniquely identified and canonical by arm_id",
                code="PROBLOG_WEIGHTED_CHOICE_INVALID_ARMS",
            )
        with localcontext() as context:
            context.prec = 128
            total = sum((Decimal(arm.probability) for arm in ordered_arms), Decimal(0))
        if total != Decimal(1):
            raise ProbLogWeightedChoiceError(
                "exclusive annotated-disjunction arm probabilities must sum exactly to 1",
                code="PROBLOG_WEIGHTED_CHOICE_PROBABILITY_TOTAL",
            )
        if not isinstance(self.branches, tuple) or not self.branches or not all(
            isinstance(branch, ProbLogWeightedChoiceBranch) for branch in self.branches
        ):
            raise ProbLogWeightedChoiceError(
                "branches must be a non-empty tuple of ProbLogWeightedChoiceBranch values",
                code="PROBLOG_WEIGHTED_CHOICE_INVALID_BRANCH",
            )
        ordered_branches = tuple(sorted(self.branches, key=lambda branch: branch.branch_index))
        if ordered_branches != self.branches or len(
            {branch.branch_index for branch in ordered_branches}
        ) != len(ordered_branches):
            raise ProbLogWeightedChoiceError(
                "branches must be uniquely indexed and canonical",
                code="PROBLOG_WEIGHTED_CHOICE_INVALID_BRANCH",
            )
        arm_ids = {arm.arm_id for arm in ordered_arms}
        branch_arm_ids = {branch.arm_id for branch in ordered_branches}
        if branch_arm_ids != arm_ids or len(ordered_branches) != len(ordered_arms):
            raise ProbLogWeightedChoiceError(
                "each exclusive arm must map to exactly one compiled branch",
                code="PROBLOG_WEIGHTED_CHOICE_UNMAPPED_ARM",
            )
        if len({branch.arm_id for branch in ordered_branches}) != len(ordered_branches):
            raise ProbLogWeightedChoiceError(
                "one compiled branch is required per exclusive arm",
                code="PROBLOG_WEIGHTED_CHOICE_NESTED_OR_UNSUPPORTED",
            )
        if (
            not isinstance(self.domain_key_variables, tuple)
            or not self.domain_key_variables
            or not all(
                isinstance(name, str) and name.startswith("$") and len(name) > 1
                for name in self.domain_key_variables
            )
        ):
            raise ProbLogWeightedChoiceError(
                "domain_key_variables must be a non-empty tuple of '$' variable names",
                code="PROBLOG_WEIGHTED_CHOICE_INVALID_SELECTION_KEY",
            )
        if (
            not isinstance(self.domain_body, tuple)
            or not self.domain_body
            or any(not isinstance(atom, tuple) for atom in self.domain_body)
        ):
            raise ProbLogWeightedChoiceError(
                "domain_body must be a non-empty tuple of compiled where atoms",
                code="PROBLOG_WEIGHTED_CHOICE_INVALID_DOMAIN",
            )
        if any(
            len(branch.key_variables) != len(self.domain_key_variables)
            for branch in ordered_branches
        ):
            raise ProbLogWeightedChoiceError(
                "each branch key must have the same arity as domain_key_variables",
                code="PROBLOG_WEIGHTED_CHOICE_KEY_VARIABLE_DIVERGENCE",
            )
        object.__setattr__(self, "arms", ordered_arms)
        object.__setattr__(self, "branches", ordered_branches)


@dataclass(frozen=True)
class ProbLogRuleExt(EngineExtBase):
    """ProbLog-specific branch weighting or one V2 annotated disjunction.

    The two channels are deliberately exclusive.  ``case_probabilities`` are
    historical independent OR-branch weights; ``weighted_choice`` is a
    categorical shared-choice relation and must not be silently flattened to
    that legacy meaning.
    """

    case_probabilities: tuple[float, ...] | None = None
    weighted_choice: ProbLogWeightedChoiceExt | None = None

    def __post_init__(self) -> None:
        normalized = normalize_problog_case_probabilities(
            self.case_probabilities,
            field_name="case_probabilities",
        )
        if self.weighted_choice is not None and not isinstance(
            self.weighted_choice, ProbLogWeightedChoiceExt
        ):
            raise ProbLogWeightedChoiceError(
                "weighted_choice must be ProbLogWeightedChoiceExt or None",
                code="PROBLOG_WEIGHTED_CHOICE_INVALID_SHAPE",
            )
        if normalized is not None and self.weighted_choice is not None:
            raise ProbLogWeightedChoiceError(
                "annotated-disjunction choices cannot combine with independent branch probabilities",
                code="PROBLOG_WEIGHTED_CHOICE_CONFLICTING_WEIGHT_CARRIERS",
            )
        object.__setattr__(self, "case_probabilities", normalized)


def normalize_problog_case_probabilities(
    raw: Any,
    *,
    field_name: str,
) -> tuple[float, ...] | None:
    """Normalize branch probabilities to a validated tuple."""
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError(f"{field_name} must be non-empty list/tuple of float in (0,1] when provided")

    out: list[float] = []
    for idx, value in enumerate(raw):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field_name}[{idx}] must be float in (0,1]")
        normalized = float(value)
        if normalized <= 0.0 or normalized > 1.0:
            raise ValueError(f"{field_name}[{idx}] must be within (0,1]")
        out.append(normalized)
    return tuple(out)


def branch_count_for_where(where: Any) -> int:
    """Return the normalized OR-branch count for a compiled where IR."""
    if not isinstance(where, list) or not where:
        raise ValueError("where must be non-empty list")
    if all(isinstance(item, list) for item in where):
        return len(where)
    return 1


def materialize_problog_case_probabilities(
    *,
    where: Any,
    engine_ext: ProbLogRuleExt | None,
) -> tuple[float, ...]:
    """Return the effective per-branch probabilities for a compiled where IR."""
    branch_count = branch_count_for_where(where)
    if engine_ext is not None and engine_ext.weighted_choice is not None:
        raise ProbLogWeightedChoiceError(
            "annotated-disjunction choices cannot be materialized as independent branch probabilities",
            code="PROBLOG_WEIGHTED_CHOICE_NOT_INDEPENDENT",
        )
    raw = None if engine_ext is None else engine_ext.case_probabilities
    if raw is None:
        return (1.0,) * branch_count
    if len(raw) != branch_count:
        raise ValueError("engine_ext.case_probabilities length must match where branch count")
    return tuple(raw)


def resolve_problog_engine_ext(
    *,
    where: Any,
    engine_ext: EngineExtBase | None,
    legacy_body_confidences: Any = None,
    semantics_profile: SemanticsProfile | None = None,
) -> ProbLogRuleExt | None:
    """Resolve explicit, legacy, and profile ProbLog branch-weight carriers."""
    branch_count = branch_count_for_where(where)
    profile = _materialize_profile_case_probabilities(
        where=where,
        semantics_profile=semantics_profile,
    )
    legacy = normalize_problog_case_probabilities(
        legacy_body_confidences,
        field_name="body_confidences",
    )
    if legacy is not None and len(legacy) != branch_count:
        raise ValueError("body_confidences length must match where branch count")

    if engine_ext is not None and not isinstance(engine_ext, ProbLogRuleExt):
        raise ValueError(f"ProbLog engine_ext must be ProbLogRuleExt, got {type(engine_ext).__name__}")

    # Do not let the old profile/legacy channels turn a sealed categorical
    # choice into independent rule-body weights.  This guard intentionally
    # lives before all materialization of those legacy carriers.
    if engine_ext is not None and engine_ext.weighted_choice is not None:
        if profile is not None or legacy is not None:
            raise ProbLogWeightedChoiceError(
                "annotated-disjunction choices cannot combine with profile or legacy branch probabilities",
                code="PROBLOG_WEIGHTED_CHOICE_CONFLICTING_WEIGHT_CARRIERS",
            )
        return engine_ext

    explicit: tuple[float, ...] | None = None
    if engine_ext is not None:
        explicit = materialize_problog_case_probabilities(
            where=where,
            engine_ext=engine_ext,
        )

    carriers: list[tuple[str, tuple[float, ...]]] = []
    if profile is not None:
        carriers.append(("SemanticsProfile.rule_projection.problog", profile))
    if explicit is not None:
        carriers.append(("ProbLogRuleExt.case_probabilities", explicit))
    if legacy is not None:
        carriers.append(("legacy_body_confidences", tuple(legacy)))

    if not carriers:
        return None
    _reject_conflicting_carriers(carriers)

    if profile is not None:
        return ProbLogRuleExt(case_probabilities=profile)
    if engine_ext is not None:
        return engine_ext
    return ProbLogRuleExt(case_probabilities=tuple(legacy)) if legacy is not None else None


def _materialize_profile_case_probabilities(
    *,
    where: Any,
    semantics_profile: SemanticsProfile | None,
) -> tuple[float, ...] | None:
    if semantics_profile is None:
        return None
    if not isinstance(semantics_profile, SemanticsProfile):
        raise ValueError(
            f"semantics_profile must be SemanticsProfile or None, got {type(semantics_profile).__name__}"
        )
    if semantics_profile.engine != "problog":
        raise ValueError(
            f"ProbLog consumption expected SemanticsProfile.engine='problog', got {semantics_profile.engine!r}"
        )

    entries = semantics_profile.rule_projection.get("problog", [])
    if not entries:
        return None

    branch_count = branch_count_for_where(where)
    probabilities = [1.0] * branch_count
    seen_targets: set[int] = set()
    for idx, entry in enumerate(entries):
        kind = entry.get("kind")
        if kind != "branch_probability":
            raise ValueError(
                f"rule_projection.problog[{idx}].kind must be branch_probability"
            )
        case_index = _parse_profile_branch_target(entry.get("target"), entry_index=idx)
        if case_index in seen_targets:
            raise ValueError(f"duplicate rule_projection.problog target branch:{case_index}")
        if case_index < 0 or case_index >= branch_count:
            raise ValueError(
                f"rule_projection.problog[{idx}] case index {case_index} out of range for {branch_count} branches"
            )
        probabilities[case_index] = _normalize_profile_probability(
            entry.get("value"),
            entry_index=idx,
        )
        seen_targets.add(case_index)
    return tuple(probabilities)


def _parse_profile_branch_target(raw: Any, *, entry_index: int) -> int:
    if not isinstance(raw, str) or not raw.startswith("branch:"):
        raise ValueError(
            f"rule_projection.problog[{entry_index}].target must use branch:{{index}}"
        )
    suffix = raw.removeprefix("branch:")
    try:
        return int(suffix)
    except ValueError as exc:
        raise ValueError(
            f"rule_projection.problog[{entry_index}].target must use branch:{{index}}"
        ) from exc


def _normalize_profile_probability(raw: Any, *, entry_index: int) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(
            f"rule_projection.problog[{entry_index}].value must be float in (0,1]"
        )
    value = float(raw)
    if value <= 0.0 or value > 1.0:
        raise ValueError(
            f"rule_projection.problog[{entry_index}].value must be float in (0,1]"
        )
    return value


def _reject_conflicting_carriers(carriers: list[tuple[str, tuple[float, ...]]]) -> None:
    _, baseline = carriers[0]
    for _name, probabilities in carriers[1:]:
        if probabilities != baseline:
            carrier_names = " and ".join(carrier_name for carrier_name, _ in carriers)
            raise ValueError(
                f"Conflicting ProbLog branch probabilities between {carrier_names}"
            )


__all__ = [
    "ProbLogRuleExt",
    "ProbLogWeightedChoiceArm",
    "ProbLogWeightedChoiceBranch",
    "ProbLogWeightedChoiceError",
    "ProbLogWeightedChoiceExt",
    "branch_count_for_where",
    "materialize_problog_case_probabilities",
    "normalize_problog_case_probabilities",
    "resolve_problog_engine_ext",
]
