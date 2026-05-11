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


@dataclass(frozen=True)
class SemanticsProfile:
    name: str
    engine: str
    version: str = SUPPORTED_VERSION
    engine_options: dict[str, Any] = field(default_factory=dict)
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
            "uncertainty_projection": bool(profile.uncertainty_projection),
            "temporal_projection": profile.temporal_projection != {"mode": "none"},
            "rule_projection": bool(profile.rule_projection),
            "certainty_projection": bool(profile.certainty_projection),
            "output_readback": bool(profile.output_readback),
        },
        "warnings": [],
    }


def _normalize_rule_projection(value: Any) -> dict[str, list[dict[str, Any]]]:
    raw = _copy_mapping(value, path="rule_projection")
    out: dict[str, list[dict[str, Any]]] = {}
    for bucket, entries in raw.items():
        bucket_name = _non_empty_str(bucket, path="rule_projection bucket")
        if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
            raise ValueError(f"rule_projection.{bucket_name} must be list")
        normalized_entries: list[dict[str, Any]] = []
        for idx, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                raise ValueError(f"rule_projection.{bucket_name}[{idx}] must be object")
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
            raise ValueError(f"uncertainty_projection.{key} must be object")
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
    if mode != "none":
        raise ValueError("temporal_projection.mode only accepts 'none' in B; Track 3 / D owns temporal projection")
    normalized = dict(raw)
    normalized["mode"] = "none"
    return normalized


def _copy_mapping(value: Any, *, path: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be object")
    return dict(value)


def _non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be non-empty string")
    return value
