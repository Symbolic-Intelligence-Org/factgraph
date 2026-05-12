from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .errors import SDKStoreError


def _copy_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SDKStoreError(f"{field_name} must be dict when provided")
    return dict(value)


def _normalize_probability_map(value: Any, *, field_name: str) -> dict[str, float]:
    raw = _copy_mapping(value, field_name=field_name)
    out: dict[str, float] = {}
    for key, raw_value in raw.items():
        if not isinstance(key, str) or not key:
            raise SDKStoreError(f"{field_name} keys must be non-empty branch ids")
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise SDKStoreError(f"{field_name}[{key!r}] must be float in (0,1]")
        probability = float(raw_value)
        if probability <= 0.0 or probability > 1.0:
            raise SDKStoreError(f"{field_name}[{key!r}] must be within (0,1]")
        out[key] = probability
    return out


def _normalize_interval(value: Any, *, field_name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise SDKStoreError(f"{field_name} must be [lower, upper]")
    lower_raw, upper_raw = value
    if isinstance(lower_raw, bool) or not isinstance(lower_raw, (int, float)):
        raise SDKStoreError(f"{field_name}[0] must be numeric")
    if isinstance(upper_raw, bool) or not isinstance(upper_raw, (int, float)):
        raise SDKStoreError(f"{field_name}[1] must be numeric")
    lower = float(lower_raw)
    upper = float(upper_raw)
    if not 0.0 <= lower <= upper <= 1.0:
        raise SDKStoreError(f"{field_name} must satisfy 0 <= lower <= upper <= 1")
    return (lower, upper)


@dataclass(frozen=True)
class ProbLogSemantics:
    branch_probabilities: dict[str, float] = field(default_factory=dict)
    name: str | None = None
    fallback: str = "reject_unconfigured"

    @property
    def engine(self) -> str:
        return "problog"

    def __post_init__(self) -> None:
        if self.name is not None and (not isinstance(self.name, str) or not self.name):
            raise SDKStoreError("ProbLogSemantics.name must be non-empty string when provided")
        if not isinstance(self.fallback, str) or not self.fallback:
            raise SDKStoreError("ProbLogSemantics.fallback must be non-empty string")
        object.__setattr__(
            self,
            "branch_probabilities",
            _normalize_probability_map(self.branch_probabilities, field_name="branch_probabilities"),
        )


@dataclass(frozen=True)
class PyReasonSemantics:
    timestep_delay: int = 0
    head_bound: tuple[float, float] | None = None
    temporal_projection: dict[str, Any] = field(default_factory=lambda: {"mode": "none"})
    uncertainty_projection: dict[str, Any] = field(default_factory=dict)
    name: str | None = None
    fallback: str = "reject_unconfigured"

    @property
    def engine(self) -> str:
        return "pyreason"

    def __post_init__(self) -> None:
        if self.name is not None and (not isinstance(self.name, str) or not self.name):
            raise SDKStoreError("PyReasonSemantics.name must be non-empty string when provided")
        if isinstance(self.timestep_delay, bool) or not isinstance(self.timestep_delay, int):
            raise SDKStoreError("PyReasonSemantics.timestep_delay must be int")
        if self.timestep_delay < 0:
            raise SDKStoreError("PyReasonSemantics.timestep_delay must be >= 0")
        if not isinstance(self.fallback, str) or not self.fallback:
            raise SDKStoreError("PyReasonSemantics.fallback must be non-empty string")
        head_bound = None if self.head_bound is None else _normalize_interval(self.head_bound, field_name="head_bound")
        object.__setattr__(self, "head_bound", head_bound)
        object.__setattr__(
            self,
            "temporal_projection",
            _copy_mapping(self.temporal_projection, field_name="temporal_projection"),
        )
        object.__setattr__(
            self,
            "uncertainty_projection",
            _copy_mapping(self.uncertainty_projection, field_name="uncertainty_projection"),
        )


__all__ = ["ProbLogSemantics", "PyReasonSemantics"]
