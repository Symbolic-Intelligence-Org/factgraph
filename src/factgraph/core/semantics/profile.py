from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

SUPPORTED_ENGINES = frozenset({"native", "souffle", "problog", "pyreason"})
SUPPORTED_VERSION = "1.0"
UNCERTAINTY_POLICIES = frozenset(
    {
        "identity_probability",
        "probability_interval",
        "possibility_interval",
        "lower",
        "midpoint",
        "upper",
        "reject",
    }
)
FALLBACK_POLICIES = frozenset({"reject_unconfigured", "warn_default", "use_default"})
TIME_BIN_SHORT_FORMS = frozenset({"1d", "1h", "15m", "1m"})


@dataclass(frozen=True)
class SemanticsProfile:
    """Canonical semantics profile consumed by runtime adapters.

    Most SDK users should start with `ProbLogConfig` or `PyReasonConfig`.
    `SemanticsProfile` is the lower-level, engine-explicit form used when a
    caller needs direct control over projections and adapter buckets.

    Args:
        name: Stable profile name.
        engine: Runtime engine name, such as `"native"`, `"problog"`, or
            `"pyreason"`.
        rule_projection: Per-engine rule annotations consumed by adapters.
    """

    name: str
    engine: str
    version: str = SUPPORTED_VERSION
    engine_options: dict[str, Any] = field(default_factory=dict)
    iteration_count: int | None = None
    uncertainty_projection: dict[str, Any] = field(default_factory=dict)
    temporal_projection: dict[str, Any] = field(default_factory=lambda: {"mode": "none"})
    rule_projection: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    certainty_projection: dict[str, Any] = field(default_factory=dict)
    output_readback: dict[str, Any] = field(default_factory=dict)
    fallback: str = "reject_unconfigured"

    def __post_init__(self) -> None:
        name = _non_empty_str(self.name, path="name")
        engine = _non_empty_str(self.engine, path="engine")
        version = _non_empty_str(self.version, path="version")
        fallback = _non_empty_str(self.fallback, path="fallback")

        if engine not in SUPPORTED_ENGINES:
            allowed = ", ".join(sorted(SUPPORTED_ENGINES))
            raise ValueError(f"engine must be one of: {allowed}")
        if version != SUPPORTED_VERSION:
            raise ValueError(f"version must be {SUPPORTED_VERSION!r}")
        if fallback not in FALLBACK_POLICIES:
            allowed = ", ".join(sorted(FALLBACK_POLICIES))
            raise ValueError(f"fallback must be one of: {allowed}")

        engine_options = _copy_mapping(self.engine_options, path="engine_options")
        iteration_count = _normalize_iteration_count(self.iteration_count)
        uncertainty_projection = _normalize_uncertainty_projection(self.uncertainty_projection)
        temporal_projection = _normalize_temporal_projection(self.temporal_projection)
        rule_projection = _normalize_rule_projection(self.rule_projection)
        certainty_projection = _copy_mapping(self.certainty_projection, path="certainty_projection")
        output_readback = _copy_mapping(self.output_readback, path="output_readback")

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "engine", engine)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "fallback", fallback)
        object.__setattr__(self, "engine_options", engine_options)
        object.__setattr__(self, "iteration_count", iteration_count)
        object.__setattr__(self, "uncertainty_projection", uncertainty_projection)
        object.__setattr__(self, "temporal_projection", temporal_projection)
        object.__setattr__(self, "rule_projection", rule_projection)
        object.__setattr__(self, "certainty_projection", certainty_projection)
        object.__setattr__(self, "output_readback", output_readback)


def inspect_semantics_profile(profile: SemanticsProfile) -> dict[str, Any]:
    if not isinstance(profile, SemanticsProfile):
        raise TypeError("inspect_semantics_profile expects SemanticsProfile")

    return {
        "engine": profile.engine,
        "profile": profile.name,
        "version": profile.version,
        "fallback": profile.fallback,
        "uses": {
            "engine_options": bool(profile.engine_options),
            "iteration_count": profile.iteration_count is not None,
            "uncertainty_projection": bool(profile.uncertainty_projection),
            "temporal_projection": profile.temporal_projection != {"mode": "none"},
            "rule_projection": bool(profile.rule_projection),
            "certainty_projection": bool(profile.certainty_projection),
            "output_readback": bool(profile.output_readback),
        },
        "warnings": [],
    }


def _normalize_iteration_count(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("iteration_count must be int or None")  # noqa: TRY004 - Public profile rejects wrong-type counts as ValueError, including bool.
    if value < 1:
        raise ValueError("iteration_count must be >= 1")
    return value


def _normalize_rule_projection(value: Any) -> dict[str, list[dict[str, Any]]]:
    raw = _copy_mapping(value, path="rule_projection")
    out: dict[str, list[dict[str, Any]]] = {}
    for bucket, entries in raw.items():
        bucket_name = _non_empty_str(bucket, path="rule_projection bucket")
        if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
            raise ValueError(f"rule_projection.{bucket_name} must be list")  # noqa: TRY004 - Public rule bucket shape-error contract.
        normalized_entries: list[dict[str, Any]] = []
        for idx, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                raise ValueError(f"rule_projection.{bucket_name}[{idx}] must be object")  # noqa: TRY004 - Public rule-entry shape errors retain indexed ValueError.
            normalized = dict(entry)
            target = normalized.get("target")
            kind = normalized.get("kind")
            if not isinstance(target, str) or not target:
                raise ValueError(f"rule_projection.{bucket_name}[{idx}].target must be non-empty string")
            if not isinstance(kind, str) or not kind:
                raise ValueError(f"rule_projection.{bucket_name}[{idx}].kind must be non-empty string")
            normalized_entries.append(normalized)
        out[bucket_name] = normalized_entries
    return out


def _normalize_uncertainty_projection(value: Any) -> dict[str, Any]:
    raw = _copy_mapping(value, path="uncertainty_projection")
    out: dict[str, Any] = {}
    for raw_kind, config in raw.items():
        key = _non_empty_str(raw_kind, path="uncertainty_projection key")
        if key == "fallback":
            if config not in FALLBACK_POLICIES:
                allowed = ", ".join(sorted(FALLBACK_POLICIES))
                raise ValueError(f"uncertainty_projection.fallback must be one of: {allowed}")
            out[key] = config
            continue
        if not isinstance(config, Mapping):
            raise ValueError(f"uncertainty_projection.{key} must be object")  # noqa: TRY004 - Public uncertainty bucket shape-error contract.
        normalized = dict(config)
        policy = normalized.get("policy")
        if policy not in UNCERTAINTY_POLICIES:
            allowed = ", ".join(sorted(UNCERTAINTY_POLICIES))
            raise ValueError(f"uncertainty_projection.{key}.policy must be one of: {allowed}")
        out[key] = normalized
    return out


def _normalize_temporal_projection(value: Any) -> dict[str, Any]:
    raw = _copy_mapping(value, path="temporal_projection")
    mode = raw.get("mode", "none")
    if mode == "none":
        normalized = dict(raw)
        normalized["mode"] = "none"
        return normalized
    if mode == "fixed_timesteps":
        normalized = _normalize_fixed_timesteps(raw)
        normalized["mode"] = "fixed_timesteps"
        return normalized
    if mode == "valid_time_boundaries":
        normalized = _normalize_valid_time_boundaries(raw)
        normalized["mode"] = "valid_time_boundaries"
        return normalized
    if mode == "fact_boundaries":
        normalized = _normalize_valid_time_boundaries(raw)
        normalized["mode"] = "fact_boundaries"
        return normalized
    if mode == "time_binned":
        normalized = _normalize_time_binned(raw)
        normalized["mode"] = "time_binned"
        return normalized
    allowed = "fact_boundaries, fixed_timesteps, none, time_binned, valid_time_boundaries"
    raise ValueError(
        f"temporal_projection.mode {mode!r} is not supported in D; supported modes: {allowed}"
    )


def _normalize_fixed_timesteps(raw: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys(raw, path="temporal_projection", allowed={"mode", "timesteps"})
    timesteps = raw.get("timesteps")
    if isinstance(timesteps, bool) or not isinstance(timesteps, int) or timesteps <= 0:
        raise ValueError("temporal_projection.timesteps must be positive int")
    return {"timesteps": timesteps}


def _normalize_valid_time_boundaries(raw: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys(raw, path="temporal_projection", allowed={"mode", "universe"})
    return {"universe": _normalize_temporal_universe(raw)}


def _normalize_time_binned(raw: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys(
        raw,
        path="temporal_projection",
        allowed={"mode", "universe", "bin_size"},
    )
    return {
        "universe": _normalize_temporal_universe(raw),
        "bin_size": _normalize_time_binned_bin_size(raw.get("bin_size")),
    }


def _normalize_temporal_universe(raw: dict[str, Any]) -> list[str]:
    universe = raw.get("universe")
    if (
        isinstance(universe, (str, bytes))
        or not isinstance(universe, Sequence)
        or len(universe) != 2
    ):
        raise ValueError("temporal_projection.universe must be [start, end]")
    start, end = universe
    if not isinstance(start, str) or not start:
        raise ValueError("temporal_projection.universe[0] must be non-empty string")
    if not isinstance(end, str) or not end:
        raise ValueError("temporal_projection.universe[1] must be non-empty string")
    if start >= end:
        raise ValueError("temporal_projection.universe start must be before end")
    return [start, end]


def _normalize_time_binned_bin_size(value: Any) -> str:
    path = "SemanticsProfile.temporal_projection.time_binned.bin_size"
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be one of: P<n>D, PT<n>H, PT<n>M, 1d, 1h, 15m, 1m")
    if value in TIME_BIN_SHORT_FORMS:
        return value
    amount: str | None = None
    if value.startswith("PT") and value.endswith(("H", "M")):
        amount = value[2:-1]
    elif value.startswith("P") and value.endswith("D"):
        amount = value[1:-1]
    if amount is None or not amount.isdigit() or int(amount) <= 0:
        raise ValueError(f"{path} must be one of: P<n>D, PT<n>H, PT<n>M, 1d, 1h, 15m, 1m")
    return value


def _reject_unknown_keys(raw: dict[str, Any], *, path: str, allowed: set[str]) -> None:
    unknown = sorted(str(key) for key in raw if key not in allowed)
    if unknown:
        allowed_text = ", ".join(sorted(allowed))
        unknown_text = ", ".join(unknown)
        raise ValueError(f"{path} unsupported keys: {unknown_text}. Supported keys: {allowed_text}")


def _copy_mapping(value: Any, *, path: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be object")  # noqa: TRY004 - All profile mapping fields share the public ValueError boundary.
    return dict(value)


def _non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be non-empty string")
    return value
