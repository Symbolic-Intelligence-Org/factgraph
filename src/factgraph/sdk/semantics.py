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


def _normalize_atom_interval_map(value: Any, *, field_name: str) -> dict[str, tuple[float, float]]:
    raw = _copy_mapping(value, field_name=field_name)
    out: dict[str, tuple[float, float]] = {}
    for key, raw_value in raw.items():
        if not isinstance(key, str) or not key:
            raise SDKStoreError(f"{field_name} keys must be non-empty atom ids")
        _require_canonical_atom_id(key, field_name=field_name)
        try:
            out[key] = _normalize_interval(raw_value, field_name=f"{field_name}[{key!r}]")
        except SDKStoreError as exc:
            raise SDKStoreError(f"{field_name}[{key!r}] value must be [lower, upper]") from exc
    return out


def _require_canonical_atom_id(value: str, *, field_name: str) -> None:
    rule_id, marker, condition_index = value.rpartition(":atom_")
    if not rule_id or marker != ":atom_" or not condition_index:
        raise SDKStoreError(f"{field_name} keys must use <rule_id>:atom_<index>")
    if not condition_index.isdigit():
        raise SDKStoreError(f"{field_name} keys must use non-negative condition indexes")


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
class ProbLogConfig:
    """Public ProbLog semantics wrapper for Rule or Inference evaluation.

    Pass to `fg.eval.evaluate(application_rule_or_inference, config=...)` to
    configure ProbLog semantics without constructing a raw `SemanticsProfile`.
    The SDK derives `engine="problog"` from this wrapper.

    Args:
        case_probabilities: Mapping from branch id to probability in `(0, 1]`.
        rule_params: Per-Rule metadata keyed by application `Rule.id`; lowered
            into canonical `SemanticsProfile.rule_projection` for future
            adapter cycles.
        uncertainty_projection: Raw uncertainty projection policy mapping,
            using the same schema as `SemanticsProfile.uncertainty_projection`.
        name: Optional profile name used in the lowered canonical profile.
        fallback: Policy for unconfigured semantics.
    """

    case_probabilities: dict[str, float] = field(default_factory=dict)
    rule_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    uncertainty_projection: dict[str, Any] = field(default_factory=_default_problog_uncertainty_projection)
    name: str | None = None
    fallback: str = "reject_unconfigured"

    @property
    def engine(self) -> str:
        """Return the legacy engine name selected by this configuration."""
        return "problog"

    def __post_init__(self) -> None:
        if self.name is not None and (not isinstance(self.name, str) or not self.name):
            raise SDKStoreError("ProbLogConfig.name must be non-empty string when provided")
        if not isinstance(self.fallback, str) or not self.fallback:
            raise SDKStoreError("ProbLogConfig.fallback must be non-empty string")
        object.__setattr__(
            self,
            "case_probabilities",
            _normalize_probability_map(self.case_probabilities, field_name="case_probabilities"),
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
class PyReasonConfig:
    """Public PyReason semantics wrapper for Rule or Inference evaluation.

    Pass to `fg.eval.evaluate(application_rule_or_inference, config=...)` to
    configure PyReason time delay and interval bounds. The SDK derives
    `engine="pyreason"` from this wrapper.

    Args:
        timestep_delay: Non-negative timestep delay for compiled rules.
        iteration_count: Positive global PyReason inference round count.
        derived_bound: Optional canonical `[lower, upper]` interval for rule heads.
        atom_bounds: Optional body atom intervals keyed by `<rule_id>:atom_<index>`.
        head_bound: Optional global `[lower, upper]` interval for rule heads.
        case_bounds: Optional per-branch interval overrides keyed by branch id.
        rule_params: Per-Rule metadata keyed by application `Rule.id`; lowered
            into canonical `SemanticsProfile.rule_projection` for future
            adapter cycles.
    """

    timestep_delay: int = 0
    iteration_count: int = 1
    derived_bound: tuple[float, float] | None = None
    atom_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    head_bound: tuple[float, float] | None = None
    case_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    rule_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    temporal_projection: dict[str, Any] = field(default_factory=lambda: {"mode": "none"})
    uncertainty_projection: dict[str, Any] = field(default_factory=dict)
    name: str | None = None
    fallback: str = "reject_unconfigured"

    @property
    def engine(self) -> str:
        """Return the legacy engine name selected by this configuration."""
        return "pyreason"

    def __post_init__(self) -> None:
        if self.name is not None and (not isinstance(self.name, str) or not self.name):
            raise SDKStoreError("PyReasonConfig.name must be non-empty string when provided")
        if isinstance(self.timestep_delay, bool) or not isinstance(self.timestep_delay, int):
            raise SDKStoreError("PyReasonConfig.timestep_delay must be int")
        if self.timestep_delay < 0:
            raise SDKStoreError("PyReasonConfig.timestep_delay must be >= 0")
        if isinstance(self.iteration_count, bool) or not isinstance(self.iteration_count, int):
            raise SDKStoreError("PyReasonConfig.iteration_count must be int")
        if self.iteration_count < 1:
            raise SDKStoreError("PyReasonConfig.iteration_count must be >= 1")
        if not isinstance(self.fallback, str) or not self.fallback:
            raise SDKStoreError("PyReasonConfig.fallback must be non-empty string")
        derived_bound = (
            None
            if self.derived_bound is None
            else _normalize_interval(self.derived_bound, field_name="PyReasonConfig.derived_bound")
        )
        if derived_bound is not None and self.head_bound is not None:
            raise SDKStoreError("PyReasonConfig.derived_bound conflicts with PyReasonConfig.head_bound")
        object.__setattr__(self, "derived_bound", derived_bound)
        object.__setattr__(
            self,
            "atom_bounds",
            _normalize_atom_interval_map(self.atom_bounds, field_name="PyReasonConfig.atom_bounds"),
        )
        head_bound = None if self.head_bound is None else _normalize_interval(self.head_bound, field_name="head_bound")
        object.__setattr__(self, "head_bound", head_bound)
        object.__setattr__(
            self,
            "case_bounds",
            _normalize_interval_map(self.case_bounds, field_name="case_bounds"),
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


__all__ = ["ProbLogConfig", "PyReasonConfig"]
