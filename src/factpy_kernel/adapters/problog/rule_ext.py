"""ProbLog adapter-local rule and derivation extensions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factpy_kernel.core.store.types import EngineExtBase


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
) -> ProbLogRuleExt | None:
    """Resolve explicit and legacy ProbLog branch-weight carriers into one typed ext."""
    branch_count = branch_count_for_where(where)
    legacy = normalize_problog_branch_probabilities(
        legacy_body_confidences,
        field_name="body_confidences",
    )
    if legacy is not None and len(legacy) != branch_count:
        raise ValueError("body_confidences length must match where branch count")

    if engine_ext is None:
        return ProbLogRuleExt(branch_probabilities=legacy) if legacy is not None else None

    if not isinstance(engine_ext, ProbLogRuleExt):
        raise ValueError(f"ProbLog engine_ext must be ProbLogRuleExt, got {type(engine_ext).__name__}")

    explicit = materialize_problog_branch_probabilities(
        where=where,
        engine_ext=engine_ext,
    )
    if legacy is None:
        return engine_ext
    if explicit != legacy:
        raise ValueError(
            "Conflicting ProbLog branch probabilities between engine_ext.branch_probabilities and body_confidences"
        )
    return engine_ext


__all__ = [
    "ProbLogRuleExt",
    "branch_count_for_where",
    "materialize_problog_branch_probabilities",
    "normalize_problog_branch_probabilities",
    "resolve_problog_engine_ext",
]
