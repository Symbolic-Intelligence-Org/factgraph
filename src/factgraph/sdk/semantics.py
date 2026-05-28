from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from factgraph.core.semantics import SemanticsProfile

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


def _normalize_interval_map(value: Any, *, field_name: str) -> dict[str, tuple[float, float]]:
    raw = _copy_mapping(value, field_name=field_name)
    out: dict[str, tuple[float, float]] = {}
    for key, raw_value in raw.items():
        if not isinstance(key, str) or not key:
            raise SDKStoreError(f"{field_name} keys must be non-empty branch ids")
        try:
            out[key] = _normalize_interval(raw_value, field_name=f"{field_name}[{key!r}]")
        except SDKStoreError as exc:
            raise SDKStoreError(f"{field_name}[{key!r}] value must be [lower, upper]") from exc
    return out


def _normalize_rule_params_map(value: Any, *, field_name: str) -> dict[str, dict[str, Any]]:
    raw = _copy_mapping(value, field_name=field_name)
    out: dict[str, dict[str, Any]] = {}
    for key, raw_value in raw.items():
        if not isinstance(key, str) or not key:
            raise SDKStoreError(f"{field_name} keys must be non-empty Rule ids")
        if not isinstance(raw_value, Mapping):
            raise SDKStoreError(f"{field_name}[{key!r}] must be an object")
        out[key] = dict(raw_value)
    return out


def _default_problog_uncertainty_projection() -> dict[str, Any]:
    return {
        "probabilistic": {"policy": "reject"},
        "possibilistic": {"policy": "reject"},
        "fallback": "reject_unconfigured",
    }


def _normalize_uncertainty_projection_map(value: Any, *, field_name: str) -> dict[str, Any]:
    raw = _copy_mapping(value, field_name=field_name)
    try:
        profile = SemanticsProfile(
            name="_sdk_probe",
            engine="problog",
            uncertainty_projection=raw,
        )
    except ValueError as exc:
        raise SDKStoreError(str(exc)) from exc
    return dict(profile.uncertainty_projection)


@dataclass(frozen=True)
class ProbLogSemantics:
    """Public ProbLog semantics wrapper for Rule or Inference evaluation.

    Pass to `fg.eval.evaluate(application_rule_or_inference, semantics=...)` to
    configure ProbLog semantics without constructing a raw `SemanticsProfile`.
    The SDK derives `engine="problog"` from this wrapper.

    Args:
        branch_probabilities: Mapping from branch id to probability in `(0, 1]`.
        rule_params: Per-Rule metadata keyed by application `Rule.id`; lowered
            into canonical `SemanticsProfile.rule_projection` for future
            adapter cycles.
        uncertainty_projection: Raw uncertainty projection policy mapping,
            using the same schema as `SemanticsProfile.uncertainty_projection`.
        name: Optional profile name used in the lowered canonical profile.
        fallback: Policy for unconfigured semantics.
    """

    branch_probabilities: dict[str, float] = field(default_factory=dict)
    rule_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    uncertainty_projection: dict[str, Any] = field(default_factory=_default_problog_uncertainty_projection)
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
        object.__setattr__(
            self,
            "rule_params",
            _normalize_rule_params_map(self.rule_params, field_name="rule_params"),
        )
        object.__setattr__(
            self,
            "uncertainty_projection",
            _normalize_uncertainty_projection_map(
                self.uncertainty_projection,
                field_name="uncertainty_projection",
            ),
        )


@dataclass(frozen=True)
class PyReasonSemantics:
    """Public PyReason semantics wrapper for Rule or Inference evaluation.

    Pass to `fg.eval.evaluate(application_rule_or_inference, semantics=...)` to
    configure PyReason time delay and interval bounds. The SDK derives
    `engine="pyreason"` from this wrapper.

    Args:
        timestep_delay: Non-negative timestep delay for compiled rules.
        iteration_count: Positive global PyReason inference round count.
        head_bound: Optional global `[lower, upper]` interval for rule heads.
        branch_bounds: Optional per-branch interval overrides keyed by branch id.
        rule_params: Per-Rule metadata keyed by application `Rule.id`; lowered
            into canonical `SemanticsProfile.rule_projection` for future
            adapter cycles.
    """

    timestep_delay: int = 0
    iteration_count: int = 1
    head_bound: tuple[float, float] | None = None
    branch_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    rule_params: dict[str, dict[str, Any]] = field(default_factory=dict)
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
        if isinstance(self.iteration_count, bool) or not isinstance(self.iteration_count, int):
            raise SDKStoreError("PyReasonSemantics.iteration_count must be int")
        if self.iteration_count < 1:
            raise SDKStoreError("PyReasonSemantics.iteration_count must be >= 1")
        if not isinstance(self.fallback, str) or not self.fallback:
            raise SDKStoreError("PyReasonSemantics.fallback must be non-empty string")
        head_bound = None if self.head_bound is None else _normalize_interval(self.head_bound, field_name="head_bound")
        object.__setattr__(self, "head_bound", head_bound)
        object.__setattr__(
            self,
            "branch_bounds",
            _normalize_interval_map(self.branch_bounds, field_name="branch_bounds"),
        )
        object.__setattr__(
            self,
            "rule_params",
            _normalize_rule_params_map(self.rule_params, field_name="rule_params"),
        )
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
