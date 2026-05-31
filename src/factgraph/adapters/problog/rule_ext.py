"""ProbLog adapter-local rule and derivation extensions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factgraph.core.semantics import SemanticsProfile
from factgraph.core.store.types import EngineExtBase


@dataclass(frozen=True)
class ProbLogRuleExt(EngineExtBase):
    """ProbLog-specific branch weighting for normalized OR branches."""

    branch_probabilities: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        normalized = normalize_problog_branch_probabilities(
            self.branch_probabilities,
            field_name="branch_probabilities",
        )
        object.__setattr__(self, "branch_probabilities", normalized)


def normalize_problog_branch_probabilities(
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


def materialize_problog_branch_probabilities(
    *,
    where: Any,
    engine_ext: ProbLogRuleExt | None,
) -> tuple[float, ...]:
    """Return the effective per-branch probabilities for a compiled where IR."""
    branch_count = branch_count_for_where(where)
    raw = None if engine_ext is None else engine_ext.branch_probabilities
    if raw is None:
        return (1.0,) * branch_count
    if len(raw) != branch_count:
        raise ValueError("engine_ext.branch_probabilities length must match where branch count")
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
    profile = _materialize_profile_branch_probabilities(
        where=where,
        semantics_profile=semantics_profile,
    )
    legacy = normalize_problog_branch_probabilities(
        legacy_body_confidences,
        field_name="body_confidences",
    )
    if legacy is not None and len(legacy) != branch_count:
        raise ValueError("body_confidences length must match where branch count")

    explicit: tuple[float, ...] | None = None
    if engine_ext is not None:
        if not isinstance(engine_ext, ProbLogRuleExt):
            raise ValueError(f"ProbLog engine_ext must be ProbLogRuleExt, got {type(engine_ext).__name__}")
        explicit = materialize_problog_branch_probabilities(
            where=where,
            engine_ext=engine_ext,
        )

    carriers: list[tuple[str, tuple[float, ...]]] = []
    if profile is not None:
        carriers.append(("SemanticsProfile.rule_projection.problog", profile))
    if explicit is not None:
        carriers.append(("ProbLogRuleExt.branch_probabilities", explicit))
    if legacy is not None:
        carriers.append(("legacy_body_confidences", tuple(legacy)))

    if not carriers:
        return None
    _reject_conflicting_carriers(carriers)

    if profile is not None:
        return ProbLogRuleExt(branch_probabilities=profile)
    if engine_ext is not None:
        return engine_ext
    return ProbLogRuleExt(branch_probabilities=tuple(legacy)) if legacy is not None else None


def _materialize_profile_branch_probabilities(
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
    "branch_count_for_where",
    "materialize_problog_branch_probabilities",
    "normalize_problog_branch_probabilities",
    "resolve_problog_engine_ext",
]
