"""Probability configuration and resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
import warnings

from symir.errors import ValidationError


MissingProbPolicy = Literal["inject_default", "warn_and_default", "error"]


@dataclass(frozen=True)
class ProbabilityConfig:
    """Default probability configuration for facts and rules."""

    default_fact_prob: float = 1.0
    default_rule_prob: float = 1.0
    missing_prob_policy: MissingProbPolicy = "inject_default"


def resolve_probability(
    prob: Optional[float],
    *,
    default_value: float,
    policy: MissingProbPolicy,
    context: str,
) -> float:
    if prob is not None:
        if not (0.0 <= prob <= 1.0):
            raise ValidationError(f"Probability out of range in {context}: {prob}")
        return float(prob)
    if policy == "inject_default":
        return float(default_value)
    if policy == "warn_and_default":
        warnings.warn(f"Missing probability in {context}; using default {default_value}")
        return float(default_value)
    raise ValidationError(f"Missing probability in {context}")
